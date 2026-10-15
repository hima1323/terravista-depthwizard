"""Validation of a processed scene against reference heights, and calibration with ground control points (GCPs).

Reference data the viewer can check against (SIH26175: "validate estimated heights against reference datasets"):
  * a raster: a reference DSM (surface, m above sea level), nDSM (height above ground, e.g. LiDAR-derived) or DTM
    (bare ground). Georeferenced rasters are reprojected onto the scene's pixel grid; for a scene or a reference
    without georeferencing the two must cover the same area and are matched pixel to pixel (resized).
  * surveyed points: a CSV with lon,lat,z (WGS84) or col,row,z (image pixels) of known surface heights;
  * NASA ICESat-2 laser photons inside the scene (terrain.icesat2_photons): ground photons vs our terrain,
    all photons vs our surface model.
Metrics: MAE, RMSE, bias, NMAD, Pearson correlation r, share within 1 / 2 m; overall and split by landscape type
(land cover: urban / forested / sparse-open / water; terrain slope: flat / rolling / hilly) and by height band.

GCPs: points of known elevation fit  z = ground + a + bx·u + by·v + s·height  (u, v = image position 0..1); the
number of terms grows with the number of points. Leave-one-out error tells how well the fit predicts a point it
did not see. Without terrain (PNG/JPG) ground is 0, so GCPs turn the relative DSM into absolute heights.
"""
import csv, io, json, math, os

import cv2
import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform as warp_transform, transform_bounds

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(ROOT, 'demo', 'results')
REFERENCE = os.path.join(ROOT, 'demo', 'reference')
GRID = 512
# model land-cover classes (infer_height.LANDCOVER order) grouped into the landscape types of the evaluation
LANDSCAPES = {'urban (buildings, roads, paved)': (2, 3, 7), 'forested (trees)': (4,),
              'sparse / open (bare, grass, fields)': (0, 1, 6), 'water': (5,)}
SLOPES = [('flat (< 5°)', 0, 5), ('rolling (5–15°)', 5, 15), ('hilly (> 15°)', 15, 90)]
BANDS = [('0–3 m', -1e9, 3), ('3–10 m', 3, 10), ('10–20 m', 10, 20), ('> 20 m', 20, 1e9)]


def metrics(pred, ref):
    """Error statistics of pred vs ref (same shape); None if fewer than 10 valid pairs."""
    pred, ref = np.asarray(pred, np.float64).ravel(), np.asarray(ref, np.float64).ravel()
    ok = np.isfinite(pred) & np.isfinite(ref)
    if ok.sum() < 10:
        return None
    p, r = pred[ok], ref[ok]
    e = p - r
    med = float(np.median(e))
    sp, sr = p.std(), r.std()
    return {'n': int(ok.sum()), 'mae': float(np.abs(e).mean()), 'rmse': float(np.sqrt((e ** 2).mean())),
            'bias': float(e.mean()), 'median': med, 'nmad': float(1.4826 * np.median(np.abs(e - med))),
            'r': float(((p - p.mean()) * (r - r.mean())).mean() / (sp * sr)) if sp > 0 and sr > 0 else None,
            'within_1m_pct': float(100 * (np.abs(e) <= 1).mean()), 'within_2m_pct': float(100 * (np.abs(e) <= 2).mean())}


def breakdowns(pred, ref, lc, slope, band_by):
    """Metrics per landscape type, terrain slope class and height band (each only where there is data)."""
    out = {'landscape': {}, 'slope': {}, 'height': {}}
    if lc is not None:
        for k, cls in LANDSCAPES.items():
            m = metrics(pred[np.isin(lc, cls)], ref[np.isin(lc, cls)])
            if m:
                out['landscape'][k] = m
    if slope is not None:
        for k, lo, hi in SLOPES:
            sel = (slope >= lo) & (slope < hi)
            m = metrics(pred[sel], ref[sel])
            if m:
                out['slope'][k] = m
    for k, lo, hi in BANDS:
        sel = (band_by >= lo) & (band_by < hi)
        m = metrics(pred[sel], ref[sel])
        if m:
            out['height'][k] = m
    return out


