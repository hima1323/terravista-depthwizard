"""Measure RS3DAda height accuracy on GAMUS (the dataset the SIH26175 statement recommends) against LiDAR nDSM.

usage: .venv/bin/python demo/gamus_benchmark.py [tiles_per_city=50]
GAMUS test split from Hugging Face (earthflow/GAMUS, CC-BY-4.0): 1024x1024 RGB / height-above-ground / class tiles
from Washington DC, New York and Philadelphia. We take an evenly spaced sample per city (list saved to
data/GAMUS_bench.txt), download only those tiles, and use the same protocol as demo/benchmark.py for DFC2019:
one 504x504 centre crop per tile, 4-flip TTA in one batch, the repo's official metrics (utils/metrics.py).
Writes demo/benchmark/gamus_results.md/json and example_gamus_*.png. Predictions are cached.
"""
import json, os, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark as B  # predict_tile, official, pooled, BANDS, save_example (also stubs metrics.py's unused imports)
import infer_height

HF = 'https://huggingface.co/datasets/earthflow/GAMUS'
DATA = os.path.join(B.ROOT, 'data', 'GAMUS')
LIST = os.path.join(B.ROOT, 'data', 'GAMUS_bench.txt')
PRED = os.path.join(B.OUT, 'gamus', 'pred')
CLASSES = {1: 'ground', 2: 'low vegetation', 3: 'buildings', 4: 'water', 5: 'road', 6: 'trees'}  # GAMUS codes
# GAMUS classes grouped into the landscape types SIH26175 evaluates (urban / sparse / forested; hilly needs terrain,
# which GAMUS's flat US cities do not have: see demo/landscape_benchmark.py for that)
LANDSCAPES = {'urban (buildings, roads)': (3, 5), 'forested (trees)': (6,), 'sparse / open (ground, low vegetation)': (1, 2), 'water': (4,)}
KINDS = {'images': 'RGB', 'heights': 'AGL', 'classes': 'CLS'}


def tile_list(per_city):
    """Evenly spaced test tiles per city (fixed once written, so reruns use the same tiles)."""
    if os.path.exists(LIST):
        return [l.strip() for l in open(LIST) if l.strip()]
    sib = json.load(urllib.request.urlopen(f'https://huggingface.co/api/datasets/earthflow/GAMUS', timeout=60))['siblings']
    names = sorted(s['rfilename'].split('/')[-1][:-7] for s in sib if s['rfilename'].startswith('heights/test/'))
    out = []
    for city in sorted({n.split('_')[0] for n in names}):
        c = [n for n in names if n.split('_')[0] == city]
        out += [c[int(i)] for i in np.linspace(0, len(c) - 1, min(per_city, len(c)))]
    os.makedirs(os.path.dirname(LIST), exist_ok=True)   # data/ is not in the repo
    open(LIST, 'w').write('\n'.join(out) + '\n')
    return out


def path(kind, name, suffix=None):
    if kind == 'images' and suffix is None:  # New York images are *_IMG.h5, the others *_RGB.h5
        return next((p for p in (path(kind, name, s) for s in ('RGB', 'IMG')) if os.path.exists(p)), path(kind, name, 'RGB'))
    return os.path.join(DATA, kind, 'test', f'{name}_{suffix or KINDS[kind]}.h5')


def fetch(job):
    kind, name = job
    if os.path.exists(path(kind, name)):
        return
    for suffix in [KINDS[kind]] + (['IMG'] if kind == 'images' else []):
        f = path(kind, name, suffix)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        for attempt in range(4):
            try:
                urllib.request.urlretrieve(f'{HF}/resolve/main/{kind}/test/{os.path.basename(f)}', f + '.part')
                return os.replace(f + '.part', f)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    break          # try the other file name
                if attempt == 3:
                    raise
            except OSError:
                if attempt == 3:
                    raise
            time.sleep(3)
    raise FileNotFoundError(f'{kind}/test/{name} not on Hugging Face')


def read(kind, name):
    """504x504 centre crop, as for DFC2019."""
    with h5py.File(path(kind, name)) as h:
        a = h['image']
        t, l = (a.shape[0] - 504) // 2, (a.shape[1] - 504) // 2
        return a[t:t + 504, l:l + 504]


