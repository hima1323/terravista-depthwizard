"""Bare-ground terrain (DTM) under a georeferenced image, for absolute heights:
    DSM (metres above mean sea level, EGM2008) = DTM + model height above ground (nDSM).

Terrain source, in order:
  1. a DEM GeoTIFF you drop in demo/terrain/ that covers the scene (e.g. CartoDEM from ISRO Bhuvan);
     name it *_egm96.tif if its heights are EGM96-based (CartoDEM, SRTM) and it is shifted to EGM2008;
  2. otherwise Copernicus GLO-30 (EGM2008), read window-only from the AWS open-data bucket (no login).
All such 30 m DEMs are *surface* models: in towns their cells are raised by roofs and canopy. So per 30 m cell we
subtract the model's own mean height above ground and weight the cell by how much of it the land-cover map
calls open ground, then fill/smooth by normalised Gaussian convolution. Result is on the image's pixel grid.
Finally laser_correct() shifts it to agree with NASA ICESat-2 ground photons in the scene, where there are enough.
"""
import glob, math, os

import cv2
import numpy as np
import rasterio
import rasterio.transform
import rasterio.warp
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.transform import from_origin

ROOT = os.path.dirname(os.path.abspath(__file__))
USER_DEM_DIR = os.path.join(ROOT, 'demo', 'terrain')
GLO30 = '/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{0}/{0}.tif'
DATUM = 'EGM2008 geoid (EPSG:3855): metres above mean sea level'
RES = 1 / 3600          # working grid: 1 arc-second (~30 m), the native GLO-30 / CartoDEM spacing
MARGIN = 0.003          # degrees (~300 m) of extra terrain around the scene, for smooth edges
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                GDAL_HTTP_MAX_RETRY='3', GDAL_HTTP_RETRY_DELAY='1')


