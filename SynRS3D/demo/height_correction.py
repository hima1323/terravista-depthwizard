"""Learn a height correction on DFC19 *training* tiles and measure it on the untouched *test* tiles.

usage: .venv/bin/python demo/height_correction.py [--no-infer]
Tiles: data/DFC19_train_bench.txt (fit) and data/DFC19_bench.txt (evaluate); predictions are cached.
--no-infer uses only cached predictions (no model run); land-cover variants then need every tile's land cover.
The correction maps predicted -> true height, either for all pixels at once ("height only") or separately for
predicted buildings / trees / other pixels ("by land cover"):
  'curve'  = monotone piecewise-linear curve through binned medians (flexible)
  'linear' = one straight line per group for pixels above 2 m (simple)
Besides the in-domain split we test city -> other city (JAX -> OMA, OMA -> JAX), the honest proxy for
"calibrate on one place, use on another". Writes correction.md / correction.json in demo/benchmark/.
"""
import json, os, sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark as B  # read(), MEAN/STD, official(); also stubs metrics.py's unused imports
import infer_height

FULL = os.path.join(B.OUT, 'full')
BANDS = [(0, 3), (3, 10), (10, 20), (20, 1e9)]


def names(listfile):
    return [l.strip() for l in open(os.path.join(B.ROOT, 'data', listfile)) if l.strip()]


def infer(tiles):
    """Cache TTA height, spread and land cover for each tile (504x504 centre crop, as in evaluation.py)."""
    os.makedirs(FULL, exist_ok=True)
    model = None
    for i, n in enumerate(tiles, 1):
        f = os.path.join(FULL, n + '.npz')
        if os.path.exists(f):
            continue
        if model is None:
            model, device, dtype = infer_height.load_model(
                os.path.join(B.ROOT, 'pretrain', 'RS3DAda_vitl_DPT_height.pth'), fp16=True)
        x = (B.read('opt', n)[:3].transpose(1, 2, 0).astype(np.float32) - B.MEAN) / B.STD
        batch = torch.from_numpy(np.stack([x, x[:, ::-1], x[::-1], x[::-1, ::-1]]).transpose(0, 3, 1, 2).copy())
        with torch.no_grad():
            out = model(batch.to(device, dtype))
        p = out['regression'].float().cpu().numpy()[:, 0]
        hs = np.stack([p[0], p[1][:, ::-1], p[2][::-1], p[3][::-1, ::-1]])
        s = out['segmentation'].float().cpu().numpy()
        seg = (s[0] + s[1][:, :, ::-1] + s[2][:, ::-1] + s[3][:, ::-1, ::-1]) / 4
        np.savez_compressed(f, h=hs.mean(0).astype(np.float16), u=hs.std(0).astype(np.float16),
                            lc=seg.argmax(0).astype(np.uint8))
        print(f'[{i}/{len(tiles)}] {n}', flush=True)


def load(tiles):
    """(name, height, land cover or None, truth). Heights come from the benchmark cache when it has the tile
    (so 'raw' matches demo/benchmark/results.md exactly), else from the full cache; land cover only from the
    full cache."""
    rows = []
    for n in tiles:
        full, bench = os.path.join(FULL, n + '.npz'), os.path.join(B.OUT, 'pred', n + '.npz')
        z = np.load(full) if os.path.exists(full) else None
        h = np.load(bench)['tta'] if os.path.exists(bench) else z['h']
        gt = B.read('gt_nDSM', n)[0].astype(np.float32)
        rows.append((n, np.clip(h.astype(np.float32), 0, None), z['lc'] if z is not None else None, gt))
    return rows


def groups_of(lc, shape, by_landcover):
    g = np.zeros(shape, np.uint8)
    if by_landcover:
        for k, cls in infer_height.CORRECTION_GROUPS.items():
            g[lc == cls] = k
    return g


VARIANTS = {'curve, height only': ('curve', False), 'linear, height only': ('linear', False),
            'curve, by land cover': ('curve', True), 'linear, by land cover': ('linear', True)}


# ---------------------------------------------------------------- correction models
def fit(rows, method, by_landcover, nbins=40):
    P = np.concatenate([r[1].ravel() for r in rows])
    Gr = np.concatenate([groups_of(r[2], r[1].shape, by_landcover).ravel() for r in rows])
    T = np.concatenate([r[3].ravel() for r in rows])
    ok = np.isfinite(T)
    params = {}
    for k in [0] + (list(infer_height.CORRECTION_GROUPS) if by_landcover else []):
        sel = ok & (Gr == k)
        p, t = P[sel], np.clip(T[sel], 0, None)
        if method == 'curve':
            q = np.unique(np.percentile(p, np.linspace(0, 100, nbins + 1)))
            xs, ys = [], []
            for lo, hi in zip(q[:-1], q[1:]):
                b = (p >= lo) & (p <= hi)
                if b.sum() >= 200:
                    xs.append(float(np.median(p[b])))
                    ys.append(float(np.median(t[b])))
            ys = list(np.maximum.accumulate(ys))  # monotone: taller prediction never maps lower
            params[k] = {'x': xs, 'y': ys}
        else:  # linear, only above 2 m (below that is ground, left alone)
            b = p >= 2
            a, c = np.polyfit(p[b], t[b], 1) if b.sum() > 100 else (1.0, 0.0)
            params[k] = {'a': float(a), 'b': float(c)}
    return {'method': method, 'by_landcover': by_landcover, 'params': params}


