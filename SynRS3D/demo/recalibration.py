"""Tall-object recalibration (plan step 6b): class-wise isotonic regression predicted -> reference height, separately for
PREDICTED building and PREDICTED tree pixels (ground untouched), leave-one-city-out on GAMUS.

usage: .venv/bin/python demo/recalibration.py              (needs the land-cover cache of demo/uncertainty_calibration.py --predict)
       .venv/bin/python demo/recalibration.py --selftest
Data: the 150 frozen GAMUS tiles (demo/gamus_v2.py), 504x504 centre crop, 4-flip TTA, predicted land cover from the same
batch (demo/benchmark/v2/cache/gamus_lc). Fit: every finite pixel of the predicted class in the two training cities,
binned at 0.1 m of predicted height; scipy.optimize.isotonic_regression (L2, increasing) on the bin means weighted by
pixel counts ('isotonic_mean', primary). Secondary, reported only: the same on bin medians ('isotonic_median').
The curve is applied with infer_height.correct_heights (method 'curve': linear between knots, beyond the last knot the
last ratio). Scored on the held-out city with demo/eval_v2.py (mean over tiles [95% CI] (pooled)).
Ship rule (fixed before running): held-out per-tile mean MAE lower AND |per-tile mean bias| lower in the 10-20 m and
>20 m reference bins, in all three folds, for the primary variant. Only then calibration/recal.json is written.
Earlier negative result: demo/benchmark/correction.md (DFC19 curve/linear corrections, none shipped; DFC19 is inside
RS3DAda's adaptation domain, so that test was not zero-shot).
"""
import json, os, sys, time

import numpy as np
from scipy.optimize import isotonic_regression

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark as B
import gamus_v2 as GV
import eval_v2 as E
import infer_height
import uncertainty_calibration as U

V2 = os.path.join(B.OUT, 'v2')
SHIP = os.path.join(B.ROOT, 'calibration', 'recal.json')
STEP = 0.1
GROUPS = infer_height.CORRECTION_GROUPS          # {1: buildings, 2: trees}; 0 = everything else, untouched
CMD = '.venv/bin/python demo/recalibration.py'


def fit_curve(p, g, stat='mean', step=STEP):
    """Isotonic curve of reference on prediction: knots (x, y) for np.interp."""
    b = np.floor(p / step).astype(np.int64)
    order = np.argsort(b, kind='stable')
    b, p, g = b[order], p[order], g[order]
    starts = np.r_[0, np.flatnonzero(np.diff(b)) + 1]
    cnt = np.diff(np.r_[starts, len(b)])
    x = np.add.reduceat(p, starts) / cnt
    y = np.add.reduceat(g, starts) / cnt if stat == 'mean' else np.array([np.median(g[s:s + c]) for s, c in zip(starts, cnt)])
    fy = isotonic_regression(y, weights=cnt.astype(np.float64), increasing=True).x
    keep = np.r_[True, np.diff(fy) != 0] | np.r_[np.diff(fy) != 0, True]   # ends of each flat block
    return x[keep], fy[keep], int(cnt.sum())


def corr_dict(curves):
    return {'method': 'curve', 'by_landcover': True,
            'params': {str(k): {'x': [round(float(v), 4) for v in x], 'y': [round(float(v), 4) for v in y]} for k, (x, y, _) in curves.items()}}


def fit_all(T, names, stat, groups=GROUPS):
    out = {}
    for k, cls in groups.items():
        p = np.concatenate([T[n]['p'][(T[n]['lc'] == cls) & np.isfinite(T[n]['g'])] for n in names])
        g = np.concatenate([T[n]['g'][(T[n]['lc'] == cls) & np.isfinite(T[n]['g'])] for n in names])
        out[k] = fit_curve(p, g, stat)
    return out


