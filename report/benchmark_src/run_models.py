"""Fresh predictions for the report: same tiles, same crop, every model. Cached per model/dataset as int16 cm."""
import glob, json, os, sys, time
import numpy as np, torch, h5py
from PIL import Image
ROOT = '/home/sv/Downloads/terravista-depthwizard/SynRS3D'; OUT = sys.argv[1]
os.chdir(ROOT); sys.path[:0] = [ROOT, ROOT + '/demo']
import benchmark as B, gamus_benchmark as G, infer_height
GP = ROOT + '/data/geopose'
def ctr(a, s):
    t, l = (a.shape[0] - s) // 2, (a.shape[1] - s) // 2
    return a[t:t + s, l:l + s]
def gamus_tiles():
    for n in [l.strip() for l in open(G.LIST) if l.strip()]:
        with h5py.File(G.path('images', n)) as h: yield n, ctr(h['image'], 512)
def ogc_tiles(c):
    for n in [l.strip() for l in open(f'{GP}/OGC_{c}/bench.txt') if l.strip()]:
        f = next(iter(glob.glob(f'{GP}/OGC_{c}/opt/{n}.*')))
        yield n, ctr(np.array(Image.open(f))[:, :, :3], 512)
SETS = {'GAMUS': gamus_tiles, 'OGC_ATL': lambda: ogc_tiles('ATL'), 'OGC_ARG': lambda: ogc_tiles('ARG')}
class HF:
    def __init__(s, repo):
        from transformers import AutoModelForDepthEstimation
        s.m = AutoModelForDepthEstimation.from_pretrained(repo, use_safetensors=True).eval().to('cuda', torch.float16)
    def __call__(s, x): return {'regression': s.m(pixel_values=x).predicted_depth.unsqueeze(1)}
    def parameters(s): return s.m.parameters()
def loader(k):
    if k == 'rs3dada': m, d, t = infer_height.load_model(ROOT + '/pretrain/RS3DAda_vitl_DPT_height.pth', fp16=True); return m, t, 504
    if k == 'student': m, d, t = infer_height.load_model(ROOT + '/pretrain/student_mambavision_t.pth', fp16=True); return m, t, 512
    return HF({'dav2_rel': 'depth-anything/Depth-Anything-V2-Large-hf', 'dav2_metric': 'depth-anything/Depth-Anything-V2-Metric-Outdoor-Large-hf'}[k]), torch.float16, 504
for k in ['rs3dada', 'student', 'dav2_rel', 'dav2_metric']:
    torch.cuda.reset_peak_memory_stats(); model, dtype, size = loader(k)
    params = sum(p.numel() for p in model.parameters())
    for ds, it in SETS.items():
        f = f'{OUT}/pred/{k}_{ds}.npz'
        if os.path.exists(f): continue
        names, single, tta, t = [], [], [], []; rng = []
        for n, rgb in it():
            t0 = time.perf_counter(); p, m, _ = B.predict_tile(model, 'cuda', dtype, ctr(np.asarray(rgb), size)); torch.cuda.synchronize(); t.append(time.perf_counter() - t0)
            sc = 100   # metres, or unitless disparity (about 20 to 60): both fit int16 at this scale
            if k == 'dav2_rel':   # unitless and large: per-tile rescale to int16, harmless because scoring refits scale and offset per tile
                rng.append((float(m.min()), float(m.max())))
                p, m = (p - p.min()) / max(p.max() - p.min(), 1e-6) * 30000, (m - m.min()) / max(m.max() - m.min(), 1e-6) * 30000; sc = 1
            names.append(n); single.append(np.clip(ctr(p, 504) * sc, -32000, 32000).astype(np.int16)); tta.append(np.clip(ctr(m, 504) * sc, -32000, 32000).astype(np.int16))
            if len(names) % 50 == 0: print(k, ds, len(names), round(np.median(t), 3), flush=True)
        if rng: print(k, ds, 'raw range', min(r[0] for r in rng), max(r[1] for r in rng), flush=True)
        assert max(np.abs(x).max() for x in tta) < 32000 and min(x.std() for x in tta) > 0, f'{k} {ds}: clipped or constant'
        np.savez_compressed(f, names=np.array(names), single=np.stack(single), tta=np.stack(tta), sc=sc, batch4_s=np.median(t[5:]))
    json.dump({'params': params, 'vram_peak_mib': torch.cuda.max_memory_allocated() / 2**20, 'tile': size}, open(f'{OUT}/{k}_info.json', 'w'))
    del model; torch.cuda.empty_cache()
print('ALL DONE', flush=True)
