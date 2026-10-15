"""Measure RS3DAda height accuracy on DFC19 test tiles against LiDAR ground truth.

usage: .venv/bin/python demo/benchmark.py            (tiles listed in data/DFC19_bench.txt)
Official metrics use the repo's own utils.metrics (Result / AverageMeter), one forward pass per
512x512 tile center-cropped to 504x504, as in evaluation.py. Extra breakdowns (land cover, height band) are pixel-pooled.
Writes demo/benchmark/results.json, results.md and example PNGs. Re-runs reuse cached predictions.
"""
import json, os, sys, time

import numpy as np
import rasterio
import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# utils/metrics.py imports skimage.ssim and sklearn.accuracy_score at top level but Result/AverageMeter
# never call them; stub them instead of installing two heavy packages.
import types
for mod, attr in [('skimage.metrics', 'structural_similarity'), ('sklearn.metrics', 'accuracy_score')]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod.split('.')[0]] = types.ModuleType(mod.split('.')[0])
            sys.modules[mod] = types.SimpleNamespace(**{attr: None})
import infer_height
from utils.metrics import AverageMeter, Result

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'DFC19')
OUT = os.path.join(ROOT, 'demo', 'benchmark')
CLASSES = {2: 'ground', 5: 'trees', 6: 'buildings', 9: 'water', 17: 'bridge'}  # DFC19 LiDAR class codes
BANDS = [(0, 3), (3, 10), (10, 20), (20, 1e9)]
MEAN = np.array([123.675, 116.28, 103.53], np.float32)
STD = np.array([58.395, 57.12, 57.375], np.float32)


def read(kind, name):
    """Tile center-cropped to 504x504 (a multiple of the 14-px ViT patch), exactly like evaluation.py."""
    with rasterio.open(os.path.join(DATA, kind, name + '.tif')) as src:
        a = src.read()
    t, l = (a.shape[1] - 504) // 2, (a.shape[2] - 504) // 2
    return a[:, t:t + 504, l:l + 504]


def predict_tile(model, device, dtype, rgb):
    """Returns (single-pass prediction, 4-flip TTA mean, 4-flip spread) for one tile; all from one batch."""
    x = (rgb.astype(np.float32) - MEAN) / STD
    flips = [x, x[:, ::-1], x[::-1], x[::-1, ::-1]]
    batch = torch.from_numpy(np.stack(flips).transpose(0, 3, 1, 2).copy()).to(device, dtype)
    with torch.no_grad():
        p = model(batch)['regression'].float().cpu().numpy()[:, 0]
    stack = np.stack([p[0], p[1][:, ::-1], p[2][::-1], p[3][::-1, ::-1]])
    return p[0], stack.mean(0), stack.std(0)


def official(pairs):
    meter = AverageMeter()
    for pred, gt in pairs:
        r = Result()
        r.update(pred.copy(), gt.copy())
        meter.update(r)
    avg = meter.average()
    return {k: {'mae': float(avg[k].values['mae']), 'rmse': float(avg[k].values['rmse']),
                'f1_1.25': float(avg[k].values['f1_score'][0]) if k == 'whole' else None,
                'tiles': meter.total[k]} for k in ['whole', 'high']}


def pooled(pred, gt, mask):
    """Pixel-pooled MAE, RMSE, bias and Pearson correlation r (SIH26175 asks for RMSE, MAE and correlation)."""
    if not mask.any():
        return None
    p, g = pred[mask].astype(np.float64), gt[mask].astype(np.float64)
    d = p - g
    r = float(np.corrcoef(p, g)[0, 1]) if p.std() > 0 and g.std() > 0 else None
    return {'mae': float(np.abs(d).mean()), 'rmse': float(np.sqrt((d ** 2).mean())), 'bias': float(d.mean()),
            'r': r, 'pixels': int(mask.sum())}


def save_example(name, rgb, gt, pred):
    vmax = max(5.0, float(np.percentile(gt, 99)))
    def cmap(h):  # turbo-like ramp, same idea as the web viewer
        v = np.clip(h / vmax, 0, 1)
        return (np.stack([np.clip(1.5 - abs(4 * v - 3), 0, 1), np.clip(1.5 - abs(4 * v - 2), 0, 1),
                          np.clip(1.5 - abs(4 * v - 1), 0, 1)], -1) * 255).astype(np.uint8)
    Image.fromarray(np.concatenate([rgb, cmap(gt), cmap(pred)], 1)).save(os.path.join(OUT, f'example_{name}.png'))


