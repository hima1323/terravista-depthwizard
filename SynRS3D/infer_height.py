import os
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')  # CPU fallback for any op MPS lacks
import numpy as np
import torch
from albumentations import Compose, Normalize
from albumentations.pytorch import ToTensorV2

from models.dpt import make_model
import argparse
from tqdm import tqdm
import rasterio
from utils import geo_func

def save_tiff_with_geo_info(input_path, output_path, data):
    """Save a float32 height map with the input's CRS/transform (rasterio instead of GDAL)."""
    with rasterio.open(input_path) as src:
        profile = src.profile
    profile.update(driver='GTiff', count=1, dtype='float32', nodata=None, photometric=None)
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(data.astype(np.float32), 1)

def get_arguments():
    """Parse all the arguments provided from the CLI.

    Returns:
      A list of parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Inference of Height Estimation")
    parser.add_argument("--data_dir", type=str, default='path/to/your/input.tif',
                        help="Path of the image.")
    parser.add_argument("--output_path", type=str, default='path/to/your/ouput.tif',
                        help="Path to the output director.")
    parser.add_argument("--restore_from", type=str, default=WEIGHTS,
                        help="Where restore model parameters from.")
    parser.add_argument("--gpu", type=str, default='0',
                        help="choose gpu device.")
    parser.add_argument("--patch_size", type=int, default=518,
                        help="Make sure it is divisible by 14")
    parser.add_argument("--overlap", type=int, default=259,
                        help="overlap size.")
    parser.add_argument("--fp16", action='store_true', help="Half precision: ~2x less memory, faster on Apple MPS / CUDA.")
    parser.add_argument("--use_tta", action='store_true', help="Whether to use test-time augmentation.")
    parser.add_argument("--dsm_path", type=str, default=None,
                        help="GeoTIFF input only: also save the absolute DSM (metres above mean sea level, EGM2008) "
                             "= bare-ground terrain (Copernicus GLO-30 or a DEM in demo/terrain/) + predicted height.")
    parser.add_argument("--uncertainty_path", type=str, default=None,
                        help="With --use_tta: also save the per-pixel spread of the 4 flipped predictions (m) here.")
    return parser.parse_args()

# which weights the app and the benchmarks load: RS3DAda, or a student from train_distill.py (DW_WEIGHTS=path)
WEIGHTS = os.environ.get('DW_WEIGHTS') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pretrain', 'RS3DAda_vitl_DPT_height.pth')


def load_model(restore_from=WEIGHTS, fp16=False):
    """RS3DAda (a bare state dict, ViT-L) or a train_distill.py student ({'encoder', 'patch_size', 'state_dict'}).
    model.patch_size = the tile side predict() uses for it."""
    ckpt = torch.load(restore_from, map_location='cpu', weights_only=True)
    student = isinstance(ckpt, dict) and 'state_dict' in ckpt
    model, patch = make_model(ckpt['encoder'] if student else 'vitl', pretrained=False)
    model.patch_size = ckpt.get('patch_size', patch) if student else patch
    device = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
    model.load_state_dict(ckpt['state_dict'] if student else ckpt)
    model.eval()
    dtype = torch.float16 if fp16 and device != 'cpu' else torch.float32   # half precision only on a GPU
    model.to(device, dtype)
    return model, device, dtype

LANDCOVER = ['bareland', 'rangeland', 'developed', 'road', 'trees', 'water', 'agriculture', 'buildings']  # seg head order


def predict(model, device, dtype, img0, patch_size=None, stride=None, use_tta=True, progress=None, full=False):
    """img0: HxWxC uint8 array -> HxW height map in metres. progress(done, total) is called per patch. Tiles are
    model.patch_size (518 for ViT encoders) with 50% overlap unless given.
    full=True returns a dict instead: 'height'; 'std' = per-pixel spread (m) of the 4 flipped predictions,
    used as an uncertainty map (None without use_tta); 'landcover' = HxW uint8 class index into LANDCOVER,
    from the model's second (land-cover) head, which runs anyway."""
    if img0.shape[2] > 3:
        img0 = img0[:,:,[0,1,2]]
    height = img0.shape[0]
    width = img0.shape[1]
    patch_size = patch_size or getattr(model, 'patch_size', 518)
    stride = stride or patch_size // 2
    C = max(1, int(np.ceil((width - patch_size) / stride) + 1))
    R = max(1, int(np.ceil((height - patch_size) / stride) + 1))
    
    # weight matrix B for avoiding boundaries of patches
    w = patch_size
    if patch_size > stride:
        s1 = stride
        s2 = w - s1
        d = 1/(1+s2)
        B1 = np.ones((w,w))
        B1[:,s1::] = np.dot(np.ones((w,1)),(-np.arange(1,s2+1)*d+1).reshape(1,s2))
        B2 = np.flip(B1)
        B3 = B1.T
        B4 = np.flip(B3)
        B = B1*B2*B3*B4
    else:
        B = np.ones((w,w))

    img1 = np.zeros((patch_size+stride*(R-1), patch_size+stride*(C-1),3))
    img1[0:height,0:width,:] = img0.copy()

    pred_all = np.zeros((patch_size+stride*(R-1), patch_size+stride*(C-1)))
    weight = np.zeros((patch_size+stride*(R-1), patch_size+stride*(C-1)))
    std_all = np.zeros_like(pred_all)
    seg_all = np.zeros((len(LANDCOVER),) + pred_all.shape, np.float32) if full else None
    patch_transformed = Compose([
        Normalize(mean=(123.675, 116.28, 103.53), std=(58.395, 57.12, 57.375), max_pixel_value=1),
        ToTensorV2()
    ])
    for r in tqdm(range(R), desc="Row"):
        for c in range(C):
            img = img1[r*stride:r*stride+patch_size,c*stride:c*stride+patch_size,:].copy().astype(np.float32)
            if use_tta:
                imgs = [
                    img.copy(),
                    img[:, ::-1, :].copy(),
                    img[::-1, :, :].copy(),
                    img[::-1, ::-1, :].copy()
                ]
                input = torch.cat([patch_transformed(image=x)['image'].to(device).unsqueeze(0) for x in imgs], dim=0).to(device, dtype)
            else:
                input = patch_transformed(image=img)['image'].to(device).unsqueeze(0).to(device, dtype)

            pred = []
            with torch.no_grad():
                outputs = model(input)
                if use_tta:
                    p = outputs.get('regression', None).float().cpu().numpy()[:, 0]
                    stack = np.stack([p[0], p[1][:, ::-1], p[2][::-1, :], p[3][::-1, ::-1]])  # un-flip
                    pred, spread = stack.mean(0), stack.std(0)
                else:
                    pred = outputs.get('regression', None).float().cpu().numpy().squeeze()
                if full:
                    sg = outputs['segmentation'].float().cpu().numpy()
                    seg = (sg[0] + sg[1][:, :, ::-1] + sg[2][:, ::-1, :] + sg[3][:, ::-1, ::-1]) / 4 if use_tta else sg[0]

            pred_all[r*stride:r*stride+patch_size,c*stride:c*stride+patch_size] += pred.copy()*B
            weight[r*stride:r*stride+patch_size,c*stride:c*stride+patch_size] += B
            if use_tta:
                std_all[r*stride:r*stride+patch_size,c*stride:c*stride+patch_size] += spread*B
            if full:
                seg_all[:, r*stride:r*stride+patch_size,c*stride:c*stride+patch_size] += seg*B
            if progress:
                progress(r*C+c+1, R*C)

    pred_all /= weight
    if full:
        return {'height': pred_all[0:height, 0:width],
                'std': (std_all / weight)[0:height, 0:width] if use_tta else None,
                'landcover': seg_all[:, 0:height, 0:width].argmax(0).astype(np.uint8)}
    return pred_all[0:height, 0:width]

