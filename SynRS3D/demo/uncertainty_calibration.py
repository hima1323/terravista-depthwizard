"""Calibrated uncertainty for RS3DAda heights (plan step 4): normalised split-conformal intervals, Mondrian by PREDICTED
land cover and PREDICTED height bin, leave-one-city-out on GAMUS, per pixel and per building (the app's block readout).

usage: /usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/uncertainty_calibration.py --predict
                       cache predicted land cover for the 150 frozen GAMUS tiles (model, ~10 min)
       .venv/bin/python demo/uncertainty_calibration.py          analysis from the cache; writes calibration/conformal.json
       .venv/bin/python demo/uncertainty_calibration.py --selftest
Data: the 150 tiles of data/GAMUS_bench.txt (demo/gamus_v2.py test set), 504x504 centre crop, 4-flip TTA in one batch exactly
as demo/benchmark.predict_tile, plus the land-cover head (logits averaged over the flips, argmax, as infer_height.predict).
Cache: demo/benchmark/v2/cache/gamus_lc/<tile>.npz (single, tta, std float16; lc uint8).
Method: score = |ref - pred| / (spread + c) (spread = 4-flip std); interval = pred +- q (spread + c), q = the
ceil((n+1)(1-alpha))-th smallest calibration score (finite-sample split conformal). Pixels: one random pixel per 16x16
block per tile (spatial thinning). Calibrate on two cities, test on the third (3 folds). c is chosen on the calibration
cities only (inner split by tile: q on even tiles, mean 90% width on odd tiles). Mondrian groups = predicted class group
x predicted height bin; groups with < MIN_GROUP calibration samples fall back to the pooled q. Buildings: the app's blocks
(app.extract_buildings on the predicted heights / land cover), reported height = block median, spread = block median
spread, reference = 90th percentile of the LiDAR nDSM inside the block; symmetric and signed (asymmetric) variants.
"""
import json, math, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark as B
import gamus_benchmark as G
import gamus_v2 as GV
import eval_v2 as E