def score(P, T, sel):
    """eval_v2 metrics on tiles sel for predictions P[n]."""
    ev = lambda m: E.evaluate([((P[n] - T[n]['g'])[m(n)], T[n]['g'][m(n)]) for n in sel], min_n=GV.MIN_PX)
    hi = lambda union: E.aggregate([E.high_metrics(P[n], T[n]['g'], union=union) for n in sel],
                                   E.high_metrics(np.concatenate([P[n].ravel() for n in sel]), np.concatenate([T[n]['g'].ravel() for n in sel]), union=union))
    bl = {n: E.building_level(P[n], T[n]['g'], T[n]['c'] == 3) for n in sel}
    r = {'whole': E.evaluate([(P[n] - T[n]['g'], T[n]['g']) for n in sel]), 'high_ref3': hi(False), 'high_official_union': hi(True),
         'bins': {lbl: ev(lambda n, lo=lo, h=h: (T[n]['g'] >= lo) & (T[n]['g'] < h)) for lbl, (lo, h) in zip(E.BIN_LABELS, E.BINS)},
         'pred_class': {nm: ev(lambda n, c=c: (T[n]['lc'] == c) & np.isfinite(T[n]['g'])) for nm, c in (('buildings', 7), ('trees', 4))},
         'buildings_p90': E.aggregate([E.metrics(bl[n][0] - bl[n][1], bl[n][1]) if len(bl[n][1]) else None for n in sel],
                                      E.metrics(np.concatenate([bl[n][0] - bl[n][1] for n in sel]), np.concatenate([bl[n][1] for n in sel])))}
    return r


def passes(raw, new):
    mae = new['whole']['mae']['mean'] < raw['whole']['mae']['mean']
    b = {lbl: abs(new['bins'][lbl]['bias']['mean']) < abs(raw['bins'][lbl]['bias']['mean']) for lbl in ('10-20 m', '20-inf m')}
    return {'mae_lower': bool(mae), 'abs_bias_lower': b, 'pass': bool(mae and all(b.values()))}


def main():
    t0 = time.time()
    names = GV.names150()
    T = {}
    for n in names:
        c = np.load(os.path.join(U.CACHE, n + '.npz'))
        T[n] = {'p': np.clip(c['tta'].astype(np.float32), 0, None), 'lc': c['lc'],
                'g': GV.clean(GV.read('heights', n).astype(np.float32)), 'c': GV.read('classes', n).astype(np.uint8)}
    city = lambda n: n.split('_')[0]
    R = {'command': CMD, 'protocol': 'Data: ' + __doc__.split('Data:')[1].split('Earlier')[0].strip(), 'folds': {}}
    for held in ('DC', 'NYC', 'PHL'):
        train, test = [n for n in names if city(n) != held], [n for n in names if city(n) == held]
        f = {'train': sorted({city(n) for n in train}), 'raw': score({n: T[n]['p'] for n in test}, T, test)}
        for v, (stat, groups) in VARIANTS.items():
            curves = fit_all(T, train, stat, groups)
            corr = corr_dict(curves)
            P = {n: infer_height.correct_heights(T[n]['p'], T[n]['lc'], corr) for n in test}
            f[v] = {'score': score(P, T, test), 'fit_px': {str(k): c[2] for k, c in curves.items()},
                    'curve': {GROUPS_NAME[k]: {'x': corr['params'][str(k)]['x'], 'y': corr['params'][str(k)]['y']} for k in curves}}
            f[v]['rule'] = passes(f['raw'], f[v]['score'])
        R['folds'][held] = f
        print(f'fold {held} done ({time.time() - t0:.0f} s)', flush=True)
    R['ship'] = all(R['folds'][c]['isotonic_mean']['rule']['pass'] for c in R['folds'])
    R['secondary_would_pass'] = all(R['folds'][c]['isotonic_median']['rule']['pass'] for c in R['folds'])
    R['posthoc_buildings_only_would_pass'] = all(R['folds'][c][POSTHOC]['rule']['pass'] for c in R['folds'])
    curves = fit_all(T, names, 'mean')
    R['curve_all_cities'] = {GROUPS_NAME[k]: {'x': v['x'], 'y': v['y']} for k, v in corr_dict(curves)['params'].items() for k in [int(k)]}
    if R['ship']:
        out = {**corr_dict(curves), 'source': 'GAMUS DC+NYC+PHL LiDAR, isotonic per predicted class (demo/recalibration.py)',
               'provenance': {'command': CMD, 'report': 'demo/benchmark/v2/recal_gamus.md', 'date': time.strftime('%Y-%m-%d'),
                              'held_out': {c: R['folds'][c]['isotonic_mean']['rule'] for c in R['folds']}}}
        os.makedirs(os.path.dirname(SHIP), exist_ok=True)
        json.dump(out, open(SHIP, 'w'), indent=1)
        R['shipped'] = SHIP
    if '--no-india' not in sys.argv:
        R['india'] = india(corr_dict(curves), R['ship'])
    json.dump(R, open(os.path.join(V2, 'recal_gamus.json'), 'w'), indent=1)
    write_md(R)