def slope_deg(dtm, transform):
    """Terrain slope (degrees) of a DTM on a projected or geographic pixel grid."""
    dx, dy = abs(transform.a), abs(transform.e)
    gy, gx = np.gradient(dtm.astype(np.float64), dy, dx)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)


class Scene:
    """The saved full-resolution products of one processed scene (demo/results)."""

    def __init__(self, name, image_path):
        self.name, self.image_path = name, image_path
        r = lambda sfx: os.path.join(RESULTS, name + sfx)
        with rasterio.open(r('_height.tif')) as src:
            self.h = src.read(1).astype(np.float32)
            self.crs, self.transform = src.crs, src.transform
        self.shape = self.h.shape
        self.lc = rasterio.open(r('_landcover.tif')).read(1).astype(np.uint8)
        self.dtm = rasterio.open(r('_dtm.tif')).read(1).astype(np.float32) if os.path.exists(r('_dtm.tif')) else None
        self.dsm = None if self.dtm is None else self.dtm + np.clip(self.h, 0, None)
        self.meta = json.load(open(r('.json')))
        self.gsd = self.meta.get('gsd', 0.5)
        # terrain slope on the ground pixel size (works for projected and lon/lat grids alike)
        self.slope = None if self.dtm is None else slope_deg(self.dtm, rasterio.Affine(self.gsd, 0, 0, 0, -self.gsd, 0))

    def product(self, kind):
        """Our counterpart of a reference of this kind: dsm / ndsm / dtm."""
        if kind == 'ndsm':
            return np.clip(self.h, 0, None)
        if kind == 'dtm':
            return self.dtm
        return self.dsm


def read_reference(scene, path, datum='egm2008'):
    """Reference raster on the scene's pixel grid (NaN = no data) and how it was matched."""
    with rasterio.open(path) as src:
        nodata = src.nodata
        if scene.crs and src.crs:
            out = np.full(scene.shape, np.nan, np.float32)
            reproject(rasterio.band(src, 1), out, src_transform=src.transform, src_crs=src.crs, src_nodata=nodata,
                      dst_transform=scene.transform, dst_crs=scene.crs, dst_nodata=np.nan, resampling=Resampling.bilinear)
            how = 'reprojected onto the scene grid (both georeferenced)'
        else:
            a = src.read(1).astype(np.float32)
            if nodata is not None:
                a[a == nodata] = np.nan
            out = cv2.resize(a, (scene.shape[1], scene.shape[0]), interpolation=cv2.INTER_LINEAR)
            how = 'matched pixel to pixel (resized to the image; assumes both cover the same area)'
    out[~np.isfinite(out) | (out < -1000) | (out > 9000)] = np.nan
    shift = datum_shift(scene, datum)
    if shift:
        out = out + shift
    return out, how, shift


def datum_shift(scene, datum):
    """Metres to add to a reference in this vertical datum to bring it onto EGM2008 (what our DSM uses)."""
    if datum in (None, '', 'egm2008', 'none'):
        return 0.0
    import terrain
    with rasterio.open(scene.image_path) as img:
        if not img.crs:
            return 0.0
        w, s, e, n = transform_bounds(img.crs, 'EPSG:4326', *img.bounds)
    lon, lat = (w + e) / 2, (s + n) / 2
    if datum == 'egm96':
        return terrain.geoid_shift(lon, lat) or 0.0
    if datum == 'ellipsoid':   # ellipsoidal height h -> orthometric H = h - N
        N = scene.meta.get('terrain', {}).get('geoid_undulation_m')
        return -N if N is not None else 0.0
    return 0.0