ROOT = B.ROOT
V2 = os.path.join(B.OUT, 'v2')
CACHE = os.path.join(V2, 'cache', 'gamus_lc')
SHIP = os.path.join(ROOT, 'calibration', 'conformal.json')
LEVELS = (0.68, 0.90, 0.95)
CS = (0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
BLOCK, MIN_GROUP, MIN_GROUP_B = 16, 200, 40
LC = ['bareland', 'rangeland', 'developed', 'road', 'trees', 'water', 'agriculture', 'buildings']  # infer_height.LANDCOVER
CLASS_GROUP = {'buildings': 'buildings', 'trees': 'trees', 'water': 'water'}  # every other class -> 'ground'
GROUPS = ['buildings', 'trees', 'ground', 'water']
CMD = '.venv/bin/python demo/uncertainty_calibration.py'


def predict_full(model, device, dtype, rgb):
    """benchmark.predict_tile plus the land-cover head, from the same 4-flip batch: (single, tta, std, landcover)."""
    import torch
    x = (rgb.astype(np.float32) - B.MEAN) / B.STD
    batch = torch.from_numpy(np.stack([x, x[:, ::-1], x[::-1], x[::-1, ::-1]]).transpose(0, 3, 1, 2).copy()).to(device, dtype)
    with torch.no_grad():
        o = model(batch)
    p, s = o['regression'].float().cpu().numpy()[:, 0], o['segmentation'].float().cpu().numpy()
    stack = np.stack([p[0], p[1][:, ::-1], p[2][::-1], p[3][::-1, ::-1]])
    seg = s[0] + s[1][:, :, ::-1] + s[2][:, ::-1] + s[3][:, ::-1, ::-1]
    return p[0], stack.mean(0), stack.std(0), seg.argmax(0).astype(np.uint8)


def predict():
    import infer_height
    os.makedirs(CACHE, exist_ok=True)
    todo = [n for n in GV.names150() if not os.path.exists(os.path.join(CACHE, n + '.npz'))]
    if not todo:
        return print('land-cover cache complete')
    model, device, dtype = infer_height.load_model(os.path.join(ROOT, 'pretrain', 'RS3DAda_vitl_DPT_height.pth'), fp16=True)
    t0, dmax = time.time(), 0.0
    for i, n in enumerate(todo, 1):
        single, tta, std, lc = predict_full(model, device, dtype, GV.read('images', n))
        np.savez_compressed(os.path.join(CACHE, n + '.npz'), single=single.astype(np.float16), tta=tta.astype(np.float16),
                            std=std.astype(np.float16), lc=lc)
        d = float(np.abs(tta.astype(np.float16).astype(np.float32) - GV.pred(n)['tta']).max())
        dmax = max(dmax, d)
        print(f'[{i}/{len(todo)}] {n} on {device}, max |tta - old cache| {d:.3f} m ({time.time() - t0:.0f} s)', flush=True)
    print(f'done; max |tta - old cache| over tiles {dmax:.3f} m')


GSD = 0.33                                               # GAMUS orthophotos (gamus_v2.json source)
RELIAB = sorted(set(np.round(np.arange(0.05, 0.96, 0.05), 2).tolist()) | {0.68})
GRP = np.array([CLASS_GROUP.get(c, 'ground') for c in LC])


def qpair(t, level, signed=False):
    """Finite-sample split-conformal bounds (lo, hi) on t = (ref - pred) / scale. Symmetric: (-q, q), q = the
    ceil((n+1) level)-th smallest |t|. Signed: alpha/2 per tail (floor((n+1) alpha/2)-th and ceil((n+1)(1-alpha/2))-th
    smallest t). +-inf when n is too small for the level."""
    n = len(t)
    if not signed:
        k = math.ceil((n + 1) * level - 1e-9)   # epsilon: (n+1)*level is often 9.000000001
        q = float(np.sort(np.abs(t))[k - 1]) if k <= n else math.inf
        return -q, q
    a, al = np.sort(t), (1 - level) / 2
    k_lo, k_hi = math.floor((n + 1) * al + 1e-9), math.ceil((n + 1) * (1 - al) - 1e-9)
    return float(a[k_lo - 1]) if k_lo >= 1 else -math.inf, float(a[k_hi - 1]) if k_hi <= n else math.inf


def scale(u, c):
    """Normaliser spread + c; c = inf means constant width (plain split conformal)."""
    return np.ones_like(u) if math.isinf(c) else u + c


def fit(p, u, g, key, c, levels=LEVELS, signed=False, min_n=MIN_GROUP):
    """Mondrian table {level: {'pooled': (lo, hi), group: (lo, hi)}}; a group with < min_n samples uses 'pooled'.
    key None = pooled only."""
    t = (g - p) / scale(u, c)
    out = {}
    for lv in levels:
        d = {'pooled': qpair(t, lv, signed)}
        for k in ([] if key is None else np.unique(key)):
            m = key == k
            if m.sum() >= min_n:
                d[str(k)] = qpair(t[m], lv, signed)
        out[lv] = d
    return out


def interval(tab, lv, p, u, key, c):
    lo, hi, s = np.empty(len(p)), np.empty(len(p)), scale(u, c)
    keys = np.full(len(p), 'pooled') if key is None else key
    for k in np.unique(keys):
        m = keys == k
        ql, qh = tab[lv].get(str(k), tab[lv]['pooled'])
        lo[m], hi[m] = p[m] + ql * s[m], p[m] + qh * s[m]
    return lo, hi


def block_sample(shape, seed, b=BLOCK):
    """Flat indices of one random pixel per b x b block (partial edge blocks included)."""
    rng, (H, W) = np.random.default_rng(seed), shape
    r0, c0 = np.arange(0, H, b), np.arange(0, W, b)
    R = r0[:, None] + rng.integers(0, np.minimum(b, H - r0)[:, None], (len(r0), len(c0)))
    C = c0[None, :] + rng.integers(0, np.minimum(b, W - c0)[None, :], (len(r0), len(c0)))
    return (R * W + C).ravel()


def bin_label(h):
    return np.array(E.BIN_LABELS)[np.digitize(h, [3, 10, 20])]


def load():
    T = {}
    for n in GV.names150():
        c = np.load(os.path.join(CACHE, n + '.npz'))
        T[n] = {'h': c['tta'].astype(np.float32), 'u': c['std'].astype(np.float32), 'lc': c['lc'],
                'g': GV.clean(GV.read('heights', n).astype(np.float32)), 'c': GV.read('classes', n).astype(np.uint8)}
    return T


def pixel_samples(T):
    cols = {k: [] for k in ('tile', 'city', 'p', 'u', 'g', 'plc', 'rcls')}
    for i, (n, d) in enumerate(T.items()):
        idx = block_sample(d['g'].shape, i)
        idx = idx[np.isfinite(d['g'].ravel()[idx])]
        for k, v in (('tile', np.full(len(idx), i)), ('city', np.full(len(idx), n.split('_')[0])), ('p', np.clip(d['h'].ravel()[idx], 0, None)),
                     ('u', d['u'].ravel()[idx]), ('g', d['g'].ravel()[idx]), ('plc', d['lc'].ravel()[idx]), ('rcls', d['c'].ravel()[idx])):
            cols[k].append(v)
    S = {k: np.concatenate(v) for k, v in cols.items()}
    S['key'] = np.char.add(np.char.add(GRP[S['plc']], '|'), bin_label(S['p']))
    S['by'] = {'predicted class': np.array(LC)[S['plc']], 'predicted height bin': bin_label(S['p']),
               'reference height bin': bin_label(S['g']),
               'reference class (GAMUS, diagnostic)': np.array(['?', *G.CLASSES.values()])[np.clip(S['rcls'], 0, 6)]}
    return S


def building_samples(T):
    """The app's building blocks on each tile (app.extract_buildings on the predicted heights, spread and land cover),
    reported height = block median (what the viewer shows), reference = 90th pct of the LiDAR nDSM inside the block."""
    import app
    from scipy import ndimage
    cols = {k: [] for k in ('tile', 'city', 'p', 'u', 'g', 'p90', 'px')}
    for i, (n, d) in enumerate(T.items()):
        bid, blocks = app.extract_buildings(d['h'], d['u'], d['lc'], GSD, GV.read('images', n))
        objs = ndimage.find_objects(bid.astype(np.int32))
        for b in blocks:
            sl = objs[b['id'] - 1]
            g = d['g'][sl][bid[sl] == b['id']]
            ok = np.isfinite(g)
            if ok.sum() < 20 or ok.mean() < 0.5:
                continue
            for k, v in (('tile', i), ('city', n.split('_')[0]), ('p', b['height_m']), ('u', b['unc_m']),
                         ('g', float(np.percentile(g[ok], 90))), ('p90', b['height_p90']), ('px', int(ok.sum()))):
                cols[k].append(v)
    S = {k: np.array(v) for k, v in cols.items()}
    S['key'] = bin_label(S['p'])
    S['by'] = {'predicted height bin': S['key'], 'reference height bin': bin_label(S['g'])}
    return S


def choose_c(S, m, cs, signed, min_n, use_key=True):
    """c with the smallest mean 90% width on odd calibration tiles when q is fitted on even ones (calibration data only)."""
    tiles = np.unique(S['tile'][m])
    A, Bm = m & np.isin(S['tile'], tiles[::2]), m & np.isin(S['tile'], tiles[1::2])
    out = {}
    for c in cs:
        tab = fit(S['p'][A], S['u'][A], S['g'][A], S['key'][A] if use_key else None, c, (0.9,), signed, min_n)
        lo, hi = interval(tab, 0.9, S['p'][Bm], S['u'][Bm], S['key'][Bm] if use_key else None, c)
        out[c] = {'width_90': float((np.clip(hi, 0, None) - np.clip(lo, 0, None)).mean()),
                  'coverage_90': float(((lo <= S['g'][Bm]) & (S['g'][Bm] <= hi)).mean())}
    return min(out, key=lambda c: out[c]['width_90']), {('inf' if math.isinf(c) else str(c)): v for c, v in out.items()}


def report(S, m, tab, c, levels, use_key=True):
    out = {}
    for lv in levels:
        lo, hi = interval(tab, lv, S['p'][m], S['u'][m], S['key'][m] if use_key else None, c)
        g, t = S['g'][m], S['tile'][m]
        cov, w = (lo <= g) & (g <= hi), np.clip(hi, 0, None) - np.clip(lo, 0, None)
        per = [cov[t == k].mean() for k in np.unique(t)]
        r = {'n': int(m.sum()), 'coverage': float(cov.mean()), 'coverage_tile_mean': float(np.mean(per)),
             'coverage_tile_ci95': list(E.bootstrap_ci(per)), 'width_mean': float(w.mean()), 'width_median': float(np.median(w)),
             'by': {name: {str(k): {'n': int((a == k).sum()), 'coverage': float(cov[a == k].mean()), 'width_mean': float(w[a == k].mean())}
                           for k in np.unique(a)} for name, arr in S['by'].items() for a in [arr[m]]}}
        out[str(lv)] = r
    return out


def cross_validate(S, variants, levels=LEVELS):
    """Leave-one-city-out: c and q from the two other cities, coverage on the held-out one."""
    res = {}
    for vname, (cs, signed, min_n, use_key) in variants.items():
        res[vname] = {}
        for city in ('DC', 'NYC', 'PHL'):
            cal, te = S['city'] != city, S['city'] == city
            c, sel = choose_c(S, cal, cs, signed, min_n, use_key)
            tab = fit(S['p'][cal], S['u'][cal], S['g'][cal], S['key'][cal] if use_key else None, c, sorted(set(levels) | set(RELIAB)), signed, min_n)
            r = report(S, te, tab, c, levels, use_key)
            rel = report({**S, 'by': {}}, te, tab, c, RELIAB, use_key)
            res[vname][city] = {'c': None if math.isinf(c) else c, 'c_selection': sel, 'calibration_n': int(cal.sum()),
                                'test': r, 'reliability': {lv: rel[str(lv)]['coverage'] for lv in RELIAB}}
        for lv in map(str, levels):
            cv = [res[vname][k]['test'][lv]['coverage'] for k in ('DC', 'NYC', 'PHL')]
            res[vname].setdefault('summary', {})[lv] = {'coverage_per_fold': cv, 'max_abs_gap_pp': float(100 * max(abs(x - float(lv)) for x in cv)),
                                                         'width_mean_per_fold': [res[vname][k]['test'][lv]['width_mean'] for k in ('DC', 'NYC', 'PHL')]}
    return res


def ship_table(S, cs, signed, min_n, levels=LEVELS):
    m = np.ones(len(S['p']), bool)
    c, sel = choose_c(S, m, cs, signed, min_n)
    tab = fit(S['p'], S['u'], S['g'], S['key'], c, levels, signed, min_n)
    return {'c': None if math.isinf(c) else c, 'c_selection': sel, 'signed': signed, 'min_group_n': min_n,
            'n': int(len(S['p'])), 'group_n': {str(k): int((S['key'] == k).sum()) for k in np.unique(S['key'])},
            'q': {str(lv): {k: [round(v[0], 4), round(v[1], 4)] for k, v in tab[lv].items()} for lv in levels}}


def plot(res_px, res_b, out):
    from PIL import Image, ImageDraw
    col = {'DC': (200, 120, 50), 'NYC': (70, 110, 190), 'PHL': (60, 140, 90)}
    S, L = 400, 50
    im = Image.new('RGB', (2 * (S + L + 20), S + L + 60), 'white')
    d = ImageDraw.Draw(im)
    for j, (title, r) in enumerate((('pixels (one per 16x16 block)', res_px), ('building blocks (app readout)', res_b))):
        x0 = j * (S + L + 20) + L
        X, Y = lambda v: x0 + v * S, lambda v: 30 + (1 - v) * S
        d.rectangle([X(0), Y(1), X(1), Y(0)], outline='black')
        for dv in (-0.03, 0.03):
            d.line([X(max(0, -dv)), Y(max(0, dv)), X(min(1, 1 - dv)), Y(min(1, 1 + dv))], fill=(200, 200, 200))
        d.line([X(0), Y(0), X(1), Y(1)], fill=(120, 120, 120))
        for v in (0, 0.25, 0.5, 0.75, 1):
            d.text((X(v) - 10, Y(0) + 4), f'{v:.2f}', fill='black')
            d.text((x0 - 34, Y(v) - 6), f'{v:.2f}', fill='black')
        for k, (city, cc) in enumerate(col.items()):
            pts = [(X(float(lv)), Y(cv)) for lv, cv in sorted(r[city]['reliability'].items(), key=lambda a: float(a[0]))]
            d.line(pts, fill=cc, width=2)
            for x, y in pts:
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=cc)
            d.text((X(0.04), Y(0.96) + 14 * k), f'held-out {city}', fill=cc)
        d.text((x0, 8), f'Reliability, {title}', fill='black')
        d.text((x0 + 80, Y(0) + 22), 'nominal level (grey band = +-3 pp)', fill='black')
    im.save(out)