GROUPS_NAME = {1: 'buildings', 2: 'trees'}
POSTHOC = 'isotonic_mean_buildings_only (post hoc)'   # added after the first run showed the tree curve learns leaf-off
VARIANTS = {'isotonic_mean': ('mean', GROUPS), 'isotonic_median': ('median', GROUPS), POSTHOC: ('mean', {1: GROUPS[1]})}
# India transfer check (plan step 6c): app scenes in demo/results with an ICESat-2 photon cache (guwahati has 0 photons)
INDIA = ['bengaluru_electronic_city', 'chandigarh_sector17', 'delhi_central', 'iit_ropar', 'mumbai_highrise', 'shimla_hill_town']
OSM = os.path.join(V2, 'cache', 'osm')
MIN_ROOF_PH, GROUND_R = 3, 75.0     # roof photons per building; search radius (m) for ground photons around it


def overpass(bounds, out_f):
    """OSM building footprints inside lon/lat bounds (same query as demo/india_eval_v2.osm_buildings), cached."""
    import urllib.parse, urllib.request
    if not os.path.exists(out_f) or not os.path.getsize(out_f):
        w, s, e, n = bounds
        q = f'[out:json][timeout:90];(way["building"]({s},{w},{n},{e});relation["building"]({s},{w},{n},{e}););out geom;'
        for k, url in enumerate(('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter')):
            req = urllib.request.Request(url, urllib.parse.urlencode({'data': q}).encode(), {'User-Agent': 'DepthWizard-eval/2 (SIH26175 research)'})
            try:
                body = urllib.request.urlopen(req, timeout=180).read()   # fetch first: a failed request leaves no empty cache
                break
            except OSError:
                if k:
                    raise
        os.makedirs(os.path.dirname(out_f), exist_ok=True)
        open(out_f, 'wb').write(body)
    els = json.load(open(out_f)).get('elements', [])
    rings = [e['geometry'] for e in els if e['type'] == 'way' and 'geometry' in e]
    return rings + [m['geometry'] for e in els if e['type'] == 'relation' for m in e.get('members', []) if m.get('role') == 'outer' and 'geometry' in m]