def to_grid(a, gw, gh):
    """Full-resolution float array -> the browser's grid (area average, NaN-aware)."""
    ok = np.isfinite(a).astype(np.float32)
    s = cv2.resize(np.nan_to_num(a).astype(np.float32), (gw, gh), interpolation=cv2.INTER_AREA)
    w = cv2.resize(ok, (gw, gh), interpolation=cv2.INTER_AREA)
    return np.where(w > 0.5, s / np.maximum(w, 1e-6), np.nan).astype(np.float32)


def compare_raster(scene, ref_path, kind='dsm', datum='egm2008'):
    """Full comparison of our product with a reference raster. Writes <scene>_valerr.f32 (error on the browser grid)."""
    ref, how, shift = read_reference(scene, ref_path, datum)
    ours = scene.product(kind)
    relative = ours is None   # e.g. a reference DSM for a scene without terrain: compare after a best-fit line
    if relative:
        ours = np.clip(scene.h, 0, None)
    ok = np.isfinite(ours) & np.isfinite(ref)
    if ok.sum() < 100:
        raise ValueError('the reference does not overlap the scene (fewer than 100 valid pixels)')
    fit = None
    pred = ours.astype(np.float64)
    if relative:   # no absolute scale: ref ≈ a + s·ours, then compare
        s, a = np.polyfit(pred[ok], ref[ok].astype(np.float64), 1)
        pred, fit = a + s * pred, {'scale': float(s), 'offset': float(a)}
    err = np.where(ok, pred - ref, np.nan)
    res = {'kind': kind, 'datum': datum, 'datum_shift_m': shift, 'matched': how, 'reference': os.path.basename(ref_path),
           'relative_fit': fit, 'coverage_pct': float(100 * ok.mean()),
           'overall': metrics(pred[ok], ref[ok])}
    b = res['overall']['bias']
    res['bias_removed'] = metrics(pred[ok] - b, ref[ok])   # e.g. an unknown datum offset in the reference
    band_by = ref - scene.dtm if (kind == 'dsm' and scene.dtm is not None) else ref
    res.update(breakdowns(np.where(ok, pred, np.nan), np.where(ok, ref, np.nan), scene.lc, scene.slope,
                          band_by if kind != 'dtm' else np.zeros_like(ref)))
    # scatter sample + error histogram for the viewer
    idx = np.flatnonzero(ok)
    rng = np.random.default_rng(0)
    pick = rng.choice(idx, min(3000, len(idx)), replace=False)
    res['scatter'] = {'ref': np.round(ref.ravel()[pick], 2).tolist(), 'ours': np.round(pred.ravel()[pick], 2).tolist()}
    e = err[ok]
    lim = float(max(1.0, np.percentile(np.abs(e), 98)))
    counts, edges = np.histogram(np.clip(e, -lim, lim), bins=40, range=(-lim, lim))
    res['histogram'] = {'counts': counts.tolist(), 'lo': -lim, 'hi': lim}
    gw, gh = scene.meta['grid_w'], scene.meta['grid_h']
    to_grid(err, gw, gh).astype('<f4').tofile(os.path.join(RESULTS, scene.name + '_valerr.f32'))
    res['error_grid'] = True
    res['error_range'] = lim
    return res


def read_points(text):
    """CSV text -> list of dicts with lon/lat or col/row and z. Header names are matched loosely."""
    rows = list(csv.reader(io.StringIO(text.strip())))
    if not rows:
        raise ValueError('empty CSV')
    head = [h.strip().lower() for h in rows[0]]
    pick = lambda *names: next((head.index(n) for n in names if n in head), None)
    ix, iy, iz = pick('lon', 'longitude', 'x', 'col', 'column'), pick('lat', 'latitude', 'y', 'row'), pick('z', 'elev', 'elevation', 'height', 'h', 'alt')
    if None in (ix, iy, iz):
        raise ValueError('CSV needs a header with lon,lat,z (WGS84) or col,row,z (image pixels)')
    pix = head[ix] in ('col', 'column')
    pts = []
    for r in rows[1:]:
        try:
            x, y, z = float(r[ix]), float(r[iy]), float(r[iz])
        except (ValueError, IndexError):
            continue
        pts.append({'col': x, 'row': y, 'z': z} if pix else {'lon': x, 'lat': y, 'z': z})
    return pts