def main():
    t0 = time.time()
    missing = [n for n in GV.names150() if not os.path.exists(os.path.join(CACHE, n + '.npz'))]
    assert not missing, f'{len(missing)} tiles lack the land-cover cache: run --predict first'
    T = load()
    S = pixel_samples(T)
    print(f'{len(S["p"]):,} pixel samples ({time.time() - t0:.0f} s)', flush=True)
    Bs = building_samples(T)
    print(f'{len(Bs["p"]):,} building blocks ({time.time() - t0:.0f} s)', flush=True)
    fin, inf = CS, (math.inf,)
    px = cross_validate(S, {'mondrian_normalised': (fin, False, MIN_GROUP, True), 'pooled_normalised': (fin, False, MIN_GROUP, False),
                            'mondrian_constant_width': (inf, False, MIN_GROUP, True)})
    bl = cross_validate(Bs, {'symmetric': (fin, False, MIN_GROUP_B, True), 'signed': (fin, True, MIN_GROUP_B, True),
                             'symmetric_constant_width': (inf, False, MIN_GROUP_B, True)})
    # diagnostic, not shippable by the rule below: normaliser = reported height + c instead of spread + c
    bl.update(cross_validate({**Bs, 'u': Bs['p'].astype(np.float64)}, {'symmetric_height_scaled (diagnostic)': (fin, False, MIN_GROUP_B, True)}))
    print(f'cross-validation done ({time.time() - t0:.0f} s)', flush=True)
    ok = lambda r: r['summary']['0.9']['max_abs_gap_pp'] <= 3
    bvar = 'signed' if ok(bl['signed']) and np.mean(bl['signed']['summary']['0.9']['width_mean_per_fold']) < \
        np.mean(bl['symmetric']['summary']['0.9']['width_mean_per_fold']) else 'symmetric'
    acc = {'block_median_vs_ref_p90': E.evaluate([(Bs['p'][Bs['tile'] == t] - Bs['g'][Bs['tile'] == t], Bs['g'][Bs['tile'] == t]) for t in np.unique(Bs['tile'])]),
           'block_p90_vs_ref_p90': E.evaluate([(Bs['p90'][Bs['tile'] == t] - Bs['g'][Bs['tile'] == t], Bs['g'][Bs['tile'] == t]) for t in np.unique(Bs['tile'])]),
           'spearman_block_spread_vs_abs_error': E.spearman(Bs['u'], np.abs(Bs['p'] - Bs['g']))}
    prov = {'data': 'GAMUS test split, 150 frozen tiles (demo/gamus_v2.py, data/GAMUS_bench.txt): Washington DC, New York, '
                    'Philadelphia; 0.33 m aerial orthophotos; LiDAR nDSM reference; 504x504 centre crop; 4-flip TTA fp16 MPS',
            'folds': 'leave-one-city-out (calibrate on two cities, test on the third); shipped table refitted on all three',
            'command': CMD, 'script': 'demo/uncertainty_calibration.py', 'report': 'demo/benchmark/v2/uncertainty_calibration.md',
            'date': time.strftime('%Y-%m-%d')}
    shipped = {
        'version': 1, 'label': '90% interval (calibrated on GAMUS, US cities)',
        'formula': 'interval = [h + q_lo * (spread + c), h + q_hi * (spread + c)], lower end clipped at 0; spread = 4-flip std '
                   '(m); c = null means constant width (spread + c -> 1); group = predicted height bin (buildings) or '
                   'predicted land-cover group | predicted height bin (pixels); unknown group -> "pooled"',
        'bins': E.BIN_LABELS, 'class_groups': {c: CLASS_GROUP.get(c, 'ground') for c in LC},
        'building': {**ship_table(Bs, fin, bvar == 'signed', MIN_GROUP_B), 'variant': bvar,
                     'reported_height': 'block median of the predicted height (app.extract_buildings height_m)',
                     'reference': '90th percentile of the LiDAR nDSM inside the block',
                     'held_out_coverage': bl[bvar]['summary']},
        'pixel': {**ship_table(S, fin, False, MIN_GROUP), 'variant': 'mondrian_normalised',
                  'held_out_coverage': px['mondrian_normalised']['summary'],
                  'note': 'not shown in the viewer: the per-pixel map stays the flip spread, labelled consistency score'},
        'provenance': prov}
    os.makedirs(os.path.dirname(SHIP), exist_ok=True)
    json.dump(shipped, open(SHIP, 'w'), indent=1)
    R = {'command': CMD, 'provenance': prov, 'pixel_samples': int(len(S['p'])), 'building_blocks': int(len(Bs['p'])),
         'building_blocks_per_city': {c: int((Bs['city'] == c).sum()) for c in ('DC', 'NYC', 'PHL')},
         'pixel': px, 'building': bl, 'building_variant_shipped': bvar, 'building_accuracy': acc, 'shipped': SHIP}
    india = india_check(shipped)
    if india:
        R['india'] = india
    json.dump(R, open(os.path.join(V2, 'uncertainty_calibration.json'), 'w'), indent=1)
    plot(px['mondrian_normalised'], bl[bvar], os.path.join(V2, 'uncertainty_reliability.png'))
    write_md(R)
    print(f'done ({time.time() - t0:.0f} s)')


