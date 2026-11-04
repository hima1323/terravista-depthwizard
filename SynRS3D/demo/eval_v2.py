"""Shared metrics for evaluation protocol v2 (plan step 2): one definition of every number, so the GAMUS, Indian
ICESat-2 / GEDI and calibration tracks report comparable values.

usage:  sys.path.insert(0, '<repo>/SynRS3D/demo'); from eval_v2 import metrics, evaluate, ...
        .venv/bin/python demo/eval_v2.py --selftest          (offline, synthetic data, asserts only)
Definitions (e = ours - reference, metres):
  metrics(e, ref)      n, MAE, RMSE, bias = mean(e), median, NMAD = 1.4826 median|e - median(e)|, Pearson r of ours vs
                       reference (needs ref; ours = ref + e), share of |e| <= 1 m and <= 2 m. None if nothing finite.
  high_metrics         utils/metrics.py 'high': both clipped at 0, pixels where reference > 3 m OR ours > 3 m
                       (union=False: reference > 3 m only). Unlike utils/metrics.py, a unit is not dropped when one side
                       has no pixel above 3 m.
  binned_bias          metrics per REFERENCE height bin [0,3) [3,10) [10,20) [20,inf)
  bootstrap_ci         95% percentile bootstrap of the mean over units (tiles / scenes), 2000 resamples, default_rng(0)
  aggregate/evaluate   per-unit mean + CI for every metric, plus the pixel-pooled value labelled 'pooled'
  building_level       connected components (4-connectivity) of the reference building mask, >= 20 px; 90th percentile
                       of ours vs of the reference inside each
  footprint_sample     laser footprints: disc of radius_m around each shot; 'median' for ground, 95/98 for top surface,
                       'pixel' for the single containing pixel
  spearman             rank correlation, average ranks for ties (the old argsort ranks broke float16 ties at random)
"""
import sys

import numpy as np
from scipy import ndimage, stats

BINS = [(0, 3), (3, 10), (10, 20), (20, np.inf)]
BIN_LABELS = [f'{lo:g}-{hi:g} m' for lo, hi in BINS]   # '0-3 m' ... '20-inf m'


def metrics(e, ref=None):
    e = np.asarray(e, np.float64).ravel()
    ok = np.isfinite(e)
    if ref is not None:
        ref = np.asarray(ref, np.float64).ravel()
        ok &= np.isfinite(ref)
        ref = ref[ok]
    e = e[ok]
    if not len(e):
        return None
    a, med = np.abs(e), float(np.median(e))
    r = None
    if ref is not None and len(e) > 2 and ref.std() > 0 and (ref + e).std() > 0:
        r = float(np.corrcoef(ref + e, ref)[0, 1])
    return {'n': int(len(e)), 'mae': float(a.mean()), 'rmse': float(np.sqrt((e * e).mean())), 'bias': float(e.mean()),
            'median': med, 'nmad': float(1.4826 * np.median(np.abs(e - med))), 'r': r,
            'within_1m': float((a <= 1).mean()), 'within_2m': float((a <= 2).mean())}


def high_metrics(pred, ref, thr=3.0, union=True):
    p, g = np.clip(np.asarray(pred, np.float64), 0, None), np.clip(np.asarray(ref, np.float64), 0, None)
    m = ((g > thr) | (p > thr)) if union else (g > thr)
    return metrics(p[m] - g[m], g[m])


def binned_bias(pred, ref, bins=BINS):
    p, g = np.asarray(pred, np.float64).ravel(), np.asarray(ref, np.float64).ravel()
    return {f'{lo:g}-{hi:g} m': metrics(p[m] - g[m], g[m]) for lo, hi in bins for m in [(g >= lo) & (g < hi)]}


def bootstrap_ci(values, n_boot=2000, seed=0):
    """95% percentile CI of the mean over units; None/NaN units dropped; (None, None) with fewer than 2 units."""
    v = np.array([x for x in values if x is not None], np.float64)
    v = v[np.isfinite(v)]
    if len(v) < 2:
        return None, None
    s = v[np.random.default_rng(seed).integers(0, len(v), (n_boot, len(v)))].mean(1)
    lo, hi = np.percentile(s, [2.5, 97.5])
    return float(lo), float(hi)


def aggregate(per_unit, pooled=None):
    """per_unit: list of metric dicts (None = unit without data, skipped). pooled: the same metric computed on all
    pixels/points together (the caller concatenates: median, NMAD and r cannot be pooled from per-unit summaries)."""
    units = [d for d in per_unit if d]
    out = {'units': len(units), 'pooled': pooled}
    for k in (units[0] if units else {}):
        v = [d[k] for d in units if d.get(k) is not None]
        if v and k != 'n':
            lo, hi = bootstrap_ci(v)
            out[k] = {'mean': float(np.mean(v)), 'ci95': [lo, hi], 'units': len(v)}
    return out


