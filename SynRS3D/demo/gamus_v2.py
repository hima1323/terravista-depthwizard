"""GAMUS evaluation, protocol v2 (plan step 2): per-tile means with 95% bootstrap CIs, pooled values beside them,
a terrain-only baseline (nDSM = 0), building-level errors, leaf-on/leaf-off trees and uncertainty-as-ranking.

usage: .venv/bin/python demo/gamus_v2.py                  analysis from cached predictions (no model, no network)
       .venv/bin/python demo/gamus_v2.py --fetch-old45    download the 21 tiles of the old 45-tile README set that are
                                                          not among the 150 cached ones (data/GAMUS_old45/, ~200 MB)
       lockf -k -t 14400 <model.lock> .venv/bin/python demo/gamus_v2.py --predict-old45   predict those 21 (model)
       .venv/bin/python demo/gamus_v2.py --selftest
Test set (frozen): the 150 tiles of data/GAMUS_bench.txt = demo/gamus_benchmark.py 50 (evenly spaced, 50 per city,
GAMUS test split). Same crop and predictions as demo/gamus_benchmark.py: 504x504 centre crop, cached single pass, 4-flip
TTA mean and 4-flip spread (demo/benchmark/gamus/pred). The old README headline (45 tiles = gamus_benchmark.py 15) is
reproduced first with the old code path (benchmark.official / benchmark.pooled) to prove alignment.
v2 cleaning: reference -5 m voids (no LiDAR return, mostly water) are excluded; small negative reference heights and
negative predictions are clipped to 0. Metrics: demo/eval_v2.py. Per-tile class/bin means use tiles with >= 500 px of it.
Writes demo/benchmark/v2/gamus_v2.json, gamus_v2.md, gamus_v2_exg_hist.png, gamus_v2_exg_tiles.png.
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark as B
import gamus_benchmark as G
import eval_v2 as E

V2 = os.path.join(B.OUT, 'v2')
MAIN, OLD45 = G.DATA, os.path.join(B.ROOT, 'data', 'GAMUS_old45')
OLD45_LIST, OLD45_PRED = os.path.join(OLD45, 'GAMUS_bench_old45.txt'), os.path.join(V2, 'gamus_old45_pred')
MIN_PX, TREE_MIN_PX = 500, 5000
OLD = {'mae': 4.01, 'rmse': 7.21, 'bias': -2.58, 'r': 0.664, 'official_mae': 4.01, 'official_rmse': 5.90, 'spearman': 0.56}
CMD = '.venv/bin/python demo/gamus_v2.py'


def names150():
    return [l.strip() for l in open(G.LIST) if l.strip()]


def names45():
    """The old README set: gamus_benchmark.tile_list(15) on the same Hugging Face listing (needs network once)."""
    lst, G.LIST = G.LIST, OLD45_LIST
    os.makedirs(OLD45, exist_ok=True)
    try:
        return G.tile_list(15)
    finally:
        G.LIST = lst


def read(kind, n):
    # ponytail: switches gamus_benchmark's module-level DATA so its read()/path() (crop, NYC *_IMG names) are reused
    G.DATA = MAIN if os.path.exists(os.path.join(MAIN, 'heights', 'test', n + '_AGL.h5')) else OLD45
    return G.read(kind, n)


def pred(n):
    f = os.path.join(G.PRED, n + '.npz')
    c = np.load(f if os.path.exists(f) else os.path.join(OLD45_PRED, n + '.npz'))
    return {k: c[k].astype(np.float32) for k in ('single', 'tta', 'std')}


def extra45():
    have = set(names150())
    return [n for n in names45() if n not in have]


def fetch_old45():
    G.DATA = OLD45
    jobs = [(k, n) for n in extra45() for k in G.KINDS]
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(G.fetch, jobs))
    print(f'{len(jobs)} files in {OLD45}')


def predict_old45():
    import infer_height
    os.makedirs(OLD45_PRED, exist_ok=True)
    todo = [n for n in extra45() if not os.path.exists(os.path.join(OLD45_PRED, n + '.npz'))]
    if not todo:
        return print('old-45 predictions already cached')
    model, device, dtype = infer_height.load_model(infer_height.WEIGHTS, fp16=True)
    for i, n in enumerate(todo, 1):
        single, tta, std = B.predict_tile(model, device, dtype, read('images', n))
        np.savez_compressed(os.path.join(OLD45_PRED, n + '.npz'), single=single.astype(np.float16),
                            tta=tta.astype(np.float16), std=std.astype(np.float16))
        print(f'[{i}/{len(todo)}] {n} on {device}', flush=True)


def clean(raw):
    """v2 reference: -5 m voids -> NaN, small negatives -> 0."""
    return np.where(raw <= -4.99, np.nan, np.clip(raw, 0, None)).astype(np.float32)


def otsu(v):
    """Threshold maximising between-class variance of 1-D values; also eta = between / total variance (1 = separable)."""
    v = np.sort(np.asarray(v, np.float64))
    best = max(((i / len(v)) * (1 - i / len(v)) * (v[:i].mean() - v[i:].mean()) ** 2, i) for i in range(1, len(v)))
    return float((v[best[1] - 1] + v[best[1]]) / 2), float(best[0] / v.var())


def exg(rgb, m):
    """Mean excess green 2g - r - b in chromatic coordinates (brightness-free) over mask m."""
    x = rgb[m].astype(np.float64)
    s = x.sum(1) + 1e-6
    return float(((2 * x[:, 1] - x[:, 0] - x[:, 2]) / s).mean())


def reproduce(n45):
    """Old README numbers with the old code path (raw reference, voids as 0 m, argsort ranks on a 200k subsample)."""
    out = {}
    rows = {n: (pred(n), read('heights', n).astype(np.float32)) for n in n45}
    for city in ['ALL', 'DC', 'NYC', 'PHL']:
        sel = [n for n in n45 if city == 'ALL' or n.split('_')[0] == city]
        out[city] = {m: B.official([(rows[n][0][m], rows[n][1]) for n in sel]) for m in ('single', 'tta')}
    P = np.concatenate([np.clip(rows[n][0]['tta'], 0, None).ravel() for n in n45])
    Gt = np.concatenate([np.clip(rows[n][1], 0, None).ravel() for n in n45])
    U = np.concatenate([rows[n][0]['std'].ravel() for n in n45])
    out['pooled_tta'] = B.pooled(P, Gt, np.isfinite(Gt))
    ranks = lambda x: np.argsort(np.argsort(x))
    sub = np.random.default_rng(0).choice(len(U), min(200_000, len(U)), replace=False)
    out['spearman_old_method'] = float(np.corrcoef(ranks(U[sub]), ranks(np.abs(P - Gt)[sub]))[0, 1])
    out['spearman_tied_ranks_all_pixels'] = E.spearman(U, np.abs(P - Gt))
    return out


def analyse(names):
    T = {}
    for n in names:
        p, raw = pred(n), read('heights', n).astype(np.float32)
        assert p['tta'].shape == raw.shape == (504, 504), n
        g = clean(raw)
        T[n] = {'p': np.clip(p['tta'], 0, None), 'ps': np.clip(p['single'], 0, None), 'u': p['std'], 'g': g,
                'raw': raw, 'c': read('classes', n).astype(np.uint8), 'rgb': read('images', n)}
    city = lambda n: n.split('_')[0]
    cities = sorted({city(n) for n in names})
    ev = lambda sel, key='p', mask=None, min_n=MIN_PX: E.evaluate(
        [((T[n][key] if key != 'zero' else 0) - T[n]['g'], T[n]['g']) if mask is None else
         (((T[n][key] if key != 'zero' else 0) - T[n]['g'])[mask(T[n])], T[n]['g'][mask(T[n])]) for n in sel], min_n=min_n)
    hi = lambda sel, key='p', union=True: E.aggregate(
        [E.high_metrics(T[n][key] if key != 'zero' else np.zeros_like(T[n]['g']), T[n]['g'], union=union) for n in sel],
        E.high_metrics(*[np.concatenate([(T[n][key] if key != 'zero' else np.zeros_like(T[n]['g'])).ravel() for n in sel]),
                         np.concatenate([T[n]['g'].ravel() for n in sel])], union=union))
    # official metric: clipping ours at 0 first changes nothing (Result sets <= 0 to 1e-6); raw reference as before
    res = {'official_150': {c: {m: B.official([(T[n][k], T[n]['raw']) for n in names if c == 'ALL' or city(n) == c])
                                for m, k in (('single', 'ps'), ('tta', 'p'))} for c in ['ALL'] + cities}}
    t0 = time.time()
    res['overall'] = {'tta': ev(names, min_n=1), 'single': ev(names, 'ps', min_n=1), 'zero_baseline': ev(names, 'zero', min_n=1)}
    d = [E.metrics(T[n]['p'] - T[n]['g'])['mae'] - E.metrics(T[n]['ps'] - T[n]['g'])['mae'] for n in names]
    res['tta_minus_single_mae'] = {'mean': float(np.mean(d)), 'ci95': list(E.bootstrap_ci(d)), 'tiles_tta_better': int(np.sum(np.array(d) < 0))}
    res['high'] = {'union_official': {k: hi(names, k) for k in ('p', 'ps', 'zero')},
                   'ref_gt3': {k: hi(names, k, union=False) for k in ('p', 'ps', 'zero')}}
    for h in res['high'].values():
        h['tta'], h['single'], h['zero_baseline'] = h.pop('p'), h.pop('ps'), h.pop('zero')
    res['per_city'] = {c: {'tiles': sum(city(n) == c for n in names), 'tta': ev([n for n in names if city(n) == c], min_n=1),
                           'zero_baseline': ev([n for n in names if city(n) == c], 'zero', min_n=1),
                           'high_union_tta': hi([n for n in names if city(n) == c])} for c in cities}
    grp = {**{f'landscape: {k}': v for k, v in G.LANDSCAPES.items()}, **{f'class: {v}': (k,) for k, v in G.CLASSES.items()},
           'class: unlabelled (0)': (0,)}
    res['per_group'] = {k: {'tta': ev(names, mask=lambda t, v=v: np.isin(t['c'], v)),
                            'zero_baseline': ev(names, 'zero', mask=lambda t, v=v: np.isin(t['c'], v))} for k, v in grp.items()}
    res['height_bins'] = {lbl: {'tta': ev(names, mask=lambda t, lo=lo, h=h: (t['g'] >= lo) & (t['g'] < h)),
                                'single': ev(names, 'ps', mask=lambda t, lo=lo, h=h: (t['g'] >= lo) & (t['g'] < h))}
                          for lbl, (lo, h) in zip(E.BIN_LABELS, E.BINS)}
    print(f'pixel metrics {time.time() - t0:.0f} s', flush=True)

    # buildings: connected components of reference class 3, >= 20 px, 90th percentile inside each
    bl = {n: E.building_level(T[n]['p'], T[n]['g'], T[n]['c'] == 3) for n in names}
    O, Gq = np.concatenate([bl[n][0] for n in names]), np.concatenate([bl[n][1] for n in names])
    bunits = lambda sel, z=False: E.aggregate([E.metrics((0 if z else bl[n][0]) - bl[n][1], bl[n][1]) if len(bl[n][1]) else None
                                              for n in sel], E.metrics(np.concatenate([(0 * bl[n][0] if z else bl[n][0]) - bl[n][1] for n in sel]),
                                                                       np.concatenate([bl[n][1] for n in sel])))
    res['buildings'] = {'count': int(len(Gq)), 'tiles_with_buildings': int(sum(len(bl[n][1]) > 0 for n in names)),
                        'median_px': float(np.median(np.concatenate([bl[n][2] for n in names]))),
                        'tta': bunits(names), 'zero_baseline': bunits(names, True),
                        'by_ref_p90_bin_pooled': E.binned_bias(O, Gq),
                        'per_city': {c: bunits([n for n in names if city(n) == c]) for c in cities}}

    # uncertainty (4-flip spread) as a ranking of |error|
    sp = lambda sel, mask: (lambda per, pool: {'mean': float(np.mean([x for x in per if x is not None])),
                                               'ci95': list(E.bootstrap_ci(per)), 'tiles': sum(x is not None for x in per), 'pooled': pool})(
        [E.spearman(T[n]['u'][mask(T[n])], np.abs(T[n]['p'] - T[n]['g'])[mask(T[n])]) if mask(T[n]).sum() >= MIN_PX else None for n in sel],
        E.spearman(np.concatenate([T[n]['u'][mask(T[n])] for n in sel]), np.concatenate([np.abs(T[n]['p'] - T[n]['g'])[mask(T[n])] for n in sel])))
    res['uncertainty_spearman'] = {'all pixels': sp(names, lambda t: np.isfinite(t['g'])),
                                   'high (ref or ours > 3 m)': sp(names, lambda t: (t['g'] > 3) | (t['p'] > 3)),
                                   'high (ref > 3 m)': sp(names, lambda t: t['g'] > 3),
                                   'flat (ref and ours < 1 m)': sp(names, lambda t: (t['g'] < 1) & (t['p'] < 1)),
                                   **{f'class: {v}': sp(names, lambda t, k=k: (t['c'] == k) & np.isfinite(t['g'])) for k, v in G.CLASSES.items()}}
    print(f'+ buildings, spearman {time.time() - t0:.0f} s', flush=True)

    # trees, leaf-on vs leaf-off proxy: ExG over reference tree canopy (class 6, > 3 m)
    canopy = lambda t: (t['c'] == 6) & (t['g'] > 3)
    tn = [n for n in names if canopy(T[n]).sum() >= TREE_MIN_PX]
    x = {n: exg(T[n]['rgb'], canopy(T[n])) for n in tn}
    grass = {n: exg(T[n]['rgb'], T[n]['c'] == 2) if (T[n]['c'] == 2).sum() >= MIN_PX else None for n in tn}
    thr, eta = otsu(list(x.values()))
    on, off = [n for n in tn if x[n] >= thr], [n for n in tn if x[n] < thr]
    tree = lambda sel: ev(sel, mask=lambda t: t['c'] == 6) if sel else None
    bias = {n: E.metrics((T[n]['p'] - T[n]['g'])[T[n]['c'] == 6])['bias'] for n in tn}
    res['trees_leaf'] = {
        'proxy': 'per tile mean ExG = (2G-R-B)/(R+G+B) over reference tree pixels > 3 m; tiles with >= '
                 f'{TREE_MIN_PX} such px; Otsu threshold on the per-tile values', 'threshold': thr, 'otsu_eta': eta,
        'tiles': len(tn), 'leaf_on_tiles': len(on), 'leaf_off_tiles': len(off),
        'by_city': {c: {'on': sum(city(n) == c for n in on), 'off': sum(city(n) == c for n in off)} for c in cities},
        'spearman_tile_exg_vs_tree_bias': E.spearman([x[n] for n in tn], [bias[n] for n in tn]),
        'spearman_tile_exg_trees_vs_grass': E.spearman([x[n] for n in tn if grass[n] is not None], [grass[n] for n in tn if grass[n] is not None]),
        'trees_all_tiles': tree(names), 'trees_tree_tiles': tree(tn), 'trees_leaf_on': tree(on), 'trees_leaf_off': tree(off),
        # confound checks: the split follows the city; within-city ExG vs bias, and how tall the canopy is per group
        'canopy_height_and_ratio': {k: canopy_ratio(T, sel, canopy) for k, sel in [('proxy_on', on), ('proxy_off', off)] +
                                    [(c, [n for n in tn if city(n) == c]) for c in cities]},
        'within_city': {c: {'tiles': len(sel), 'exg_median': float(np.median([x[n] for n in sel])),
                            'spearman_exg_vs_tree_bias': E.spearman([x[n] for n in sel], [bias[n] for n in sel]),
                            'trees_proxy_on': tree([n for n in sel if n in on]), 'trees_proxy_off': tree([n for n in sel if n in off])}
                        for c in cities for sel in [[n for n in tn if city(n) == c]]},
        'tile_exg': {n: round(x[n], 4) for n in tn}}
    plots(T, x, thr, canopy)
    return res


def canopy_ratio(T, sel, canopy):
    """Pooled over the canopy pixels (class 6, ref > 3 m) of the tiles: mean reference height and mean ours / mean ref."""
    g = np.concatenate([T[n]['g'][canopy(T[n])] for n in sel]) if sel else np.zeros(0)
    p = np.concatenate([T[n]['p'][canopy(T[n])] for n in sel]) if sel else np.zeros(0)
    return {'tiles': len(sel), 'px': int(len(g)), 'ref_mean_m': float(g.mean()) if len(g) else None,
            'ours_over_ref': float(p.mean() / g.mean()) if len(g) else None}


def plots(T, x, thr, canopy):
    """Histogram of per-tile tree ExG (stacked by city) with the threshold; contact sheet of 6 lowest, 6 around the
    threshold, 6 highest; and canopy-centred crops of the 4 greenest tiles per city (the visual leaf-on check)."""
    v = np.array(list(x.values()))
    edges = np.linspace(v.min(), v.max(), 26)
    h, _ = np.histogram(v, edges)
    hc = {c: np.histogram([x[n] for n in x if n.split('_')[0] == c], edges)[0] for c in ('DC', 'NYC', 'PHL')}
    col = {'DC': (200, 120, 50), 'NYC': (70, 110, 190), 'PHL': (60, 140, 90)}
    W, H, L, Bm = 760, 420, 60, 60
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    X = lambda e: L + (e - edges[0]) / (edges[-1] - edges[0]) * (W - L - 20)
    Y = lambda c: H - Bm - c / max(h.max(), 1) * (H - Bm - 50)
    for i in range(len(h)):
        base = 0
        for cname, hh in hc.items():
            if hh[i]:
                d.rectangle([X(edges[i]) + 1, Y(base + hh[i]), X(edges[i + 1]) - 1, Y(base)], fill=col[cname])
            base += hh[i]
    for j, (cname, cc) in enumerate(col.items()):
        d.rectangle([W - 120, 40 + 18 * j, W - 108, 52 + 18 * j], fill=cc)
        d.text((W - 100, 40 + 18 * j), cname, fill='black')
    d.line([X(thr), 40, X(thr), H - Bm], fill=(200, 40, 40), width=2)
    d.line([L, H - Bm, W - 20, H - Bm], fill='black')
    for e in np.linspace(edges[0], edges[-1], 6):
        d.text((X(e) - 15, H - Bm + 6), f'{e:.3f}', fill='black')
    for c in range(0, h.max() + 1, max(1, h.max() // 5)):
        d.text((10, Y(c) - 6), str(c), fill='black')
    d.text((L, 12), f'GAMUS tiles: mean ExG over reference tree canopy (n={len(v)}); red = Otsu threshold {thr:.3f} '
                    '(left = proxy leaf-off)', fill='black')
    d.text((W // 2 - 120, H - 22), 'ExG = (2G - R - B) / (R + G + B), per-tile mean', fill='black')
    im.save(os.path.join(V2, 'gamus_v2_exg_hist.png'))
    order = sorted(x, key=x.get)
    k = int(np.searchsorted([x[n] for n in order], thr))
    pick = order[:6] + order[max(0, k - 3):k + 3] + order[-6:]
    s = 168
    sheet = Image.new('RGB', (6 * s, 3 * (s + 16)), 'white')
    dd = ImageDraw.Draw(sheet)
    for i, n in enumerate(pick):
        r, c = divmod(i, 6)
        sheet.paste(Image.fromarray(T[n]['rgb']).resize((s, s)), (c * s, r * (s + 16) + 16))
        dd.text((c * s + 4, r * (s + 16) + 2), f'{n} {x[n]:+.3f}', fill='black')
    sheet.save(os.path.join(V2, 'gamus_v2_exg_tiles.png'))
    s = 330
    sheet = Image.new('RGB', (4 * s, 3 * (s + 16)), 'white')
    dd = ImageDraw.Draw(sheet)
    for r, cname in enumerate(('DC', 'NYC', 'PHL')):
        for k, n in enumerate(sorted([n for n in x if n.split('_')[0] == cname], key=x.get)[-4:]):
            m = canopy(T[n])
            frac, i, j = max((m[i:i + 168, j:j + 168].mean(), i, j) for i in range(0, 337, 56) for j in range(0, 337, 56))
            sheet.paste(Image.fromarray(T[n]['rgb'][i:i + 168, j:j + 168]).resize((s, s)), (k * s, r * (s + 16) + 16))
            dd.text((k * s + 4, r * (s + 16) + 2), f'{n} ExG {x[n]:+.3f}, canopy {frac:.0%} of crop', fill='black')
    sheet.save(os.path.join(V2, 'gamus_v2_trees_greenest.png'))


def write_md(R):
    c, v = E.cell, R['v2']
    f = lambda x, nd=2: '–' if x is None else f'{x:.{nd}f}'
    rp, o45 = R['reproduction'], R['reproduction']['old45']
    L = ['# GAMUS, evaluation protocol v2', '',
         'Commands (from `SynRS3D/`; metrics library `demo/eval_v2.py`, self-checks via `--selftest` on both scripts):', '', '```',
         '.venv/bin/python demo/gamus_v2.py --fetch-old45        # once: the 21 old-45 tiles not in the 150 (network)',
         '/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/gamus_v2.py --predict-old45   # once: model',
         f'{CMD}                       # this report, from cached predictions only (~2 min, no model)', '```', '',
         '**Data source.** ' + R['source']['summary'], '',
         f"**Test set (frozen in gamus_v2.json).** {R['test_set']['n']} tiles, 50 per city (DC, NYC, PHL), evenly spaced "
         "over the GAMUS test split (`gamus_benchmark.py 50`, `data/GAMUS_bench.txt`); 504x504 centre crop; reference = "
         "LiDAR nDSM; -5 m voids excluded, negatives clipped to 0. Cells: **mean over tiles [95% bootstrap CI over tiles] "
         "(pooled over pixels)**. TTA prediction unless stated.", '',
         '## 1. Reproduction of the old headline', '',
         f"The README's 45 tiles are `gamus_benchmark.py 15` (np.linspace, 15 per city, over the 361 DC / 1000 NYC / 1500 "
         f"PHL test tiles); the cached 150 are `gamus_benchmark.py 50`. {o45['in_150']} of the 45 are among the 150; the other "
         f"{45 - o45['in_150']} were {'downloaded and predicted here (MPS fp16; the old run was CUDA fp16)' if o45['complete'] else 'NOT available: run --fetch-old45 and --predict-old45'}. "
         "Old code path (official per-tile utils/metrics.py, raw reference with -5 m voids as 0 m).", '',
         '| Tiles | City | Pass | MAE old → now | RMSE old → now | MAE >3 m old → now | RMSE >3 m old → now |', '|---|---|---|---|---|---|---|']
    oj, o = rp['old_json'], v['official_150']
    for k in ('ALL', 'DC', 'NYC', 'PHL'):
        for m, om in (('tta', 'tta'), ('single', 'single_pass')):
            a = o45['metrics'][k][m] if o45['complete'] else None
            L.append(f"| 45 | {k} | {m} | " + ' | '.join(f"{oj[k][om][w][q]:.2f} → {f(a[w][q]) if a else '–'}" for w in ('whole', 'high') for q in ('mae', 'rmse')) + ' |')
    for k in ('ALL', 'DC', 'NYC', 'PHL'):
        for m in ('tta', 'single'):
            L.append(f"| 150 | {k} | {m} | " + ' | '.join(f"– → {f(o[k][m][w][q])}" for w in ('whole', 'high') for q in ('mae', 'rmse')) + ' |')
    if o45['complete']:
        a = o45['metrics']
        L += ['', f"45 tiles, pixel-pooled TTA, old → now: MAE 4.01 → {f(a['pooled_tta']['mae'])}, RMSE 7.21 → {f(a['pooled_tta']['rmse'])}, "
              f"bias -2.58 → {a['pooled_tta']['bias']:+.2f}, r 0.664 → {f(a['pooled_tta']['r'], 3)}; Spearman spread vs |error| "
              f"(old method: argsort ranks, 200k random px) 0.56 → {f(a['spearman_old_method'])} (tie-aware ranks, all px: "
              f"{f(a['spearman_tied_ranks_all_pixels'])})."]
    b = rp['old_method_150']['pooled_tta']
    L += ['', f"150 tiles, same old code path, pixel-pooled TTA: MAE {f(b['mae'])}, RMSE {f(b['rmse'])}, bias {b['bias']:+.2f}, "
          f"r {f(b['r'], 3)}; Spearman (old method) {f(rp['old_method_150']['spearman_old_method'])}.", '',
          "**Why 45 and 150 differ.** Same code, crop and model: the old 45-tile numbers are reproduced to within 0.01 m (MPS "
          "vs CUDA fp16 does not matter), so alignment is proven. The 150 tiles are a larger, different sample (only "
          f"{o45['in_150']} tiles shared): overall official MAE {oj['ALL']['tta']['whole']['mae']:.2f} → {o['ALL']['tta']['whole']['mae']:.2f}, "
          "but per city " + ', '.join(f"{k} {oj[k]['tta']['whole']['mae']:.2f} → {o[k]['tta']['whole']['mae']:.2f}" for k in ('DC', 'NYC', 'PHL'))
          + f", and pooled r {OLD['r']:.2f} → {b['r']:.2f}. Fifteen tiles per city is too few to rank cities, hence the per-tile CIs "
          "below. v2 also excludes the -5 m no-return voids that the old code scored as 0 m.",
          '', '## 2. Overall and per city (leave-one-city-out units)', '',
          '| Set | Tiles | MAE (m) | RMSE (m) | Bias (m) | NMAD (m) | r | within ±2 m | Baseline nDSM=0 MAE |', '|---|---|---|---|---|---|---|---|---|']
    rows = [('ALL, TTA', R['test_set']['n'], v['overall']['tta'], v['overall']['zero_baseline']),
            ('ALL, single pass', R['test_set']['n'], v['overall']['single'], None)]
    rows += [(k, e['tiles'], e['tta'], e['zero_baseline']) for k, e in v['per_city'].items()]
    for k, n, a, z in rows:
        L.append(f"| {k} | {n} | {c(a, 'mae')} | {c(a, 'rmse')} | {c(a, 'bias')} | {c(a, 'nmad')} | {c(a, 'r')} | {c(a, 'within_2m')} | {c(z, 'mae') if z else '–'} |")
    t = v['tta_minus_single_mae']
    L += ['', f"TTA minus single-pass MAE, paired per tile: {t['mean']:+.3f} m [{t['ci95'][0]:+.3f}, {t['ci95'][1]:+.3f}]; "
          f"TTA better on {t['tiles_tta_better']} of {R['test_set']['n']} tiles.", '',
          "Baseline nDSM = 0 (terrain only, ours = 0 everywhere): r is undefined; its bias = -(mean reference height). Share "
          f"within ±1 m: ours {v['overall']['tta']['within_1m']['mean']:.2f}, baseline {v['overall']['zero_baseline']['within_1m']['mean']:.2f}; "
          f"within ±2 m: ours {v['overall']['tta']['within_2m']['mean']:.2f}, baseline {v['overall']['zero_baseline']['within_2m']['mean']:.2f} "
          "(half the pixels are flat ground, where predicting 0 is already right).", '',
          '## 3. High (> 3 m) metrics', '',
          '| Definition | Prediction | MAE (m) | RMSE (m) | Bias (m) | r | Pixels (pooled) |', '|---|---|---|---|---|---|---|']
    for dn, lbl in [('union_official', 'ref or ours > 3 m (utils/metrics.py)'), ('ref_gt3', 'ref > 3 m')]:
        for k in ('tta', 'single', 'zero_baseline'):
            a = v['high'][dn][k]
            L.append(f"| {lbl} | {k} | {c(a, 'mae')} | {c(a, 'rmse')} | {c(a, 'bias')} | {c(a, 'r')} | {a['pooled']['n']:,} |")
    L += ['', '## 4. Per landscape / land-cover class (tiles with >= 500 px of the class)', '',
          '| Group | Tiles | MAE (m) | Bias (m) | NMAD (m) | r | Baseline MAE | Pixels (pooled) |', '|---|---|---|---|---|---|---|---|']
    for k, e in v['per_group'].items():
        a = e['tta']
        L.append(f"| {k} | {a['units']} | {c(a, 'mae')} | {c(a, 'bias')} | {c(a, 'nmad')} | {c(a, 'r')} | {c(e['zero_baseline'], 'mae')} | {a['pooled']['n']:,} |")
    L += ['', '## 5. Bias by reference height bin', '', '| Bin | Tiles | Bias TTA (m) | MAE TTA (m) | Bias single (m) | Pixels |', '|---|---|---|---|---|---|']
    for k, e in v['height_bins'].items():
        L.append(f"| {k} | {e['tta']['units']} | {c(e['tta'], 'bias')} | {c(e['tta'], 'mae')} | {c(e['single'], 'bias')} | {e['tta']['pooled']['n']:,} |")
    b = v['buildings']
    L += ['', '## 6. Building level (90th percentile height per building)', '',
          f"{b['count']:,} buildings = connected components of the reference building class with >= 20 px, in "
          f"{b['tiles_with_buildings']} tiles (median {b['median_px']:.0f} px; terraced rows merge into one component).", '',
          '| Set | MAE (m) | RMSE (m) | Bias (m) | NMAD (m) | r | within ±2 m |', '|---|---|---|---|---|---|---|']
    for k, a in [('ALL, TTA', b['tta']), ('ALL, baseline nDSM=0', b['zero_baseline'])] + list(b['per_city'].items()):
        L.append(f"| {k} | {c(a, 'mae')} | {c(a, 'rmse')} | {c(a, 'bias')} | {c(a, 'nmad')} | {c(a, 'r')} | {c(a, 'within_2m')} |")
    L += ['', 'Pooled over buildings, by reference building height (90th pct):', '', '| Building height | Buildings | Bias (m) | MAE (m) |', '|---|---|---|---|']
    for k, a in b['by_ref_p90_bin_pooled'].items():
        if a:
            L.append(f"| {k} | {a['n']:,} | {a['bias']:+.2f} | {a['mae']:.2f} |")
    tl = v['trees_leaf']
    L += ['', '## 7. Trees: leaf-on vs leaf-off (RGB proxy, judged unreliable)', '',
          f"Proxy: {tl['proxy']}. Threshold {tl['threshold']:.3f} (Otsu eta = {tl['otsu_eta']:.2f}; 1 = perfectly two-mode). "
          f"{tl['tiles']} tiles qualify: {tl['leaf_on_tiles']} 'proxy-on', {tl['leaf_off_tiles']} 'proxy-off'; by city "
          + ', '.join(f"{k} {e['on']} on / {e['off']} off" for k, e in tl['by_city'].items()) + '. '
          f"Spearman across tiles of tree ExG vs tree bias: {f(tl['spearman_tile_exg_vs_tree_bias'])}; tree ExG vs grass ExG: "
          f"{f(tl['spearman_tile_exg_trees_vs_grass'])}. Histogram (stacked by city): `gamus_v2_exg_hist.png`; spot-checks: "
          "`gamus_v2_exg_tiles.png` (lowest / around threshold / highest), `gamus_v2_trees_greenest.png` (canopy crops of the 4 "
          "greenest tiles per city).", '', R['trees_note'], '',
          '| Tree pixels (class 6) in | Tiles | MAE (m) | Bias (m) | NMAD (m) | r | Pixels (pooled) |', '|---|---|---|---|---|---|---|']
    rows = [(k.replace('trees_', '').replace('leaf_', 'proxy ').replace('_', ' '), tl[k]) for k in
            ('trees_all_tiles', 'trees_tree_tiles', 'trees_leaf_on', 'trees_leaf_off')]
    rows += [(f"{k}, proxy {o}", e[f'trees_proxy_{o}']) for k, e in tl['within_city'].items() for o in ('on', 'off')]
    for k, a in rows:
        if a and a['units']:
            L.append(f"| {k} | {a['units']} | {c(a, 'mae')} | {c(a, 'bias')} | {c(a, 'nmad')} | {c(a, 'r')} | {a['pooled']['n']:,} |")
    L += ['', 'Confound check, pooled over canopy pixels (class 6, ref > 3 m) of the qualifying tiles:', '',
          '| Group | Tiles | Mean reference canopy height (m) | Mean ours / mean reference | Within-city Spearman ExG vs tree bias |',
          '|---|---|---|---|---|']
    for k, e in tl['canopy_height_and_ratio'].items():
        w = tl['within_city'].get(k)
        L.append(f"| {k} | {e['tiles']} | {f(e['ref_mean_m'], 1)} | {f(e['ours_over_ref'])} | {f(w['spearman_exg_vs_tree_bias']) if w else '–'} |")
    L += ['', '## 8. Uncertainty (4-flip spread) as a ranking of |error|', '',
          '| Pixels | Tiles | Spearman rho, mean over tiles [CI] | Pooled |', '|---|---|---|---|']
    for k, e in v['uncertainty_spearman'].items():
        L.append(f"| {k} | {e['tiles']} | {e['mean']:.2f} [{e['ci95'][0]:.2f}, {e['ci95'][1]:.2f}] | {f(e['pooled'])} |")
    L += ['', '## How to word it', '', R['wording'], '']
    open(os.path.join(V2, 'gamus_v2.md'), 'w').write('\n'.join(L))
    print('\n'.join(L))


SOURCE = {
    'summary': 'GAMUS (Xiong et al. 2023, arXiv:2305.14914, CC-BY-4.0, Hugging Face earthflow/GAMUS): "High-resolution '
               'orthophotos, semantic maps, and nDSM (height) are derived and processed from open Data DC catalog and open '
               'data in the Philadelphia region"; nDSM = LiDAR DSM minus LiDAR DTM; images "with a resolution of 0.33m". '
               'So the images are **aerial orthophotos at 0.33 m GSD, not satellite images**, and the reference is airborne '
               'LiDAR. The paper does not name the NYC imagery source or any acquisition dates (leaf state unknown). '
               'RS3DAda never saw GAMUS: it was trained on synthetic SynRS3D tiles with unlabeled target images from DFC18, '
               'DFC19 JAX/OMA, GeoNRW and Overhead Geopose ARG/ATL only (RS3DAda.sh).',
    'paper': 'https://arxiv.org/abs/2305.14914', 'dataset': 'https://huggingface.co/datasets/earthflow/GAMUS',
    'image_type': 'aerial orthophoto (RGB)', 'gsd_m': 0.33, 'reference': 'airborne LiDAR nDSM (DSM - DTM)',
    'test_cities': ['DC', 'NYC', 'PHL']}


TREES_NOTE = (
    "**Verdict: the proxy is not a reliable leaf-on/leaf-off split; it mostly encodes the city.** Manual spot-check of the "
    "contact sheets (Claude reading the PNGs, 2026-10-18): DC and NYC trees are bare in every sampled tile, including the 4 "
    "greenest per city (bare crowns with long shadows over brown or green lawns). PHL looks like spring green-up: forest "
    "crowns budding (PHL_5262, PHL_5448) and some street/yard trees in leaf (PHL_4465, PHL_4205). ExG also follows each "
    "city's colour balance (DC brown, NYC blue-grey) and lawn green-up (tree vs grass ExG rho above). So 'proxy-off' is in "
    "effect DC, and the across-tile ExG-vs-bias rho shrinks within each city (confound table). PHL trees are also much "
    "shorter in the reference, so its better tree score cannot be credited to foliage alone. Fair statement: GAMUS tree "
    "numbers are mostly leaf-off / early-spring trees seen in RGB, the hardest case for single-image height, and do not "
    "measure leaf-on canopy.")


def wording(R):
    v = R['v2']
    a, z, h = v['overall']['tta'], v['overall']['zero_baseline'], v['high']['ref_gt3']['tta']
    b, t, u = v['buildings']['tta'], v['per_group']['class: trees']['tta'], v['uncertainty_spearman']
    m = lambda d, k='mae': f"{d[k]['mean']:.1f} m (95% CI {d[k]['ci95'][0]:.1f}-{d[k]['ci95'][1]:.1f})"
    return (f"Say: \"On {R['test_set']['n']} held-out GAMUS tiles (Washington DC, New York, Philadelphia; 0.33 m aerial "
            f"orthophotos with an airborne-LiDAR reference, never seen in training), height above ground from a single RGB image "
            f"has a mean per-tile MAE of {m(a)}, against {z['mae']['mean']:.1f} m for a flat-ground (nDSM = 0) baseline. Building "
            f"heights (90th percentile per building, {v['buildings']['count']:,} buildings) have MAE {m(b)}, bias "
            f"{b['bias']['mean']:+.1f} m. Tall objects are under-estimated: on pixels above 3 m the bias is "
            f"{h['bias']['mean']:+.1f} m and growing with height; leaf-off trees are the weakest class (MAE {t['mae']['mean']:.1f} m).\" "
            "Do not call GAMUS a satellite test: it is aerial imagery at 0.33 m GSD, about as sharp as pan-sharpened Cartosat-3 "
            "(~0.25-0.3 m) and much finer than other ISRO RGB, with aerial (not satellite) viewing geometry, haze and MTF; a satellite claim needs a satellite test set "
            "(Overhead Geopose / WorldView, plan step 5). Lead with per-tile MAE/NMAD and CIs, not pooled r (pooled r mixes "
            "flat ground and towers). Call the 4-flip spread a 'consistency score': its rank correlation with |error| is "
            f"{u['all pixels']['mean']:.2f} per tile overall but {u['high (ref or ours > 3 m)']['mean']:+.2f} on pixels where LiDAR or the model is above 3 m "
            f"({u['high (ref > 3 m)']['mean']:+.2f} where LiDAR is above 3 m) "
            f"and {u['class: trees']['mean']:+.2f} on trees, so it flags errors on flat ground and edges, not on the tall objects "
            "where the big errors are; it is not an error bar.")


def main():
    names = names150()
    os.makedirs(V2, exist_ok=True)
    n45 = names45()
    have = set(names)
    complete = all(os.path.exists(os.path.join(G.PRED if n in have else OLD45_PRED, n + '.npz')) for n in n45)
    old = json.load(open(os.path.join(B.OUT, 'gamus_results.json')))
    R = {'command': CMD, 'source': SOURCE,
         'test_set': {'n': len(names), 'selection': 'gamus_benchmark.tile_list(50): np.linspace over the sorted '
                      'Hugging Face heights/test listing, 50 per city; 504x504 centre crop', 'list_file': 'data/GAMUS_bench.txt',
                      'tiles': [{'tile': n, 'city': n.split('_')[0]} for n in names]},
         'reproduction': {'old_json': {k: {m: old[k][m] for m in ('single_pass', 'tta')} for k in ('ALL', 'DC', 'NYC', 'PHL')},
                          'old_reported': OLD, 'old45': {'tiles': [{'tile': n, 'city': n.split('_')[0]} for n in n45],
                                                        'in_150': len(have & set(n45)), 'complete': complete,
                                                        'metrics': reproduce(n45) if complete else None}}}
    R['reproduction']['old_method_150'] = reproduce(names)
    print('reproduction done', flush=True)
    R['v2'] = analyse(names)
    v = R['v2']['trees_leaf']
    R['trees_note'] = TREES_NOTE
    R['wording'] = wording(R)
    json.dump(R, open(os.path.join(V2, 'gamus_v2.json'), 'w'), indent=1)
    write_md(R)


def selftest():
    thr, eta = otsu(np.r_[np.random.default_rng(0).normal(-0.05, 0.01, 40), np.random.default_rng(1).normal(0.05, 0.01, 60)])
    assert -0.03 < thr < 0.03 and eta > 0.8
    g = clean(np.array([-5.0, -0.2, 0.0, 7.5], np.float32))
    assert np.isnan(g[0]) and g[1] == 0 and g[3] == 7.5
    rgb = np.array([[[10, 200, 10], [100, 100, 100]]], np.uint8)
    assert abs(exg(rgb, np.array([[True, False]])) - (400 - 20) / 220) < 1e-6 and abs(exg(rgb, np.array([[False, True]]))) < 1e-9
    assert len(names150()) == 150 and all(n.split('_')[0] in ('DC', 'NYC', 'PHL') for n in names150())
    print('gamus_v2 selftest OK')


if __name__ == '__main__':
    {'--selftest': selftest, '--fetch-old45': fetch_old45, '--predict-old45': predict_old45}.get(
        sys.argv[1] if len(sys.argv) > 1 else '', main)()