def india_check(shipped):
    """Building-interval coverage in India, computed by demo/recalibration.py (step 6c: ICESat-2 roof photons inside OSM
    footprints, with this table); None until that has run."""
    f = os.path.join(V2, 'recal_gamus.json')
    I = json.load(open(f)).get('india') if os.path.exists(f) else None
    return None if not I or not I.get('interval_coverage') else {'source': 'demo/benchmark/v2/recal_gamus.json :: india',
                                                                 'buildings': I['n'], 'interval_coverage': I['interval_coverage']}


def findings(R):
    """Summary lines, every number read from R."""
    cv = lambda r, lv='0.9': ', '.join(f"{k} {100 * r[k]['test'][lv]['coverage']:.1f}%" for k in ('DC', 'NYC', 'PHL'))
    w = lambda r, lv='0.9': np.mean(r['summary'][lv]['width_mean_per_fold'])
    pm, pc, bs = R['pixel']['mondrian_normalised'], R['pixel']['mondrian_constant_width'], R['building'][R['building_variant_shipped']]
    out = ['## Findings', '',
           f"- **Target missed.** 90% intervals on the held-out city cover pixels {cv(pm)} (largest gap {pm['summary']['0.9']['max_abs_gap_pp']:.1f} pp) "
           f"and building blocks {cv(bs)} (largest gap {bs['summary']['0.9']['max_abs_gap_pp']:.1f} pp), not within ±3 pp. Coverage moves with the "
           "city: DC (leaf-off trees, taller buildings) is under-covered, PHL over-covered. The split-conformal guarantee needs exchangeable "
           "data (in theory: same city; not tested here); across cities it does not hold, so an interval calibrated on three US cities is "
           "only approximately 90% elsewhere.",
           "- **Tall blocks are badly under-covered** (90% block interval, held-out city, by LiDAR height bin: " + '; '.join(
               f"{k} " + ', '.join(f"{b} {100 * v['coverage']:.0f}% (n {v['n']})" for b, v in sorted(bs[k]['test']['0.9']['by']['reference height bin'].items(),
                                   key=lambda t: float(t[0].split('-')[0])) if isinstance(v, dict) and 'coverage' in v) for k in ('DC', 'NYC', 'PHL'))
           + "). The per-city figure is carried by 3-10 m blocks; blocks with LiDAR height above 10 m, the ones that matter for flood and "
           "evacuation use, are often taller than the whole interval. The viewer says so next to the interval. In practice the interval "
           "is close to a constant ±6 m, clipped at 0 m, so for low-rise blocks it says little (e.g. a 4.9 m block gets 0.0-11.5 m).",
           f"- **The flip spread adds nothing as a normaliser.** c is chosen at the top of the grid ({', '.join(str(pm[k]['c']) for k in ('DC', 'NYC', 'PHL'))} "
           f"for pixels), i.e. spread + c is almost constant, and constant-width Mondrian intervals have the same coverage and width "
           f"(mean 90% width {w(pc):.2f} m vs {w(pm):.2f} m). The width comes from the predicted class and height bin, not from the spread "
           f"(block spread vs |error| Spearman {R['building_accuracy']['spearman_block_spread_vs_abs_error']:.2f}).",
           f"- **Intervals are wide**: mean 90% width {w(pm):.1f} m per pixel and {w(bs):.1f} m per block, because tall objects are under-estimated "
           "and the groups cannot see which ones (coverage for blocks whose LiDAR height is above 20 m is far below 90%, section 2).",
           '- **Shipped anyway, labelled honestly**: the block interval is the best-calibrated statement available; the flip spread map is '
           "relabelled 'consistency score'.", '']
    if R.get('india'):
        v = R['india']['interval_coverage']['0.9']
        out[-1:-1] = [f"- **India (ICESat-2 roof photons in OSM footprints)**: the 90% block interval covers {100 * v['coverage']:.0f}% of {v['n']} "
                      "buildings: under-coverage, as expected under the domain shift."]
    return out