def point_pixels(scene, pts):
    """Fractional image pixel (col, row) of each point; points outside the image are dropped."""
    out = []
    for p in pts:
        if 'col' in p:
            c, r = p['col'], p['row']
        elif 'u' in p:
            c, r = p['u'] * scene.shape[1], p['v'] * scene.shape[0]
        else:
            if not scene.crs:
                raise ValueError('lon/lat points need a georeferenced (GeoTIFF) scene; use col,row for PNG/JPG')
            xs, ys = warp_transform('EPSG:4326', scene.crs, [p['lon']], [p['lat']])
            r, c = rasterio.transform.rowcol(scene.transform, xs[0], ys[0], op=float)
        if 0 <= c < scene.shape[1] and 0 <= r < scene.shape[0]:
            out.append(dict(p, c=float(c), r=float(r)))
    return out


def sample(a, c, r, win=1):
    """Median of a (2·win+1)² window around a pixel (robust to a point sitting on an edge)."""
    if a is None:
        return float('nan')
    ci, ri = int(c), int(r)
    w = a[max(0, ri - win):ri + win + 1, max(0, ci - win):ci + win + 1]
    w = w[np.isfinite(w)]
    return float(np.median(w)) if len(w) else float('nan')


def compare_points(scene, pts, datum='egm2008'):
    """Our surface height at surveyed points vs their known heights."""
    pts = point_pixels(scene, pts)
    if len(pts) < 3:
        raise ValueError('need at least 3 points inside the scene')
    shift = datum_shift(scene, datum)
    ours_arr = scene.dsm if scene.dsm is not None else np.clip(scene.h, 0, None)
    ours = np.array([sample(ours_arr, p['c'], p['r']) for p in pts])
    ref = np.array([p['z'] + shift for p in pts])
    fit = None
    if scene.dsm is None:
        s, a = np.polyfit(ours, ref, 1) if len(pts) >= 3 else (1.0, 0.0)
        ours, fit = a + s * ours, {'scale': float(s), 'offset': float(a)}
    return {'kind': 'points', 'datum': datum, 'datum_shift_m': shift, 'relative_fit': fit, 'overall': metrics(ours, ref) or
            {'n': len(pts), 'mae': float(np.nanmean(np.abs(ours - ref))), 'rmse': float(np.sqrt(np.nanmean((ours - ref) ** 2))),
             'bias': float(np.nanmean(ours - ref)), 'r': None},
            'points': [{'u': p['c'] / scene.shape[1], 'v': p['r'] / scene.shape[0], 'ref': float(z), 'ours': float(o)}
                       for p, z, o in zip(pts, ref, ours)],
            'scatter': {'ref': ref.round(2).tolist(), 'ours': ours.round(2).tolist()}}


