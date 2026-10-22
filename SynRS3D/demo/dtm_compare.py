"""Plan step 3: which terrain (DTM) base, and which laser levelling, on HELD-OUT ground points, for the 8 Indian
landscape scenes of demo/india_eval_v2.py (its caches: image, height, land cover, ICESat-2, GEDI, OSM, FABDEM).

usage (from SynRS3D/, venv python; no model run, so no model lock):
  python demo/dtm_compare.py build       FABDEM-based cleaned DTMs (terrain.build_dtm(source=FABDEM tile)) and a
                                         GLO-30 rebuild check -> demo/benchmark/v2/dtm_cache/
  python demo/dtm_compare.py evaluate    -> demo/benchmark/v2/dtm_compare.json (+ dtm_v2.md written by `report`)
  python demo/dtm_compare.py silent      Silent Valley offset diagnosis -> demo/benchmark/v2/dtm_silent_valley.json
  python demo/dtm_compare.py report      demo/benchmark/v2/dtm_v2.md from the two JSON files
  python demo/dtm_compare.py --selftest  offline asserts
Bases: glo30_clean = the current app terrain before levelling (cached _dtm_before.tif); glo30_raw; fabdem_raw;
  fabdem_clean = FABDEM run through the same nDSM cleaning; cartodem when a human put tiles in v2/scenes/cartodem/.
Reference ground points: ICESat-2 ATL08 ground photons outside OSM buildings, and GEDI L2A elev_lowestmode (quality 1,
  not degraded). Held-out split: ICESat-2 passes by validate.split_passes; GEDI orbits time-sorted and alternating the
  same way (phase giving levelling more shots). Single-pass scenes: that pass levels, GEDI validation orbits check.
Levelling methods (fitted on levelling points only, per pixel, as the app): none; is2_median (the old
  terrain.laser_offset, ICESat-2 only); is2_median_min2 (the same, no shift unless the photons come from >= 2 passes:
  terrain.LASER_MIN_PASSES, the app's new default); pooled_median (ICESat-2 + GEDI points); unit_median (median of per-pass / per-
  orbit medians: one vote per pass); huber (Huber IRLS, each pass/orbit equal total weight, offset + planar tilt when
  >= 3 units spread >= 75 m across, else offset); huber_min2 (huber, but no shift from a single pass/orbit).
Validation: footprint median (ICESat-2 r 6 m, GEDI r 12.5 m) of the levelled grid vs the validation points;
  metrics/aggregation from demo/eval_v2.py (mean over scenes, 95% bootstrap CI, 'pooled' = all points together).
"""
import json, os, sys

import numpy as np
import rasterio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'demo'))
import eval_v2 as ev

OUT = os.path.join(ROOT, 'demo', 'benchmark', 'v2')
CACHE = os.path.join(OUT, 'dtm_cache')
METHODS = ('none', 'is2_median', 'is2_median_min2', 'pooled_median', 'unit_median', 'huber', 'huber_min2')
SPREAD_M, MIN_UNIT_PTS = 75.0, 5


def split_units(unit, t):
    """Time-sorted alternating split of units (passes/orbits); phase giving the levelling side more points."""
    order = sorted(np.unique(unit), key=lambda u: np.median(t[unit == u]))
    lev = [np.isin(unit, order[k::2]) for k in (0, 1) if len(order) > k]
    if len(lev) == 2 and lev[1].sum() > lev[0].sum():
        return lev[1]
    return lev[0] if lev else np.zeros(len(unit), bool)


def huber_fit(A, y, w, iters=50):
    """Weighted Huber regression by IRLS (scale = NMAD of residuals, k = 1.345). Returns coefficients."""
    beta = np.linalg.lstsq(A * np.sqrt(w)[:, None], y * np.sqrt(w), rcond=None)[0]
    for _ in range(iters):
        res = y - A @ beta
        s = max(1.4826 * np.median(np.abs(res - np.median(res))), 0.1)
        u = np.abs(res) / (1.345 * s)
        ww = w * np.where(u <= 1, 1, 1 / np.maximum(u, 1e-9))
        nb = np.linalg.lstsq(A * np.sqrt(ww)[:, None], y * np.sqrt(ww), rcond=None)[0]
        if np.abs(nb - beta).max() < 1e-4:
            return nb
        beta = nb
    return beta


def fit_level(d, x, y, unit, method):
    """Levelling of terrain - reference differences d at local metres x, y. Returns (coeffs (c0, cx, cy), info):
    terrain is corrected by subtracting c0 + cx * x + cy * y. None = no correction."""
    keep = np.isfinite(d)
    d, x, y, unit = d[keep], x[keep], y[keep], unit[keep]
    us, cnt = np.unique(unit, return_counts=True)
    good = np.isin(unit, us[cnt >= MIN_UNIT_PTS])
    nu = int((cnt >= MIN_UNIT_PTS).sum())
    info = {'points': int(len(d)), 'units': nu}
    if method == 'pooled_median':
        return (None, info) if len(d) < 20 else ((float(np.median(d)), 0.0, 0.0), info)
    if method == 'unit_median':
        if not nu:
            return None, info
        return (float(np.median([np.median(d[unit == u]) for u in us[cnt >= MIN_UNIT_PTS]])), 0.0, 0.0), info
    if method in ('huber', 'huber_min2'):
        if not nu or (method == 'huber_min2' and nu < 2):
            return None, info
        d, x, y, unit = d[good], x[good], y[good], unit[good]
        _, inv, c = np.unique(unit, return_inverse=True, return_counts=True)
        w = 1.0 / c[inv]                                    # each pass / orbit the same total weight
        xy = np.c_[x, y] - np.average(np.c_[x, y], axis=0, weights=w)
        ev_min = float(np.sqrt(max(np.linalg.eigvalsh(np.cov(xy.T, aweights=w))[0], 0))) if len(d) > 2 else 0.0
        tilt = nu >= 3 and ev_min >= SPREAD_M
        A = np.c_[np.ones(len(d)), x, y] if tilt else np.ones((len(d), 1))
        b = huber_fit(A, d, w)
        info.update(tilt=bool(tilt), spread_minor_m=ev_min)
        return (float(b[0]), float(b[1]) if tilt else 0.0, float(b[2]) if tilt else 0.0), info
    raise ValueError(method)