def write_md(R):
    f = lambda x, nd=2: '–' if x is None else f'{x:.{nd}f}'
    pct = lambda x: '–' if x is None else f'{100 * x:.1f}'
    L = ['# Calibrated uncertainty: split-conformal intervals on GAMUS (plan step 4)', '', 'Commands (from `SynRS3D/`):', '', '```',
         '/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/uncertainty_calibration.py --predict   # model, once',
         f'{CMD}          # this report + calibration/conformal.json, from the cache', f'{CMD} --selftest', '```', '',
         f"**Data.** {R['provenance']['data']}. Pixels: one random pixel per 16x16 block per tile ({R['pixel_samples']:,} samples, "
         "voids excluded). Buildings: the app's own blocks (`app.extract_buildings` on predicted height, spread and land cover; "
         f"{R['building_blocks']:,} blocks with >= 20 LiDAR px: " + ', '.join(f'{k} {v}' for k, v in R['building_blocks_per_city'].items()) + ').', '',
         '**Method.** Normalised split-conformal, score |ref - pred| / (spread + c), spread = 4-flip std. q = the '
         'ceil((n+1)(1-alpha))-th smallest calibration score. Leave-one-city-out: c and q from two cities, coverage on the '
         'third. c chosen on the calibration cities only (q on even tiles, smallest mean 90% width on odd tiles) from '
         f"{list(CS)}. Mondrian groups use only inference-time quantities: predicted land-cover group (buildings / trees / "
         f"water / other) x predicted height bin; groups with < {MIN_GROUP} (pixels) or < {MIN_GROUP_B} (blocks) calibration "
         "samples use the pooled q. Coverage = share of held-out samples inside the interval (pooled), with the per-tile mean "
         "[95% bootstrap CI over tiles] beside it. Width = mean interval width after clipping the lower end at 0 m.", '',
         *findings(R),
         '## 1. Pixels: held-out coverage (target: within ±3 pp of nominal)', '',
         '| Variant | Held-out city | c | ' + ' | '.join(f'{int(100 * l)}%: coverage (tile mean [CI]) | width (m)' for l in LEVELS) + ' |',
         '|---|---|---|' + '---|---|' * len(LEVELS)]
    for res, name in ((R['pixel'], 'pixel'),):
        for v, r in res.items():
            for city in ('DC', 'NYC', 'PHL'):
                t = r[city]['test']
                L.append(f"| {v} | {city} | {f(r[city]['c']) if r[city]['c'] is not None else 'const'} | " + ' | '.join(
                    f"{pct(t[str(l)]['coverage'])} ({pct(t[str(l)]['coverage_tile_mean'])} [{pct(t[str(l)]['coverage_tile_ci95'][0])}, {pct(t[str(l)]['coverage_tile_ci95'][1])}]) | {f(t[str(l)]['width_mean'])}"
                    for l in LEVELS) + ' |')
    pm = R['pixel']['mondrian_normalised']
    L += ['', 'Largest gap to nominal over the three held-out cities (pp), Mondrian normalised: ' +
          ', '.join(f"{int(100 * float(l))}% {pm['summary'][l]['max_abs_gap_pp']:.1f}" for l in pm['summary']), '']
    for title, key in (('predicted class', 'predicted class'), ('predicted height bin', 'predicted height bin'),
                       ('reference height bin (not available at inference: diagnostic)', 'reference height bin'),
                       ('reference class (GAMUS LiDAR classes: diagnostic)', 'reference class (GAMUS, diagnostic)')):
        groups = sorted({g for c in ('DC', 'NYC', 'PHL') for g in pm[c]['test']['0.9']['by'][key]})
        L += [f'### 90% interval by {title}, Mondrian normalised', '', '| Group | ' + ' | '.join(f'{c}: n, coverage, width' for c in ('DC', 'NYC', 'PHL')) + ' |', '|---|---|---|---|']
        for g in groups:
            cells = []
            for c in ('DC', 'NYC', 'PHL'):
                e = pm[c]['test']['0.9']['by'][key].get(g)
                cells.append('–' if not e else f"{e['n']:,}, {pct(e['coverage'])}%, {f(e['width_mean'])} m")
            L.append(f'| {g} | ' + ' | '.join(cells) + ' |')
        L.append('')
    L += ['## 2. Building blocks: held-out coverage', '',
          'Reported height = block median of the prediction (the value the viewer shows); reference = 90th percentile of '
          'the LiDAR nDSM inside the block. `signed` uses separate lower / upper quantiles (alpha/2 each) of the signed '
          'normalised residual, so it can follow the known under-estimation.', '',
          '| Variant | Held-out city | Blocks | c | ' + ' | '.join(f'{int(100 * l)}%: coverage (tile mean [CI]) | width (m)' for l in LEVELS) + ' |',
          '|---|---|---|---|' + '---|---|' * len(LEVELS)]
    for v, r in R['building'].items():
        for city in ('DC', 'NYC', 'PHL'):
            t = r[city]['test']
            L.append(f"| {v} | {city} | {t['0.9']['n']} | {f(r[city]['c']) if r[city]['c'] is not None else 'const'} | " + ' | '.join(
                f"{pct(t[str(l)]['coverage'])} ({pct(t[str(l)]['coverage_tile_mean'])} [{pct(t[str(l)]['coverage_tile_ci95'][0])}, {pct(t[str(l)]['coverage_tile_ci95'][1])}]) | {f(t[str(l)]['width_mean'])}"
                for l in LEVELS) + ' |')
    bv = R['building'][R['building_variant_shipped']]
    L += ['', f"Shipped building variant: **{R['building_variant_shipped']}** (rule: `signed` only if its 90% coverage is within ±3 pp in "
          "all three held-out cities and its mean width is smaller than `symmetric`). Largest gap (pp): " +
          ', '.join(f"{int(100 * float(l))}% {bv['summary'][l]['max_abs_gap_pp']:.1f}" for l in bv['summary']), '']
    for key in ('predicted height bin', 'reference height bin'):
        groups = sorted({g for c in ('DC', 'NYC', 'PHL') for g in bv[c]['test']['0.9']['by'][key]})
        L += [f'### Blocks, 90% interval by {key}', '', '| Group | ' + ' | '.join(f'{c}: n, coverage, width' for c in ('DC', 'NYC', 'PHL')) + ' |', '|---|---|---|---|']
        for g in groups:
            L.append(f'| {g} | ' + ' | '.join('–' if not (e := bv[c]['test']['0.9']['by'][key].get(g)) else f"{e['n']}, {pct(e['coverage'])}%, {f(e['width_mean'])} m" for c in ('DC', 'NYC', 'PHL')) + ' |')
        L.append('')
    a = R['building_accuracy']
    L += ['Block height accuracy against the reference (all 150 tiles, mean over tiles [CI] (pooled)): block median MAE '
          f"{E.cell(a['block_median_vs_ref_p90'], 'mae')} m, bias {E.cell(a['block_median_vs_ref_p90'], 'bias')} m; block 90th pct "
          f"MAE {E.cell(a['block_p90_vs_ref_p90'], 'mae')} m, bias {E.cell(a['block_p90_vs_ref_p90'], 'bias')} m. Spearman block "
          f"spread vs |error|: {f(a['spearman_block_spread_vs_abs_error'])}.", '',
          '## 3. Reliability plot', '', '![reliability](uncertainty_reliability.png)', '',
          'Empirical vs nominal coverage on each held-out city (pixels: Mondrian normalised; blocks: shipped variant).', '',
          '## 4. Shipped', '', f"`SynRS3D/calibration/conformal.json`: c, [q_lo, q_hi] per group and level for blocks and pixels, refitted on all "
          "150 tiles, with the held-out coverage above as provenance. The viewer shows the block's 90% interval labelled "
          "'90% interval (calibrated on GAMUS, US cities)'. The per-pixel map stays the flip spread, relabelled 'consistency "
          "score'; the per-pixel table is shipped for reference only.", '',
          '## 5. Limits', '',
          '- Calibrated on US aerial orthophotos at 0.33 m (DC, NYC, PHL). Coverage elsewhere (Indian 0.5 m satellite '
          'imagery, other building stock) is not guaranteed: conformal coverage holds only for data exchangeable with the '
          'calibration set, and the city-to-city gaps above show how far it moves under a modest shift.',
          '- GAMUS DC and NYC imagery is mostly leaf-off (gamus_v2.md), so tree intervals reflect leaf-off conditions.',
          '- India (building blocks only; from demo/recalibration.py, ICESat-2 roof photons inside OSM footprints, footprint median '
          'and median spread as block values; reference = median roof photon minus ground, not the LiDAR 90th percentile inside an app block used on GAMUS, so the two coverages are not strictly comparable): ' + ('; '.join(f"{int(100 * float(lv))}% interval covers {100 * v['coverage']:.0f}% of "
          f"{v['n']} buildings (mean over {v['scene_mean']['scenes']} scenes {100 * v['scene_mean']['mean']:.0f}%)" for lv, v in R['india']['interval_coverage'].items())
          + '. Under-coverage: the GAMUS calibration does not transfer to Indian 0.5 m imagery without loss.'
          if R.get('india') else 'not yet available (run demo/recalibration.py, then this script again).'),
          '- Per-pixel intervals are not tested in India: the Indian laser references (ICESat-2 segments, GEDI rh98) are '
          'footprint-scale top heights, not pixel heights.']
    open(os.path.join(V2, 'uncertainty_calibration.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L[:40]))


def selftest():
    rng = np.random.default_rng(0)
    # exchangeable heteroscedastic data: error ~ N(0, (u + 0.5)^2); coverage of the normalised interval ~ nominal
    n = 20000
    u = rng.gamma(2, 0.5, n)
    p = rng.uniform(0, 20, n)
    g = p + rng.normal(0, u + 0.5)
    key = bin_label(p)
    cal, te = np.arange(n) < n // 2, np.arange(n) >= n // 2
    for signed in (False, True):
        tab = fit(p[cal], u[cal], g[cal], key[cal], 0.5, LEVELS, signed)
        for lv in LEVELS:
            lo, hi = interval(tab, lv, p[te], u[te], key[te], 0.5)
            cov = ((lo <= g[te]) & (g[te] <= hi)).mean()
            assert abs(cov - lv) < 0.02, (signed, lv, cov)
    # finite-sample rule: n = 9 scores 1..9, level 0.9 -> k = ceil(10 * 0.9) = 9 -> q = 9; level 0.95 -> k = 10 > n -> inf
    t = np.arange(1, 10.0)
    assert qpair(t, 0.9) == (-9, 9) and qpair(t, 0.95)[1] == math.inf and qpair(t, 0.5) == (-5, 5)
    assert qpair(np.arange(-49, 50.0), 0.9, True) == (-45, 45)   # n = 99: floor(100*.05)=5th, ceil(100*.95)=95th
    # normalisation narrows intervals where spread is informative; constant width (c = inf) is the fallback
    w_norm = np.mean(np.diff(np.c_[interval(fit(p, u, g, None, 0.5), 0.9, p, u, None, 0.5)], axis=1))
    w_const = np.mean(np.diff(np.c_[interval(fit(p, u, g, None, math.inf), 0.9, p, u, None, math.inf)], axis=1))
    assert w_norm < w_const
    # small groups fall back to pooled
    tab = fit(p[:300], u[:300], g[:300], np.r_[np.full(250, 'a'), np.full(50, 'b')], 0.5, (0.9,))
    assert 'a' in tab[0.9] and 'b' not in tab[0.9]
    idx = block_sample((504, 504), 0)
    assert len(idx) == 32 * 32 and len(np.unique(idx // 504 // 16 * 32 + idx % 504 // 16)) == 32 * 32 and idx.max() < 504 * 504
    assert list(bin_label(np.array([0, 2.9, 3, 10, 25.0]))) == ['0-3 m', '0-3 m', '3-10 m', '10-20 m', '20-inf m']
    print('uncertainty_calibration selftest OK')


if __name__ == '__main__':
    {'--predict': predict, '--selftest': selftest}.get(sys.argv[1] if len(sys.argv) > 1 else '', main)()
