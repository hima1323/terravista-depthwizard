"""Server-side analysis tools behind the viewer's newer cards (all on saved results, no model run):

  change()            before / after images: height change per building (collapsed / damaged / intact / new) and
                      canopy loss, both scenes put on the after scene's grid (reprojected, then aligned by phase
                      correlation of the photos)
  observed_flood()    an observed water mask (Sentinel-1 backscatter in dB or linear, or any 0/1 mask) on the grid
  mosaic_arrays()     several georeferenced scenes merged into one (image + model outputs), for larger areas
  footprints() / geojson() / cityjson()   building blocks as GeoJSON footprints or CityJSON LOD1 solids
  conformal()         turns the 4-flip spread into calibrated error bars (split conformal) from a validation
  fit_tree_scale() / apply_class_scale()   tall-object fixes: per-class height scale for buildings and trees
  wms_overlay()       a WMS map (OpenStreetMap, ISRO Bhuvan, ...) fetched for the scene and warped onto its grid
  gnss_points()       GNSS / GPS points (CSV, GPX, field app) -> image position + height above sea level (EGM2008)
"""
import io, json, math, os, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject, transform as warp_transform, transform_bounds

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(ROOT, 'demo', 'results')
BUILDING, TREES = 7, 4     # land-cover classes (infer_height.LANDCOVER)


def r(name, sfx):
    return os.path.join(RESULTS, name + sfx)


def load_meta(name):
    return json.load(open(r(name, '.json')))


def grid_f32(name, sfx, meta):
    return np.fromfile(r(name, sfx), '<f4').reshape(meta['grid_h'], meta['grid_w'])


def grid_geo(image_path, meta):
    """(crs, transform) of the browser grid of a scene, or (None, None) without georeferencing."""
    with rasterio.open(image_path) as src:
        if not src.crs:
            return None, None
        return src.crs, src.transform * Affine.scale(src.width / meta['grid_w'], src.height / meta['grid_h'])


def onto(arr, src_geo, dst_geo, shape, how):
    out = np.full(shape, np.nan, np.float32)
    reproject(arr.astype(np.float32), out, src_transform=src_geo[1], src_crs=src_geo[0], dst_transform=dst_geo[1],
              dst_crs=dst_geo[0], src_nodata=np.nan, dst_nodata=np.nan, resampling=how)
    return out


def gray_photo(name, gw, gh):
    p = cv2.imread(r(name, '.jpg'), cv2.IMREAD_GRAYSCALE)
    return cv2.resize(p, (gw, gh), interpolation=cv2.INTER_AREA).astype(np.float32)