def glo30_tile(lat, lon):
    """Name of the 1-degree GLO-30 tile containing (lat, lon); tiles are named by their south-west corner."""
    lat, lon = math.floor(lat), math.floor(lon)
    return (f"Copernicus_DSM_COG_10_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_"
            f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM")


def geoid_shift(lon, lat, src='EPSG:4326+5773', dst='EPSG:4326+3855'):
    """Height difference between vertical datums at one point (default EGM96 -> EGM2008), via PROJ's online
    geoid grids. Constant over a <1 km scene. Returns None if the grids cannot be fetched."""
    try:
        import pyproj
        pyproj.network.set_network_enabled(True)
        z = pyproj.Transformer.from_crs(src, dst, always_xy=True).transform(lon, lat, 0.0)[2]
        return float(z) if math.isfinite(z) else None
    except Exception:
        return None


def _sources(bounds):
    """[(path, source label, needs EGM96->EGM2008 shift)] covering the lon/lat bounds."""
    w, s, e, n = bounds
    for f in sorted(glob.glob(os.path.join(USER_DEM_DIR, '*.tif'))):
        with rasterio.open(f) as src:
            if not src.crs:
                continue
            fw, fs, fe, fn = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
        if fw <= w and fs <= s and fe >= e and fn >= n:
            return [(f, os.path.basename(f), 'egm96' in os.path.basename(f).lower())]
    return [(GLO30.format(glo30_tile(lat, lon)), 'Copernicus GLO-30', False)
            for lat in range(math.floor(s), math.floor(n) + 1) for lon in range(math.floor(w), math.floor(e) + 1)]


def _warp(src_array_or_band, src_transform, src_crs, dst_shape, dst_transform, dst_crs, how):
    out = np.full(dst_shape, np.nan, np.float32)
    reproject(src_array_or_band, out, src_transform=src_transform, src_crs=src_crs, dst_transform=dst_transform,
              dst_crs=dst_crs, resampling=how, src_nodata=np.nan, dst_nodata=np.nan)
    return out


def fill_normalised(values, weights, sigma):
    """Weighted Gaussian interpolation: smooth everywhere, fills cells without weight from their neighbours."""
    v = np.nan_to_num(values) * weights
    out = np.full(values.shape, np.nan, np.float32)
    while np.isnan(out).any() and sigma < 4 * max(values.shape):
        num = cv2.GaussianBlur(v.astype(np.float32), (0, 0), sigma)
        den = cv2.GaussianBlur(weights.astype(np.float32), (0, 0), sigma)
        est = np.where(den > 1e-3, num / np.maximum(den, 1e-6), np.nan)
        out = np.where(np.isnan(out), est, out)
        sigma *= 2
    return out


def fill_terrain(sample, weight, known_min=0.2, iters=5000):
    """Cells with enough weight keep their (lightly smoothed) sample; the rest get a harmonic (Laplace) fill,
    which reproduces planes and slopes exactly across gaps instead of leaning towards the better-sampled side."""
    known = weight >= known_min
    z = fill_normalised(sample, weight, sigma=1.0)                      # smooth estimate everywhere = start value
    z = np.where(known, fill_normalised(sample, weight * known, sigma=1.0), z)
    for _ in range(iters):                                               # Jacobi relaxation of the unknown cells
        zp = np.pad(z, 1, mode='edge')
        nb = (zp[:-2, 1:-1] + zp[2:, 1:-1] + zp[1:-1, :-2] + zp[1:-1, 2:]) / 4
        step = np.where(known, 0, nb - z)
        z = z + step
        if np.abs(step).max() < 1e-4:
            break
    return z


def surface_share(dem, mean_h, inside, sigma=2.0):
    """How much of the objects' height the coarse surface model contains (0..1). Radar/stereo 30 m DEMs catch only
    part of narrow towers. Estimated from fine detail only: high-pass both (removes hills), regress DEM on heights."""
    core = cv2.erode(inside.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & np.isfinite(dem)
    if core.sum() < 20:
        return 1.0
    d = np.where(np.isfinite(dem), dem, np.nanmean(dem)).astype(np.float32)
    hp = lambda a: a - cv2.GaussianBlur(a, (0, 0), sigma)
    x, y = hp(mean_h.astype(np.float32))[core], hp(d)[core]
    return float(np.clip((x * y).sum() / max((x * x).sum(), 1e-6), 0, 1))


def build_dtm(image_path, ndsm, ground):
    """Bare-ground elevation (float32, image pixel grid, EGM2008 metres) and an info dict, or (None, info)
    when the image has no georeferencing (PNG/JPG). ndsm = model height above ground, ground = bool mask of
    pixels the model calls open ground (roads, bare, water...), both on the image grid."""
    with rasterio.open(image_path) as img:
        if not img.crs:
            return None, {'none': 'image has no georeferencing, so heights stay relative (above ground)'}
        crs, transform, shape = img.crs, img.transform, (img.height, img.width)
        w, s, e, n = transform_bounds(crs, 'EPSG:4326', *img.bounds)
    w, s, e, n = w - MARGIN, s - MARGIN, e + MARGIN, n + MARGIN
    gw, gh = math.ceil((e - w) / RES), math.ceil((n - s) / RES)
    grid_t = from_origin(w, n, RES, RES)

    # 1. raw terrain surface on a 1" lon/lat grid (all tiles that touch the scene; missing tiles = open sea)
    dem = np.full((gh, gw), np.nan, np.float32)
    labels, shift_needed = [], False
    with rasterio.Env(**GDAL_ENV):
        for path, label, egm96 in _sources((w, s, e, n)):
            try:
                with rasterio.open(path) as src:
                    part = _warp(rasterio.band(src, 1), src.transform, src.crs, dem.shape, grid_t, 'EPSG:4326',
                                 Resampling.bilinear)
            except rasterio.errors.RasterioIOError:
                continue
            dem = np.where(np.isnan(dem), part, dem)
            labels.append(label)
            shift_needed |= egm96
    if np.isnan(dem).all():
        raise RuntimeError('no terrain data for this area')
    info = {'source': ', '.join(sorted(set(labels))), 'datum': DATUM}
    cx, cy = (w + e) / 2, (s + n) / 2
    if shift_needed:  # bring EGM96-based DEMs (CartoDEM, SRTM) onto EGM2008
        d = geoid_shift(cx, cy)
        info['egm96_to_egm2008_m'] = d
        if d is not None:
            dem += d
        else:
            info['warning'] = 'EGM96->EGM2008 shift not applied (geoid grid unavailable), up to a few metres'
    info['geoid_undulation_m'] = geoid_shift(cx, cy, 'EPSG:4326+3855', 'EPSG:4979')  # add to get ellipsoidal (ICESat-2)

    # 2. per 30 m cell: how much of it is open ground, and the model's mean height above ground there
    ones = np.ones(shape, np.float32)
    avg = lambda a: _warp(a.astype(np.float32), transform, crs, dem.shape, grid_t, 'EPSG:4326', Resampling.average)
    cover, ground_frac, mean_h = avg(ones), avg(ground), avg(np.clip(ndsm, 0, None))
    inside = np.nan_to_num(cover) > 0.5
    # surface model ~ cell-average top of surface, so ground ~ DEM - mean height. Every cell inside the scene keeps
    # its corrected value (so hills keep their real shape); mostly-open cells weigh more in the light smoothing.
    mh, gf = np.nan_to_num(mean_h), np.clip(np.nan_to_num(ground_frac), 0, 1)
    ok = inside & np.isfinite(dem)
    smooth = cv2.GaussianBlur(np.where(np.isfinite(dem), dem, np.nanmean(dem)).astype(np.float32), (0, 0), 3)
    relief = float(np.percentile(smooth[ok], 95) - np.percentile(smooth[ok], 5))
    info['relief_m'] = relief
    if relief < 50 and (gf[ok] >= 0.5).sum() >= 5:
        # flat town: open-ground cells pin the terrain; roof/canopy-covered cells are dropped and filled in
        info['mode'] = 'flat: pinned by open-ground cells'
        dtm_grid = fill_terrain(dem - mh, np.where(ok, gf ** 2, 0), known_min=0.25)
    else:
        # hills (or no open ground): keep every cell's real shape, remove the share of object height it contains
        alpha = surface_share(dem, mh, inside)
        info['mode'], info['alpha'] = 'hilly: terrain shape kept, object heights removed', alpha
        dtm_grid = fill_terrain(dem - alpha * mh, np.where(ok, 0.2 + 0.8 * gf ** 2, 0), known_min=0.2)
    info['open_cells'] = int((gf[ok] >= 0.5).sum())
    raised = (dem - dtm_grid)[ok]  # how much roofs/canopy had lifted the raw surface model
    info['cleaning_removed_mean_m'], info['cleaning_removed_max_m'] = float(raised.mean()), float(raised.max())

    # 3. onto the image's own pixel grid (smooth: terrain varies slowly)
    dtm = _warp(dtm_grid, grid_t, 'EPSG:4326', shape, transform, crs, Resampling.cubic)
    info.update(min=float(np.nanmin(dtm)), max=float(np.nanmax(dtm)))
    return dtm.astype(np.float32), info


ICESAT2_CACHE = os.path.join(ROOT, 'demo', 'benchmark', 'icesat2')
LASER_MIN_PHOTONS = 50   # ICESat-2 ground photons needed before we trust a laser offset


def icesat2_photons(bounds):
    """High-confidence ICESat-2 photons (ATL03, with ATL08 class 1 ground / 2 canopy / 3 top of canopy) inside lon/lat
    bounds, all passes since 2018, from NASA's public SlideRule service (no login); cached per bounds. Arrays lon, lat,
    h (m above the WGS84 ellipsoid), cls, t (unix s), track (rgt*1e5 + cycle*100 + spot)."""
    w, s, e, n = bounds
    f = os.path.join(ICESAT2_CACHE, f'{w:.5f}_{s:.5f}_{e:.5f}_{n:.5f}.npz')
    if not os.path.exists(f):
        import sliderule
        sliderule.init(verbose=False)
        poly = [{'lon': w, 'lat': s}, {'lon': e, 'lat': s}, {'lon': e, 'lat': n}, {'lon': w, 'lat': n}, {'lon': w, 'lat': s}]
        g = sliderule.run('atl03x', {'poly': poly, 'cnf': 4,
                                     'atl08_class': ['atl08_ground', 'atl08_canopy', 'atl08_top_of_canopy']})
        cols = {} if not len(g) else dict(
            lon=g.geometry.x, lat=g.geometry.y, h=g['height'], cls=g['atl08_class'],
            t=g.index.to_numpy().astype('datetime64[s]').astype(np.int64),
            track=g['rgt'].astype(np.int64) * 100000 + g['cycle'].astype(np.int64) * 100 + g['spot'])
        os.makedirs(ICESAT2_CACHE, exist_ok=True)
        np.savez_compressed(f, **{k: np.asarray(cols.get(k, [])) for k in ('lon', 'lat', 'h', 'cls', 't', 'track')})
    return dict(np.load(f))


def laser_offset(dtm, transform, crs, p, undulation):
    """Median of (terrain - ICESat-2 ground photon heights) inside the scene, or None if there are too few photons.
    undulation = EGM2008 geoid height above the ellipsoid, to put the photons on the terrain's datum."""
    g = p['cls'] == 1
    info = {'ground_photons': int(g.sum())}
    if undulation is None or g.sum() < LASER_MIN_PHOTONS:
        return None, dict(info, none=f'{int(g.sum())} ICESat-2 ground photons in the scene (need {LASER_MIN_PHOTONS})')
    xs, ys = rasterio.warp.transform('EPSG:4326', crs, p['lon'][g].tolist(), p['lat'][g].tolist())
    r, c = (np.asarray(v) for v in rasterio.transform.rowcol(transform, xs, ys))
    ok = (r >= 0) & (r < dtm.shape[0]) & (c >= 0) & (c < dtm.shape[1])
    d = dtm[r[ok], c[ok]] - (p['h'][g][ok] - undulation)
    d = d[np.isfinite(d)]
    if len(d) < LASER_MIN_PHOTONS:
        return None, dict(info, none=f'{len(d)} usable ICESat-2 ground photons (need {LASER_MIN_PHOTONS})')
    off = float(np.median(d))
    days = np.sort(p['t'][g]).astype('datetime64[s]').astype(str)
    return off, dict(info, offset_m=off, spread_nmad_m=float(1.4826 * np.median(np.abs(d - off))),
                     passes=int(len(np.unique(p['track'][g]))), first=days[0][:10], last=days[-1][:10])


def laser_correct(image_path, dtm, undulation):
    """Shift the terrain so it agrees (median) with NASA ICESat-2 laser ground photons in the scene: 30 m DEMs are often
    off by a few metres, ICESat-2 by decimetres. Returns (terrain, info); unchanged without enough photons or internet."""
    try:
        with rasterio.open(image_path) as img:
            crs, tr = img.crs, img.transform
            p = icesat2_photons(transform_bounds(crs, 'EPSG:4326', *img.bounds))
    except Exception as e:  # offline, service down, client not installed
        return dtm, {'none': f'ICESat-2 photons unavailable ({type(e).__name__})'}
    off, info = laser_offset(dtm, tr, crs, p, undulation)
    return (dtm if off is None else dtm - off), info


def save_with_tags(ref_path, out_path, data, save, **tags):
    """save(ref_path, out_path, data) writes the GeoTIFF (infer_height.save_tiff_with_geo_info); then tag it."""
    save(ref_path, out_path, data)
    with rasterio.open(out_path, 'r+') as dst:
        dst.update_tags(**{k: str(v) for k, v in tags.items()})


if __name__ == '__main__':
    # self-check on synthetic data: a sloping plain with buildings raising some 30 m cells of the "DEM"
    rng = np.random.default_rng(0)
    H = W = 64
    slope = np.linspace(100, 110, W)[None, :].repeat(H, 0)          # true ground: 100 -> 110 m west to east
    h = np.zeros((H, W), np.float32)
    h[10:30, 10:30] = 20                                               # a 20 m building block
    dem_surface = slope + cv2.blur(h, (5, 5))                          # what a coarse surface model would see
    sample = dem_surface - cv2.blur(h, (5, 5))                         # step-2 correction with perfect heights
    ground = (h == 0).astype(np.float32)
    dtm = fill_terrain(sample, ground ** 2)
    assert np.abs(dtm - slope).max() < 0.3, np.abs(dtm - slope).max()
    raw_err = np.abs(fill_normalised(dem_surface, np.ones_like(ground), 1.0) - slope)[10:30, 10:30].mean()
    print(f'self-check ok: cleaned DTM error {np.abs(dtm - slope).mean():.3f} m (uncleaned would be {raw_err:.1f} m '
          f'under the block)')
    # laser offset: terrain 12 m, ground photons at 7 m ellipsoidal with geoid -3 m -> 10 m a.s.l. -> offset +2 m
    tr = from_origin(76.0, 31.0, 1e-4, 1e-4)
    ph = {'lon': 76.0 + np.linspace(1e-4, 60e-4, 80), 'lat': 31.0 - np.linspace(1e-4, 60e-4, 80), 'h': np.full(80, 7.0),
          'cls': np.r_[np.ones(60), np.full(20, 2)], 't': np.zeros(80, np.int64), 'track': np.ones(80)}
    off, _ = laser_offset(np.full((64, 64), 12.0), tr, 'EPSG:4326', ph, -3.0)
    assert abs(off - 2.0) < 1e-9, off
    assert laser_offset(np.full((64, 64), 12.0), tr, 'EPSG:4326', dict(ph, cls=np.full(80, 2)), -3.0)[0] is None
    assert glo30_tile(30.97, 76.47) == 'Copernicus_DSM_COG_10_N30_00_E076_00_DEM'
    assert glo30_tile(-0.5, -1.2) == 'Copernicus_DSM_COG_10_S01_00_W002_00_DEM'