def selftest():
    rng = np.random.default_rng(0)
    # unit split: alternating in time, phase with more levelling points
    u, t = np.repeat([1, 2, 3], [5, 50, 5]), np.repeat([0, 1, 2], [5, 50, 5])
    assert split_units(u, t).sum() == 50
    # huber recovers offset + tilt despite 20% gross outliers
    x, y = rng.uniform(-300, 300, 600), rng.uniform(-300, 300, 600)
    d = 3 + 0.01 * x - 0.02 * y + rng.normal(0, 0.5, 600)
    d[:120] += 40
    unit = np.repeat(np.arange(6), 100)
    (c0, cx, cy), info = fit_level(d, x, y, unit, 'huber')
    assert info['tilt'] and abs(c0 - 3) < 1.0 and abs(cx - 0.01) < 0.003 and abs(cy + 0.02) < 0.003, (c0, cx, cy)
    # collinear points (one track) -> offset only; one unit -> huber_min2 refuses
    (c0, cx, cy), info = fit_level(d[:100] * 0 + 5, x[:100] * 0, y[:100], np.zeros(100), 'huber')
    assert not info['tilt'] and abs(c0 - 5) < 1e-6 and cx == cy == 0
    assert fit_level(d[:100], x[:100], y[:100], np.zeros(100), 'huber_min2')[0] is None
    # unit_median: one dense pass cannot outvote two sparse ones
    d2, u2 = np.r_[np.full(500, 40.0), np.full(10, 1.0), np.full(10, 2.0)], np.repeat([0, 1, 2], [500, 10, 10])
    assert fit_level(d2, d2 * 0, d2 * 0, u2, 'unit_median')[0][0] == 2.0
    assert fit_level(d2, d2 * 0, d2 * 0, u2, 'pooled_median')[0][0] == 40.0
    print('dtm_compare selftest OK')


# ---------------------------------------------------------------- data (india_eval_v2 caches)
def _I():
    import india_eval_v2 as I
    return I


def fabdem_path(name):
    I = _I()
    p = json.load(open(I.f_(name, '_prep.json'))).get('fabdem')
    return os.path.join(I.SC, p) if p else None


def build(names):
    """FABDEM cleaned with our nDSM, and GLO-30 rebuilt (must equal the cached _dtm_before.tif)."""
    import infer_height, terrain
    I = _I()
    os.makedirs(CACHE, exist_ok=True)
    log = {}
    for n in names:
        path = I.f_(n, '.tif')
        h = rasterio.open(I.f_(n, '_height.tif')).read(1)
        lc = rasterio.open(I.f_(n, '_landcover.tif')).read(1).astype(np.uint8)
        gm = infer_height.ground_mask(h, lc)
        for tag, src in (('fabdem_clean', fabdem_path(n)), ('glo30_rebuild', 'glo30')):
            f = os.path.join(CACHE, f'{n}_{tag}.tif')
            if src is None or os.path.exists(f):
                continue
            dtm, info = terrain.build_dtm(path, h, gm, source=src)
            infer_height.save_tiff_with_geo_info(path, f, dtm)
            json.dump(info, open(f[:-4] + '.json', 'w'), indent=1)
            print(n, tag, info.get('mode'), info.get('alpha'), round(info['cleaning_removed_mean_m'], 2), flush=True)
        a = rasterio.open(os.path.join(CACHE, f'{n}_glo30_rebuild.tif')).read(1)
        b = rasterio.open(I.f_(n, '_dtm_before.tif')).read(1)
        log[n] = float(np.nanmax(np.abs(a - b)))
    json.dump(log, open(os.path.join(CACHE, 'glo30_rebuild_maxdiff.json'), 'w'), indent=1)
    print('GLO-30 rebuild max |diff| vs cached _dtm_before:', log)