# ---------------------------------------------------------------- before / after change
def change(after, after_path, before, before_path):
    """Height change from `before` to `after` on the after scene's grid. Writes <after>_dh.f32 (after - before, m)
    and <after>_bidb.f32 (before building ids on this grid). Returns per-building before/after medians; the viewer
    classifies them (so its thresholds can change without a new run)."""
    ma, mb = load_meta(after), load_meta(before)
    gw, gh = ma['grid_w'], ma['grid_h']
    ha, hb = grid_f32(after, '.f32', ma), grid_f32(before, '.f32', mb)
    bidb, lcb = grid_f32(before, '_bid.f32', mb), grid_f32(before, '_lc.f32', mb) if os.path.exists(r(before, '_lc.f32')) else None
    ga, gb = grid_geo(after_path, ma), grid_geo(before_path, mb)
    notes = []
    pb = gray_photo(before, mb['grid_w'], mb['grid_h'])
    if ga[0] is not None and gb[0] is not None:
        how = 'reprojected onto the after scene (both georeferenced)'
        put = lambda a, m: onto(a, gb, ga, (gh, gw), m)
        hb2, bid2, pb2 = put(hb, Resampling.bilinear), put(bidb, Resampling.nearest), put(pb, Resampling.bilinear)
        lc2 = put(lcb, Resampling.nearest) if lcb is not None else None
    else:
        how = 'matched pixel to pixel (resized; assumes both images cover the same area)'
        if abs(mb['width'] / mb['height'] - ma['width'] / ma['height']) > 0.02 * ma['width'] / ma['height']:
            notes.append('the two images have different shapes: without georeferencing they must cover the same area')
        rs = lambda a, m: cv2.resize(a.astype(np.float32), (gw, gh), interpolation=m)
        hb2, bid2, pb2 = rs(hb, cv2.INTER_LINEAR), rs(bidb, cv2.INTER_NEAREST), rs(pb, cv2.INTER_LINEAR)
        lc2 = rs(lcb, cv2.INTER_NEAREST) if lcb is not None else None
    # fine alignment: the photos' phase correlation (georeferencing of two images often differs by a few metres)
    ok = np.isfinite(pb2)
    if ok.mean() < 0.2:
        raise ValueError('the before image does not overlap this scene')
    pa = gray_photo(after, gw, gh)
    fill = float(np.nanmean(pb2))
    win = cv2.createHanningWindow((gw, gh), cv2.CV_32F)
    (sx, sy), resp = cv2.phaseCorrelate(np.where(ok, pb2, fill).astype(np.float32), pa, win)
    shift = None
    if resp > 0.05 and 0.5 <= math.hypot(sx, sy) <= 0.1 * max(gw, gh):
        M = np.float32([[1, 0, sx], [0, 1, sy]])
        warp = lambda a, i: cv2.warpAffine(a, M, (gw, gh), flags=i, borderMode=cv2.BORDER_CONSTANT, borderValue=np.nan)
        hb2, bid2 = warp(hb2, cv2.INTER_LINEAR), warp(bid2, cv2.INTER_NEAREST)
        lc2 = warp(lc2, cv2.INTER_NEAREST) if lc2 is not None else None
        cell = ma['width'] * ma['gsd'] / gw
        shift = {'dx_m': round(float(sx) * cell, 2), 'dy_m': round(float(sy) * cell, 2), 'response': round(float(resp), 3)}
    dh = (ha - hb2).astype(np.float32)
    dh.astype('<f4').tofile(r(after, '_dh.f32'))
    bid2 = np.nan_to_num(bid2, nan=0).round().astype(np.float32)
    bid2.astype('<f4').tofile(r(after, '_bidb.f32'))
    cell_m2 = (ma['width'] * ma['gsd'] / gw) * (ma['height'] * ma['gsd'] / gh)
    blocks_b = {b['id']: b for b in json.load(open(r(before, '_buildings.json')))}
    out = []
    flat_b, flat_a, flat_id = hb2.ravel(), ha.ravel(), bid2.ravel().astype(np.int64)
    order = np.argsort(flat_id, kind='stable')
    counts = np.bincount(flat_id)
    starts = np.cumsum(counts) - counts
    for k in range(1, len(counts)):
        pix = order[starts[k]:starts[k] + counts[k]]
        if len(pix) < 3 or k not in blocks_b:
            continue
        bb, aa = flat_b[pix], flat_a[pix]
        good = np.isfinite(bb)
        if good.mean() < 0.5:
            continue
        x, y = pix % gw, pix // gw
        out.append({'id': int(k), 'cells': int(len(pix)), 'area_m2': round(len(pix) * cell_m2, 1),
                    'before_m': round(float(np.median(bb[good])), 2), 'after_m': round(float(np.median(aa[good])), 2),
                    'floors': blocks_b[k].get('floors', 1),
                    'cx': round(float(x.mean() + 0.5) / gw, 4), 'cy': round(float(y.mean() + 0.5) / gh, 4)})
    # new structures: after blocks standing where the before scene had (almost) nothing
    bida = grid_f32(after, '_bid.f32', ma).ravel().astype(np.int64)
    new = []
    for b in json.load(open(r(after, '_buildings.json'))):
        sel = bida == b['id']
        bb = flat_b[sel]
        bb = bb[np.isfinite(bb)]
        if len(bb) >= 3 and np.median(bb) < 1.5 and b['height_m'] >= 3 and (bid2.ravel()[sel] > 0).mean() < 0.2:
            new.append({'id': b['id'], 'height_m': b['height_m'], 'area_m2': b['area_m2'], 'cx': b['cx'], 'cy': b['cy']})
    canopy = None
    lca = grid_f32(after, '_lc.f32', ma) if os.path.exists(r(after, '_lc.f32')) else None
    if lc2 is not None and lca is not None:
        was = (lc2 == TREES) & (hb2 >= 3)
        lost = was & ((ha < 0.4 * hb2) | (lca != TREES))
        canopy = {'before_m2': round(float(was.sum()) * cell_m2), 'lost_m2': round(float(lost.sum()) * cell_m2)}
    fin = np.isfinite(dh)
    nonb = fin & (bid2 == 0)
    return {'before': before, 'matched': how, 'shift': shift, 'notes': notes, 'cell_m2': cell_m2,
            'coverage_pct': round(100 * float(fin.mean()), 1), 'buildings': out, 'new': new, 'canopy': canopy,
            'ground_lost_m3': round(float(np.clip(-dh[nonb], 0, None).sum() * cell_m2)),
            'ground_gained_m3': round(float(np.clip(dh[nonb], 0, None).sum() * cell_m2))}