def compare_icesat2(scene):
    """Our terrain and surface vs NASA ICESat-2 photons inside the scene, by photon class and landscape."""
    import terrain
    if not scene.crs or scene.dtm is None:
        raise ValueError('ICESat-2 needs a georeferenced scene with terrain')
    t = scene.meta.get('terrain', {})
    N = t.get('geoid_undulation_m')
    if N is None:
        raise ValueError('geoid height unknown for this scene (terrain was built offline)')
    with rasterio.open(scene.image_path) as img:
        bounds = transform_bounds(img.crs, 'EPSG:4326', *img.bounds)
    d = terrain.icesat2_photons(bounds)
    if not len(d['h']):
        return {'photons': 0, 'note': 'No ICESat-2 laser track crosses this scene (tracks are kilometres apart).'}
    xs, ys = warp_transform('EPSG:4326', scene.crs, d['lon'].tolist(), d['lat'].tolist())
    r, c = (np.asarray(v) for v in rasterio.transform.rowcol(scene.transform, xs, ys))
    inside = (r >= 0) & (r < scene.shape[0]) & (c >= 0) & (c < scene.shape[1])
    r, c = r[inside], c[inside]
    h = d['h'][inside] - N                                   # ellipsoidal -> m above sea level (EGM2008)
    cls = d['cls'][inside]
    if not len(h):
        return {'photons': 0, 'note': 'No ICESat-2 photons inside the image itself.'}
    off = (t.get('laser') or {}).get('offset_m')
    dtm_before = scene.dtm[r, c] + (off or 0)               # independent check: terrain before the laser levelling
    dsm = scene.dsm[r, c]
    g = cls == 1
    lc = scene.lc[r, c]
    slope = scene.slope[r, c] if scene.slope is not None else None
    res = {'photons': int(len(h)), 'ground_photons': int(g.sum()), 'passes': int(len(np.unique(d['track'][inside]))),
           'dates': [str(np.datetime64(int(d['t'][inside].min()), 's'))[:10], str(np.datetime64(int(d['t'][inside].max()), 's'))[:10]],
           'laser_shift_m': None if off is None else -off,
           'terrain_vs_ground': metrics(dtm_before[g], h[g]),
           'surface_vs_all': metrics(dsm, h)}
    res.update(breakdowns(dsm, h, lc, slope, np.clip(scene.h[r, c], 0, None)))
    keep = np.random.default_rng(0).choice(len(h), min(2500, len(h)), replace=False)
    res['photons_xy'] = {'u': (c[keep] / scene.shape[1]).round(4).tolist(), 'v': (r[keep] / scene.shape[0]).round(4).tolist(),
                         'h': h[keep].round(2).tolist(), 'ours': dsm[keep].round(2).tolist(), 'cls': cls[keep].astype(int).tolist()}
    res['scatter'] = {'ref': h[keep].round(2).tolist(), 'ours': dsm[keep].round(2).tolist()}
    return res


# ---------- ground control points ----------
def fit_gcp(scene, pts):
    """Fit z = ground + a + bx·u + by·v + s·height to the points (ground = our terrain, or 0 without one).
    Terms used: 1 point -> a; 2-3 -> a, s (if the points differ in height by >= 3 m); >= 4 -> a, bx, by (+ s)."""
    pts = point_pixels(scene, pts)
    n = len(pts)
    if n < 1:
        raise ValueError('no control points inside the scene')
    G = np.array([sample(scene.dtm, p['c'], p['r']) if scene.dtm is not None else 0.0 for p in pts])
    Hh = np.array([max(0.0, sample(scene.h, p['c'], p['r'])) for p in pts])
    U = np.array([p['c'] / scene.shape[1] - 0.5 for p in pts])
    V = np.array([p['r'] / scene.shape[0] - 0.5 for p in pts])
    Z = np.array([p['z'] for p in pts])
    use_s = n >= 2 and np.ptp(Hh) >= 3
    use_tilt = n >= 4 + use_s
    cols, names = [np.ones(n)], ['a']
    if use_tilt:
        cols += [U, V]; names += ['bx', 'by']
    if use_s:
        cols.append(Hh); names.append('s')
    A = np.stack(cols, 1)
    y = Z - G - (0 if use_s else Hh)

    def solve(A, y):
        return np.linalg.lstsq(A, y, rcond=None)[0]
    coef = dict(zip(names, solve(A, y)))
    warn = None
    if use_s and not 0.3 <= coef['s'] <= 3:   # implausible scale: keep the model's metric heights
        warn = f"fitted height scale {coef['s']:.2f} is implausible, kept 1.0"
        cols, names = cols[:-1], names[:-1]
        A, y = np.stack(cols, 1), Z - G - Hh
        coef, use_s = dict(zip(names, solve(A, y))), False
    p = {'a': float(coef.get('a', 0)), 'bx': float(coef.get('bx', 0)), 'by': float(coef.get('by', 0)), 's': float(coef.get('s', 1))}
    pred = G + p['a'] + p['bx'] * U + p['by'] * V + p['s'] * Hh
    loo = None
    if n > len(names):   # leave-one-out: refit without each point and predict it
        errs = []
        for i in range(n):
            m = np.arange(n) != i
            c = solve(A[m], y[m])
            errs.append(float(A[i] @ c - y[i]))
        loo = {'rmse': float(np.sqrt(np.mean(np.square(errs)))), 'mae': float(np.mean(np.abs(errs)))}
    before = G + Hh
    return dict(p, terms=names, n=n, warning=warn, loo=loo, absolute=scene.dtm is None,
                points=[{'u': float(u + 0.5), 'v': float(v + 0.5), 'z': float(z), 'before': float(b), 'after': float(q)}
                        for u, v, z, b, q in zip(U, V, Z, before, pred)],
                rmse_before=float(np.sqrt(np.mean((before - Z) ** 2))) if scene.dtm is not None else None,
                rmse_after=float(np.sqrt(np.mean((pred - Z) ** 2))))