def evaluate(rows, corr=None):
    pairs, P, T = [], [], []
    for _, p, lc, t in rows:
        pc = infer_height.correct_heights(p, lc, corr) if corr else p
        pairs.append((pc, t))
        P.append(pc.ravel())
        T.append(t.ravel())
    off = B.official(pairs)
    P, T = np.concatenate(P), np.clip(np.concatenate(T), 0, None)
    ok = np.isfinite(T)
    bands = {}
    for lo, hi in BANDS:
        m = ok & (T >= lo) & (T < hi)
        d = P[m] - T[m]
        bands[f'{lo}-{hi if hi < 1e9 else "inf"} m'] = {'mae': float(np.abs(d).mean()), 'bias': float(d.mean())}
    return {'whole_mae': off['whole']['mae'], 'whole_rmse': off['whole']['rmse'],
            'high_mae': off['high']['mae'], 'high_rmse': off['high']['rmse'], 'bands': bands}


CHOSEN = os.path.join(B.OUT, 'height_correction_chosen.json')


def choose(res, fits):
    """The correction to ship, or None: it must lower MAE in every split (in-domain and both other-city
    tests); among passing methods take the lowest average other-city MAE. Returns the both-cities fit."""
    ok = []
    for v in fits:
        if all(r[v]['whole_mae'] < r['raw']['whole_mae'] for r in res.values()):
            cross = [r[v]['whole_mae'] for k, r in res.items() if 'other city' in k]
            ok.append((sum(cross) / len(cross), v))
    if not ok:
        return None
    v = min(ok)[1]
    return dict(fits[v], variant=v, source='DFC2019 training tiles (US LiDAR)')


def main():
    train, test = names('DFC19_train_bench.txt'), names('DFC19_bench.txt')
    if '--no-infer' not in sys.argv:
        infer(train + test)
    tr, te = load(train), load(test)
    have_lc = all(r[2] is not None for r in tr + te)
    variants = {v: mb for v, mb in VARIANTS.items() if have_lc or not mb[1]}
    city = lambda rows, c: [r for r in rows if r[0].startswith(c)]
    splits = {'both cities -> both cities': (tr, te),
              'JAX -> OMA (other city)': (city(tr, 'JAX'), city(te, 'OMA')),
              'OMA -> JAX (other city)': (city(tr, 'OMA'), city(te, 'JAX'))}
    res = {}
    for split, (a, b) in splits.items():
        res[split] = {'raw': evaluate(b)}
        for v, (method, by_lc) in variants.items():
            res[split][v] = evaluate(b, fit(a, method, by_lc))
    final = {v: fit(tr, method, by_lc) for v, (method, by_lc) in variants.items()}
    json.dump({'results': res, 'fits_both_cities': final}, open(os.path.join(B.OUT, 'correction.json'), 'w'), indent=2)
    chosen = choose(res, final)
    if chosen:
        json.dump(chosen, open(CHOSEN, 'w'), indent=2)
    elif os.path.exists(CHOSEN):
        os.remove(CHOSEN)
    print('shipped correction:', chosen['variant'] if chosen else 'none (did not pass every split)')

    L = ['# Height correction on DFC19: learned on training tiles, measured on untouched test tiles', '',
         f'{len(train)} training tiles, {len(test)} test tiles; official metric (utils/metrics.py), TTA predictions.'
         + ('' if have_lc else ' Land-cover variants skipped (land cover not cached for every tile).'), '',
         f"Shipped: **{chosen['variant'] if chosen else 'none'}** (must lower MAE in all three splits).", '',
         '| Split (learn → test) | Method | MAE whole | RMSE whole | MAE >3 m | RMSE >3 m | Bias 10–20 m | Bias >20 m |',
         '|---|---|---|---|---|---|---|---|']
    for split, r in res.items():
        for m in ['raw'] + list(variants):
            e = r[m]
            L.append(f"| {split} | {m} | {e['whole_mae']:.2f} | {e['whole_rmse']:.2f} | {e['high_mae']:.2f} | "
                     f"{e['high_rmse']:.2f} | {e['bands']['10-20 m']['bias']:+.2f} | {e['bands']['20-inf m']['bias']:+.2f} |")
    open(os.path.join(B.OUT, 'correction.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
