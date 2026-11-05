"""Score the cached predictions of run.py: raw and per-tile aligned, per dataset. Writes results.json and examples.png."""
import json, os, sys
import numpy as np
from PIL import Image
ROOT = '/home/sv/Downloads/terravista-depthwizard/SynRS3D'; OUT = sys.argv[1]
os.chdir(ROOT); sys.path[:0] = [ROOT, ROOT + '/demo']
import benchmark as B, gamus_benchmark as G, geopose_benchmark as P, eval_v2 as E
import h5py
METRES = ('rs3dada', 'student', 'dav2_metric')
MODELS = ('rs3dada', 'student', 'dav2_rel', 'dav2_metric')
def align(p, g):
    ok = np.isfinite(g) & np.isfinite(p)
    if p[ok].std() < 1e-6: return np.full_like(p, np.nanmean(g))
    a, b = np.polyfit(p[ok].ravel(), g[ok].ravel(), 1)
    return np.clip(a * p + b, 0, None)
def refs(ds, names):
    if ds == 'GAMUS': return [np.where(G.read('heights', n) <= -4.99, np.nan, np.clip(G.read('heights', n), 0, None)).astype(np.float32) for n in names]
    return [P.read_gt(ds[-3:], str(n)) for n in names]
def score(preds, gt):
    w = E.aggregate([E.metrics(np.clip(p, 0, None) - g, g) for p, g in zip(preds, gt)])
    h = E.aggregate([E.high_metrics(p[np.isfinite(g)], g[np.isfinite(g)]) for p, g in zip(preds, gt)])
    return {'whole': w, 'high': h}, [float(np.nanmean(np.abs(np.clip(p, 0, None) - g))) for p, g in zip(preds, gt)]
def paired(a, b):
    d = np.array(a) - np.array(b); lo, hi = E.bootstrap_ci(list(d)); return {'mean': float(d.mean()), 'ci95': [lo, hi]}