def apply_gcp(scene, p):
    """Calibrated DSM on the full image grid."""
    H, W = scene.shape
    U = (np.arange(W) + 0.5)[None, :] / W - 0.5
    V = (np.arange(H) + 0.5)[:, None] / H - 0.5
    ground = scene.dtm if scene.dtm is not None else 0.0
    return (ground + p['a'] + p['bx'] * U + p['by'] * V + p['s'] * np.clip(scene.h, 0, None)).astype(np.float32)


if __name__ == '__main__':
    # self-checks on synthetic numbers (no scene needed)
    rng = np.random.default_rng(1)
    ref = rng.uniform(0, 30, 5000)
    m = metrics(ref + 1.0, ref)
    assert abs(m['bias'] - 1) < 1e-9 and abs(m['mae'] - 1) < 1e-9 and abs(m['r'] - 1) < 1e-9 and m['within_2m_pct'] == 100
    m = metrics(ref + rng.normal(0, 2, ref.size), ref)
    assert 1.8 < m['rmse'] < 2.2 and m['r'] > 0.95, m
    assert metrics(np.ones(5), np.ones(5)) is None

    class Fake:   # flat 100 m terrain sloping east, 10 m building in the middle; truth: +3 m offset, heights ×1.2
        shape = (100, 100); crs = None; transform = rasterio.Affine(1, 0, 0, 0, -1, 0)
        dtm = np.fromfunction(lambda r, c: 100 + 0.02 * c, (100, 100)).astype(np.float32)
        h = np.zeros((100, 100), np.float32); h[40:60, 40:60] = 10
    f = Fake()
    truth = lambda c, r: f.dtm[int(r), int(c)] + 3 + 1.2 * f.h[int(r), int(c)]
    pts = [{'col': c, 'row': r, 'z': truth(c, r)} for c, r in [(10, 10), (90, 15), (50, 50), (15, 85), (85, 80), (45, 55)]]
    p = fit_gcp(f, pts)
    assert abs(p['a'] - 3) < 0.05 and abs(p['s'] - 1.2) < 0.01 and p['rmse_after'] < 0.05, p
    assert np.abs(apply_gcp(f, p)[50, 50] - truth(50, 50)) < 0.1
    p1 = fit_gcp(f, pts[:1])
    assert p1['terms'] == ['a'] and abs(p1['a'] - 3) < 0.05
    assert read_points('lon,lat,z\n76.1,30.2,350\n') == [{'lon': 76.1, 'lat': 30.2, 'z': 350.0}]
    assert read_points('col,row,elev\n5,6,7\n') == [{'col': 5.0, 'row': 6.0, 'z': 7.0}]
    print('validate.py self-check ok')