def main():
    names = tile_list(int(sys.argv[1]) if len(sys.argv) > 1 else 50)
    jobs = [(k, n) for n in names for k in KINDS]
    with ThreadPoolExecutor(4) as ex:
        for i, _ in enumerate(ex.map(fetch, jobs), 1):
            if i % 60 == 0 or i == len(jobs):
                print(f'downloaded {i}/{len(jobs)} files', flush=True)
    os.makedirs(PRED, exist_ok=True)
    model, rows, t0 = None, [], time.time()
    for i, n in enumerate(names, 1):
        cache = os.path.join(PRED, n + '.npz')
        if not os.path.exists(cache):
            if model is None:
                model, device, dtype = infer_height.load_model(os.path.join(B.ROOT, 'pretrain', 'RS3DAda_vitl_DPT_height.pth'), fp16=True)
            single, tta, std = B.predict_tile(model, device, dtype, read('images', n))
            np.savez_compressed(cache, single=single.astype(np.float16), tta=tta.astype(np.float16), std=std.astype(np.float16))
            print(f'[{i}/{len(names)}] {n}  ({(time.time() - t0) / 60:.1f} min elapsed)', flush=True)
        c = np.load(cache)
        rows.append((n, c['single'].astype(np.float32), c['tta'].astype(np.float32), c['std'].astype(np.float32)))

    gts = {r[0]: read('heights', r[0]).astype(np.float32) for r in rows}
    import torch
    dev = 'CUDA GPU' if torch.cuda.is_available() else 'Apple MPS' if torch.backends.mps.is_available() else 'CPU'
    res = {'tiles': len(rows), 'protocol': 'GAMUS test split (Hugging Face earthflow/GAMUS), evenly spaced tiles per '
           f'city, 504x504 centre crop, LiDAR nDSM ground truth, official utils/metrics.py; fp16 on {dev}'}
    for city in ['ALL'] + sorted({r[0].split('_')[0] for r in rows}):
        sel = [r for r in rows if city == 'ALL' or r[0].split('_')[0] == city]
        entry = {'tiles': len(sel)}
        for mode, idx in [('single_pass', 1), ('tta', 2)]:
            entry[mode] = B.official([(r[idx], gts[r[0]]) for r in sel])
        if city == 'ALL':  # pixel-pooled breakdowns of the TTA prediction; water voids (-5) count as 0 m, as officially
            P = np.concatenate([np.clip(r[2], 0, None).ravel() for r in sel])
            G = np.concatenate([np.clip(gts[r[0]], 0, None).ravel() for r in sel])
            L = np.concatenate([read('classes', r[0]).ravel() for r in sel])
            entry['by_land_cover'] = {lbl: B.pooled(P, G, L == c) for c, lbl in CLASSES.items()}
            entry['by_landscape'] = {lbl: B.pooled(P, G, np.isin(L, cls)) for lbl, cls in LANDSCAPES.items()}
            entry['by_true_height'] = {f'{lo}-{hi if hi < 1e9 else "inf"} m': B.pooled(P, G, (G >= lo) & (G < hi)) for lo, hi in B.BANDS}
            entry['all_pixels'] = B.pooled(P, G, np.isfinite(G))
            U, err = np.concatenate([r[3].ravel() for r in sel]), np.abs(P - G)
            ranks = lambda x: np.argsort(np.argsort(x))
            sub = np.random.default_rng(0).choice(len(U), min(200_000, len(U)), replace=False)
            entry['spearman_unc_vs_error'] = float(np.corrcoef(ranks(U[sub]), ranks(err[sub]))[0, 1])
        res[city] = entry
    for n, _, tta, _ in sorted(rows, key=lambda r: -np.percentile(gts[r[0]], 98))[:3]:   # tallest scenes as examples
        B.save_example('gamus_' + n, read('images', n), np.clip(gts[n], 0, None), np.clip(tta, 0, None))
    json.dump(res, open(os.path.join(B.OUT, 'gamus_results.json'), 'w'), indent=2)
    write_md(res)


def write_md(res):
    a = res['ALL']
    L = ['# RS3DAda on GAMUS (LiDAR ground truth)', '', res['protocol'] + '.', '',
         '| Tiles | Pass | MAE whole (m) | RMSE whole (m) | MAE >3 m (m) | RMSE >3 m (m) |', '|---|---|---|---|---|---|']
    for city in [k for k in res if k not in ('tiles', 'protocol')]:
        for mode in ['single_pass', 'tta']:
            e = res[city][mode]
            L.append(f"| {city} ({res[city]['tiles']}) | {mode.replace('_', ' ')} | {e['whole']['mae']:.2f} | "
                     f"{e['whole']['rmse']:.2f} | {e['high']['mae']:.2f} | {e['high']['rmse']:.2f} |")
    L += ['', 'Pixel-pooled, TTA prediction (r = Pearson correlation with the LiDAR heights):', '',
          '| Group | MAE (m) | RMSE (m) | Bias (m) | r | Pixels |', '|---|---|---|---|---|---|']
    for grp in ['all_pixels', 'by_landscape', 'by_land_cover', 'by_true_height']:
        items = {'all pixels': a[grp]}.items() if grp == 'all_pixels' else a.get(grp, {}).items()
        for k, e in items:
            if e:
                r = '–' if e.get('r') is None else f"{e['r']:.3f}"
                L.append(f"| {k} | {e['mae']:.2f} | {e['rmse']:.2f} | {e['bias']:+.2f} | {r} | {e['pixels']:,} |")
    L += ['', f"Uncertainty (± = spread of the 4 flips) vs real error, Spearman rank correlation: {a['spearman_unc_vs_error']:.2f}"]
    open(os.path.join(B.OUT, 'gamus_results.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