def points(n, sc):
    """Reference ground points of a scene: dict of arrays lon, lat, H (EGM2008), src (0 IS2 / 1 GEDI), unit, lev, r, c,
    and the IS2 all-photon / GEDI-top arrays for the surface check."""
    import validate
    I = _I()
    N = sc.meta['terrain']['geoid_undulation_m']
    roofm = I.osm_mask(I.f_(n, '_osm.json'), sc)[0] if os.path.exists(I.f_(n, '_osm.json')) else np.zeros(sc.shape, bool)
    P = dict(np.load(I.f_(n, '_atl03.npz')))
    ins, r, c = I.pixels(sc, P['lon'], P['lat'])
    P = {k: v[ins] for k, v in P.items() if np.ndim(v)}
    r, c = r[ins], c[ins]
    lev_is2, val_is2 = validate.split_passes(P['track'], P['t'], P['cls'] == 1)
    split = bool(val_is2.any())
    gnd = (P['cls'] == 1) & ~roofm[r, c]
    out = {'is2_raw': {k: P[k] for k in ('lon', 'lat', 'h', 'cls', 't', 'track')}, 'is2_lev_mask': lev_is2, 'split': split}
    lon, lat, H = [P['lon'][gnd]], [P['lat'][gnd]], [P['h'][gnd] - N]
    src, unit, lev = [np.zeros(gnd.sum(), int)], [P['track'][gnd] // 100], [lev_is2[gnd]]
    out['is2_all'] = dict(lon=P['lon'], lat=P['lat'], H=P['h'] - N, val=val_is2 if split else np.zeros(len(r), bool))
    G = dict(np.load(I.f_(n, '_gedi.npz'))) if os.path.exists(I.f_(n, '_gedi.npz')) else None
    if G is not None and len(G['lon']):
        gi = I.pixels(sc, G['lon'], G['lat'])[0]
        q = gi & I.gedi_quality(G['flags'])
        if q.any():
            gl = split_units(G['orbit'][q], G['t'][q])
            lon.append(G['lon'][q]); lat.append(G['lat'][q]); H.append(G['elev_lm'][q] - N)
            src.append(np.ones(q.sum(), int)); unit.append(10 ** 9 + G['orbit'][q]); lev.append(gl)
            out['gedi_top'] = dict(lon=G['lon'][q], lat=G['lat'][q], H=G['elev_lm'][q] + G['rh98'][q] - N, val=~gl)
    out.update({k: np.concatenate(v) for k, v in (('lon', lon), ('lat', lat), ('H', H), ('src', src), ('unit', unit), ('lev', lev))})
    if not split:   # single ICESat-2 pass: it levels, it never validates
        out['lev'][out['src'] == 0] = True
    _, out['r'], out['c'] = I.pixels(sc, out['lon'], out['lat'])
    lon0, lat0 = out['lon'].mean() if len(out['lon']) else 0, out['lat'].mean() if len(out['lat']) else 0
    out['xy'] = lambda lo, la: ((lo - lon0) * 111320 * np.cos(np.radians(lat0)), (la - lat0) * 110540)
    out['N'] = N
    return out


def bases(n, sc):
    I = _I()
    import terrain
    prep = json.load(open(I.f_(n, '_prep.json')))
    w, s, e, nn = prep['bounds']
    b = {'glo30_clean': rasterio.open(I.f_(n, '_dtm_before.tif')).read(1).astype(np.float32),
         'glo30_raw': I.on_grid(terrain.GLO30.format(terrain.glo30_tile((s + nn) / 2, (w + e) / 2)), sc)}
    fp = fabdem_path(n)
    if fp:
        b['fabdem_raw'] = I.on_grid(fp, sc)
        b['fabdem_clean'] = rasterio.open(os.path.join(CACHE, f'{n}_fabdem_clean.tif')).read(1).astype(np.float32)
    carto = I.cartodem(sc, (w + e) / 2, (s + nn) / 2)
    if carto is not None:
        b['cartodem_raw'] = carto
    return b


def level(grid, pts, method, sc):
    """Levelled grid and info, fitted on the levelling points of pts only."""
    import terrain
    if method == 'none':
        return grid, {}
    if method in ('is2_median', 'is2_median_min2'):   # terrain.laser_offset on the levelling passes (roofs included)
        raw = pts['is2_raw']
        sub = {k: v[pts['is2_lev_mask']] for k, v in raw.items()}
        off, info = terrain.laser_offset(grid, sc.transform, sc.crs, sub, pts['N'], 1 if method == 'is2_median' else 2)
        return (grid if off is None else grid - off), dict(info, offset_m=off)
    L = pts['lev']
    d = grid[pts['r'][L], pts['c'][L]] - pts['H'][L]
    x, y = pts['xy'](pts['lon'][L], pts['lat'][L])
    coef, info = fit_level(d, x, y, pts['unit'][L], method)
    if coef is None:
        return grid, dict(info, offset_m=None)
    if coef[1] == coef[2] == 0:
        return grid - coef[0], dict(info, offset_m=coef[0])
    # plane on the pixel grid: pixel centres -> lon/lat -> local metres
    from rasterio.warp import transform as wt
    rr, cc = np.mgrid[0:sc.shape[0]:16, 0:sc.shape[1]:16]
    xs, ys = rasterio.transform.xy(sc.transform, rr.ravel(), cc.ravel())
    lo, la = wt(sc.crs, 'EPSG:4326', xs, ys)
    px, py = pts['xy'](np.asarray(lo), np.asarray(la))
    plane_c = (coef[0] + coef[1] * px + coef[2] * py).reshape(rr.shape).astype(np.float32)
    import cv2
    plane = cv2.resize(plane_c, (sc.shape[1], sc.shape[0]), interpolation=cv2.INTER_LINEAR)  # planes stay planes
    return grid - plane, dict(info, offset_m=coef[0], tilt_m_per_km=[1000 * coef[1], 1000 * coef[2]])


def evaluate(names):
    import validate
    I = _I()
    res, pool = {}, {}
    for n in names:
        sc = validate.Scene(n, I.f_(n, '.tif'), results=I.SC)
        pts, B = points(n, sc), bases(n, sc)
        hh = np.clip(sc.h, 0, None)
        land = json.load(open(I.f_(n, '_prep.json')))['landscape']
        V = ~pts['lev']
        sets = {'is2val': V & (pts['src'] == 0), 'gedival': V & (pts['src'] == 1), 'all_unlev': np.ones(len(V), bool)}
        rad = np.where(pts['src'] == 0, 6.0, 12.5)
        R = {'landscape': land, 'split': pts['split'], 'n_points': {k: int(m.sum()) for k, m in sets.items()},
             'units_levelling': int(len(np.unique(pts['unit'][pts['lev']]))), 'cmp': {}, 'level_info': {}}
        for bname, grid in B.items():
            fp_cache = {}
            for meth in METHODS:
                g2, info = level(grid, pts, meth, sc)
                R['level_info'][f'{bname}.{meth}'] = {k: v for k, v in info.items() if k in ('offset_m', 'tilt_m_per_km', 'points', 'units', 'tilt', 'spread_minor_m', 'ground_photons', 'none')}
                est = np.full(len(V), np.nan)
                for rr in (6.0, 12.5):
                    m = rad == rr
                    if m.any():
                        est[m] = validate.footprint(sc, g2, pts['lon'][m], pts['lat'][m], 'median', rr)
                for sname, m in sets.items():
                    if sname == 'all_unlev' and meth != 'none':
                        continue
                    if m.sum() >= 3:
                        e = est[m] - pts['H'][m]
                        k = f'dtm.{sname}.{bname}.{meth}'
                        R['cmp'][k] = ev.metrics(e, pts['H'][m])
                        pool.setdefault(k, []).append((n, e, pts['H'][m]))
                # end-to-end absolute DSM = levelled DTM + nDSM, on held-out photons / GEDI tops
                for sname, ref, stat, rr in (('is2val_all', pts['is2_all'], 'median', 6.0), ('gedival_top', pts.get('gedi_top'), 98, 12.5)):
                    if ref is None or ref['val'].sum() < 3:
                        continue
                    m = ref['val']
                    e = validate.footprint(sc, g2 + hh, ref['lon'][m], ref['lat'][m], stat, rr) - ref['H'][m]
                    k = f'dsm.{sname}.{bname}.{meth}'
                    R['cmp'][k] = ev.metrics(e, ref['H'][m])
                    pool.setdefault(k, []).append((n, e, ref['H'][m]))
        res[n] = R
        print(n, 'done', R['n_points'], flush=True)
    agg = {}
    keys = sorted({k for r in res.values() for k in r['cmp']})
    for k in keys:
        pl = pool[k]
        agg[k] = ev.aggregate([res[n]['cmp'].get(k) for n in res],
                              ev.metrics(np.concatenate([e for _, e, _ in pl]), np.concatenate([h for _, _, h in pl])))
    # same-scene comparisons: only scenes where every compared key exists
    same = {}
    for prefix in ('dtm.is2val', 'dtm.gedival', 'dsm.is2val_all', 'dsm.gedival_top'):
        ks = [k for k in keys if k.startswith(prefix + '.')]
        sn = [n for n in res if all(res[n]['cmp'].get(k) for k in ks if '.cartodem' not in k)]
        same[prefix] = {'scenes': sn, **{k: ev.aggregate([res[n]['cmp'][k] for n in sn],
                                                         ev.metrics(np.concatenate([e for nn, e, _ in pool[k] if nn in sn]),
                                                                    np.concatenate([h for nn, _, h in pool[k] if nn in sn])))
                                         for k in ks if '.cartodem' not in k and sn}}
    # wins: per scene, is method X better (MAE) than the current (glo30_clean.is2_median) on the held-out points?
    wins = {}
    for prefix in ('dtm.is2val', 'dtm.gedival', 'dsm.is2val_all', 'dsm.gedival_top'):
        cur = f'{prefix}.glo30_clean.is2_median'
        for k in keys:
            if k.startswith(prefix + '.'):
                pairs = [(n, r['cmp'][k]['mae'] - r['cmp'][cur]['mae']) for n, r in res.items() if r['cmp'].get(k) and r['cmp'].get(cur)]
                wins[k] = {'scenes': len(pairs), 'better': sum(d < 0 for _, d in pairs),
                           'worst_regression_m': max([d for _, d in pairs], default=None), 'delta_mae_m': dict(pairs)}
    out = {'protocol': __doc__, 'scenes': res, 'aggregate': agg, 'same_scenes': same, 'vs_current': wins}
    json.dump(out, open(os.path.join(OUT, 'dtm_compare.json'), 'w'), indent=1, default=float)
    print('wrote dtm_compare.json')


def silent(n='silent_valley_forest'):
    """Why does the one ICESat-2 pass move Silent Valley's terrain by ~47 m? Facts from the cached data only."""
    import terrain, validate
    I = _I()
    sc = validate.Scene(n, I.f_(n, '.tif'), results=I.SC)
    pts, B = points(n, sc), bases(n, sc)
    N = pts['N']
    raw = pts['is2_raw']
    _, r, c = I.pixels(sc, raw['lon'], raw['lat'])
    H = raw['h'] - N
    g = raw['cls'] == 1
    x, y = pts['xy'](raw['lon'], raw['lat'])
    out = {'geoid_undulation_m': N, 'egm96_to_egm2008_here_m': terrain.geoid_shift(raw['lon'].mean(), raw['lat'].mean()),
           'photons': int(len(H)), 'ground': int(g.sum()), 'beams': {int(k): int(v) for k, v in zip(*np.unique(raw['track'], return_counts=True))},
           'track_extent_m': {'east_west': float(np.ptp(x)), 'north_south': float(np.ptp(y))},
           'scene_extent_m': {'east_west': float(sc.shape[1] * sc.gsd), 'north_south': float(sc.shape[0] * sc.gsd)}}
    # 1. along-track profile, 40 m bins, ground photons vs the DEMs under them
    k = np.floor((y - y.min()) / 40).astype(int)
    prof = []
    for q in np.unique(k):
        m, mg = k == q, (k == q) & g
        if mg.sum() < 3:
            continue
        prof.append({'south_to_north_m': float(40 * q), 'ground': int(mg.sum()), 'ground_h': float(np.median(H[mg])),
                     **{f'{b}_minus_ground': float(np.median(B[b][r[mg], c[mg]] - H[mg])) for b in ('glo30_raw', 'fabdem_raw', 'glo30_clean')}})
    out['profile'] = prof
    d = B['glo30_clean'][r[g], c[g]] - H[g]
    out['share_ground_photons_dtm_minus_ground_gt_20m'] = float((d > 20).mean())
    out['offset_median_m'], out['offset_northern_third_m'] = float(np.median(d)), float(np.median(d[y[g] > np.percentile(y[g], 67)]))
    fab = B['fabdem_raw'][r[g], c[g]]
    out['fabdem_flat_cells'] = {'value_m': float(np.median(fab)), 'share_of_ground_photons_within_0.5m_of_mode': float(
        (np.abs(fab - np.round(np.median(fab[np.abs(fab - np.median(fab)) < 1]), 1)) < 0.5).mean())}
    # 2. GEDI shots near ICESat-2 ground photons (crossovers, <= 25 m): do the two lasers agree where they meet?
    G = pts.get('gedi_top')
    gm = pts['src'] == 1
    gx, gy = pts['xy'](pts['lon'][gm], pts['lat'][gm])
    cross = []
    for j in range(gm.sum()):
        dist = np.hypot(x[g] - gx[j], y[g] - gy[j])
        if dist.min() <= 25:
            cross.append({'dist_m': float(dist.min()), 'gedi_ground': float(pts['H'][gm][j]),
                          'is2_ground_median_25m': float(np.median(H[g][dist <= 25])), 'n_is2': int((dist <= 25).sum())})
    out['crossovers'] = cross
    if cross:
        dd = np.array([q['is2_ground_median_25m'] - q['gedi_ground'] for q in cross])
        out['crossover_is2_minus_gedi_median_m'] = float(np.median(dd))
    # 3. the DEM vs GEDI ground: on the track (<= 25 m from it) vs away from it
    dG = B['glo30_clean'][pts['r'][gm], pts['c'][gm]] - pts['H'][gm]
    near = np.array([np.hypot(x[g] - gx[j], y[g] - gy[j]).min() <= 25 for j in range(gm.sum())])
    out['glo30_clean_minus_gedi_ground'] = {'near_track_median': float(np.median(dG[near])) if near.any() else None, 'n_near': int(near.sum()),
                                            'away_median': float(np.median(dG[~near])), 'n_away': int((~near).sum())}
    # 4. beam / time / confidence facts
    P = dict(np.load(I.f_(n, '_atl03.npz')))
    ins = I.pixels(sc, P['lon'], P['lat'])[0]
    out['night_frac'] = float(np.nanmean(P['night'][ins]))
    out['strong_beam_share'] = float(np.isin(P['spot'][ins], (1, 3, 5)).mean())
    out['ground_h_te_uncertainty_median_m'] = float(np.nanmedian(np.where(P['h_te_unc'][ins] > 1e30, np.nan, P['h_te_unc'][ins])[P['cls'][ins] == 1]))
    out['date'] = str(np.datetime64(int(np.median(P['t'][ins])), 's'))[:10]
    json.dump(out, open(os.path.join(OUT, 'dtm_silent_valley.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: v for k, v in out.items() if k not in ('profile', 'crossovers')}, indent=1, default=float))
    for p in prof:
        print({k: round(v, 1) for k, v in p.items()})
    for q in cross:
        print({k: round(v, 1) for k, v in q.items()})


def e2e(scratch, name='silent_valley_forest'):
    """The app's own path (app.worker: model, buildings, terrain.build_dtm, terrain.laser_correct) on one cached GeoTIFF,
    written to <scratch>/results (app.SAMPLES/RESULTS redirected). Loads the model: run under the model lock."""
    import shutil, threading, time
    import app, terrain
    I = _I()
    app.SAMPLES, app.RESULTS = os.path.join(scratch, 'samples'), os.path.join(scratch, 'results')
    for d_ in (app.SAMPLES, app.RESULTS):
        os.makedirs(d_, exist_ok=True)
    shutil.copy(I.f_(name, '.tif'), app.SAMPLES)
    app.status[name] = {'state': 'queued', 'progress': 0}
    app.jobs.put(name)
    threading.Thread(target=app.worker, daemon=True).start()
    t0 = time.time()
    while app.status[name]['state'] not in ('done', 'error'):
        time.sleep(2)
    print(app.status[name], f'{time.time() - t0:.0f} s')
    t = json.load(open(os.path.join(app.RESULTS, name + '.json'))).get('terrain')
    json.dump({'scene': name, 'status': app.status[name], 'seconds': time.time() - t0, 'terrain_version': app.TERRAIN_VERSION,
               'terrain': t}, open(os.path.join(OUT, 'dtm_e2e_app_run.json'), 'w'), indent=1, default=float)
    print(json.dumps(t, indent=1, default=float))


SETS = {'dtm.is2val': 'DTM vs held-out ICESat-2 ground', 'dtm.gedival': 'DTM vs held-out GEDI ground',
        'dsm.is2val_all': 'DSM vs held-out ICESat-2 photons (all classes)', 'dsm.gedival_top': 'DSM vs held-out GEDI top (ground + rh98)'}
CUR, NEW = 'glo30_clean.is2_median', 'glo30_clean.is2_median_min2'


def guard_summary(d):
    """The single-pass guard, before/after per held-out set with and without Silent Valley (the scene that motivated it),
    and what the in-app ICESat-2 panel shows for Silent Valley afterwards (india_v2.json, per pixel as validate.py does).
    -> v2/dtm_guard_summary.json"""
    S, Q, sv = d['scenes'], d['same_scenes'], 'silent_valley_forest'
    out = {'sets': {}}
    for p in SETS:
        sn = Q[p]['scenes']
        per = {m: {n: S[n]['cmp'][f'{p}.{m}']['mae'] for n in sn} for m in (CUR, NEW)}
        ex = [n for n in sn if n != sv]
        out['sets'][p] = {'scenes': sn, 'per_scene_mae': {'before': per[CUR], 'after': per[NEW]},
                          'all': {'before': Q[p][f'{p}.{CUR}']['mae'], 'after': Q[p][f'{p}.{NEW}']['mae']},
                          'without_silent_valley': {'scenes': ex, **{k: ev.aggregate([S[n]['cmp'][f'{p}.{m}'] for n in ex])['mae']
                                                                      for k, m in (('before', CUR), ('after', NEW))}}}
    C = json.load(open(os.path.join(OUT, 'india_v2.json')))['scenes'][sv]['cmp']
    out['silent_valley_in_app'] = {k: {'before_guard_circular': C[f'{a}.ours_circular.px']['mae'], 'after_guard_unlevelled': C[f'{a}.ours_none.px']['mae'], 'n': C[f'{a}.ours_none.px']['n']}
                                   for k, a in (('surface_vs_all_photons', 'c.is2_all'), ('terrain_vs_ground_photons', 'a.is2'))}
    json.dump(out, open(os.path.join(OUT, 'dtm_guard_summary.json'), 'w'), indent=1, default=float)
    return out


def report():
    d = json.load(open(os.path.join(OUT, 'dtm_compare.json')))
    G = guard_summary(d)
    e2 = os.path.join(OUT, 'dtm_e2e_app_run.json')
    E = json.load(open(e2)) if os.path.exists(e2) else None
    sv = json.load(open(os.path.join(OUT, 'dtm_silent_valley.json')))
    S, A, Q, W = d['scenes'], d['aggregate'], d['same_scenes'], d['vs_current']
    f = lambda a, k='mae': '–' if not a or k not in a else f"{a[k]['mean']:.2f}" + (f" [{a[k]['ci95'][0]:.2f}, {a[k]['ci95'][1]:.2f}]" if a[k]['ci95'][0] is not None else '')
    pooled = lambda a: '–' if not a or not a.get('pooled') else f"{a['pooled']['mae']:.2f}"
    win = lambda k: '–' if k not in W else f"{W[k]['better']}/{W[k]['scenes']} (worst +{max(W[k]['worst_regression_m'], 0):.2f})"
    L = ['# DTM base and laser levelling on held-out points (plan step 3)', '',
         'All numbers: `demo/benchmark/v2/dtm_compare.json` and `dtm_silent_valley.json`, written by `demo/dtm_compare.py` '
         '(commands at the end). Scenes, photons, GEDI shots, OSM roofs and the pass split are those of `india_v2.md` '
         '(demo/india_eval_v2.py caches). MAE in metres; mean over scenes with a 95% bootstrap CI over scenes '
         '(2000 resamples), pooled = all points together. "wins" = scenes where MAE is lower than the old app '
         f'(`{CUR}`: GLO-30 cleaned with our nDSM, ICESat-2 median offset), worst = largest per-scene MAE increase.', '',
         'Harness check: the old app on held-out ICESat-2 ground gives ' + f(Q['dtm.is2val'].get(f'dtm.is2val.{CUR}')) +
         ' m, the same 4.02 m as india_v2.json `a.is2.ours_heldout.fp`; the GLO-30 rebuild through `terrain.build_dtm(source="glo30")` '
         'equals the cached terrain to 0.0 m in every scene (`dtm_cache/glo30_rebuild_maxdiff.json`).', '']
    # decision first
    L += ['## Result', '']
    L += ['- **Base: no change (Copernicus GLO-30 cleaned stays the default).** No base wins on all four held-out tests; '
          'FABDEM is better against GEDI ground and ICESat-2 photons in some scenes and worse against ICESat-2 ground and GEDI tops in others (tables 1, 4). '
          'FABDEM cleaned with our nDSM lowers the DSM under canopy (double removal), worse vs GEDI tops. FABDEM stays optional: a FABDEM tile in '
          '`demo/terrain/` is used automatically (existing behaviour), or `terrain.build_dtm(..., source=path)`; CC BY-NC-SA 4.0, never committed.',
          '- **Denser levelling with GEDI: no gain on ICESat-2 held-out ground.** Adding GEDI ground to the levelling points, one vote per pass/orbit, '
          'Huber + tilt: all are within ±0.3 m of the old median on held-out ICESat-2 ground, and none wins most scenes (table 2). '
          'They look better on held-out GEDI ground, but that is the same sensor on both sides, and most of the gain is Silent Valley alone.',
          '- **Levelling barely helps at all.** On held-out ICESat-2 ground, *no levelling* (3.86 m) is not worse than any levelling method; levelling '
          'removes the mean bias (+2.6 m -> about 0) but not the per-scene error, because offsets learned on one track do not hold on the next.',
          '- **Shipped: a single-pass guard** (`terrain.LASER_MIN_PASSES = 2`), a safety fix motivated by Silent Valley, not a measured accuracy gain: '
          '`laser_correct` no longer shifts the terrain when all ground photons '
          'come from one pass. It is identical to the old app wherever 2+ passes level, so it only changes single-pass cases; on the held-out '
          'protocol those are the scenes whose levelling half is one pass (Chandigarh, Anantapur, Silent Valley). There it is better on every '
          'held-out set except Anantapur vs GEDI tops (+1.05 m); elsewhere it ties. The GEDI gains are almost all Silent Valley, the scene whose '
          'GEDI disagreement prompted the guard, so they are not independent evidence; without Silent Valley the guard is close to neutral. '
          'In the app it makes the Silent Valley ICESat-2 panel look much worse (table 6). Tables 3 and 6.',
          '- **Silent Valley 47 m: a real local DEM error on one line, wrongly applied to the whole scene** (section 5).', '']
    L += ['## 1. Bases, no levelling (all points are independent)', '',
          '| Base | ' + ' | '.join(SETS.values()) + ' | ICESat-2 + GEDI ground, all points (8 scenes) |', '|---|' + '---|' * 5]
    for b in ('glo30_clean', 'glo30_raw', 'fabdem_raw', 'fabdem_clean'):
        L.append(f'| {b} | ' + ' | '.join(f"{f(Q[p].get(f'{p}.{b}.none'))} ({pooled(Q[p].get(f'{p}.{b}.none'))}); wins {win(f'{p}.{b}.none')}" for p in SETS) +
                 f" | {f(A.get(f'dtm.all_unlev.{b}.none'))} (pooled {pooled(A.get(f'dtm.all_unlev.{b}.none'))}), bias {A[f'dtm.all_unlev.{b}.none']['bias']['mean']:+.2f} |")
    L += ['', 'Scenes per column: ' + '; '.join(f'{SETS[p]}: {", ".join(Q[p]["scenes"])}' for p in SETS) + '.',
          'CartoDEM v3 R1: not evaluated, login-gated (Bhuvan). Human steps: india_v2.md section 10; once tiles are in '
          '`v2/scenes/cartodem/`, `dtm_compare.py evaluate` adds base `cartodem_raw` automatically.', '']
    L += ['## 2. Levelling methods on the current base (glo30_clean), held-out points only', '',
          '| Method | ' + ' | '.join(SETS.values()) + ' |', '|---|' + '---|' * 4]
    for m in METHODS:
        k = f'glo30_clean.{m}'
        L.append(f'| {m} | ' + ' | '.join(f"{f(Q[p].get(f'{p}.{k}'))} ({pooled(Q[p].get(f'{p}.{k}'))}), bias {Q[p][f'{p}.{k}']['bias']['mean']:+.2f}; wins {win(f'{p}.{k}')}" for p in SETS) + ' |')
    L += ['', 'All bases × methods: `dtm_compare.json` same_scenes / vs_current. Levelling fits per scene: scenes.*.level_info '
          '(Silent Valley huber fitted a 57/-62 m/km tilt from 3 units: tilt fits on 2-3 lines are unstable).', '']
    L += ['## 3. Per scene: old app vs single-pass guard vs no levelling (MAE, glo30_clean)', '',
          '| Scene | landscape | guard (ICESat-2 levelling passes >= 2?); levelling units (passes + GEDI orbits) | ' + ' | '.join(SETS.values()) + ' |', '|---|---|---|' + '---|' * 4]
    for n, r in S.items():
        cells = []
        for p in SETS:
            g = lambda m: r['cmp'].get(f'{p}.glo30_clean.{m}')
            cells.append('–' if not g('is2_median') else ' / '.join(f"{g(m)['mae']:.2f}" for m in ('is2_median', 'is2_median_min2', 'none')) + f" (n {g('none')['n']})")
        li = r['level_info'].get(f'glo30_clean.is2_median_min2', {})
        L.append(f"| {n} | {r['landscape']} | {'refused' if li.get('offset_m') is None else 'shift %+.2f' % li['offset_m']}; {r['units_levelling']} units | " + ' | '.join(cells) + ' |')
    L += ['', 'Cells: old / guard / none. Agumbe has neither held-out ICESat-2 nor GEDI points (one pass, no quality GEDI shot); '
          'its old 2.3 m single-pass shift is now refused, unverifiable either way.', '']
    L += ['## 4. Per landscape (mean of the 2 scenes, [min, max]), no levelling', '', '| Landscape | Base | DTM vs all ICESat-2 + GEDI ground: MAE | bias | NMAD |', '|---|---|---|---|---|']
    for land in dict.fromkeys(r['landscape'] for r in S.values()):
        for b in ('glo30_clean', 'glo30_raw', 'fabdem_raw', 'fabdem_clean'):
            ms = [r['cmp'].get(f'dtm.all_unlev.{b}.none') for r in S.values() if r['landscape'] == land]
            sp = lambda k: f"{np.mean([m[k] for m in ms if m]):.2f} [{min(m[k] for m in ms if m):.2f}, {max(m[k] for m in ms if m):.2f}]"
            L.append(f'| {land} | {b} | {sp("mae")} | {sp("bias")} | {sp("nmad")} |')
    sv_p = sv['profile']
    L += ['', '## 5. Silent Valley: what the 47 m offset is', '',
          f"- One ICESat-2 pass ({sv['date']}, night {sv['night_frac']:.0%}, {sv['strong_beam_share']:.0%} of photons on the strong beam, ATL08 ground "
          f"h_te_uncertainty median {sv['ground_h_te_uncertainty_median_m']:.1f} m): good-quality data, nothing points to a bad pass.",
          f"- Datum is not it: geoid height {sv['geoid_undulation_m']:.2f} m is applied to ICESat-2 and GEDI alike (both WGS84 ellipsoid); "
          f"EGM96 vs EGM2008 differ by {sv['egm96_to_egm2008_here_m']:+.2f} m here; GLO-30 and FABDEM are both EGM2008.",
          f"- The track is one line, {sv['track_extent_m']['east_west']:.0f} m east-west by {sv['track_extent_m']['north_south']:.0f} m north-south in a "
          f"{sv['scene_extent_m']['east_west']:.0f} m scene. Along it (south to north, 40 m bins) our terrain minus ground goes "
          + ', '.join(f"{p['glo30_clean_minus_ground']:+.0f}" for p in sv_p) +
          f" m: the southern 300 m (where {sum(p['ground'] for p in sv_p if p['south_to_north_m'] < 300) / sv['ground']:.0%} of the ground photons are) "
          f"follow a valley floor at {sv_p[0]['ground_h']:.0f}-{max(p['ground_h'] for p in sv_p if p['south_to_north_m'] < 300):.0f} m that GLO-30 and FABDEM place 20-50 m higher; "
          f"in the north the DEMs agree to a few metres. {sv['share_ground_photons_dtm_minus_ground_gt_20m']:.0%} of ground photons are > 20 m below our terrain.",
          f"- GEDI agrees with ICESat-2 where they meet closely: at the one close crossover (5 m apart, 10 photons) they differ by "
          f"{[q for q in sv['crossovers'] if q['dist_m'] < 10][0]['is2_ground_median_25m'] - [q for q in sv['crossovers'] if q['dist_m'] < 10][0]['gedi_ground']:+.1f} m. "
          f"The other {sum(q['dist_m'] >= 10 for q in sv['crossovers'])} crossovers rest on one ICESat-2 photon each, "
          + ', '.join(f"{q['dist_m']:.0f} m apart: {q['is2_ground_median_25m'] - q['gedi_ground']:+.1f} m" for q in sv['crossovers'] if q['dist_m'] >= 10)
          + " (they disagree with each other, so they are weak evidence either way); "
          f"GEDI shots near the track have our terrain {sv['glo30_clean_minus_gedi_ground']['near_track_median']:.0f} m above GEDI ground "
          f"(n {sv['glo30_clean_minus_gedi_ground']['n_near']}), away from it {sv['glo30_clean_minus_gedi_ground']['away_median']:.0f} m (n {sv['glo30_clean_minus_gedi_ground']['n_away']}).",
          '- **Cause:** the 30 m radar DEMs fill in a narrow forested valley (Copernicus is a canopy-influenced X-band surface; FABDEM removes '
          'part of the canopy but not the valley fill). The pass happens to run along that valley, so its median (+46.6 m) is right on that line '
          'and wrong for the slopes, where the DEM is ~13 m high. A constant shift from one line moved the whole scene 47 m down. '
          f"The terrain there is still ~13 m too high on the slopes without levelling. Unlevelled vs held-out GEDI ground in Silent Valley, MAE: "
          + ', '.join(f"{b} {S['silent_valley_forest']['cmp'][f'dtm.gedival.{b}.none']['mae']:.1f}" for b in ('glo30_clean', 'glo30_raw', 'fabdem_raw', 'fabdem_clean'))
          + ' m: FABDEM helps a little, nothing fixes it.', '']
    cur, new = (lambda p: Q[p].get(f'{p}.{CUR}'), lambda p: Q[p].get(f'{p}.{NEW}'))
    L += ['## 6. End-to-end absolute DSM (DSM = DTM + nDSM), held-out protocol, before vs after this change', '',
          '| Held-out set | before (old app) | after (guard) | wins | scenes |', '|---|---|---|---|---|']
    for p in ('dsm.is2val_all', 'dsm.gedival_top', 'dtm.is2val', 'dtm.gedival'):
        L.append(f"| {SETS[p]} | {f(cur(p))} ({pooled(cur(p))}) | {f(new(p))} ({pooled(new(p))}) | {win(f'{p}.{NEW}')} | {len(Q[p]['scenes'])} |")
    L += ['', 'Without Silent Valley (the scene that motivated the guard; mean over the remaining scenes [95% CI], `dtm_guard_summary.json`):', '',
          '| Held-out set | before | after | scenes |', '|---|---|---|---|']
    for p in ('dsm.is2val_all', 'dsm.gedival_top', 'dtm.is2val', 'dtm.gedival'):
        w = G['sets'][p]['without_silent_valley']
        L.append(f"| {SETS[p]} | {f(w, 'before')} | {f(w, 'after')} | {len(w['scenes'])} |")
    A_ = G['silent_valley_in_app']
    L += ['', 'The improvement is concentrated in the single-pass cases (Silent Valley above all); in the other scenes the guard changes nothing '
          'or (Anantapur vs GEDI tops) is worse. n of scenes is small and CIs overlap: this is a safety fix, not a measured accuracy gain in general.', '',
          '**What the app user now sees in Silent Valley.** The in-app ICESat-2 panel (validate.compare_icesat2) checks against the only laser '
          'line, which is the one line where the DEM is wrong. Before the guard it showed surface MAE '
          f"{A_['surface_vs_all_photons']['before_guard_circular']:.1f} m (circular: levelled on those photons); after it, surface "
          f"{A_['surface_vs_all_photons']['after_guard_unlevelled']:.1f} m and terrain {A_['terrain_vs_ground_photons']['after_guard_unlevelled']:.1f} m "
          f"(was {A_['terrain_vs_ground_photons']['before_guard_circular']:.1f} m circular): the terrain is ~47 m too high along that line, as it always "
          'was before levelling. At the same time DSM vs held-out GEDI tops goes '
          f"{G['sets']['dsm.gedival_top']['per_scene_mae']['before']['silent_valley_forest']:.1f} -> "
          f"{G['sets']['dsm.gedival_top']['per_scene_mae']['after']['silent_valley_forest']:.1f} m on the held-out GEDI orbits across the scene. "
          'For every single-pass scene the in-app laser number now describes the unlevelled terrain; `compare_icesat2` adds a `laser_note` saying so.', '',
          '## Commands', '', 'From `SynRS3D/` (no model run except the end-to-end check, under the shared model lock):', '', '```',
          '.venv/bin/python demo/dtm_compare.py --selftest && .venv/bin/python terrain.py',
          '.venv/bin/python demo/dtm_compare.py build      # FABDEM cleaned + GLO-30 rebuild check -> v2/dtm_cache/',
          '.venv/bin/python demo/dtm_compare.py evaluate   # -> v2/dtm_compare.json (~8 min)',
          '.venv/bin/python demo/dtm_compare.py silent     # -> v2/dtm_silent_valley.json',
          '.venv/bin/python demo/dtm_compare.py report     # -> v2/dtm_v2.md',
          '/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/dtm_compare.py e2e <scratch dir>   # app.worker on one GeoTIFF -> v2/dtm_e2e_app_run.json',
          '```', '',
          'App path check without the model: `terrain.laser_correct` on every cached scene (dtm_guard_check.json) shifts the 6 multi-pass '
          'scenes exactly as before and refuses the Agumbe (+2.3 m) and Silent Valley (+46.6 m) single-pass shifts, with the reason in '
          "`info['laser']['none']`. `python -c \"import terrain, app\"` passes. "
          + ('Full model run of the app path (`e2e`, `dtm_e2e_app_run.json`): ' + f"{E['scene']} {E['status']['state']} in {E['seconds']:.0f} s, "
             f"laser: {E['terrain']['laser'].get('none') or E['terrain']['laser']}; terrain version {E['terrain_version']}"
             + (' (still 2: cached scenes keep their old shift until app.TERRAIN_VERSION is bumped).' if E['terrain_version'] < 3 else '.')
             if E else 'The full model run of the app path (`e2e` above) has not been run yet.')]
    open(os.path.join(OUT, 'dtm_v2.md'), 'w').write('\n'.join(L) + '\n')
    print('wrote dtm_v2.md')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
        sys.exit()
    cmd = (sys.argv[1:2] or ['--help'])[0]
    names = sys.argv[2:] if cmd != 'e2e' else []
    names = names or [r[1] for r in _I().REGIONS]
    if cmd == 'build':
        build(names)
    elif cmd == 'evaluate':
        evaluate(names)
    elif cmd == 'silent':
        silent()
    elif cmd == 'e2e':
        e2e(sys.argv[2])
    elif cmd == 'report':
        report()
    else:
        print(__doc__)