res, cost, examples = {}, {}, {}
for ds in ('GAMUS', 'OGC_ATL', 'OGC_ARG'):
    res[ds] = {}; tiles = {}
    first = np.load(f'{OUT}/pred/rs3dada_{ds}.npz'); names = list(first['names']); gt = refs(ds, names)
    res[ds]['flat'] = {'raw': score([np.zeros_like(g) for g in gt], gt)[0]}; tiles['flat', 'raw'] = score([np.zeros_like(g) for g in gt], gt)[1]
    keep = {}
    for k in MODELS:
        c = np.load(f'{OUT}/pred/{k}_{ds}.npz'); assert list(c['names']) == names
        cost[k] = float(c['batch4_s']); sc = float(c['sc']); tta = [x.astype(np.float32) / sc for x in c['tta']]
        assert np.abs(c['tta']).max() < 32000 and c['tta'].reshape(len(names), -1).std(1).min() > 0, (k, ds, 'clipped or constant')
        res[ds][k] = {}
        if k in ('rs3dada', 'student'):
            res[ds][k]['raw'], tiles[k, 'raw'] = score(tta, gt)
            nodata = [np.nan_to_num(g) for g in gt]
            res[ds][k]['official_tta'] = B.official([(p.copy(), g) for p, g in zip(tta, nodata)])
            res[ds][k]['official_single'] = B.official([(x.astype(np.float32) / sc, g) for x, g in zip(c['single'], nodata)])
        al = [align(p, g) for p, g in zip(tta, gt)]; res[ds][k]['aligned'], tiles[k, 'aligned'] = score(al, gt)
        keep[k] = (tta, al)
    res[ds]['paired_mae'] = {'student_minus_rs3dada_raw': paired(tiles['student', 'raw'], tiles['rs3dada', 'raw']),
                             'rs3dada_minus_flat_raw': paired(tiles['rs3dada', 'raw'], tiles['flat', 'raw']),
                             'student_minus_flat_raw': paired(tiles['student', 'raw'], tiles['flat', 'raw']),
                             'dav2rel_minus_rs3dada_aligned': paired(tiles['dav2_rel', 'aligned'], tiles['rs3dada', 'aligned']),
                             'dav2metric_minus_rs3dada_aligned': paired(tiles['dav2_metric', 'aligned'], tiles['rs3dada', 'aligned'])}
    res[ds]['bins'] = {k: {b: (m and {x: m[x] for x in ('mae', 'bias', 'n')}) for b, m in E.binned_bias(np.clip(np.stack(keep[k][0]), 0, None)[np.isfinite(np.stack(gt))], np.stack(gt)[np.isfinite(np.stack(gt))]).items()} for k in ('rs3dada', 'student')}
    if ds == 'GAMUS':
        cl = np.stack([G.read('classes', n) for n in names]); G_ = np.stack(gt); out = {}
        for lab, codes in G.LANDSCAPES.items():
            m = np.isin(cl, codes) & np.isfinite(G_); row = {'pixels': int(m.sum()), 'flat': float(G_[m].mean())}
            for k, idx, nm in (('rs3dada', 0, 'rs3dada_raw'), ('student', 0, 'student_raw'), ('rs3dada', 1, 'rs3dada_aligned'), ('dav2_rel', 1, 'dav2_rel_aligned'), ('dav2_metric', 1, 'dav2_metric_aligned')):
                p = np.clip(np.stack(keep[k][idx]), 0, None)[m]; row[nm] = float(np.abs(p - G_[m]).mean()); row[nm + '_bias'] = float((p - G_[m]).mean())
            out[lab] = row
        res[ds]['landscape'] = out
    i = int(np.argsort(tiles['rs3dada', 'raw'])[len(names) // 2])
    examples[ds] = (names[i], gt[i], keep['rs3dada'][0][i], keep['student'][0][i], keep['dav2_rel'][1][i])
res['cost'] = {k: {**json.load(open(f'{OUT}/{k}_info.json')), 'batch4_s': cost[k], 'tiles_per_min': 60 / cost[k]} for k in MODELS}
json.dump(res, open(f'{OUT}/results.json', 'w'), indent=1)
import cv2
from PIL import ImageDraw
S, GAP, LEFT, HEAD = 240, 8, 96, 26
canvas = Image.new('RGB', (LEFT + 5 * (S + GAP), HEAD + 3 * (S + GAP)), 'white'); draw = ImageDraw.Draw(canvas)
for c, t in enumerate(('Input', 'Reference', 'RS3DAda', 'Student', 'DA-V2 (aligned)')):
    draw.text((LEFT + c * (S + GAP) + 4, 8), t, fill='black')
for r, (ds, (n, g, a, s_, d)) in enumerate(examples.items()):
    if ds == 'GAMUS':
        with h5py.File(G.path('images', n)) as h: rgb = h['image'][260:764, 260:764]
    else:
        import glob
        rgb = np.array(Image.open(glob.glob(f'{ROOT}/data/geopose/OGC_{ds[-3:]}/opt/{n}.*')[0]))[4:508, 4:508, :3]
    top = float(max(5, np.nanpercentile(g, 99.5)))
    draw.text((6, HEAD + r * (S + GAP) + 8), {'GAMUS': 'GAMUS', 'OGC_ATL': 'Atlanta', 'OGC_ARG': 'San Fernando'}[ds], fill='black')
    draw.text((6, HEAD + r * (S + GAP) + 26), f'0 to {top:.0f} m', fill='black')
    for c, im in enumerate((rgb, g, a, s_, d)):
        if c == 0: t = Image.fromarray(np.asarray(im, np.uint8))
        else:
            u = (np.clip(np.nan_to_num(im) / top, 0, 1) * 255).astype(np.uint8)
            t = Image.fromarray(cv2.cvtColor(cv2.applyColorMap(u, cv2.COLORMAP_VIRIDIS), cv2.COLOR_BGR2RGB))
        canvas.paste(t.resize((S, S), Image.BILINEAR), (LEFT + c * (S + GAP), HEAD + r * (S + GAP)))
canvas.save(f'{OUT}/examples.png')
print('done')