def main():
    names = [l.strip() for l in open(os.path.join(ROOT, 'data', 'DFC19_bench.txt')) if l.strip()]
    names = [n for n in names if os.path.exists(os.path.join(DATA, 'gt_nDSM', n + '.tif'))]
    os.makedirs(os.path.join(OUT, 'pred'), exist_ok=True)
    model = None
    rows, t0 = [], time.time()
    for i, n in enumerate(names, 1):
        cache = os.path.join(OUT, 'pred', n + '.npz')
        if not os.path.exists(cache) or 'std' not in np.load(cache):  # older caches lack the spread
            if model is None:
                model, device, dtype = infer_height.load_model(os.path.join(ROOT, 'pretrain', 'RS3DAda_vitl_DPT_height.pth'), fp16=True)
            single, tta, std = predict_tile(model, device, dtype, read('opt', n)[:3].transpose(1, 2, 0))
            np.savez_compressed(cache, single=single.astype(np.float16), tta=tta.astype(np.float16),
                                std=std.astype(np.float16))
            el = time.time() - t0
            print(f'[{i}/{len(names)}] {n}  ({el / 60:.1f} min elapsed)', flush=True)
        c = np.load(cache)
        rows.append((n, c['single'].astype(np.float32), c['tta'].astype(np.float32), c['std'].astype(np.float32)))

    res = {'tiles': len(rows), 'protocol': 'DFC19 test tiles (512x512, center-cropped to 504 as in evaluation.py), LiDAR nDSM ground truth; fp16 on Apple MPS'}
    for city in ['ALL', 'JAX', 'OMA']:
        sel = [r for r in rows if city == 'ALL' or r[0].startswith(city)]
        gts = {r[0]: read('gt_nDSM', r[0])[0].astype(np.float32) for r in sel}
        entry = {'tiles': len(sel)}
        for mode, idx in [('single_pass', 1), ('tta', 2)]:
            entry[mode] = official([(r[idx], gts[r[0]]) for r in sel])
        if city == 'ALL':  # pixel-pooled breakdowns, TTA prediction (what the demo shows)
            P = np.concatenate([np.clip(r[2], 0, None).ravel() for r in sel])
            G = np.concatenate([np.clip(gts[r[0]], 0, None).ravel() for r in sel])
            L = np.concatenate([read('gt_ss_mask', r[0])[0].ravel() for r in sel])
            ok = np.isfinite(G)
            entry['by_land_cover'] = {lbl: pooled(P, G, ok & (L == c)) for c, lbl in CLASSES.items()}
            entry['by_true_height'] = {f'{lo}-{hi if hi < 1e9 else "inf"} m': pooled(P, G, ok & (G >= lo) & (G < hi)) for lo, hi in BANDS}
            entry['all_pixels'] = pooled(P, G, ok)
            # does the ± (TTA spread) predict the real error? bin pixels into uncertainty quintiles
            U = np.concatenate([r[3].ravel() for r in sel])
            err = np.abs(P - G)
            edges = np.percentile(U[ok], [0, 20, 40, 60, 80, 100])
            entry['error_by_uncertainty'] = [
                {'unc_range': f'{lo:.2f}-{hi:.2f} m', 'mean_unc': float(U[m].mean()), 'mae': float(err[m].mean()),
                 'pixels': int(m.sum())}
                for lo, hi in zip(edges[:-1], edges[1:])
                for m in [ok & (U >= lo) & (U <= hi if hi == edges[-1] else U < hi)]]
            ranks = lambda x: np.argsort(np.argsort(x))
            sub = np.random.default_rng(0).choice(np.flatnonzero(ok), 200_000, replace=False)
            entry['spearman_unc_vs_error'] = float(np.corrcoef(ranks(U[sub]), ranks(err[sub]))[0, 1])
        res[city] = entry

    # examples: the tiles with the most tall structure
    tallest = sorted(rows, key=lambda r: -np.percentile(read('gt_nDSM', r[0])[0], 98))[:3]
    for n, _, tta, _ in tallest:
        save_example(n, read('opt', n)[:3].transpose(1, 2, 0), read('gt_nDSM', n)[0], np.clip(tta, 0, None))
    json.dump(res, open(os.path.join(OUT, 'results.json'), 'w'), indent=2)
    write_md(res)
    print(open(os.path.join(OUT, 'results.md')).read())


def write_md(res):
    f = lambda v: '–' if v is None else f'{v:.2f}'
    a = res['ALL']
    L = [f"# RS3DAda on DFC19 ({res['tiles']} test tiles)", '', res['protocol'], '',
         '## Official metrics (repo utils/metrics.py, per-tile average)', '',
         '| Subset | Mode | MAE whole (m) | RMSE whole (m) | MAE high >3 m | RMSE high >3 m | F1 (δ<1.25) |', '|---|---|---|---|---|---|---|']
    for city in ['ALL', 'JAX', 'OMA']:
        for mode in ['single_pass', 'tta']:
            m = res[city][mode]
            L.append(f"| {city} ({res[city]['tiles']}) | {mode} | {f(m['whole']['mae'])} | {f(m['whole']['rmse'])} | "
                     f"{f(m['high']['mae'])} | {f(m['high']['rmse'])} | {f(m['whole']['f1_1.25'])} |")
    for title, key in [('By land cover (LiDAR class), pixel-pooled, TTA', 'by_land_cover'),
                       ('By true height band, pixel-pooled, TTA', 'by_true_height')]:
        L += ['', f'## {title}', '', '| Group | MAE (m) | RMSE (m) | Bias pred−true (m) | Pixels |', '|---|---|---|---|---|']
        for k, v in a[key].items():
            if v:
                L.append(f"| {k} | {f(v['mae'])} | {f(v['rmse'])} | {v['bias']:+.2f} | {v['pixels']:,} |")
    L += ['', '## Does the ± (TTA spread) predict real error? Pixels binned by uncertainty', '',
          f"Spearman rank correlation, uncertainty vs absolute error: **{a['spearman_unc_vs_error']:.2f}**", '',
          '| Uncertainty quintile | Mean ± (m) | Real MAE (m) | Pixels |', '|---|---|---|---|']
    for b in a['error_by_uncertainty']:
        L.append(f"| {b['unc_range']} | {b['mean_unc']:.2f} | {b['mae']:.2f} | {b['pixels']:,} |")
    open(os.path.join(OUT, 'results.md'), 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