# ---------------------------------------------------------------- observed flood (e.g. Sentinel-1)
def otsu(v, lo, hi):
    hist, edges = np.histogram(np.clip(v, lo, hi), bins=256, range=(lo, hi))
    p = hist / max(1, hist.sum())
    mids = (edges[:-1] + edges[1:]) / 2
    w0, m0 = np.cumsum(p), np.cumsum(p * mids)
    mt = m0[-1]
    between = (mt * w0 - m0) ** 2 / np.maximum(w0 * (1 - w0), 1e-12)
    return float(mids[int(np.argmax(between))])


def observed_flood(name, image_path, ref_path, kind='auto', threshold=None):
    """Observed water on the browser grid (1 water, 0 dry, NaN no data) -> <name>_obsflood.f32.
    kind: 'mask' (water = value > 0), 'db' (radar backscatter in dB: water = below threshold, default Otsu between
    -30 and 0 dB, else -18 dB), 'linear' (backscatter in linear power, converted to dB), or 'auto'."""
    meta = load_meta(name)
    gw, gh = meta['grid_w'], meta['grid_h']
    geo = grid_geo(image_path, meta)
    with rasterio.open(ref_path) as src:
        a = src.read(1).astype(np.float32)
        if src.nodata is not None:
            a[a == src.nodata] = np.nan
        sgeo = (src.crs, src.transform)
    v = a[np.isfinite(a)]
    if not v.size:
        raise ValueError('the file has no valid pixels')
    uniq = np.unique(v[:: max(1, v.size // 100000)])
    if kind == 'auto':
        kind = 'mask' if len(uniq) <= 3 and set(uniq.tolist()) <= {0.0, 1.0, 255.0} else 'db' if np.median(v) < 0 else 'linear'
    if kind == 'linear':
        a = 10 * np.log10(np.clip(a, 1e-6, None))
        kind = 'db'
    used = None
    if kind == 'db':
        vv = a[np.isfinite(a)]
        used = float(threshold) if threshold not in (None, '') else otsu(vv, -30, 0)
        if threshold in (None, '') and not -24 <= used <= -12:   # no clear water peak: the usual VV threshold
            used = -18.0
        water = np.where(np.isfinite(a), (a < used).astype(np.float32), np.nan)
    else:
        water = np.where(np.isfinite(a), (a > 0).astype(np.float32), np.nan)
    if geo[0] is not None and sgeo[0] is not None:
        g = onto(water, sgeo, geo, (gh, gw), Resampling.average)
        how = 'reprojected onto the scene'
    else:
        g = cv2.resize(water, (gw, gh), interpolation=cv2.INTER_AREA)
        how = 'resized to the scene (no georeferencing: must cover the same area)'
    g = np.where(np.isfinite(g), (g >= 0.5).astype(np.float32), np.nan).astype(np.float32)
    if np.isfinite(g).mean() < 0.05:
        raise ValueError('the observed flood map does not overlap this scene')
    g.astype('<f4').tofile(r(name, '_obsflood.f32'))
    fin = np.isfinite(g)
    return {'kind': kind, 'threshold_db': used, 'matched': how, 'file': os.path.basename(ref_path),
            'coverage_pct': round(100 * float(fin.mean()), 1), 'water_pct': round(100 * float(np.nansum(g) / max(1, fin.sum())), 1)}


# ---------------------------------------------------------------- mosaics
def mosaic_arrays(sources, max_px=12000):
    """sources = [(image_path, name)] of processed, georeferenced scenes -> (rgb HxWx3, h, unc, lc, profile).
    Scenes in another coordinate system are warped onto the first one's. Overlaps keep the first scene listed."""
    from rasterio.merge import merge
    from rasterio.vrt import WarpedVRT
    with rasterio.open(sources[0][0]) as first:
        crs = first.crs
        res = (abs(first.transform.a), abs(first.transform.e))
    if not crs:
        raise ValueError('mosaics need georeferenced (GeoTIFF) scenes')

    def stack(paths, band_count, method='first'):
        ds = []
        try:
            for p in paths:
                s = rasterio.open(p)
                if not s.crs:
                    raise ValueError(f'{os.path.basename(p)} has no georeferencing')
                ds.append(s if s.crs == crs else WarpedVRT(s, crs=crs))
            return merge(ds, res=res, indexes=list(range(1, band_count + 1)), method=method, nodata=0)
        finally:
            for s in ds:
                s.close()

    from utils import geo_func
    imgs = []
    for p, _ in sources:   # photos as 8-bit RGB first, so band order / bit depth are handled per scene
        with rasterio.open(p) as s:
            prof = s.profile.copy()
        rgb = geo_func.load_multiband(p)
        prof.update(driver='GTiff', count=3, dtype='uint8', nodata=None, photometric='RGB')
        mem = rasterio.MemoryFile()
        with mem.open(**prof) as dst:
            dst.write(np.moveaxis(rgb, -1, 0))
        imgs.append(mem)
    try:
        ds = [m.open() for m in imgs]
        ds = [d if d.crs == crs else WarpedVRT(d, crs=crs) for d in ds]
        rgb, tr = merge(ds, res=res, nodata=0)
        for d in ds:
            d.close()
    finally:
        for m in imgs:
            m.close()
    if max(rgb.shape[1:]) > max_px:
        raise ValueError(f'mosaic would be {rgb.shape[2]}×{rgb.shape[1]} px (limit {max_px}); use fewer scenes')
    out = {}
    for sfx in ('_height.tif', '_uncertainty.tif', '_landcover.tif'):
        a, _ = stack([r(n, sfx) for _, n in sources], 1)
        if a.shape[1:] != rgb.shape[1:]:
            raise ValueError('the scenes\' results do not line up with their images; re-process them first')
        out[sfx] = a[0]
    profile = dict(driver='GTiff', height=rgb.shape[1], width=rgb.shape[2], count=3, dtype='uint8', crs=crs, transform=tr,
                   photometric='RGB')
    return np.moveaxis(rgb, 0, -1), out['_height.tif'], out['_uncertainty.tif'], out['_landcover.tif'].astype(np.uint8), profile


# ---------------------------------------------------------------- 3D city / footprint export
def _crs_for_metres(src):
    """The scene's CRS if projected, else its UTM zone (CityJSON wants metres)."""
    if src.crs.is_projected:
        return src.crs
    w, s, e, n = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
    lon, lat = (w + e) / 2, (s + n) / 2
    return rasterio.crs.CRS.from_epsg((32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1)


def footprints(name, image_path):
    """Building blocks as polygons: [(block, ring of (x, y) in the scene CRS or local metres)], crs (None = local)."""
    meta = load_meta(name)
    gw, gh = meta['grid_w'], meta['grid_h']
    bid = grid_f32(name, '_bid.f32', meta).astype(np.int32)
    blocks = json.load(open(r(name, '_buildings.json')))
    scale = meta_class_scale(meta).get('buildings', 1.0)
    gcp = meta.get('gcp')
    with rasterio.open(image_path) as src:
        crs, tr = src.crs, src.transform
        W, H = src.width, src.height
    sx, sy = W / gw, H / gh
    out = []
    for b in blocks:
        m = (bid == b['id']).astype(np.uint8)
        if not m.any():
            continue
        cs, _ = cv2.findContours(cv2.resize(m, (gw * 2, gh * 2), interpolation=cv2.INTER_NEAREST), cv2.RETR_EXTERNAL,
                                 cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea)
        c = cv2.approxPolyDP(c, 1.0, True)[:, 0, :].astype(np.float64) / 2   # grid cells (outline at cell edges)
        if len(c) < 3:
            continue
        cols, rows = c[:, 0] * sx, c[:, 1] * sy
        if crs:
            xs, ys = tr * (cols, rows)
        else:
            xs, ys = cols * meta['gsd'], -rows * meta['gsd']
        h = b['height_m'] * scale
        ground = b.get('ground_m', 0.0) or 0.0
        if gcp:
            h *= gcp['s']
            ground += gcp['a'] + gcp['bx'] * (b['cx'] - 0.5) + gcp['by'] * (b['cy'] - 0.5)
        out.append((dict(b, height_m=round(h, 2), ground_m=round(ground, 2), roof_m=round(ground + h, 2),
                         floors=max(1, round(h / meta.get('floor_m', 3.0)))), list(zip(np.asarray(xs), np.asarray(ys)))))
    return out, crs, meta


def _ccw(ring):
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))
    return ring if a > 0 else ring[::-1]


def geojson(name, image_path):
    polys, crs, meta = footprints(name, image_path)
    feats = []
    for b, ring in polys:
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        if crs:
            xs, ys = warp_transform(crs, 'EPSG:4326', xs, ys)
        pts = _ccw([(round(x, 7), round(y, 7)) for x, y in zip(xs, ys)])
        feats.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [[list(p) for p in pts + pts[:1]]]},
                      'properties': {k: b.get(k) for k in ('id', 'height_m', 'ground_m', 'roof_m', 'floors', 'area_m2', 'unc_m')}})
    fc = {'type': 'FeatureCollection', 'name': f'{name} building blocks (DepthWizard)', 'features': feats}
    if not crs:
        fc['note'] = 'image has no georeferencing: coordinates are local metres from the top-left corner (y = -row)'
    return fc