GROUND_CLASSES = [LANDCOVER.index(c) for c in ('bareland', 'rangeland', 'developed', 'road', 'water', 'agriculture')]


def ground_mask(h, landcover, max_height=1.5):
    """Pixels that show open ground: a ground-type land-cover class and (almost) no height above ground."""
    return np.isin(landcover, GROUND_CLASSES) & (h < max_height)


CORRECTION_GROUPS = {1: LANDCOVER.index('buildings'), 2: LANDCOVER.index('trees')}  # 0 = everything else


def correct_heights(h, landcover, corr):
    """Apply a learned height correction (demo/height_correction.py), either to all pixels at once or
    separately to predicted building / tree / other pixels.
    corr = {'method': 'curve'|'linear', 'by_landcover': bool, 'params': {group: ...}}."""
    groups = np.zeros(h.shape, np.uint8)
    if corr.get('by_landcover', True):  # else one correction for all pixels (landcover may be None)
        for k, cls in CORRECTION_GROUPS.items():
            groups[landcover == cls] = k
    out = np.clip(h, 0, None).astype(np.float32)
    for k, prm in corr['params'].items():
        sel = groups == int(k)
        p = out[sel]
        if corr['method'] == 'curve':
            x, y = np.array(prm['x']), np.array(prm['y'])
            v = np.interp(p, x, y)
            hi = p > x[-1]  # beyond the last knot keep the last ratio
            v[hi] = p[hi] * (y[-1] / max(x[-1], 1e-3))
        else:
            ramp = np.clip(p - 1, 0, 1)  # blend in between 1 and 2 m so ground stays untouched
            v = p + (prm['a'] * p + prm['b'] - p) * ramp
        out[sel] = np.clip(v, 0, None)
    return out


CONFORMAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calibration', 'conformal.json')


def load_conformal(path=CONFORMAL):
    """Split-conformal interval table (demo/uncertainty_calibration.py), or None if it is not installed."""
    import json
    return json.load(open(path)) if os.path.exists(path) else None


def building_interval(height, spread, table, level='0.9'):
    """Calibrated interval (lo, hi) in m for a building block's reported height (block median, app.extract_buildings)
    from its median 4-flip spread: lo/hi = height + q_lo/q_hi * (spread + c), q per predicted height bin, from
    split-conformal calibration on GAMUS LiDAR (US cities, calibration/conformal.json). None without a table."""
    if not table:
        return None
    b = table['building']
    q = b['q'][level]
    ql, qh = q.get(table['bins'][int(np.digitize(height, [3, 10, 20]))], q['pooled'])
    s = 1.0 if b['c'] is None else spread + b['c']
    return max(0.0, height + ql * s), height + qh * s


def main():
    args = get_arguments()
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
    model, device, dtype = load_model(args.restore_from, args.fp16)
    img0 = geo_func.load_multiband(args.data_dir)
    out = predict(model, device, dtype, img0, args.patch_size, args.overlap, args.use_tta, full=True)
    save_tiff_with_geo_info(args.data_dir, args.output_path, out['height'])
    if args.uncertainty_path and out['std'] is not None:
        save_tiff_with_geo_info(args.data_dir, args.uncertainty_path, out['std'])
    if args.dsm_path:
        import terrain  # only needed here; fetches terrain over the network
        dtm, info = terrain.build_dtm(args.data_dir, out['height'], ground_mask(out['height'], out['landcover']))
        if dtm is None:
            print('No georeferencing in the input: only the relative height map was saved. ' + info['none'])
        else:
            dtm, laser = terrain.laser_correct(args.data_dir, dtm, info.get('geoid_undulation_m'), out['height'], out['landcover'])
            terrain.save_with_tags(args.data_dir, args.dsm_path, dtm + np.clip(out['height'], 0, None),
                                   save_tiff_with_geo_info, VERTICAL_DATUM=terrain.DATUM, UNITS='metre',
                                   TERRAIN_SOURCE=info['source'], LASER_CORRECTION=laser)
            print(f"DSM saved ({info['source']}, ground {np.nanmin(dtm):.1f}-{np.nanmax(dtm):.1f} m above sea level; "
                  + (f"shifted {-laser['offset_m']:+.2f} m to match {laser['ground_photons']} ICESat-2 laser ground photons)"
                     if 'offset_m' in laser else f"no ICESat-2 correction: {laser['none']})"))

if __name__ == '__main__':
    main()