def evaluate(units, fn=metrics, min_n=1):
    """units: list of argument tuples for fn, one per tile/scene, e.g. [(e_tile, ref_tile), ...]. A unit enters the
    per-unit mean only with >= min_n values; the pooled value uses every unit."""
    per = [fn(*u) if np.size(u[0]) >= min_n else None for u in units]
    pooled = fn(*[np.concatenate([np.ravel(u[i]) for u in units]) for i in range(len(units[0]))]) if units else None
    return aggregate(per, pooled)


def cell(agg, key, nd=2):
    """'mean [lo, hi] (pooled x)' for markdown tables."""
    if not agg or key not in agg:
        return '–'
    m, (lo, hi) = agg[key]['mean'], agg[key]['ci95']
    p = (agg.get('pooled') or {}).get(key)
    s = f'{m:.{nd}f}' + (f' [{lo:.{nd}f}, {hi:.{nd}f}]' if lo is not None else '')
    return s + (f' ({p:.{nd}f})' if p is not None else '')


def building_level(pred, ref, building_mask, min_px=20, q=90):
    """Per building: (ours q-th pct, reference q-th pct, pixels) as arrays; buildings = connected components of the
    reference building mask with >= min_px finite pixels. Terraced rows that touch merge into one component."""
    lab, _ = ndimage.label(building_mask)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        if sl is None:
            continue
        m = lab[sl] == i
        o, g = pred[sl][m], ref[sl][m]
        ok = np.isfinite(o) & np.isfinite(g)
        if ok.sum() >= min_px:
            out.append((np.percentile(o[ok], q), np.percentile(g[ok], q), ok.sum()))
    o, g, n = (np.array(c, np.float64) for c in zip(*out)) if out else (np.zeros(0),) * 3
    return o, g, n.astype(int)


def footprint_sample(grid, transform, lon, lat, radius_m=6.0, stat='median', crs=None):
    """Sample a raster at laser shots (lon/lat, EPSG:4326). transform: the grid's affine (rasterio src.transform, no
    rotation); crs: the grid's CRS (anything pyproj accepts, e.g. src.crs); None = the grid itself is lon/lat.
    stat: 'pixel' (containing pixel), 'median', 'mean' or a number = percentile (95-98 for the top surface).
    Disc = pixel centres within radius_m of the shot, plus the containing pixel. NaN outside / no finite pixels.
    ICESat-2 footprint ~11 m -> radius_m ~6; GEDI ~25 m -> ~12.5."""
    a, b, c, d, e, f = tuple(transform)[:6]
    assert b == 0 and d == 0, 'rotated grids not supported'
    lon, lat = np.atleast_1d(np.asarray(lon, np.float64)), np.atleast_1d(np.asarray(lat, np.float64))
    x, y, mx, my = lon, lat, abs(a) * 111320 * np.cos(np.radians(lat)), np.full(len(lat), abs(e) * 110540)
    if crs is not None:
        import pyproj
        crs = pyproj.CRS.from_user_input(crs)
        x, y = pyproj.Transformer.from_crs('EPSG:4326', crs, always_xy=True).transform(lon, lat)
        if not crs.is_geographic:   # projected: transform units are metres
            mx, my = np.full(len(lat), abs(a)), np.full(len(lat), abs(e))
    cf, rf = (np.asarray(x) - c) / a, (np.asarray(y) - f) / e
    H, W = grid.shape
    out = np.full(len(lon), np.nan)
    # ponytail: Python loop per shot (~10^4-10^5 shots/scene is seconds); vectorise if a run needs millions
    for k in range(len(lon)):
        r0, c0 = int(np.floor(rf[k])), int(np.floor(cf[k]))
        if not (0 <= r0 < H and 0 <= c0 < W):
            continue
        if stat == 'pixel':
            out[k] = grid[r0, c0]
            continue
        ry, rx = int(np.ceil(radius_m / my[k])), int(np.ceil(radius_m / mx[k]))
        rr, cc = np.mgrid[max(0, r0 - ry):min(H, r0 + ry + 1), max(0, c0 - rx):min(W, c0 + rx + 1)]
        m = ((cc + 0.5 - cf[k]) * mx[k]) ** 2 + ((rr + 0.5 - rf[k]) * my[k]) ** 2 <= radius_m ** 2
        m |= (rr == r0) & (cc == c0)
        v = grid[rr[m], cc[m]].astype(np.float64)
        v = v[np.isfinite(v)]
        if len(v):
            out[k] = np.median(v) if stat == 'median' else v.mean() if stat == 'mean' else np.percentile(v, float(stat))
    return out


def spearman(a, b):
    a, b = np.asarray(a, np.float64).ravel(), np.asarray(b, np.float64).ravel()
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or a[ok].std() == 0 or b[ok].std() == 0:
        return None
    return float(stats.spearmanr(a[ok], b[ok]).statistic)