def india_scene(name, curve, table, v2=False):
    """Per OSM building with >= MIN_ROOF_PH ICESat-2 photons inside: roof = median photon height inside the footprint,
    ground = median ATL08 ground photon outside every footprint within GROUND_R m, carried to the building along our
    DTM's slope (fallback: our DTM + geoid undulation), ours = median predicted nDSM at the roof photon pixels (raw and
    with the GAMUS curve), plus the calibrated building interval (calibration/conformal.json) for the footprint median.
    v2: a scene of demo/india_eval_v2.py (demo/benchmark/v2/scenes, read only) instead of an app scene in demo/results."""
    import rasterio
    from rasterio import features
    from rasterio.warp import transform as wt, transform_bounds
    base = os.path.join(V2, 'scenes', name) if v2 else os.path.join(B.ROOT, 'demo', 'results', name)
    img = base + '.tif' if v2 else os.path.join(B.ROOT, 'demo', 'samples', name + '.tif')
    res = lambda s: base + s
    with rasterio.open(img) as src:
        crs, tr, shape = src.crs, src.transform, (src.height, src.width)
        bounds = transform_bounds(crs, 'EPSG:4326', *src.bounds)
    ph = np.load(res('_atl03.npz') if v2 else os.path.join(B.OUT, 'icesat2', '{:.5f}_{:.5f}_{:.5f}_{:.5f}.npz'.format(*bounds)))
    if v2 and not os.path.exists(res('_osm.json')):
        raise FileNotFoundError('no OSM cache from india_eval_v2')
    rings = [r for r in overpass(bounds, res('_osm.json') if v2 else os.path.join(OSM, name + '.json')) if len(r) >= 3]
    shapes = []
    for i, ring in enumerate(rings, 1):
        xs, ys = wt('EPSG:4326', crs, [p['lon'] for p in ring], [p['lat'] for p in ring])
        shapes.append(({'type': 'Polygon', 'coordinates': [list(zip(xs, ys)) + [(xs[0], ys[0])]]}, i))
    bid = features.rasterize(shapes, shape, transform=tr, fill=0, dtype='int32') if shapes else np.zeros(shape, np.int32)
    h = rasterio.open(res('_height.tif')).read(1)
    lc = rasterio.open(res('_landcover.tif')).read(1).astype(np.uint8)
    dtm = rasterio.open(res('_dtm.tif')).read(1) if os.path.exists(res('_dtm.tif')) else None
    hc = infer_height.correct_heights(h, lc, curve)
    u = rasterio.open(res('_uncertainty.tif')).read(1) if os.path.exists(res('_uncertainty.tif')) else None
    N = json.load(open(res('.json'))).get('terrain', {}).get('geoid_undulation_m')
    xs, ys = wt('EPSG:4326', crs, ph['lon'].tolist(), ph['lat'].tolist())
    r, c = (np.asarray(v) for v in rasterio.transform.rowcol(tr, xs, ys))
    ins = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
    r, c = np.clip(r, 0, shape[0] - 1), np.clip(c, 0, shape[1] - 1)
    b = np.where(ins, bid[r, c], 0)
    X, Y = np.asarray(xs), np.asarray(ys)
    mpu = 111320 * np.cos(np.radians(np.mean(bounds[1::2]))) if crs.is_geographic else (np.cos(np.radians(np.mean(bounds[1::2]))) if crs.to_epsg() == 3857 else 1.0)
    gnd = ins & (b == 0) & (ph['cls'] == 1)
    rows = []
    for k in np.unique(b[b > 0]):
        m = b == k
        if m.sum() < MIN_ROOF_PH:
            continue
        d = np.hypot(X[gnd] - X[m].mean(), Y[gnd] - Y[m].mean()) * mpu
        near = d <= GROUND_R
        src = 'photons'
        if near.sum() >= 3 and dtm is not None and N is not None:   # photon ground level, carried to the building along our DTM's slope
            gi = np.flatnonzero(gnd)[near]
            ground = float(np.median(dtm[bid == k]) + N + np.median(ph['h'][gi] - (dtm[r[gi], c[gi]] + N)))
            src = 'photons + DTM slope'
        elif near.sum() >= 3:
            ground = float(np.median(ph['h'][gnd][near]))
        elif dtm is not None and N is not None:
            ground, src = float(np.median(dtm[bid == k])) + N, 'dtm'
        else:
            continue
        ref = float(np.median(ph['h'][m])) - ground
        rows.append({'scene': name, 'osm_index': int(k), 'roof_photons': int(m.sum()), 'ground_from': src,
                     'ground_photons': int(near.sum()), 'passes': int(len(np.unique(ph['track'][m]))),
                     'ref_m': ref, 'ours_raw_m': float(np.median(h[r[m], c[m]])), 'ours_curve_m': float(np.median(hc[r[m], c[m]])),
                     'ours_raw_footprint_median_m': float(np.median(h[bid == k])),
                     'pred_building_share': float((lc[bid == k] == infer_height.LANDCOVER.index('buildings')).mean())})
        if u is not None and table:
            hf, uf = float(np.median(h[bid == k])), float(np.median(u[bid == k]))
            iv = {lv: infer_height.building_interval(hf, uf, table, lv) for lv in table['building']['q']}
            rows[-1].update(unc_footprint_m=uf, interval={lv: list(v) for lv, v in iv.items()},
                            covered={lv: bool(v[0] <= ref <= v[1]) for lv, v in iv.items()})
    return rows, {'osm_buildings': len(shapes), 'photons': int(ins.sum()), 'ground_photons_outside_osm': int(gnd.sum()),
                  'roof_photons_in_osm': int((b > 0).sum())}


