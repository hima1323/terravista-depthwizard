"""Evaluation protocol v2, Indian side (plan step 2): a non-circular, baselined accuracy check of the 8 landscape scenes
of demo/landscape_benchmark.py against NASA ICESat-2 photons and GEDI L2A footprints, without the app server.

usage (from SynRS3D/, with the venv python):
  python demo/india_eval_v2.py prepare [name ...]   network only: laser window, Esri image + its acquisition date,
                                                    ICESat-2 photons (+ATL08 segment fields), GEDI L2A, OSM buildings,
                                                    FABDEM tile. Cached in demo/benchmark/v2/scenes/
  lockf -k -t 14400 <model.lock> python demo/india_eval_v2.py predict      the height model, all scenes, one batch
  python demo/india_eval_v2.py terrain              DTM / DSM exactly as app.ensure_terrain (terrain.build_dtm +
                                                    terrain.laser_correct), cached before and after levelling
  python demo/india_eval_v2.py evaluate             -> demo/benchmark/v2/india_v2.json + india_v2.md
  python demo/india_eval_v2.py report               -> india_v2.md again from india_v2.json (no recompute)
  python demo/india_eval_v2.py --selftest           offline asserts
Protocols per scene (ICESat-2 passes = rgt + cycle, split by validate.split_passes: time-sorted, alternating):
  (i) no levelling: terrain straight from terrain.build_dtm; (ii) held-out: levelled (terrain.laser_offset) on the
  levelling passes, checked on the validation passes only; (iii) circular: the old protocol (levelled and checked on
  all photons, validate.compare_icesat2). Scenes with one pass: (i) only (+ (iii) for comparison).
Error budget: (a) DTM vs ground (held-out ICESat-2 ground photons, GEDI elev_lowestmode); (b) nDSM vs laser-only height
  (ICESat-2 20 m along-track segments: 98th pct photon - median nearby ground photon; GEDI rh98), no DEM involved;
  (c) DSM vs all held-out photons. Footprint sampling (ICESat-2 disc radius 6 m, segments 10 m, GEDI 12.5 m: median for
  ground, 98th pct for the top surface) and single pixel. Roof photons = inside OSM building footprints (Overpass).
Baselines at the same points: Copernicus GLO-30 (raw DSM), FABDEM V1-2 (HuggingFace mirror of the Bristol release,
  CC BY-NC-SA 4.0: evaluation only, not committed), our DTM alone (nDSM = 0). CartoDEM: see india_v2.md.
Metrics: demo/eval_v2.py. r is on nDSM, or on heights after removing a least-squares plane (relief inflates raw r).
"""
import json, os, sys, time, urllib.parse, urllib.request

import numpy as np
import rasterio
from rasterio.warp import Resampling, transform as warp_transform, transform_bounds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'demo'))
import terrain, validate
import eval_v2 as ev
from fetch_scene import fetch, wayback
from landscape_benchmark import REGIONS, best_window

OLD_DIR = os.path.join(ROOT, 'demo', 'benchmark')
OUT = os.path.join(OLD_DIR, 'v2')
SC = os.path.join(OUT, 'scenes')
terrain.ICESAT2_CACHE = os.path.join(SC, 'icesat2')   # v2 photon caches never touch demo/benchmark/icesat2
OLD = json.load(open(os.path.join(OLD_DIR, 'landscape_results.json')))['scenes']
UA = {'User-Agent': 'DepthWizard-eval/2 (SIH26175 research)'}
FABDEM = 'https://huggingface.co/datasets/pavelzaitsau/fabdem-v12/resolve/main/tiles/{g}_FABDEM_V1-2/{t}_FABDEM_V1-2.tif'
WAYBACK = {'R07 2026-08-05': (26334, 'World_Imagery_Metadata_2026_r07'), 'R09 2026-09-24': (63116, 'World_Imagery_Metadata_2026_r09')}
POWER_BEAMS = (5, 6, 8, 11)   # GEDI full-power beams; 0-3 are coverage beams
f_ = lambda name, sfx: os.path.join(SC, name + sfx)


def get(url, data=None, timeout=120, tries=3):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=timeout).read()
        except OSError:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def poly(b):
    w, s, e, n = b
    return [{'lon': w, 'lat': s}, {'lon': e, 'lat': s}, {'lon': e, 'lat': n}, {'lon': w, 'lat': n}, {'lon': w, 'lat': s}]


def scene_bounds(path):
    with rasterio.open(path) as src:
        return transform_bounds(src.crs, 'EPSG:4326', *src.bounds)