def selftest():
    close = lambda x, y, t=1e-9: abs(x - y) < t
    m = metrics([1, -1, 2, -2, np.nan])
    assert m['n'] == 4 and close(m['mae'], 1.5) and close(m['rmse'], np.sqrt(2.5)) and close(m['bias'], 0)
    assert close(m['median'], 0) and close(m['nmad'], 1.4826 * 1.5) and m['within_1m'] == 0.5 and m['within_2m'] == 1
    assert m['r'] is None and metrics([np.nan]) is None
    g = np.arange(10.0)
    assert close(metrics(np.zeros(10), g)['r'], 1) and close(metrics(0.5 * g, g)['bias'], 2.25)
    assert metrics(-g, g)['r'] is None   # ours = 0 everywhere (the terrain-only baseline): r undefined
    # high: union of ref > 3 and ours > 3, after clipping at 0
    p, r = np.array([0, 5, 1, 4, -1.0]), np.array([0, 1, 6, 4, 8.0])
    h = high_metrics(p, r)
    assert h['n'] == 4 and close(h['bias'], (4 - 5 + 0 - 8) / 4)
    assert high_metrics(p, r, union=False)['n'] == 3
    bb = binned_bias(np.array([1, 2, 12, 30.0]), np.array([0, 5, 15, 25.0]))
    assert list(bb) == BIN_LABELS and close(bb['0-3 m']['bias'], 1) and close(bb['10-20 m']['bias'], -3) and bb['20-inf m']['n'] == 1
    assert bootstrap_ci([2.0] * 7) == (2.0, 2.0) and bootstrap_ci([1.0]) == (None, None)
    x = np.random.default_rng(1).normal(5, 1, 400)
    lo, hi = bootstrap_ci(x)
    assert lo < 5 < hi and hi - lo < 0.3 and bootstrap_ci(x) == (lo, hi)   # deterministic
    # aggregate: per-unit mean differs from pooled when units differ in size
    units = [(np.ones(10), np.zeros(10)), (np.full(2, 3.0), np.zeros(2)), (np.zeros(0), np.zeros(0))]
    ag = evaluate(units)
    assert ag['units'] == 2 and close(ag['mae']['mean'], 2) and close(ag['pooled']['mae'], 16 / 12) and ag['pooled']['n'] == 12
    assert evaluate(units, min_n=5)['units'] == 1 and cell(ag, 'mae').startswith('2.00 [1.00, 3.00] (1.33)')
    # buildings: two roofs (100 px at 10 m, 64 px at 20 m), one 9-px shed dropped; ours = 0.8 x reference
    ref, mask = np.zeros((40, 40)), np.zeros((40, 40), bool)
    ref[2:12, 2:12], ref[20:28, 20:28], ref[35:38, 35:38] = 10, 20, 5
    mask[ref > 0] = True
    o, gq, n = building_level(0.8 * ref, ref, mask)
    assert sorted(gq) == [10, 20] and np.allclose(o, 0.8 * gq) and sorted(n) == [64, 100]
    assert len(building_level(ref, ref, np.zeros_like(mask))[0]) == 0
    # footprints: 1 m UTM grid (EPSG:32643), value = column index; shot at the centre of pixel (50, 50)
    import pyproj
    from rasterio.transform import from_origin
    tr = from_origin(500000, 3400100, 1, 1)
    lon, lat = pyproj.Transformer.from_crs('EPSG:32643', 'EPSG:4326', always_xy=True).transform(500050.5, 3400049.5)
    grid = np.tile(np.arange(100.0), (100, 1))
    assert close(footprint_sample(grid, tr, lon, lat, 6, 'pixel', 'EPSG:32643')[0], 50)
    assert close(footprint_sample(grid, tr, lon, lat, 6, 'median', 'EPSG:32643')[0], 50, 1e-6)
    assert close(footprint_sample(grid, tr, lon, lat, 6, 98, 'EPSG:32643')[0], 55, 0.6)   # disc spans columns 44-56
    assert np.isnan(footprint_sample(grid, tr, lon + 1, lat, 6, 'median', 'EPSG:32643')[0])
    # same on a lon/lat grid (~1 m pixels at the equator)
    trg = from_origin(76.0, 0.001, 1 / 111320, 1 / 110540)
    v = footprint_sample(grid, trg, 76.0 + 50.5 / 111320, 0.001 - 49.5 / 110540, 6, 'median')[0]
    assert close(v, 50, 1e-6)
    s = np.random.default_rng(2).normal(size=1000)
    assert close(spearman(s, np.exp(s)), 1) and close(spearman(s, -s ** 3), -1) and spearman(s, np.ones(1000)) is None
    print('eval_v2 selftest OK')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    else:
        print(__doc__)