def cityjson(name, image_path):
    """CityJSON 1.1, one LOD1 Building (extruded footprint, ground to roof) per block, in metres."""
    polys, crs, meta = footprints(name, image_path)
    dst = None
    if crs:
        with rasterio.open(image_path) as src:
            dst = _crs_for_metres(src)
    verts, objs = [], {}
    for b, ring in polys:
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        if crs and dst != crs:
            xs, ys = warp_transform(crs, dst, xs, ys)
        ring2 = _ccw(list(zip(xs, ys)))
        n, base = len(ring2), len(verts)
        z0, z1 = b['ground_m'], b['roof_m']
        verts += [[x, y, z0] for x, y in ring2] + [[x, y, z1] for x, y in ring2]
        bottom = [[base + i for i in range(n)][::-1]]
        top = [[base + n + i for i in range(n)]]
        walls = [[[base + i, base + (i + 1) % n, base + n + (i + 1) % n, base + n + i]] for i in range(n)]
        objs[f"block-{b['id']}"] = {'type': 'Building', 'attributes': {
            'measuredHeight': b['height_m'], 'storeysAboveGround': b['floors'], 'footprintArea_m2': b['area_m2'],
            'heightUncertainty_m': b.get('unc_m'), 'groundLevel_m': z0, 'source': 'DepthWizard RS3DAda single-image estimate'},
            'geometry': [{'type': 'Solid', 'lod': '1', 'boundaries': [[bottom, top] + walls]}]}
    if not verts:
        raise ValueError('no building blocks in this scene')
    V = np.array(verts)
    lo = V.min(0)
    q = np.round((V - lo) / 0.001).astype(np.int64)
    doc = {'type': 'CityJSON', 'version': '1.1', 'transform': {'scale': [0.001, 0.001, 0.001], 'translate': lo.round(3).tolist()},
           'metadata': {'title': f'{name} building blocks (LOD1, DepthWizard)'}, 'CityObjects': objs, 'vertices': q.tolist()}
    if dst:
        doc['metadata']['referenceSystem'] = f'https://www.opengis.net/def/crs/EPSG/0/{dst.to_epsg()}'
    return doc