# ---------------------------------------------------------------- prepare (network only)
def imagery_date(b, wayback_service=None):
    """Esri World Imagery source at zoom 18 at the scene centre and corners: the live map's Citations layer, or an
    archived release's metadata service (Esri Wayback, 60 cm layer = zoom 12-18)."""
    w, s, e, n = b
    base = (f'https://metadata.maptiles.arcgis.com/arcgis/rest/services/{wayback_service}/MapServer' if wayback_service
            else 'https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer')
    out = []
    for lon, lat in [((w + e) / 2, (s + n) / 2), (w, s), (e, s), (e, n), (w, n)]:
        q = urllib.parse.urlencode(dict(geometry=f'{lon},{lat}', geometryType='esriGeometryPoint', sr=4326,
                                        layers='all:5' if wayback_service else 'all:4', tolerance=0, mapExtent=f'{w},{s},{e},{n}',
                                        imageDisplay='1024,1024,96', returnGeometry='false', f='json'))
        for r in json.loads(get(base + '/identify?' + q)).get('results', []):
            a = r['attributes']
            if wayback_service:   # same keys as the live Citations layer
                a = {'DATE (YYYYMMDD)': a.get('SRC_DATE', 'Null'), 'SOURCE_INFO': a.get('NICE_NAME'), 'SOURCE': a.get('NICE_DESC'),
                     'DESCRIPTION': a.get('SRC_DESC'), 'RESOLUTION (M)': a.get('SRC_RES'), 'ACCURACY (M)': a.get('SRC_ACC'),
                     'BlockName': a.get('BlockName'), 'ReleaseName': a.get('ReleaseName'), 'FROM_CACHE_LEVEL': a.get('MinMapLevel'),
                     'TO_CACHE_LEVEL': a.get('MaxMapLevel')}
            if a.get('DATE (YYYYMMDD)', 'Null') != 'Null' and int(a['FROM_CACHE_LEVEL']) <= 18 <= int(a['TO_CACHE_LEVEL']):
                out.append({k: a.get(k) for k in ('DATE (YYYYMMDD)', 'SOURCE_INFO', 'SOURCE', 'DESCRIPTION', 'RESOLUTION (M)',
                                                  'ACCURACY (M)', 'BlockName', 'ReleaseName')} | {'at': [lon, lat]})
    dates = sorted({o['DATE (YYYYMMDD)'] for o in out})
    return {'dates': dates, 'date': dates[len(dates) // 2] if dates else None, 'records': out,
            'service': f"{wayback_service or 'World_Imagery (live)'} identify, queried {time.strftime('%Y-%m-%d')}"}


def atl03x(parms, tries=3):
    import sliderule
    sliderule.init(verbose=False)
    for _ in range(tries):
        g = sliderule.run('atl03x', parms)
        if g is not None:
            return g
    raise RuntimeError('SlideRule atl03x failed')


def icesat2_v2(b, out_f):
    """Exactly terrain.icesat2_photons' request (cnf 4, ATL08 classes), keeping atl03x's extra columns (x_atc, ...), and
    written in terrain's cache format too, so terrain.laser_correct (the app path) levels on the same photons. ATL08
    segment fields + solar elevation come from a 2nd request merged by photon id: asking for them in the 1st would drop
    every beam whose ATL08 granule lacks one of them, changing the photon set. Missing extras = NaN / -1."""
    base = {'poly': poly(b), 'cnf': 4, 'atl08_class': ['atl08_ground', 'atl08_canopy', 'atl08_top_of_canopy']}
    g = atl03x(base)
    n = len(g)
    col = lambda df, k, dt=np.float64: np.asarray(df[k], dt) if len(df) else np.zeros(0, dt)
    key = lambda df: (col(df, 'rgt', np.int64) * 1000 + col(df, 'cycle', np.int64)) * 10 ** 12 + col(df, 'spot', np.int64) * 10 ** 10 + col(df, 'ph_index', np.int64)
    d = dict(lon=np.asarray(g.geometry.x) if n else np.zeros(0), lat=np.asarray(g.geometry.y) if n else np.zeros(0),
             h=col(g, 'height'), cls=col(g, 'atl08_class', np.int64),
             t=g.index.to_numpy().astype('datetime64[s]').astype(np.int64) if n else np.zeros(0, np.int64),
             track=col(g, 'rgt', np.int64) * 100000 + col(g, 'cycle', np.int64) * 100 + col(g, 'spot', np.int64),
             x_atc=col(g, 'x_atc'), spot=col(g, 'spot', np.int64))
    extra = {'night_flag': 'night', 'solar_elevation': 'solar_elev', 'terrain/h_te_uncertainty': 'h_te_unc',
             'terrain/n_te_photons': 'n_te', 'cloud_flag_atm': 'cloud', 'snr': 'snr', 'terrain_flg': 'terrain_flg'}
    for v in extra.values():
        d[v] = np.full(n, np.nan)
    if n:
        try:
            x = atl03x(dict(base, atl08_fields=[k for k in extra if k != 'solar_elevation'], atl03_geo_fields=['solar_elevation']))
            idx = {k: i for i, k in enumerate(key(x))}
            j = np.array([idx.get(k, -1) for k in key(g)])
            for k, v in extra.items():
                if len(x) and k in x:
                    d[v] = np.where(j >= 0, col(x, k)[np.maximum(j, 0)], np.nan)
            d['extras_matched'] = np.array(float((j >= 0).mean()))
        except Exception as e:
            print('ATL08 extras failed', e)
    np.savez_compressed(out_f, **d)
    w, s, e, nn = b
    tf = os.path.join(terrain.ICESAT2_CACHE, f'{w:.5f}_{s:.5f}_{e:.5f}_{nn:.5f}.npz')
    if not os.path.exists(tf):
        os.makedirs(terrain.ICESAT2_CACHE, exist_ok=True)
        np.savez_compressed(tf, **{k: d[k] for k in ('lon', 'lat', 'h', 'cls', 't', 'track')})


def gedi_v2(b, out_f):
    """All GEDI L2A shots in the bounds (no server-side filter, so the quality counts can be reported)."""
    from sliderule import gedi
    gedi.init(verbose=False)
    g = gedi.gedi02ap({'poly': poly(b), 'anc_fields': ['rh']})
    n = len(g) if g is not None else 0
    if n and 'elevation_lm' not in g:
        n = 0
    col = lambda k, dt=np.float64: np.asarray(g[k], dt) if n else np.zeros(0, dt)
    rh = np.stack(g['rh'].to_numpy()).astype(np.float64) if n else np.zeros((0, 101))
    np.savez_compressed(out_f, lon=np.asarray(g.geometry.x) if n else np.zeros(0), lat=np.asarray(g.geometry.y) if n else np.zeros(0),
                        t=g.index.to_numpy().astype('datetime64[s]').astype(np.int64) if n else np.zeros(0, np.int64),
                        elev_lm=col('elevation_lm'), elev_hr=col('elevation_hr'), beam=col('beam', np.int64),
                        flags=col('flags', np.int64), sensitivity=col('sensitivity'), solar_elev=col('solar_elevation'),
                        orbit=col('orbit', np.int64), rh98=rh[:, 98] if n else np.zeros(0), rh100=rh[:, 100] if n else np.zeros(0))


def osm_buildings(b, out_f):
    w, s, e, n = b
    q = f'[out:json][timeout:90];(way["building"]({s},{w},{n},{e});relation["building"]({s},{w},{n},{e}););out geom;'
    open(out_f, 'wb').write(get('https://overpass-api.de/api/interpreter', urllib.parse.urlencode({'data': q}).encode(), 180))


def fabdem_name(lat, lon):
    """(10-degree folder, 1-degree tile) names of the FABDEM V1-2 tile holding lat/lon (named by south-west corners)."""
    tag = lambda a, o: f"{'N' if a >= 0 else 'S'}{abs(a):02d}{'E' if o >= 0 else 'W'}{abs(o):03d}"
    la, lo = int(np.floor(lat)), int(np.floor(lon))
    g0, g1 = (la // 10) * 10, (lo // 10) * 10
    return f'{tag(g0, g1)}-{tag(g0 + 10, g1 + 10)}', tag(la, lo)


def fabdem_tile(lat, lon):
    g, t = fabdem_name(lat, lon)
    out = os.path.join(SC, 'fabdem', t + '_FABDEM_V1-2.tif')
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out + '.part', 'wb').write(get(FABDEM.format(g=g, t=t), timeout=600))
        os.replace(out + '.part', out)
    return out


def prepare(name):
    land, _, lat0, lon0 = next(r for r in REGIONS if r[1] == name)
    os.makedirs(SC, exist_ok=True)
    meta_f = f_(name, '_prep.json')
    meta = json.load(open(meta_f)) if os.path.exists(meta_f) else {'landscape': land}
    log = lambda k: print(f'{name}: {k}', flush=True)
    if 'window' not in meta:
        old = (OLD[name]['lat'], OLD[name]['lon'])
        new = (lat0, lon0, None) if name == 'chandigarh_sector17' else best_window(lat0, lon0)   # as landscape_benchmark
        meta['window'] = {'old': old, 'recomputed': new[:2], 'laser_score': new[2],
                          'same': bool(abs(new[0] - old[0]) < 1e-6 and abs(new[1] - old[1]) < 1e-6), 'used': 'old'}
        json.dump(meta, open(meta_f, 'w'), indent=1)
        log(f"window old {old} recomputed {new} same={meta['window']['same']}")
    lat, lon = meta['window']['old']   # the old scene, so old and new protocols see the same ground
    img = f_(name, '.tif')
    if not os.path.exists(img):   # Chandigarh too: the old run's numbers are reproduced with today's live image (R09),
        fetch(name, lat, lon, SC)  # not with this machine's older demo sample (R07): india_oldprotocol_check.json
        log('image ready')
    b = scene_bounds(img)
    meta['bounds'] = b
    if 'wayback' not in meta:   # which archived Esri release is this image? (the old run's date is not recorded)
        a = rasterio.open(img).read().astype(np.int16)
        diff = lambda p: float(np.abs(rasterio.open(p).read().astype(np.int16) - a).mean())
        meta['wayback'] = {tag: diff(fetch(f'{name}_wayback{rel}', lat, lon, SC, url=wayback(rel), headers=UA))
                           for tag, (rel, _) in WAYBACK.items()} | {'live': diff(fetch(f'{name}_live', lat, lon, SC))}
        log(f"mean |pixel difference| to Esri releases {meta['wayback']}")
    if 'imagery' not in meta:
        meta['imagery'] = imagery_date(b)
        log(f"imagery {meta['imagery']['dates']}")
    json.dump(meta, open(meta_f, 'w'), indent=1)
    for sfx, fn in (('_atl03.npz', icesat2_v2), ('_gedi.npz', gedi_v2), ('_osm.json', osm_buildings)):
        if not os.path.exists(f_(name, sfx)):
            try:
                fn(b, f_(name, sfx))
                log(sfx + ' done')
            except Exception as e:
                log(f'{sfx} FAILED {type(e).__name__}: {e}')
    try:
        meta['fabdem'] = os.path.relpath(fabdem_tile((b[1] + b[3]) / 2, (b[0] + b[2]) / 2), SC)
    except Exception as e:
        meta['fabdem_error'] = f'{type(e).__name__}: {e}'
    json.dump(meta, open(meta_f, 'w'), indent=1)


# ---------------------------------------------------------------- model + terrain (the app's processing path)
def predict_all(names):
    """app.worker's model step for every scene that has an image but no height yet (one model load)."""
    import app, infer_height
    from utils import geo_func
    todo = [n for n in names if os.path.exists(f_(n, '.tif')) and not os.path.exists(f_(n, '_landcover.tif'))]
    if not todo:
        return print('all predictions cached')
    model, device, dtype = infer_height.load_model(os.path.join(ROOT, 'pretrain', 'RS3DAda_vitl_DPT_height.pth'), fp16=True)
    for name in todo:
        t0, path = time.time(), f_(name, '.tif')
        out = infer_height.predict(model, device, dtype, geo_func.load_multiband(path), use_tta=True, full=True)
        h, u, lc = out['height'], out['std'], out['landcover']
        infer_height.save_tiff_with_geo_info(path, f_(name, '_height.tif'), h)
        infer_height.save_tiff_with_geo_info(path, f_(name, '_uncertainty.tif'), u)
        infer_height.save_tiff_with_geo_info(path, f_(name, '_landcover.tif'), lc.astype(np.float32))  # written last = done
        json.dump({'gsd': app.ground_gsd(path) or 0.5, 'width': h.shape[1], 'height': h.shape[0], 'device': str(device),
                   'max': float(h.max()), 'mean': float(h.mean())}, open(f_(name, '.json'), 'w'))
        print(f'{name}: predicted in {time.time() - t0:.0f} s on {device}', flush=True)


def terrain_all(names):
    """app.ensure_terrain on the cached predictions: build_dtm, then laser_correct with every photon (as the app)."""
    import infer_height
    for name in names:
        path, meta_f = f_(name, '.tif'), f_(name, '.json')
        w, s, e, n = scene_bounds(path) if os.path.exists(path) else (0, 0, 0, 0)
        cached = os.path.exists(os.path.join(terrain.ICESAT2_CACHE, f'{w:.5f}_{s:.5f}_{e:.5f}_{n:.5f}.npz'))
        if not os.path.exists(f_(name, '_landcover.tif')) or not cached:
            print(f'{name}: no prediction or no prepared photons yet')   # laser_correct must level on the prepared photons
            continue
        meta = json.load(open(meta_f))
        if 'terrain' in meta and os.path.exists(f_(name, '_dtm_before.tif')):
            continue
        h = rasterio.open(f_(name, '_height.tif')).read(1)
        lc = rasterio.open(f_(name, '_landcover.tif')).read(1).astype(np.uint8)
        dtm0, info = terrain.build_dtm(path, h, infer_height.ground_mask(h, lc))
        dtm, info['laser'] = terrain.laser_correct(path, dtm0, info.get('geoid_undulation_m'))
        for sfx, a in (('_dtm_before.tif', dtm0), ('_dtm.tif', dtm), ('_dsm.tif', dtm + np.clip(h, 0, None))):
            infer_height.save_tiff_with_geo_info(path, f_(name, sfx), a)
        meta['terrain'] = info
        json.dump(meta, open(meta_f, 'w'), indent=1)
        print(f"{name}: terrain {info['source']} {info['mode']}, laser {info['laser']}", flush=True)


# ---------------------------------------------------------------- evaluation (from the caches; GLO-30 read from AWS)
YEAR = 365.25 * 86400
POOL = {}     # comparison key -> [(scene, errors, detrended reference)], for the pixel/point-pooled values
CUR = [None]  # scene being evaluated (tags POOL entries)


def on_grid(path, sc):
    """A DEM GeoTIFF / COG resampled (bilinear) onto the scene's pixel grid, as terrain.build_dtm reads it."""
    with rasterio.Env(**terrain.GDAL_ENV), rasterio.open(path) as src:
        a = terrain._warp(rasterio.band(src, 1), src.transform, src.crs, sc.shape, sc.transform, sc.crs, Resampling.bilinear)
    a[(a < -500) | (a > 9000)] = np.nan   # nodata (e.g. -9999) that slipped through
    return a


def cartodem(sc, lon, lat):
    """CartoDEM v3 R1 (Bhuvan, login needed) if a human put a covering tile in v2/scenes/cartodem/; EGM96 -> EGM2008."""
    import glob
    for f in sorted(glob.glob(os.path.join(SC, 'cartodem', '*.tif'))):
        with rasterio.open(f) as src:
            l, b_, r_, t = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
        if l <= lon <= r_ and b_ <= lat <= t:
            return on_grid(f, sc) + (terrain.geoid_shift(lon, lat) or 0.0)
    return None


def osm_mask(f, sc):
    """OSM building footprints (Overpass 'out geom' JSON; ways + outer rings of relations) rasterised on the scene grid."""
    from rasterio import features
    els = json.load(open(f)).get('elements', [])
    rings = [e['geometry'] for e in els if e['type'] == 'way' and 'geometry' in e]
    rings += [m['geometry'] for e in els if e['type'] == 'relation' for m in e.get('members', [])
              if m.get('role') == 'outer' and 'geometry' in m]
    shapes = []
    for ring in (q for q in rings if len(q) >= 3):
        xs, ys = warp_transform('EPSG:4326', sc.crs, [p['lon'] for p in ring], [p['lat'] for p in ring])
        shapes.append(({'type': 'Polygon', 'coordinates': [list(zip(xs, ys)) + [(xs[0], ys[0])]]}, 1))
    if not shapes:
        return np.zeros(sc.shape, bool), 0
    return features.rasterize(shapes, sc.shape, transform=sc.transform, fill=0, dtype='uint8').astype(bool), len(shapes)


def pixels(sc, lon, lat):
    """(inside mask, row, col) of lon/lat points on the scene grid."""
    if not len(lon):
        return np.zeros(0, bool), np.zeros(0, int), np.zeros(0, int)
    xs, ys = warp_transform('EPSG:4326', sc.crs, np.asarray(lon).tolist(), np.asarray(lat).tolist())
    r, c = (np.asarray(v) for v in rasterio.transform.rowcol(sc.transform, xs, ys))
    inside = (r >= 0) & (r < sc.shape[0]) & (c >= 0) & (c < sc.shape[1])
    return inside, np.clip(r, 0, sc.shape[0] - 1), np.clip(c, 0, sc.shape[1] - 1)


def local_xy(lon, lat):
    return (lon - lon.mean()) * 111320 * np.cos(np.radians(lat.mean())), (lat - lat.mean()) * 110540


def M(ours, ref, xy=None, key=None):
    """eval_v2.metrics of ours - ref. With xy (local metres) r is computed after removing the least-squares plane of the
    reference from both sides (errors unchanged), so hillsides do not inflate it. key: also kept for the pooled value."""
    ours, ref = np.asarray(ours, np.float64), np.asarray(ref, np.float64)
    ok = np.isfinite(ours) & np.isfinite(ref)
    if ok.sum() < 3:
        return None
    e, rd = ours[ok] - ref[ok], ref[ok]
    m = ev.metrics(e, rd)
    if xy is not None:
        A = np.c_[np.ones(ok.sum()), xy[0][ok], xy[1][ok]]
        rd = rd - A @ np.linalg.lstsq(A, rd, rcond=None)[0]
        m['r'] = ev.metrics(e, rd)['r']
    if key:
        POOL.setdefault(key, []).append((CUR[0], e, rd))
    return m


def laser_heights(lon, lat, x_atc, track, H, ground, seg=20.0, win=20.0):
    """ICESat-2 laser-only object heights, no DEM involved. Per beam pass, 20 m along-track segments; height = 98th
    percentile of the segment's photons above the local ground line (least squares through the ground photons within
    +-win m of the segment centre, or their median if they span < 10 m). Needs >= 3 photons and >= 3 ground photons."""
    out = []
    for tr in np.unique(track):
        m = np.flatnonzero(track == tr)
        x = x_atc[m]
        k = np.floor((x - x.min()) / seg).astype(int)
        for s in np.unique(k):
            sm, xc = m[k == s], x.min() + (s + 0.5) * seg
            gm = m[ground[m] & (np.abs(x - xc) <= win)]
            if len(sm) < 3 or len(gm) < 3:
                continue
            base = np.polyval(np.polyfit(x_atc[gm], H[gm], 1), x_atc[sm]) if np.ptp(x_atc[gm]) >= 10 else np.median(H[gm])
            out.append((lon[sm].mean(), lat[sm].mean(), np.percentile(H[sm] - base, 98), len(sm), len(gm)))
    a = np.array(out, np.float64).reshape(-1, 5)
    return {k: a[:, i] for i, k in enumerate(('lon', 'lat', 'h', 'n', 'n_ground'))}


def gedi_quality(flags):
    """SlideRule GEDI flags: bit 0 = degrade, bit 1 = L2 quality_flag. Good = quality 1 and not degraded."""
    flags = np.asarray(flags, np.int64)
    return ((flags & 2) > 0) & ((flags & 1) == 0)


def epoch(yyyymmdd):
    return int(np.datetime64(f'{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}', 's').astype(np.int64)) if yyyymmdd else None


def day(t):
    return str(np.datetime64(int(t), 's'))[:10]


def evaluate_scene(name):
    CUR[0] = name
    sc = validate.Scene(name, f_(name, '.tif'), results=SC)   # h, lc, dtm (= the app's, levelled on all passes), gsd
    prep = json.load(open(f_(name, '_prep.json')))
    N = sc.meta['terrain']['geoid_undulation_m']
    hh = np.clip(sc.h, 0, None)
    dtm0 = rasterio.open(f_(name, '_dtm_before.tif')).read(1).astype(np.float32)
    w, s, e, n = prep['bounds']
    glo = on_grid(terrain.GLO30.format(terrain.glo30_tile((s + n) / 2, (w + e) / 2)), sc)
    fab = on_grid(os.path.join(SC, prep['fabdem']), sc) if prep.get('fabdem') else None
    carto = cartodem(sc, (w + e) / 2, (s + n) / 2)
    roofm, n_osm = osm_mask(f_(name, '_osm.json'), sc) if os.path.exists(f_(name, '_osm.json')) else (np.zeros(sc.shape, bool), None)
    im = prep['imagery']
    res = {'landscape': prep['landscape'], 'window': prep['window'], 'bounds': prep['bounds'],
           'imagery': {k: im[k] for k in ('date', 'dates', 'service')} | {'source': sorted({f"{r['SOURCE']} {r['DESCRIPTION']} ({r['SOURCE_INFO']}, {r['RESOLUTION (M)']} m, release {r['ReleaseName']})" for r in im['records']})},
           'terrain_info': sc.meta['terrain'], 'osm_buildings': n_osm, 'cmp': {},
           'ndsm_p50_p90_p99': np.percentile(sc.h, [50, 90, 99]).tolist(), 'trees_pct': float(100 * (sc.lc == 4).mean())}
    for k in ('wayback', 'imagery_live_now'):
        if k in prep:
            res[k] = prep[k]
    # 1. old protocol, unchanged code path (validate.compare_icesat2 = what the app's /api/icesat2 returns)
    old = validate.compare_icesat2(sc)
    res['old_protocol'] = {k: old.get(k) for k in ('photons', 'ground_photons', 'passes', 'dates', 'laser_shift_m',
                                                   'terrain_vs_ground', 'surface_vs_all', 'held_out')}
    res['old_protocol_reported'] = {k: OLD[name].get(k) for k in ('photons', 'ground_photons', 'passes', 'dates', 'laser_shift_m',
                                                                  'terrain_vs_ground', 'surface_vs_all')}
    cmp = res['cmp']
    # 2. ICESat-2 photons in the scene, pass split
    P = dict(np.load(f_(name, '_atl03.npz')))
    ins, r, c = pixels(sc, P['lon'], P['lat'])
    P = {k: v[ins] for k, v in P.items() if np.ndim(v)}
    for v in P.values():
        if v.dtype.kind == 'f':
            v[np.abs(v) > 1e30] = np.nan   # ATL08 fill values (3.4e38)
    r, c = r[ins], c[ins]
    H, g, roof = P['h'] - N, P['cls'] == 1, roofm[r, c]
    pid = P['track'] // 100
    lev, val = validate.split_passes(P['track'], P['t'], P['cls'] == 1)
    split = bool(val.any())
    V = val if split else np.ones(len(H), bool)
    img_t = epoch(im['date'])
    near = np.abs(P['t'] - img_t) <= YEAR if img_t else np.zeros(len(H), bool)
    xy = local_xy(P['lon'], P['lat'])
    sub = lambda m: {k: P[k][m] for k in ('lon', 'lat', 'h', 'cls', 't', 'track')}
    offset = lambda grid: (terrain.laser_offset(grid, sc.transform, sc.crs, sub(lev), N)[0] if split and grid is not None else None)
    o = {k: offset(v) for k, v in (('ours', dtm0), ('glo30', glo), ('fabdem', fab))}
    lv = lambda grid, k: None if grid is None or not split else grid - (o[k] or 0)
    terr = {'ours_none': dtm0, 'ours_heldout': lv(dtm0, 'ours'), 'ours_circular': sc.dtm, 'glo30': glo,
            'glo30_heldout': lv(glo, 'glo30'), 'fabdem': fab, 'fabdem_heldout': lv(fab, 'fabdem'), 'cartodem': carto}
    surf = {'ours_none': dtm0 + hh, 'ours_heldout': None if not split else lv(dtm0, 'ours') + hh, 'ours_circular': sc.dtm + hh,
            'glo30': glo, 'glo30_heldout': terr['glo30_heldout'], 'fabdem': fab, 'fabdem_heldout': terr['fabdem_heldout'],
            'dtm_only_none': dtm0, 'dtm_only_heldout': terr['ours_heldout'], 'cartodem': carto}
    res['icesat2'] = {
        'photons': int(len(H)), 'ground': int(g.sum()), 'roof_photons_osm': int(roof.sum()),
        'roof_photons_classed_ground_pct': float(100 * (roof & g).sum() / roof.sum()) if roof.any() else None,
        'passes': int(len(np.unique(pid))), 'beams': int(len(np.unique(P['track']))),
        'passes_levelling': int(len(np.unique(pid[lev]))) if split else 0, 'passes_validation': int(len(np.unique(pid[val]))),
        'validation_photons': int(V.sum()), 'validation_ground': int((V & g & ~roof).sum()), 'ground_not_roof': int((g & ~roof).sum()),
        'photons_within_12mo_of_image': int(near.sum()), 'dates': [day(P['t'].min()), day(P['t'].max())] if len(H) else None,
        'levelling_offsets_heldout_m': {k: None if v is None else float(v) for k, v in o.items()},
        'levelling_offset_circular_m': (sc.meta['terrain'].get('laser') or {}).get('offset_m'),
        'extras_matched_frac': float(P['extras_matched']) if 'extras_matched' in P else None, 'split': split}
    lon, lat = P['lon'], P['lat']
    S = lambda grid, m, stat, rad=6.0: validate.footprint(sc, grid, lon[m], lat[m], stat, rad)
    # products levelled with photons (held-out or circular) are checked on the validation passes only; unlevelled ones
    # fitted nothing to the photons, so every pass is fair for them ('is2'), and 'is2val' repeats them on the held-out points
    HELD = ('ours_heldout', 'glo30_heldout', 'fabdem_heldout', 'dtm_only_heldout', 'ours_circular')
    UNLEV = ('ours_none', 'glo30', 'fabdem')
    every = np.ones(len(H), bool)
    pts = lambda prod: V if prod in HELD else every
    top_all = (P['cls'] == 3) | roof
    xyof = lambda m: (xy[0][m], xy[1][m])
    for prod, grid in terr.items():
        if grid is None:
            continue
        ground = g & ~roof
        sets = {'is2': pts(prod) & ground, 'is2_12mo': pts(prod) & ground & near}
        if split and prod in UNLEV:
            sets['is2val'] = V & ground
        for sname, m in sets.items():
            if sname != 'is2_12mo' or prod in UNLEV + ('ours_heldout',):
                cmp[f'a.{sname}.{prod}.fp'] = M(S(grid, m, 'median'), H[m], xyof(m), f'a.{sname}.{prod}.fp')
        m = sets['is2']
        cmp[f'a.is2.{prod}.px'] = M(grid[r[m], c[m]], H[m], xyof(m), f'a.is2.{prod}.px')
    for prod, grid in surf.items():
        if grid is None:
            continue
        sets = {'is2_all': pts(prod), 'is2_all_12mo': pts(prod) & near}
        if split and prod in UNLEV + ('dtm_only_none',):
            sets['is2val_all'] = V
        for sname, m in sets.items():
            if sname != 'is2_all_12mo' or prod in UNLEV + ('ours_heldout',):
                cmp[f'c.{sname}.{prod}.fp'] = M(S(grid, m, 'median'), H[m], xyof(m), f'c.{sname}.{prod}.fp')
        m, t = pts(prod), pts(prod) & top_all
        cmp[f'c.is2_all.{prod}.px'] = M(grid[r[m], c[m]], H[m], xyof(m), f'c.is2_all.{prod}.px')
        cmp[f'c.is2_top.{prod}.fp98'] = M(S(grid, t, 98), H[t], xyof(t), f'c.is2_top.{prod}.fp98')
        cmp[f'c.is2_top.{prod}.px'] = M(grid[r[t], c[t]], H[t], xyof(t), f'c.is2_top.{prod}.px')
    # 3. (b) nDSM vs laser-only heights, all passes (no DEM, no levelling involved)
    L = laser_heights(lon, lat, P['x_atc'], P['track'], H, g & ~roof)
    obj = {'ours': hh, 'zero': np.zeros_like(hh), 'glo30_minus_fabdem': None if fab is None else glo - fab}
    li, lr, lc_ = pixels(sc, L['lon'], L['lat'])
    for prod, grid in obj.items():
        if grid is None:
            continue
        cmp[f'b.is2_seg.{prod}.fp98'] = M(validate.footprint(sc, grid, L['lon'], L['lat'], 98, 10.0), L['h'], key=f'b.is2_seg.{prod}.fp98')
        cmp[f'b.is2_seg.{prod}.px'] = M(grid[lr, lc_], L['h'], key=f'b.is2_seg.{prod}.px')
    ours_seg = validate.footprint(sc, hh, L['lon'], L['lat'], 98, 10.0)
    res['is2_segments'] = {'n': int(len(L['h'])), 'bins': ev.binned_bias(ours_seg, L['h']), 'high': ev.high_metrics(ours_seg, L['h'])}
    POOL.setdefault('arrays.is2_seg', []).append((name, ours_seg, L['h']))
    # 4. GEDI L2A (independent of every ICESat-2 levelling)
    G = dict(np.load(f_(name, '_gedi.npz'))) if os.path.exists(f_(name, '_gedi.npz')) else None
    if G is not None and len(G['lon']):
        gi, gr, gc = pixels(sc, G['lon'], G['lat'])
        q = gi & gedi_quality(G['flags'])
        res['gedi'] = {'shots_in_scene': int(gi.sum()), 'quality': int(q.sum()),
                       'power_beam': int((q & np.isin(G['beam'], POWER_BEAMS)).sum()), 'coverage_beam': int((q & ~np.isin(G['beam'], POWER_BEAMS)).sum()),
                       'night': int((q & (G['solar_elev'] < 0)).sum()), 'sensitivity_median': float(np.median(G['sensitivity'][q])) if q.any() else None,
                       'dates': [day(G['t'][q].min()), day(G['t'][q].max())] if q.any() else None,
                       'within_12mo_of_image': int((q & (np.abs(G['t'] - img_t) <= YEAR)).sum()) if img_t else 0,
                       'rh98_median': float(np.median(G['rh98'][q])) if q.any() else None}
        if q.sum() >= 3:
            gl, gt = G['lon'][q], G['lat'][q]
            gH, rh = G['elev_lm'][q] - N, G['rh98'][q]
            gxy = local_xy(gl, gt)
            Sg = lambda grid, stat: validate.footprint(sc, grid, gl, gt, stat, 12.5)
            for prod, grid in terr.items():
                if grid is not None:
                    cmp[f'a.gedi.{prod}.fp'] = M(Sg(grid, 'median'), gH, gxy, f'a.gedi.{prod}.fp')
            for prod, grid in obj.items():
                if grid is not None:
                    cmp[f'b.gedi.{prod}.fp98'] = M(Sg(grid, 98), rh, key=f'b.gedi.{prod}.fp98')
                    cmp[f'b.gedi.{prod}.px'] = M(grid[gr[q], gc[q]], rh, key=f'b.gedi.{prod}.px')
            for prod, grid in surf.items():
                if grid is not None:
                    cmp[f'c.gedi_top.{prod}.fp98'] = M(Sg(grid, 98), gH + rh, gxy, f'c.gedi_top.{prod}.fp98')
            res['gedi']['bins'] = ev.binned_bias(Sg(hh, 98), rh)
            POOL.setdefault('arrays.gedi', []).append((name, Sg(hh, 98), rh))
    else:
        res['gedi'] = {'shots_in_scene': 0, 'note': 'no GEDI L2A file or no shot in the scene'}
    # 5. per-pass diagnostics (Silent Valley question for the DTM track); per beam for single-pass scenes
    diag = []
    for unit, ids in (('pass', pid), ('beam', P['track'])):
        for u in np.unique(ids):
            m = ids == u
            gm = m & g & ~roof
            dd = lambda a: float(np.median(a)) if len(a) else None
            diag.append({'unit': unit, 'id': int(u), 'date': day(np.median(P['t'][m])), 'role': 'only pass' if not split else 'levelling' if lev[m].all() else 'validation',
                         'photons': int(m.sum()), 'ground': int(gm.sum()), 'strong_beam_photons': int((m & np.isin(P['spot'], (1, 3, 5))).sum()),
                         'night_frac': float(np.nanmean(P['night'][m])) if np.isfinite(P['night'][m]).any() else None,
                         'solar_elev_median': dd(P['solar_elev'][m][np.isfinite(P['solar_elev'][m])]),
                         'cloud_flag_median': dd(P['cloud'][m][np.isfinite(P['cloud'][m])]),
                         'h_te_uncertainty_median': dd(P['h_te_unc'][gm][np.isfinite(P['h_te_unc'][gm])]),
                         'n_te_photons_median': dd(P['n_te'][gm][np.isfinite(P['n_te'][gm])]),
                         'ground_h_p5_p95': [float(np.percentile(H[gm], 5)), float(np.percentile(H[gm], 95))] if gm.any() else None,
                         'dtm_before_minus_ground_median': dd((dtm0[r[gm], c[gm]] - H[gm])),
                         'dtm_before_minus_ground_nmad': float(1.4826 * np.median(np.abs((d := dtm0[r[gm], c[gm]] - H[gm]) - np.median(d)))) if gm.any() else None,
                         'glo30_minus_ground_median': dd(glo[r[gm], c[gm]] - H[gm]),
                         'fabdem_minus_ground_median': None if fab is None else dd(fab[r[gm], c[gm]] - H[gm])})
    res['pass_diagnostics'] = diag
    return res


def span(ms, k):
    v = [m[k] for m in ms if m and m.get(k) is not None]
    return {'mean': float(np.mean(v)), 'min': float(np.min(v)), 'max': float(np.max(v)), 'scenes': len(v)} if v else None


def aggregate(res):
    keys = sorted({k for r in res.values() for k in r['cmp']})
    cat = lambda k, i: np.concatenate([a[i] for a in POOL.get(k, [])] or [np.zeros(0)])
    pool = lambda k, names: [(e, rd) for n, e, rd in POOL.get(k, []) if n in names]
    out = {'all_scenes': {}, 'by_landscape': {},
           'bins': {'is2_seg': ev.binned_bias(cat('arrays.is2_seg', 1), cat('arrays.is2_seg', 2)),
                    'is2_seg_zero': ev.binned_bias(0 * cat('arrays.is2_seg', 2), cat('arrays.is2_seg', 2)),
                    'gedi': ev.binned_bias(cat('arrays.gedi', 1), cat('arrays.gedi', 2)),
                    'is2_seg_high': ev.high_metrics(cat('arrays.is2_seg', 1), cat('arrays.is2_seg', 2)),
                    'gedi_high': ev.high_metrics(cat('arrays.gedi', 1), cat('arrays.gedi', 2))}}
    def agg(k, names):
        pl = pool(k, names)
        pm = ev.metrics(np.concatenate([a for a, _ in pl]), np.concatenate([b for _, b in pl])) if pl else None
        return ev.aggregate([res[n]['cmp'].get(k) for n in names], pm)
    # the three protocols on the same scenes: those with a held-out terrain / surface check
    for kind, keys3 in (('terrain', ('a.is2val.ours_none.fp', 'a.is2.ours_heldout.fp', 'a.is2.ours_circular.fp')),
                        ('surface', ('c.is2val_all.ours_none.fp', 'c.is2_all.ours_heldout.fp', 'c.is2_all.ours_circular.fp'))):
        names = [n for n in res if all(res[n]['cmp'].get(k) for k in keys3)]
        out.setdefault('same_scenes', {})[kind] = {'scenes': names, **{k: agg(k, names) for k in keys3}}
    for k in keys:
        out['all_scenes'][k] = agg(k, list(res))
        for land in dict.fromkeys(x[0] for x in REGIONS):
            ms = [r['cmp'].get(k) for r in res.values() if r['landscape'] == land]
            out['by_landscape'].setdefault(land, {})[k] = {q: span(ms, q) for q in ('mae', 'rmse', 'bias', 'nmad', 'r', 'n')}
    return out


def evaluate(names):
    res = {}
    for n in names:
        t0 = time.time()
        res[n] = evaluate_scene(n)
        print(f'{n}: evaluated in {time.time() - t0:.0f} s', flush=True)
    out = {'protocol': __doc__, 'scenes': res, 'aggregate': aggregate(res)}
    json.dump(out, open(os.path.join(OUT, 'india_v2.json'), 'w'), indent=1, default=float)
    write_md(out)


# ---------------------------------------------------------------- report
NOTES = ['', '## 10. Data sources, and what a human must do for CartoDEM', '',
         '- **FABDEM V1-2** (Hawker et al. 2022, CC BY-NC-SA 4.0, non-commercial: used for evaluation only, the tiles stay in '
         'the git-ignored `v2/scenes/fabdem/`). data.bris.ac.uk reset every connection from this machine, so the 1-degree tiles '
         'came from the HuggingFace mirror `pavelzaitsau/fabdem-v12` (a third-party copy of the Bristol release, not '
         'checksum-verified against Bristol). Datum EGM2008, like GLO-30.',
         '- **Copernicus GLO-30** read window-only from the AWS open-data bucket (as terrain.py does).',
         '- **GEDI L2A** v002 via SlideRule `gedi02ap` (public, no login), all shots in the scene; kept: L2 quality_flag = 1 '
         'and degrade_flag = 0; ground = elev_lowestmode, top = elev_lowestmode + rh98; WGS84 ellipsoid -> EGM2008 with the '
         'same geoid height as the ICESat-2 photons (terrain.geoid_shift). GEDI horizontal geolocation error is ~10 m.',
         '- **OSM buildings** via Overpass (`way/relation[building]`, out geom), rasterised on the scene grid: photons inside '
         'a footprint are roof photons (Cai et al. 2024: ATL08 classes over roofs are unreliable), kept out of every validation ground set; the levelling offsets '
         '(terrain.laser_offset on the levelling passes) use every ATL08 ground photon, roofs included, exactly as the app does.',
         '- **Esri imagery date**: World_Imagery MapServer identify, Citations layer, zoom 18 (live); for Chandigarh the demo '
         'image the old run used matches Esri Wayback release R07 pixel for pixel, dated from that release\'s metadata service.',
         '- **CartoDEM v3 R1 (not used: login-gated).** A human must: (1) register a free account at '
         'https://bhuvan.nrsc.gov.in (Sign Up; needs an e-mail address); (2) log in at '
         'https://bhuvan-app3.nrsc.gov.in/data/download/index.php; (3) choose Satellite/Sensor = CartoDEM, Version = 3 R1, '
         'and select the 1-degree tiles N30E076 (Chandigarh), N28E077 (Delhi), N25E071 (Barmer), N14E077 (Anantapur), '
         'N31E077 (Shimla), N27E088 (Gangtok), N13E075 (Agumbe), N11E076 (Silent Valley); (4) unzip the GeoTIFFs into '
         '`SynRS3D/demo/benchmark/v2/scenes/cartodem/`; (5) rerun `demo/india_eval_v2.py evaluate`. They are picked up '
         'automatically as baseline `cartodem` (EGM96 -> EGM2008 via terrain.geoid_shift). Licence: NRSC data policy, do not '
         'commit them.']
COMMANDS = ['', '## Commands', '', 'From `SynRS3D/` (the model step under the shared model lock):', '', '```',
            '.venv/bin/python demo/india_eval_v2.py --selftest && .venv/bin/python validate.py',
            '.venv/bin/python demo/india_eval_v2.py prepare      # network: windows, images, dates, ICESat-2, GEDI, OSM, FABDEM',
            '/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/india_eval_v2.py predict',
            '.venv/bin/python demo/india_eval_v2.py terrain',
            '.venv/bin/python demo/india_eval_v2.py evaluate     # -> demo/benchmark/v2/india_v2.json + india_v2.md',
            '.venv/bin/python demo/india_eval_v2.py report       # -> india_v2.md again from india_v2.json (wording only)',
            '# Chandigarh imagery check (section 1), run once before the live image became the scene:',
            '/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/india_eval_v2.py predict chandigarh_sector17_live',
            '.venv/bin/python demo/india_eval_v2.py terrain chandigarh_sector17_live && .venv/bin/python demo/india_eval_v2.py oldcheck chandigarh_sector17_live chandigarh_sector17',
            '```', '', 'Window recomputation (landscape_benchmark.best_window) ran for Delhi, Barmer and Anantapur and gave the old '
            'windows exactly; for Shimla, Gangtok, Agumbe and Silent Valley it was skipped to stay in the time budget (a 3 km '
            'SlideRule request took ~25 min) and the old windows were used. Optional plan step 9 (extra scenes per landscape) '
            'was not done.']


def fm(m, k='mae', nd=2, sign=False):
    v = None if not m else m.get(k)
    return '–' if v is None else (f'{v:+.{nd}f}' if sign else f'{v:.{nd}f}')


def mrow(m, keys=('n', 'mae', 'rmse', 'bias', 'nmad', 'r')):
    return ' | '.join('–' if not m else f"{m['n']:,}" if k == 'n' else fm(m, k, 3 if k == 'r' else 2, k == 'bias') for k in keys)


def agg_cell(a, k='mae'):
    """mean [95% CI over scenes] (pooled)"""
    if not a or k not in a:
        return '–'
    lo, hi = a[k]['ci95']
    p = (a.get('pooled') or {}).get(k)
    return f"{a[k]['mean']:.2f} [{lo:.2f}, {hi:.2f}] ({p:.2f})" if lo is not None else f"{a[k]['mean']:.2f}"


def span_cell(sp, nd=2):
    return '–' if not sp else f"{sp['mean']:.{nd}f} ({sp['min']:.{nd}f}…{sp['max']:.{nd}f})" if sp['scenes'] > 1 else f"{sp['mean']:.{nd}f} (1 scene)"


def write_md(out):
    R, A = out['scenes'], out['aggregate']
    nm = lambda n: n.replace('_', ' ')
    C = lambda n, k: R[n]['cmp'].get(k)
    L = ['# Indian landscapes vs NASA ICESat-2 and GEDI: evaluation protocol v2', '',
         'Same 8 scenes and windows as `landscape_results.md` (two per landscape type), rebuilt on this machine without the '
         'app server (`demo/india_eval_v2.py`: fetch_scene, infer_height.predict, terrain.build_dtm, terrain.laser_correct, '
         'validate.compare_icesat2 - the functions the app calls). e = ours - reference; heights in m above EGM2008. '
         'Footprint sampling: ICESat-2 photon = disc of radius 6 m on our grid (median; 98th percentile for top-of-surface '
         'photons), ICESat-2 20 m segment = 10 m, GEDI = 12.5 m; "px" = the single pixel. r is computed after removing a '
         'least-squares plane (terrain/surface) or directly on heights above ground (nDSM).', '']
    # 1. reproduction
    L += ['## 1. Old protocol reproduced first (circular: terrain levelled on the same photons it is checked on)', '',
          '| Scene | Photons old / now | Beam-tracks old / now | Surface MAE / RMSE / bias / r, old | same, rebuilt now | Terrain before levelling median / NMAD, old | same, now |',
          '|---|---|---|---|---|---|---|']
    maxd = max(abs(r['old_protocol'][a][q] - r['old_protocol_reported'][a][q]) for r in R.values() for a, q in
               (('surface_vs_all', 'mae'), ('surface_vs_all', 'rmse'), ('surface_vs_all', 'bias'), ('terrain_vs_ground', 'median'), ('terrain_vs_ground', 'nmad')))
    for n, r in R.items():
        o, p = r['old_protocol_reported'], r['old_protocol']
        so, sn, to, tn = o.get('surface_vs_all'), p.get('surface_vs_all'), o.get('terrain_vs_ground'), p.get('terrain_vs_ground')
        L.append(f"| {nm(n)} | {o.get('photons')} / {p.get('photons')} | {o.get('passes')} / {p.get('passes')} | "
                 f"{fm(so)} / {fm(so, 'rmse')} / {fm(so, 'bias', sign=True)} / {fm(so, 'r')} | {fm(sn)} / {fm(sn, 'rmse')} / {fm(sn, 'bias', sign=True)} / {fm(sn, 'r')} | "
                 f"{fm(to, 'median', sign=True)} / {fm(to, 'nmad')} | {fm(tn, 'median', sign=True)} / {fm(tn, 'nmad')} |")
    L += ['', '"Beam-tracks" is what the old report called passes (rgt + cycle + beam). The old numbers are reproduced on this '
          f'machine (MPS) within {np.ceil(maxd * 100) / 100:.2f} m (largest difference {maxd:.3f} m), with the same photons, so the rebuild is the same experiment. For Chandigarh this '
          'needed today\'s live Esri image (= Wayback release R09, Vantor 2026-07-03); this machine\'s older demo sample '
          '(Wayback R07, GE01 2025-10-19) gives surface MAE 4.77 m instead of 7.26 m with the same photons and terrain '
          '(`india_oldprotocol_check.json`): one image change moves the number by 2.5 m.', '']
    # 2. data
    L += ['## 2. Data per scene', '',
          '| Scene | Landscape | Image date (source) | Image vs Esri Wayback R07 / R09 / live (mean abs DN diff) | ICESat-2 photons (ground; ground off OSM roofs) | Passes: levelling / validation | Dates | Held-out photons (ground) | Photons within 12 mo of image | GEDI shots: all / quality / power beam | OSM buildings; roof photons (% ATL08 "ground") |',
          '|---|---|---|---|---|---|---|---|---|---|---|']
    for n, r in R.items():
        i, g, wb = r['icesat2'], r['gedi'], r.get('wayback') or {}
        src = '; '.join(r['imagery']['source']) or '–'
        L.append(f"| {nm(n)} | {r['landscape']} | {r['imagery']['date']} ({src}) | {' / '.join(fm(wb, k, 1) for k in ('R07 2026-08-05', 'R09 2026-09-24', 'live'))} | "
                 f"{i['photons']:,} ({i['ground']:,}; {i['ground_not_roof']:,}) | {i['passes_levelling']} / {i['passes_validation'] if i['split'] else 0} (of {i['passes']}) | "
                 f"{' to '.join(i['dates'] or [])} | {i['validation_photons'] if i['split'] else 0:,} ({i['validation_ground'] if i['split'] else 0:,}) | {i['photons_within_12mo_of_image']:,} | "
                 f"{g.get('shots_in_scene', 0)} / {g.get('quality', 0)} / {g.get('power_beam', 0)} | {r['osm_buildings']}; {i['roof_photons_osm']} ({fm(i, 'roof_photons_classed_ground_pct', 0)}) |")
    L += ['', 'A pass = one ICESat-2 reference ground track in one cycle (all 6 beams). Passes are sorted by time and '
          'alternate levelling / validation, starting with whichever phase gives the levelling passes more ground photons '
          '(validate.split_passes; never looks at errors); no pass is used for both. Unlevelled products (ours (i), raw '
          'GLO-30, FABDEM) fitted nothing to the photons and are checked on every pass; levelled products (ours (ii), levelled '
          'baselines, the circular (iii)) only on the validation passes. Single-pass scenes: (i) only.', '']
    # 3. protocols
    L += ['## 3. Three protocols on the same held-out photons (scenes with 2+ passes)', '',
          '(i) no levelling, (ii) levelled on the levelling passes only, (iii) circular: levelled on all passes including '
          'the validation ones (the old protocol). Footprint sampling. Single-pass scenes: (i) on all photons, (iii) for comparison.', '',
          '| Scene | Terrain vs ground photons (n): MAE (i) / (ii) / (iii) | median (i) / (ii) / (iii) | NMAD (i) / (ii) | Surface vs all photons (n): MAE (i) / (ii) / (iii) | bias (i) / (ii) / (iii) |',
          '|---|---|---|---|---|---|']
    for n, r in R.items():
        sp = r['icesat2']['split']
        t = [C(n, 'a.is2val.ours_none.fp' if sp else 'a.is2.ours_none.fp'), C(n, 'a.is2.ours_heldout.fp'), C(n, 'a.is2.ours_circular.fp')]
        s_ = [C(n, 'c.is2val_all.ours_none.fp' if sp else 'c.is2_all.ours_none.fp'), C(n, 'c.is2_all.ours_heldout.fp'), C(n, 'c.is2_all.ours_circular.fp')]
        cnt = lambda m: m['n'] if m else 0
        L.append(f"| {nm(n)}{'' if sp else ' (1 pass)'} | ({cnt(t[0])}) {' / '.join(fm(m) for m in t)} | {' / '.join(fm(m, 'median', sign=True) for m in t)} | "
                 f"{fm(t[0], 'nmad')} / {fm(t[1], 'nmad')} | ({cnt(s_[0])}) {' / '.join(fm(m) for m in s_)} | {' / '.join(fm(m, 'bias', sign=True) for m in s_)} |")
    # 4. baselines
    pair = lambda m: '–' if not m else f"{fm(m)} / {fm(m, 'bias', sign=True)} ({m['n']})"
    L += ['', '## 4. Baselines at the same points (footprint sampling): MAE / bias (n)', '',
          '### 4a. Terrain vs ICESat-2 ground photons (ATL08 ground, OSM roofs removed)', '',
          'Unlevelled, all passes: our DTM straight from terrain.build_dtm, raw Copernicus GLO-30 (a DSM), FABDEM (bare earth). '
          'Levelled, validation passes only: each shifted by its own median offset to the levelling passes (terrain.laser_offset).', '',
          '| Scene | ours (i) | GLO-30 | FABDEM | ours (ii) | GLO-30 levelled | FABDEM levelled |', '|---|---|---|---|---|---|---|']
    for n in R:
        L.append(f"| {nm(n)} | " + ' | '.join(pair(C(n, f'a.is2.{p}.fp')) for p in ('ours_none', 'glo30', 'fabdem', 'ours_heldout', 'glo30_heldout', 'fabdem_heldout')) + ' |')
    L += ['', '### 4b. Surface vs all ICESat-2 photons', '',
          '| Scene | our DSM (i) | GLO-30 | FABDEM (nDSM = 0) | our DTM only (i) | our DSM (ii) | GLO-30 levelled | our DTM only (ii) |', '|---|---|---|---|---|---|---|---|']
    for n in R:
        L.append(f"| {nm(n)} | " + ' | '.join(pair(C(n, f'c.is2_all.{p}.fp')) for p in ('ours_none', 'glo30', 'fabdem', 'dtm_only_none', 'ours_heldout', 'glo30_heldout', 'dtm_only_heldout')) + ' |')
    L += ['', '### 4c. Terrain vs GEDI ground (elev_lowestmode, 12.5 m footprint median), independent of every ICESat-2 levelling', '',
          '| Scene | ours (i) | ours (ii) | ours (iii) | GLO-30 | FABDEM |', '|---|---|---|---|---|---|']
    for n in R:
        L.append(f"| {nm(n)} | " + ' | '.join(pair(C(n, f'a.gedi.{p}.fp')) for p in ('ours_none', 'ours_heldout', 'ours_circular', 'glo30', 'fabdem')) + ' |')
    L += ['', 'CartoDEM v3 R1 is not included: it is behind a Bhuvan login (section 10).', '']
    # 5. error budget
    L += ['## 5. Error budget per scene', '',
          '(a) DTM vs ground; (b) nDSM vs laser-only height above ground (no DEM involved, all passes; p98 over the footprint); '
          '(c) DSM vs all photons and vs top-of-surface photons (ATL08 top of canopy or OSM roof; p98 over the footprint). '
          'MAE / bias, n in brackets; (i) = all passes, (ii) = held-out passes.', '',
          '| Scene | (a) ICESat-2 ground (i) | (a) ICESat-2 ground (ii) | (a) GEDI ground (i) | (b) ICESat-2 segments, r | (b) GEDI rh98, r | (c) all photons (i) | (c) all photons (ii) | (c) top photons (i) | (c) GEDI top (i) |',
          '|---|---|---|---|---|---|---|---|---|---|']
    for n, r in R.items():
        b1, b2 = C(n, 'b.is2_seg.ours.fp98'), C(n, 'b.gedi.ours.fp98')
        L.append(f"| {nm(n)} | {pair(C(n, 'a.is2.ours_none.fp'))} | {pair(C(n, 'a.is2.ours_heldout.fp'))} | {pair(C(n, 'a.gedi.ours_none.fp'))} | "
                 f"{pair(b1)}, {fm(b1, 'r')} | {pair(b2)}, {fm(b2, 'r')} | {pair(C(n, 'c.is2_all.ours_none.fp'))} | {pair(C(n, 'c.is2_all.ours_heldout.fp'))} | "
                 f"{pair(C(n, 'c.is2_top.ours_none.fp98'))} | {pair(C(n, 'c.gedi_top.ours_none.fp98'))} |")
    L += ['', '(b) by reference (laser) height, ICESat-2 20 m segments, all scenes pooled:', '',
          '| Height bin | n | MAE | bias | baseline nDSM = 0: MAE |', '|---|---|---|---|---|']
    for lab in ev.BIN_LABELS:
        m, z = A['bins']['is2_seg'].get(lab), A['bins']['is2_seg_zero'].get(lab)
        L.append(f"| {lab} | {m['n'] if m else 0:,} | {fm(m)} | {fm(m, 'bias', sign=True)} | {fm(z)} |")
    hm = A['bins'].get('is2_seg_high')
    L += ['', f"'High' (eval_v2.high_metrics: reference or ours > 3 m), ICESat-2 segments pooled: {mrow(hm)} (n | MAE | RMSE | bias | NMAD | r).",
          'GEDI rh98 by bin (all scenes pooled): ' + '; '.join(f"{lab}: n {m['n']}, MAE {m['mae']:.2f}, bias {m['bias']:+.2f}"
                                                           for lab, m in A['bins']['gedi'].items() if m) + '.']
    # 6. per landscape
    BL = A['by_landscape']
    L += ['', '## 6. Per landscape: mean over its 2 scenes (range)', '',
          'With two scenes a bootstrap confidence interval is not meaningful, so the range (min…max) is shown instead.', '',
          '| Landscape | Terrain MAE ours (i) | GLO-30 | FABDEM | Surface MAE ours (i) | our DTM only (i) | GLO-30 (DSM) | Surface MAE ours (ii) | (b) nDSM MAE (ICESat-2 seg.) | (b) nDSM bias | (b) r |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for land, d in BL.items():
        g_ = lambda k, q='mae', nd=2: span_cell((d.get(k) or {}).get(q), nd)
        L.append(f"| {land} | {g_('a.is2.ours_none.fp')} | {g_('a.is2.glo30.fp')} | {g_('a.is2.fabdem.fp')} | {g_('c.is2_all.ours_none.fp')} | "
                 f"{g_('c.is2_all.dtm_only_none.fp')} | {g_('c.is2_all.glo30.fp')} | {g_('c.is2_all.ours_heldout.fp')} | {g_('b.is2_seg.ours.fp98')} | "
                 f"{g_('b.is2_seg.ours.fp98', 'bias')} | {g_('b.is2_seg.ours.fp98', 'r', 3)} |")
    # 7. all scenes
    AS = A['all_scenes']
    L += ['', '## 7. All 8 scenes: mean over scenes [95% bootstrap CI over scenes, 2000 resamples] (pooled over all points)', '',
          '| Comparison | scenes | MAE | RMSE | bias | NMAD | r |', '|---|---|---|---|---|---|---|']
    rows = [('(a) terrain vs ICESat-2 ground, ours (i) no levelling (all passes)', 'a.is2.ours_none.fp'),
            ('(a) terrain, ours (i) on held-out passes only', 'a.is2val.ours_none.fp'),
            ('(a) terrain, ours (ii) held-out levelling', 'a.is2.ours_heldout.fp'), ('(a) terrain, ours (iii) circular', 'a.is2.ours_circular.fp'),
            ('(a) terrain, raw GLO-30', 'a.is2.glo30.fp'), ('(a) terrain, raw FABDEM', 'a.is2.fabdem.fp'),
            ('(a) terrain, GLO-30 held-out levelled', 'a.is2.glo30_heldout.fp'), ('(a) terrain, FABDEM held-out levelled', 'a.is2.fabdem_heldout.fp'),
            ('(a) terrain vs GEDI ground, ours (i)', 'a.gedi.ours_none.fp'), ('(a) terrain vs GEDI ground, FABDEM', 'a.gedi.fabdem.fp'),
            ('(b) nDSM vs ICESat-2 segment height, ours (p98)', 'b.is2_seg.ours.fp98'), ('(b) same, single pixel', 'b.is2_seg.ours.px'),
            ('(b) same, baseline nDSM = 0', 'b.is2_seg.zero.fp98'), ('(b) same, baseline GLO-30 - FABDEM', 'b.is2_seg.glo30_minus_fabdem.fp98'),
            ('(b) nDSM vs GEDI rh98, ours (p98)', 'b.gedi.ours.fp98'), ('(b) GEDI rh98, baseline nDSM = 0', 'b.gedi.zero.fp98'),
            ('(c) DSM vs all photons, ours (i)', 'c.is2_all.ours_none.fp'), ('(c) same, single pixel', 'c.is2_all.ours_none.px'),
            ('(c) DSM vs all photons, ours (i) on held-out passes only', 'c.is2val_all.ours_none.fp'),
            ('(c) DSM vs all photons, ours (ii)', 'c.is2_all.ours_heldout.fp'), ('(c) DSM vs all photons, ours (iii) circular', 'c.is2_all.ours_circular.fp'),
            ('(c) all photons, our DTM only (i)', 'c.is2_all.dtm_only_none.fp'), ('(c) all photons, raw GLO-30', 'c.is2_all.glo30.fp'),
            ('(c) all photons, FABDEM', 'c.is2_all.fabdem.fp'), ('(c) top photons p98, ours (i)', 'c.is2_top.ours_none.fp98'),
            ('(c) top photons, raw GLO-30', 'c.is2_top.glo30.fp98'), ('(c) GEDI top p98, ours (i)', 'c.gedi_top.ours_none.fp98'),
            ('(c) GEDI top, raw GLO-30', 'c.gedi_top.glo30.fp98')]
    for lab, k in rows:
        a = AS.get(k)
        L.append(f"| {lab} | {a['units'] if a else 0} | " + ' | '.join(agg_cell(a, q) for q in ('mae', 'rmse', 'bias', 'nmad', 'r')) + ' |')
    L += ['', 'The three protocols on the same scenes (those with a held-out check):', '',
          '| Comparison | scenes | MAE | RMSE | bias | NMAD |', '|---|---|---|---|---|---|']
    for kind, d in A['same_scenes'].items():
        for k, lab in zip(list(d)[1:], ('(i) no levelling', '(ii) held-out levelling', '(iii) circular')):
            L.append(f"| {kind} {lab}: {', '.join(nm(n) for n in d['scenes'])} | {d[k]['units']} | " + ' | '.join(agg_cell(d[k], q) for q in ('mae', 'rmse', 'bias', 'nmad')) + ' |')
    # 8. date filter
    L += ['', '## 8. All dates vs within 12 months of the image date (unlevelled products, all passes)', '',
          '| Scene | Image date | Terrain: n, MAE ours (i) all dates → ±12 mo | GLO-30 all → ±12 mo | Surface: n, MAE ours (i) all → ±12 mo | bias all → ±12 mo |', '|---|---|---|---|---|---|']
    for n, r in R.items():
        cc = lambda k: C(n, k)
        cnt = lambda m: m['n'] if m else 0
        ta, tb, ga, gb = cc('a.is2.ours_none.fp'), cc('a.is2_12mo.ours_none.fp'), cc('a.is2.glo30.fp'), cc('a.is2_12mo.glo30.fp')
        sa, sb = cc('c.is2_all.ours_none.fp'), cc('c.is2_all_12mo.ours_none.fp')
        L.append(f"| {nm(n)} | {r['imagery']['date']} | {cnt(ta)}: {fm(ta)} → {cnt(tb)}: {fm(tb)} | {fm(ga)} → {fm(gb)} | {cnt(sa)}: {fm(sa)} → {cnt(sb)}: {fm(sb)} | {fm(sa, 'bias', sign=True)} → {fm(sb, 'bias', sign=True)} |")
    # 9. silent valley
    sv = R.get('silent_valley_forest')
    if sv:
        L += ['', '## 9. Silent Valley diagnostics (for the DTM track; not fixed here)', '',
              '| Unit | id | date | role | photons | ground | strong-beam photons | night | solar elev. | cloud flag | ATL08 h_te_uncertainty | n_te_photons | ground h p5…p95 | DTM(i) − ground median / NMAD | GLO-30 − ground | FABDEM − ground |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
        for d in sv['pass_diagnostics']:
            p5 = d['ground_h_p5_p95']
            L.append(f"| {d['unit']} | {d['id']} | {d['date']} | {d['role']} | {d['photons']} | {d['ground']} | {d['strong_beam_photons']} | {fm(d, 'night_frac')} | "
                     f"{fm(d, 'solar_elev_median', 1)} | {fm(d, 'cloud_flag_median', 0)} | {fm(d, 'h_te_uncertainty_median', 1)} | {fm(d, 'n_te_photons_median', 0)} | "
                     f"{'–' if not p5 else f'{p5[0]:.0f}…{p5[1]:.0f}'} | {fm(d, 'dtm_before_minus_ground_median', 1, True)} / {fm(d, 'dtm_before_minus_ground_nmad', 1)} | "
                     f"{fm(d, 'glo30_minus_ground_median', 1, True)} | {fm(d, 'fabdem_minus_ground_median', 1, True)} |")
        gi = sv['gedi']
        L += ['', f"GEDI in the scene: {gi.get('shots_in_scene', 0)} shots, {gi.get('quality', 0)} quality ({gi.get('power_beam', 0)} power beam); "
              f"our DTM (i) vs GEDI ground: {mrow(sv['cmp'].get('a.gedi.ours_none.fp'), ('n', 'median', 'nmad'))} (n | median | NMAD); "
              f"GLO-30 vs GEDI ground: {mrow(sv['cmp'].get('a.gedi.glo30.fp'), ('n', 'median', 'nmad'))}."]
    open(os.path.join(OUT, 'india_v2.md'), 'w', encoding='utf-8').write('\n'.join(L + meaning(R, A) + NOTES + COMMANDS) + '\n')
    print('\n'.join(L[:12]))


def meaning(R, A):
    """Plain-language reading; every number is read from the results (india_v2.json)."""
    AS, BL, SS = A['all_scenes'], A['by_landscape'], A['same_scenes']
    mm = lambda k, q='mae': AS[k][q]['mean'] if AS.get(k) and q in AS[k] else float('nan')
    ss = lambda kind, k, q='mae': SS[kind][k][q]['mean']
    lm = lambda land, k, q='mae': ((BL[land].get(k) or {}).get(q) or {}).get('mean', float('nan'))
    cm = lambda n, k, q='mae': (R[n]['cmp'].get(k) or {}).get(q, float('nan'))
    sv = 'silent_valley_forest'
    sv_p = [d for d in R[sv]['pass_diagnostics'] if d['unit'] == 'pass'][0]
    spread = lambda n: [d['dtm_before_minus_ground_median'] for d in R[n]['pass_diagnostics'] if d['unit'] == 'pass' and d['ground']]
    gk, an = spread('gangtok_hills'), spread('anantapur_dryland')
    fa, fs = cm('agumbe_western_ghats', 'a.is2.ours_none.fp'), cm(sv, 'a.is2.ours_none.fp')
    seg, gb = A['bins']['is2_seg'], A['bins']['gedi']
    rep = max(abs(r['old_protocol'][a][q] - r['old_protocol_reported'][a][q]) for r in R.values() for a, q in
              (('surface_vs_all', 'mae'), ('surface_vs_all', 'rmse'), ('surface_vs_all', 'bias'), ('terrain_vs_ground', 'median'), ('terrain_vs_ground', 'nmad')))
    return ['', '## What this means', '',
            f"- **The old numbers are real but partly circular.** They reproduce to {np.ceil(rep * 100) / 100:.2f} m. Where a scene has two or more laser "
            f"passes, levelling the terrain on some passes and checking it on the others gives terrain MAE "
            f"{ss('terrain', 'a.is2.ours_heldout.fp'):.2f} m against {ss('terrain', 'a.is2val.ours_none.fp'):.2f} m without "
            f"levelling and {ss('terrain', 'a.is2.ours_circular.fp'):.2f} m with the old circular protocol (mean of "
            f"{len(SS['terrain']['scenes'])} scenes). Levelling removes the average offset (bias {ss('terrain', 'a.is2val.ours_none.fp', 'bias'):+.2f} -> "
            f"{ss('terrain', 'a.is2.ours_heldout.fp', 'bias'):+.2f} m) but does not lower the typical error, because a shift "
            f"learnt on one track a few hundred metres away does not hold on the next one: in Gangtok the passes disagree "
            f"with the same terrain by {min(gk):.1f} to {max(gk):.1f} m, in Anantapur by {max(an) - min(an):.1f} m. Surface MAE on held-out photons: "
            f"{ss('surface', 'c.is2_all.ours_heldout.fp'):.2f} m levelled vs {ss('surface', 'c.is2val_all.ours_none.fp'):.2f} m not.",
            f"- **Single-pass scenes cannot be checked after levelling.** In Agumbe and Silent Valley every photon comes from one "
            f"pass, so the old terrain/surface numbers there are pure self-fit. Silent Valley's surface MAE is "
            f"{cm(sv, 'c.is2_all.ours_none.fp'):.1f} m before levelling (old, circular: {R[sv]['old_protocol_reported']['surface_vs_all']['mae']:.1f} m). "
            f"The {sv_p['dtm_before_minus_ground_median']:.0f} m shift comes from one night pass ({100 * sv_p['strong_beam_photons'] / sv_p['photons']:.0f}% of "
            f"its photons on the strong beam). GEDI disagrees: its ground lies {cm(sv, 'a.gedi.ours_none.fp', 'median'):.0f} m below our unlevelled "
            f"terrain, and the levelled terrain ends up {-cm(sv, 'a.gedi.ours_circular.fp', 'median'):.0f} m below GEDI ground. One of the two "
            f"lasers is wrong there; a single pass should not be allowed to move the terrain by tens of metres.",
            f"- **Against public DEMs, at the same points.** Terrain (all 8 scenes, mean MAE): ours {mm('a.is2.ours_none.fp'):.2f} m, raw "
            f"GLO-30 {mm('a.is2.glo30.fp'):.2f} m, FABDEM {mm('a.is2.fabdem.fp'):.2f} m. Our building/tree removal clearly beats raw "
            f"GLO-30 in towns ({lm('urban', 'a.is2.ours_none.fp'):.2f} vs {lm('urban', 'a.is2.glo30.fp'):.2f} m) and edges FABDEM there "
            f"({lm('urban', 'a.is2.fabdem.fp'):.2f} m); on sparse land all three are equal (~{lm('sparse', 'a.is2.ours_none.fp'):.1f} m); in the "
            f"hills FABDEM is better ({lm('hilly', 'a.is2.fabdem.fp'):.2f} vs ours {lm('hilly', 'a.is2.ours_none.fp'):.2f} m); in forest every "
            f"product is about 20 m off and ours is the worst (ours {lm('forested', 'a.is2.ours_none.fp'):.2f}, GLO-30 {lm('forested', 'a.is2.glo30.fp'):.2f}, "
            f"FABDEM {lm('forested', 'a.is2.fabdem.fp'):.2f} m; Silent Valley dominates). Surface: our DSM "
            f"{mm('c.is2_all.ours_none.fp'):.2f} m vs raw GLO-30 {mm('c.is2_all.glo30.fp'):.2f} m vs our terrain alone "
            f"{mm('c.is2_all.dtm_only_none.fp'):.2f} m (mean MAE vs all photons): at laser footprints our absolute DSM is not more "
            f"accurate than the 30 m Copernicus DSM except on sparse land ({lm('sparse', 'c.is2_all.ours_none.fp'):.2f} vs "
            f"{lm('sparse', 'c.is2_all.glo30.fp'):.2f} m; towns {lm('urban', 'c.is2_all.ours_none.fp'):.2f} vs {lm('urban', 'c.is2_all.glo30.fp'):.2f}, "
            f"hills {lm('hilly', 'c.is2_all.ours_none.fp'):.2f} vs {lm('hilly', 'c.is2_all.glo30.fp'):.2f} m: ours loses); against GEDI canopy/roof tops it is ({mm('c.gedi_top.ours_none.fp98'):.2f} vs "
            f"{mm('c.gedi_top.glo30.fp98'):.2f} m). What the image adds is detail at 0.5 m, which a 30 m DSM cannot have, not "
            f"better absolute heights at the footprints.",
            f"- **The height model itself (no DEM in the loop).** Against laser-only heights above ground our nDSM has MAE "
            f"{mm('b.is2_seg.ours.fp98'):.2f} m (ICESat-2 20 m segments) and {mm('b.gedi.ours.fp98'):.2f} m (GEDI rh98), versus "
            f"{mm('b.is2_seg.zero.fp98'):.2f} / {mm('b.gedi.zero.fp98'):.2f} m for predicting zero and {mm('b.is2_seg.glo30_minus_fabdem.fp98'):.2f} m for "
            f"GLO-30 minus FABDEM; r = {mm('b.is2_seg.ours.fp98', 'r'):.2f}. It is too high on low ground ({seg['0-3 m']['bias']:+.1f} m below 3 m) "
            f"and too low on tall objects ({seg['10-20 m']['bias']:+.1f} m at 10-20 m, {seg['20-inf m']['bias']:+.1f} m above 20 m; GEDI "
            f"{gb['20-inf m']['bias']:+.1f} m above 20 m). Tall forest is the main failure: in Silent Valley ({R[sv]['trees_pct']:.0f}% trees) the median "
            f"predicted height is {R[sv]['ndsm_p50_p90_p99'][0]:.1f} m (99th percentile {R[sv]['ndsm_p50_p90_p99'][2]:.1f} m) where GEDI measures a "
            f"median rh98 of {R[sv]['gedi']['rh98_median']:.1f} m.",
            f"- **Correlation.** After removing the terrain plane, r between our heights and the laser is "
            f"{mm('a.is2.ours_none.fp', 'r'):.2f} (terrain) and {mm('c.is2_all.ours_none.fp', 'r'):.2f} (surface), not the 0.93-0.98 "
            f"the old report's absolute-elevation r suggested for hilly scenes: that was the hillside, not the model.",
            f"- **Uncertainty.** The two scenes of a landscape can differ enormously (forested terrain MAE {fa:.1f} m in Agumbe, "
            f"{fs:.1f} m in Silent Valley), so per-landscape values are means with their range, not confidence intervals; the "
            f"8-scene bootstrap intervals are wide. Most laser passes are years older or younger than the image; only "
            f"{sum(1 for r in R.values() if r['icesat2']['photons_within_12mo_of_image'] >= 100)} scenes have 100+ photons within 12 months of it, "
            f"and that subset does not change the picture consistently (section 8)."]


def selftest():
    import tempfile
    from rasterio.crs import CRS
    # (b) laser heights: 200 m of track on a 27 deg slope, 15 m canopy over x >= 100 m (every 4th photon reaches ground)
    x = np.arange(0, 200, 0.7)
    canopy = x >= 100
    ground = ~canopy | (np.arange(len(x)) % 4 == 0)
    H = 100 + 0.5 * x + np.where(ground, 0, 15)
    Lh = laser_heights(76 + x * 1e-5, np.full(len(x), 11.0), x, np.ones(len(x), int), H, ground)
    xc = (Lh['lon'] - 76) / 1e-5
    assert len(Lh['h']) == 10 and np.abs(Lh['h'][xc < 80]).max() < 0.3, Lh
    assert np.abs(Lh['h'][(xc > 120) & (xc < 180)] - 15).max() < 0.5, Lh
    # r after removing the plane: relief makes raw r ~1; the real agreement of the residual relief is ~0.71
    rng = np.random.default_rng(0)
    px, py, sig = rng.uniform(0, 500, 2000), rng.uniform(0, 500, 2000), rng.normal(0, 1, 2000)
    ref = 100 + 0.5 * px + 0.2 * py + sig
    ours = ref + rng.normal(0, 1, 2000)
    raw, m = ev.metrics(ours - ref, ref), M(ours, ref, (px, py), key='selftest')
    assert raw['r'] > 0.99 and 0.65 < m['r'] < 0.76 and abs(m['mae'] - raw['mae']) < 1e-12 and len(POOL.pop('selftest')) == 1
    assert M([1, 2], [1, 2]) is None
    assert gedi_quality([130, 131, 128, 2, 3]).tolist() == [True, False, False, True, False]
    assert fabdem_name(13.51, 75.097) == ('N10E070-N20E080', 'N13E075') and fabdem_name(-0.5, -1.2) == ('S10W010-N00E000', 'S01W002')
    assert epoch('20200101') == 1577836800 and epoch(None) is None and day(1577836800) == '2020-01-01'
    # OSM footprint rasterised: a 20 x 20 px building on a 1e-5 deg grid
    class Geo:
        crs, transform, shape = CRS.from_epsg(4326), rasterio.Affine(1e-5, 0, 76.0, 0, -1e-5, 11.0), (100, 100)
    sq = [{'lon': 76 + a * 1e-5, 'lat': 11 - b * 1e-5} for a, b in ((10, 10), (30, 10), (30, 30), (10, 30))]
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as t:
        json.dump({'elements': [{'type': 'way', 'geometry': sq}]}, t)
    mask, k = osm_mask(t.name, Geo())
    os.remove(t.name)
    assert k == 1 and 380 <= mask.sum() <= 420 and mask[20, 20] and not mask[50, 50], mask.sum()
    ins, r, c = pixels(Geo(), np.array([76.000205, 77.0]), np.array([10.999795, 11.0]))   # pixel centre (20, 20)
    assert ins.tolist() == [True, False] and (r[0], c[0]) == (20, 20)
    print('india_eval_v2 selftest OK')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    cmd, names = (sys.argv[1:2] or ['--help'])[0], sys.argv[2:] or [r[1] for r in REGIONS]
    if cmd == 'prepare':
        for n in names:
            prepare(n)
    elif cmd == 'predict':
        predict_all(names)
    elif cmd == 'terrain':
        terrain_all(names)
    elif cmd == 'oldcheck':   # old protocol only, any processed scene in v2/scenes (e.g. chandigarh_sector17_live)
        out = {n: {k: v for k, v in validate.compare_icesat2(validate.Scene(n, f_(n, '.tif'), results=SC)).items()
                   if k in ('photons', 'passes', 'laser_shift_m', 'terrain_vs_ground', 'surface_vs_all')} for n in names}
        json.dump(out, open(os.path.join(OUT, 'india_oldprotocol_check.json'), 'w'), indent=1)
        print(json.dumps(out, indent=1))
    elif cmd == 'evaluate':
        evaluate(names)
    elif cmd == 'report':   # india_v2.md again from india_v2.json, no recompute
        write_md(json.load(open(os.path.join(OUT, 'india_v2.json'))))
    else:
        print(__doc__)