def india(curve, shipped):
    import glob
    rows, scenes = [], {}
    table = infer_height.load_conformal()
    v2 = sorted({os.path.basename(f)[:-len('_height.tif')] for f in glob.glob(os.path.join(V2, 'scenes', '*_height.tif'))} - set(INDIA))
    for n, is_v2 in [(n, False) for n in INDIA] + [(n, True) for n in v2]:
        try:
            rr, info = india_scene(n, curve, table, is_v2)
        except Exception as e:      # Overpass down, missing cache
            scenes[n] = {'error': f'{type(e).__name__}: {e}'}
            continue
        rows += rr
        scenes[n] = {**info, 'buildings_with_photons': len(rr), 'source': 'demo/benchmark/v2/scenes (india_eval_v2)' if is_v2 else 'demo/results (app)'}
    out = {'scenes': scenes, 'buildings': rows, 'n': len(rows), 'curve_shipped': shipped,
           'curve_source': 'calibration/recal.json' if shipped else 'GAMUS isotonic_mean fitted on all three cities (NOT shipped; diagnostic)'}
    if rows:
        ref = np.array([x['ref_m'] for x in rows])
        by = lambda key: [(np.array([x[key] for x in rows if x['scene'] == s]) - np.array([x['ref_m'] for x in rows if x['scene'] == s]),
                           np.array([x['ref_m'] for x in rows if x['scene'] == s])) for s in scenes if any(x['scene'] == s for x in rows)]
        out['raw'] = E.evaluate(by('ours_raw_m'))
        out['curve'] = E.evaluate(by('ours_curve_m'))
        out['raw_footprint_median'] = E.evaluate(by('ours_raw_footprint_median_m'))
        out['ref_bins_pooled'] = {k: {'raw': E.binned_bias(np.array([x['ours_raw_m'] for x in rows]), ref, [b])[k],
                                      'curve': E.binned_bias(np.array([x['ours_curve_m'] for x in rows]), ref, [b])[k]}
                                  for k, b in zip(E.BIN_LABELS, E.BINS)}
        iv = [x for x in rows if 'covered' in x]
        out['interval_coverage'] = {lv: {
            'n': len(iv), 'coverage': float(np.mean([x['covered'][lv] for x in iv])),
            'scene_mean': (lambda v: {'mean': float(np.mean(v)), 'ci95': list(E.bootstrap_ci(v)), 'scenes': len(v)})(
                [np.mean([x['covered'][lv] for x in iv if x['scene'] == s]) for s in scenes if any(x['scene'] == s for x in iv)]),
            'width_mean': float(np.mean([x['interval'][lv][1] - x['interval'][lv][0] for x in iv]))} for lv in (iv[0]['covered'] if iv else [])}
    out['verdict'] = 'inconclusive (< 30 buildings with photons)' if len(rows) < 30 else '>= 30 buildings (the step-6c threshold), but few scenes: see CIs'
    return out


def findings(R):
    f, m = R['folds'], lambda v, h, k='whole', q='mae': f[h][v]['score'][k][q]['mean'] if v != 'raw' else f[h]['raw'][k][q]['mean']
    tr = lambda h: np.interp(1.0, f[h]['isotonic_mean']['curve']['trees']['x'], f[h]['isotonic_mean']['curve']['trees']['y'])
    bc = lambda h: np.interp(20.0, f[h]['isotonic_mean']['curve']['buildings']['x'], f[h]['isotonic_mean']['curve']['buildings']['y'])
    return ['## Findings', '',
            '- Held-out MAE raw -> isotonic_mean: ' + ', '.join(f"{h} {m('raw', h):.2f} -> {m('isotonic_mean', h):.2f}" for h in f)
            + '. It helps on DC and NYC and hurts PHL, so the rule fails.',
            f"- Most of the DC / NYC gain comes from trees: fitted on the leaf-off cities, the tree curve maps a 1 m tree prediction to "
            f"{tr('PHL'):.1f} m (fit on DC + NYC); on leaf-on PHL that raises predicted-tree MAE {f['PHL']['raw']['pred_class']['trees']['mae']['mean']:.2f} -> "
            f"{f['PHL']['isotonic_mean']['score']['pred_class']['trees']['mae']['mean']:.2f} m. The curve learns the leaf-off failure, not the model.",
            f"- The building curve is close to the identity (20 m predicted -> {', '.join(f'{bc(h):.1f}' for h in f)} m): E[reference | prediction] is "
            "already about right for predicted buildings, so recalibrating predicted heights cannot remove the bias seen per REFERENCE height bin "
            "(regression dilution: the tallest buildings are predicted lower than their true height, and the curve only sees the prediction).",
            '- The post-hoc buildings-only variant therefore changes little and also fails. Nothing is shipped.', '']