# ---------------------------------------------------------------- calibrated error bars (split conformal)
U0 = 0.25    # m added to the 4-flip spread so pixels where the flips agree still get a band
LEVELS = (0.68, 0.9, 0.95)


def conformal(err, unc, u0=U0, levels=LEVELS, seed=0):
    """Scale factors k so that |ours - reference| <= k·(spread + u0) for a share `level` of the pixels (split conformal:
    k from a random half, coverage checked on the other half). None with fewer than 30 pairs."""
    e, u = np.abs(np.asarray(err, np.float64).ravel()), np.asarray(unc, np.float64).ravel()
    ok = np.isfinite(e) & np.isfinite(u)
    e, u = e[ok], np.clip(u[ok], 0, None)
    if e.size < 30:
        return None
    if e.size > 400000:
        keep = np.random.default_rng(seed).choice(e.size, 400000, replace=False)
        e, u = e[keep], u[keep]
    s = e / (u + u0)
    perm = np.random.default_rng(seed).permutation(s.size)
    cal, test = perm[: s.size // 2], perm[s.size // 2:]
    q = lambda v, L: float(np.quantile(v, min(1.0, math.ceil((v.size + 1) * L) / v.size), method='higher'))
    out = {'u0': u0, 'n': int(s.size), 'levels': {}}
    for L in levels:
        k_cal = q(s[cal], L)
        out['levels'][f'{L:.2f}'] = {'k': q(s, L), 'coverage_check_pct': round(100 * float((s[test] <= k_cal).mean()), 1),
                                     'median_band_m': round(q(s, L) * float(np.median(u + u0)), 2)}
    return out


# ---------------------------------------------------------------- tall-object fixes (per-class height scale)
def meta_class_scale(meta):
    cs = meta.get('class_scale') or {}
    return {'buildings': float(cs.get('buildings', 1.0)), 'trees': float(cs.get('trees', 1.0))}


def scaled_heights(h, lc, scales):
    k = np.ones(h.shape, np.float32)
    k[lc == BUILDING] = scales.get('buildings', 1.0)
    k[lc == TREES] = scales.get('trees', 1.0)
    return (np.clip(h, 0, None) * k).astype(np.float32)


def fit_tree_scale(scene, photons=None):
    """Tree height scale from NASA ICESat-2 top-of-canopy photons (ATL08 class 3) over the model's tree pixels:
    canopy height = photon height (m a.s.l.) - our laser-levelled terrain. k = median(canopy / model height)."""
    import terrain
    if not scene.crs or scene.dtm is None:
        raise ValueError('needs a georeferenced scene with terrain')
    N = scene.meta.get('terrain', {}).get('geoid_undulation_m')
    if N is None:
        raise ValueError('geoid height unknown for this scene (terrain was built offline)')
    if photons is None:
        with rasterio.open(scene.image_path) as img:
            photons = terrain.icesat2_photons(transform_bounds(img.crs, 'EPSG:4326', *img.bounds))
    d = photons
    top = d['cls'] == 3
    if not top.any():
        raise ValueError('no ICESat-2 top-of-canopy photons in this scene')
    xs, ys = warp_transform('EPSG:4326', scene.crs, d['lon'][top].tolist(), d['lat'][top].tolist())
    rr, cc = (np.asarray(v) for v in rasterio.transform.rowcol(scene.transform, xs, ys))
    inside = (rr >= 0) & (rr < scene.shape[0]) & (cc >= 0) & (cc < scene.shape[1])
    rr, cc, hp = rr[inside], cc[inside], d['h'][top][inside] - N
    tree = scene.lc[rr, cc] == TREES
    ref = hp[tree] - scene.dtm[rr[tree], cc[tree]]
    ours = np.clip(scene.h_raw[rr[tree], cc[tree]], 0, None)
    ok = (ours >= 2) & (ref >= 2) & (ref <= 80)
    if ok.sum() < 30:
        raise ValueError(f'{int(ok.sum())} usable canopy photons over trees (need 30)')
    ratio = ref[ok] / ours[ok]
    k = float(np.clip(np.median(ratio), 0.5, 3.0))
    return {'k': round(k, 3), 'n': int(ok.sum()), 'canopy_median_m': round(float(np.median(ref[ok])), 2),
            'model_median_m': round(float(np.median(ours[ok])), 2),
            'mae_before': round(float(np.abs(ours[ok] - ref[ok]).mean()), 2), 'mae_after': round(float(np.abs(k * ours[ok] - ref[ok]).mean()), 2)}


def apply_class_scale(name, image_path, scales, save):
    """Write <name>_height_fixed.tif (and _dsm_fixed.tif with terrain); save = infer_height.save_tiff_with_geo_info."""
    h = rasterio.open(r(name, '_height.tif')).read(1)
    lc = rasterio.open(r(name, '_landcover.tif')).read(1).astype(np.uint8)
    hf = scaled_heights(h, lc, scales)
    save(image_path, r(name, '_height_fixed.tif'), hf)
    if os.path.exists(r(name, '_dtm.tif')):
        save(image_path, r(name, '_dsm_fixed.tif'), rasterio.open(r(name, '_dtm.tif')).read(1) + hf)
    return {'max': float(hf.max()), 'p99': float(np.percentile(hf, 99))}


# ---------------------------------------------------------------- WMS map overlays
def wms_overlay(name, image_path, url, layers, styles='', fmt='image/png', fetch=None):
    """GetMap (WMS 1.1.1, EPSG:4326, so no axis-order surprises) for the scene's bounds, warped onto the photo's
    pixel grid and saved as <name>_wms.png. fetch(url) -> bytes can be swapped for tests."""
    if not re.match(r'^https?://', url or ''):
        raise ValueError('the WMS address must start with http:// or https://')
    meta = load_meta(name)
    with rasterio.open(image_path) as src:
        if not src.crs:
            raise ValueError('map overlays need a georeferenced (GeoTIFF) scene')
        crs, tr, W, H = src.crs, src.transform, src.width, src.height
        w, s, e, n = transform_bounds(crs, 'EPSG:4326', *src.bounds)
    k = min(1.0, 2048 / max(W, H))
    ow, oh = max(1, round(W * k)), max(1, round(H * k))
    rw = min(2048, max(256, ow))
    rh = max(1, round(rw * (n - s) / max(e - w, 1e-12) / max(math.cos(math.radians((s + n) / 2)), 0.1)))
    rh = min(rh, 2048)
    q = {'SERVICE': 'WMS', 'VERSION': '1.1.1', 'REQUEST': 'GetMap', 'LAYERS': layers, 'STYLES': styles or '',
         'SRS': 'EPSG:4326', 'BBOX': f'{w},{s},{e},{n}', 'WIDTH': rw, 'HEIGHT': rh, 'FORMAT': fmt, 'TRANSPARENT': 'TRUE'}
    full = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(q)
    if fetch is None:
        def fetch(u):
            req = urllib.request.Request(u, headers={'User-Agent': 'DepthWizard/2 (offline-first viewer)'})
            with urllib.request.urlopen(req, timeout=40) as resp:
                if 'image' not in resp.headers.get('Content-Type', ''):
                    raise ValueError(f"the server did not return an image: {resp.read(300).decode('utf-8', 'replace')}")
                return resp.read(30 << 20)
    from PIL import Image
    img = np.asarray(Image.open(io.BytesIO(fetch(full))).convert('RGBA'), np.float32)
    src_t = rasterio.transform.from_bounds(w, s, e, n, img.shape[1], img.shape[0])
    dst_t = tr * Affine.scale(W / ow, H / oh)
    out = np.zeros((4, oh, ow), np.float32)
    for b in range(4):
        reproject(img[:, :, b], out[b], src_transform=src_t, src_crs='EPSG:4326', dst_transform=dst_t, dst_crs=crs,
                  resampling=Resampling.bilinear)
    Image.fromarray(np.moveaxis(out, 0, -1).clip(0, 255).astype(np.uint8), 'RGBA').save(r(name, '_wms.png'))
    return {'url': f'/results/{name}_wms.png', 'layers': layers, 'service': url.split('?')[0], 'size': [ow, oh]}


# ---------------------------------------------------------------- GNSS / GPS / field points
def parse_gnss(text):
    """CSV (lat/lon/alt or ele columns, any order) or GPX (wpt / trkpt with ele) -> [{lon, lat, z, note}]."""
    t = text.strip()
    pts = []
    if t.startswith('<'):
        root = ET.fromstring(t)
        for el in root.iter():
            if el.tag.split('}')[-1] in ('wpt', 'trkpt', 'rtept'):
                ele = next((c.text for c in el if c.tag.split('}')[-1] == 'ele'), None)
                nm = next((c.text for c in el if c.tag.split('}')[-1] == 'name'), '')
                if ele is not None:
                    pts.append({'lon': float(el.get('lon')), 'lat': float(el.get('lat')), 'z': float(ele), 'note': nm or ''})
        return pts
    import csv
    rows = list(csv.reader(io.StringIO(t)))
    head = [h.strip().lower() for h in rows[0]]
    pick = lambda *ns: next((head.index(n) for n in ns if n in head), None)
    ilon, ilat = pick('lon', 'longitude', 'lng', 'x'), pick('lat', 'latitude', 'y')
    iz = pick('alt', 'altitude', 'ele', 'elevation', 'z', 'height', 'h')
    inote = pick('name', 'note', 'id', 'label')
    if None in (ilon, ilat, iz):
        raise ValueError('CSV needs columns lat, lon and alt (or ele / z / height)')
    for row in rows[1:]:
        try:
            pts.append({'lon': float(row[ilon]), 'lat': float(row[ilat]), 'z': float(row[iz]),
                        'note': row[inote] if inote is not None and inote < len(row) else ''})
        except (ValueError, IndexError):
            continue
    return pts


def gnss_points(scene, pts, datum):
    """Points with u, v (0..1 image position) and z in m above sea level (EGM2008), inside the scene only.
    datum: 'ellipsoid' (raw GNSS / phone GPS: the W3C geolocation altitude is ellipsoidal), 'egm96' or 'egm2008'."""
    import validate
    if not scene.crs:
        raise ValueError('GNSS points need a georeferenced (GeoTIFF) scene')
    shift = validate.datum_shift(scene, datum)
    if datum == 'ellipsoid' and not shift:
        raise ValueError('geoid height unknown for this scene, cannot convert ellipsoidal heights; choose a sea-level datum')
    out = []
    for p in validate.point_pixels(scene, pts):
        out.append({'u': p['c'] / scene.shape[1], 'v': p['r'] / scene.shape[0], 'z': round(p['z'] + shift, 3),
                    'note': p.get('note', ''), 'lon': p['lon'], 'lat': p['lat']})
    return {'points': out, 'datum': datum, 'datum_shift_m': shift, 'outside': len(pts) - len(out)}


def corners_lonlat(image_path):
    """Lon/lat of the image corners (top-left, top-right, bottom-right, bottom-left), or None."""
    with rasterio.open(image_path) as src:
        if not src.crs:
            return None
        W, H = src.width, src.height
        xs, ys = src.transform * (np.array([0, W, W, 0]), np.array([0, 0, H, H]))
        lon, lat = warp_transform(src.crs, 'EPSG:4326', list(xs), list(ys))
    return [[round(a, 7), round(b, 7)] for a, b in zip(lon, lat)]


if __name__ == '__main__':
    rng = np.random.default_rng(0)
    # conformal: errors ~ N(0, 2·spread) -> k90 ≈ 2·1.645 (with u0 = 0)
    u = rng.uniform(0.5, 3, 20000)
    c = conformal(rng.normal(0, 2 * u), u, u0=0.0)
    k = c['levels']['0.90']['k']
    assert 3.0 < k < 3.6 and 88 < c['levels']['0.90']['coverage_check_pct'] < 92, c
    assert conformal(np.ones(5), np.ones(5)) is None
    # Otsu between two backscatter populations
    v = np.r_[rng.normal(-22, 1.5, 5000), rng.normal(-8, 2, 15000)]
    t = otsu(v, -30, 0)
    assert -19 < t < -11, t
    # GPX + CSV parsing
    gpx = '<gpx xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="30.1" lon="76.2"><ele>350.5</ele><name>BM1</name></wpt></gpx>'
    assert parse_gnss(gpx) == [{'lon': 76.2, 'lat': 30.1, 'z': 350.5, 'note': 'BM1'}]
    assert parse_gnss('name,latitude,longitude,altitude\nP1,30,76,300\n')[0] == {'lon': 76.0, 'lat': 30.0, 'z': 300.0, 'note': 'P1'}
    # per-class height scale
    h = np.array([[10, 10], [5, 1]], np.float32)
    lc = np.array([[BUILDING, TREES], [0, BUILDING]], np.uint8)
    assert np.allclose(scaled_heights(h, lc, {'buildings': 1.5, 'trees': 2}), [[15, 20], [5, 1.5]])
    assert _ccw([(0, 0), (0, 1), (1, 1), (1, 0)]) == [(1, 0), (1, 1), (0, 1), (0, 0)]
    print('tools.py self-check ok')