def write_md(R):
    c = E.cell
    L = ['# Class-wise isotonic recalibration on GAMUS, leave-one-city-out (plan step 6b)', '', 'Command (from `SynRS3D/`):', '', '```',
         f'{CMD}        # needs demo/uncertainty_calibration.py --predict (land-cover cache)', f'{CMD} --selftest', '```', '',
         R['protocol'], '', f"**Ship rule** (fixed before running): held-out per-tile mean MAE lower AND |bias| lower in the 10-20 m "
         f"and >20 m reference bins, in all three folds, primary variant (isotonic_mean). **Result: {'SHIPPED' if R['ship'] else 'NOT shipped'}**"
         + ('' if R['ship'] else f" (secondary isotonic_median would {'pass' if R['secondary_would_pass'] else 'also fail'}; post-hoc "
                                f"buildings-only variant would {'pass' if R['posthoc_buildings_only_would_pass'] else 'also fail'})") + '.', '',
         'Cells: mean over held-out tiles [95% bootstrap CI] (pooled).', '', *findings(R)]
    for held, f in R['folds'].items():
        L += [f"## Held-out {held} (fitted on {' + '.join(f['train'])})", '',
              '| Variant | MAE | RMSE | Bias | High MAE (ref > 3 m) | High MAE (official union) | Building p90 MAE | Pred. building px MAE | Pred. tree px MAE | Rule |',
              '|---|---|---|---|---|---|---|---|---|---|']
        for v in ('raw', *VARIANTS):
            s = f[v] if v == 'raw' else f[v]['score']
            rule = '' if v == 'raw' else ('pass' if f[v]['rule']['pass'] else 'fail: ' + ', '.join(
                [k for k, ok in [('MAE', f[v]['rule']['mae_lower'])] + list(f[v]['rule']['abs_bias_lower'].items()) if not ok]))
            L.append(f"| {v} | {c(s['whole'], 'mae')} | {c(s['whole'], 'rmse')} | {c(s['whole'], 'bias')} | {c(s['high_ref3'], 'mae')} | "
                     f"{c(s['high_official_union'], 'mae')} | {c(s['buildings_p90'], 'mae')} | {c(s['pred_class']['buildings'], 'mae')} | "
                     f"{c(s['pred_class']['trees'], 'mae')} | {rule} |")
        L += ['', 'Bias by reference height bin (tiles with >= 500 px in the bin):', '', '| Variant | ' + ' | '.join(E.BIN_LABELS) + ' |', '|---|---|---|---|---|']
        for v in ('raw', *VARIANTS):
            s = f[v] if v == 'raw' else f[v]['score']
            L.append(f'| {v} | ' + ' | '.join(c(s['bins'][b], 'bias') for b in E.BIN_LABELS) + ' |')
        L.append('')
        for g, cv in f['isotonic_mean']['curve'].items():
            x, y = np.array(cv['x']), np.array(cv['y'])
            L.append(f"Primary curve, predicted {g}: " + ', '.join(f"{q:g} m -> {np.interp(q, x, y):.1f}" for q in (1, 3, 5, 10, 15, 20, 30) if q <= x[-1]) + '.')
        L.append('')
    if R.get('india'):
        I = R['india']
        L += ['## India transfer check (plan step 6c): ICESat-2 photons inside OSM building footprints', '',
              f"App scenes in `demo/results` with an ICESat-2 photon cache ({', '.join(INDIA)}) plus the india_eval_v2 scenes with predictions "
              f"(demo/benchmark/v2/scenes, read only). Per OSM building with >= {MIN_ROOF_PH} "
              f"photons inside: reference = median photon height inside - ground, ground = median ATL08 ground photon outside all footprints within "
              f"{GROUND_R:g} m carried to the building along our DTM's slope (fallback: our DTM + geoid undulation); ours = median predicted nDSM at those photon pixels. "
              f"Curve: {I['curve_source']}. Units = scenes. **{I['n']} buildings: {I['verdict']}.**", '',
              '| Scene | OSM buildings | Photons in scene | Roof photons in OSM | Ground photons outside OSM | Buildings with photons |', '|---|---|---|---|---|---|']
        for s, v in I['scenes'].items():
            L.append(f"| {s} | " + (' | '.join(str(v.get(k, '–')) for k in ('osm_buildings', 'photons', 'roof_photons_in_osm', 'ground_photons_outside_osm', 'buildings_with_photons'))
                                   if 'error' not in v else f"error: {v['error']} | | | | ") + ' |')
        if I.get('raw'):
            L += ['', '| Model height | MAE | Bias | NMAD | r |', '|---|---|---|---|---|']
            for k, lbl in (('raw', 'raw, at roof photons'), ('curve', 'GAMUS curve, at roof photons'), ('raw_footprint_median', 'raw, footprint median')):
                L.append(f"| {lbl} | {c(I[k], 'mae')} | {c(I[k], 'bias')} | {c(I[k], 'nmad')} | {c(I[k], 'r')} |")
            if I.get('interval_coverage'):
                L += ['', 'Calibrated building interval (calibration/conformal.json, footprint median and median spread as the block values) '
                      'against the photon roof height: ' + '; '.join(f"{int(100 * float(lv))}%: coverage {100 * v['coverage']:.0f}% of {v['n']} "
                      f"buildings (scene mean {100 * v['scene_mean']['mean']:.0f}%, mean width {v['width_mean']:.1f} m)" for lv, v in I['interval_coverage'].items()) + '. '
                      'Caveat: this uses OSM footprints and the median roof photon, while the GAMUS calibration used the app\'s blocks and the '
                      'LiDAR 90th percentile inside each block, so the reference definitions differ.']
            L += ['', 'Pooled bias by reference (photon) height: ' + '; '.join(
                f"{k}: n {v['raw']['n']}, raw {v['raw']['bias']:+.2f}, curve {v['curve']['bias']:+.2f}" for k, v in I['ref_bins_pooled'].items() if v['raw'])]
        L.append('')
    L += ['## Context', '', 'DFC19 (demo/benchmark/correction.md): curve and linear height-only corrections also failed the MAE rule '
          'there; DFC19 is inside RS3DAda\'s adaptation domain (Target Domain 1), GAMUS is not.']
    open(os.path.join(V2, 'recal_gamus.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


def selftest():
    rng = np.random.default_rng(0)
    g = rng.uniform(0, 30, 50000)
    p = 0.6 * g + rng.normal(0, 1, len(g))           # under-estimation that grows with height
    x, y, n = fit_curve(np.clip(p, 0, None), g)
    assert n == len(g) and np.all(np.diff(y) >= 0) and np.all(np.diff(x) > 0)
    assert abs(np.interp(12, x, y) - 20) < 1.5        # 12 m predicted ~ 20 m true
    corr = corr_dict({1: (x, y, n)})
    lc = np.full(len(p), infer_height.LANDCOVER.index('buildings'), np.uint8)
    lc[:100] = infer_height.LANDCOVER.index('road')
    out = infer_height.correct_heights(np.clip(p, 0, None), lc, corr)
    assert np.array_equal(out[:100], np.clip(p[:100], 0, None).astype(np.float32))    # ground untouched
    assert np.abs(out[100:] - g[100:]).mean() < np.abs(np.clip(p[100:], 0, None) - g[100:]).mean()
    raw = {'whole': {'mae': {'mean': 2}}, 'bins': {'10-20 m': {'bias': {'mean': -5}}, '20-inf m': {'bias': {'mean': -9}}}}
    new = {'whole': {'mae': {'mean': 1.9}}, 'bins': {'10-20 m': {'bias': {'mean': 4}}, '20-inf m': {'bias': {'mean': -10}}}}
    assert passes(raw, new) == {'mae_lower': True, 'abs_bias_lower': {'10-20 m': True, '20-inf m': False}, 'pass': False}
    print('recalibration selftest OK')


if __name__ == '__main__':
    selftest() if '--selftest' in sys.argv else main()
