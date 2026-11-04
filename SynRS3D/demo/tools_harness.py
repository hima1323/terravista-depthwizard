"""Test harness for the toolbar tools: synthetic scenes with known truth (buildings drawn 0.75 × their true height,
trees 12 m vs 18 m true, shadows for a 45° sun from 135°, a before/after pair with 2 collapsed blocks), served by the
real app.py with the model stubbed out (no PyTorch or weights needed). Then: node demo/tools_test.js <workdir>
usage: python demo/tools_harness.py <workdir> [port]   (port 8765 for tools_test.js)"""
import json, math, os, sys, types
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)
work = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765

# ---- stub the model module (no torch here)
import rasterio
fake = types.ModuleType('infer_height')
fake.LANDCOVER = ['bareland', 'rangeland', 'developed', 'road', 'trees', 'water', 'agriculture', 'buildings']
def save_tiff_with_geo_info(input_path, output_path, data):
    with rasterio.open(input_path) as src:
        profile = src.profile
    profile.update(driver='GTiff', count=1, dtype='float32', nodata=None, photometric=None)
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(data.astype(np.float32), 1)
fake.save_tiff_with_geo_info = save_tiff_with_geo_info
fake.ground_mask = lambda h, lc, max_height=1.5: np.isin(lc, [0, 1, 2, 3, 5, 6]) & (h < max_height)
fake.correct_heights = lambda h, lc, corr: h
fake.load_model = lambda *a, **k: (None, 'cpu', None)
sys.modules['infer_height'] = fake

import terrain, validate, tools, app
for mod in (app, validate, tools):
    mod.RESULTS = os.path.join(work, 'results')
app.SAMPLES = os.path.join(work, 'samples')
if os.environ.get('DW_WEB'):
    app.WEB = os.environ['DW_WEB']
validate.REFERENCE = os.path.join(work, 'reference')
terrain.USER_DEM_DIR = os.path.join(work, 'terrain')
for d in ('results', 'samples', 'reference', 'terrain'):
    os.makedirs(os.path.join(work, d), exist_ok=True)

N_GEOID = -40.0
S = 800; GSD = 0.5
X0, Y0 = 680000.0, 3440000.0     # UTM 43N, near Shimla
CRS = 'EPSG:32643'
yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
DTM = (1000 + 0.06 * xx * GSD + 25 * np.exp(-(((xx - 600) / 150) ** 2 + ((yy - 200) / 150) ** 2))).astype(np.float32)  # slope + hill

def fake_build_dtm(image_path, ndsm, ground, prefer=None):
    with rasterio.open(image_path) as src:
        if not src.crs:
            return None, {'none': 'image has no georeferencing'}
        tr = src.transform
    # terrain under any part of the synthetic area: evaluate the formula at the pixel's map position
    h, w = ndsm.shape
    cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    x, y = tr * (cols, rows)
    px, py = (x - X0) / GSD, (Y0 - y) / GSD
    d = 1000 + 0.06 * px * GSD + 25 * np.exp(-(((px - 600) / 150) ** 2 + ((py - 200) / 150) ** 2))
    src = 'synthetic test terrain' if not prefer else prefer.split('__')[-1]
    return d.astype(np.float32), {'source': src, 'datum': terrain.DATUM, 'geoid_undulation_m': N_GEOID, 'relief_m': 30}
terrain.build_dtm = fake_build_dtm
terrain.laser_correct = lambda path, dtm, und: (dtm, {'none': '0 ICESat-2 ground photons in the scene (need 50)'})
terrain.geoid_shift = lambda lon, lat, *a: 0.6

BUILDINGS = [  # (row0, col0, size_rows, size_cols, true height m)
    (100, 100, 40, 60, 24), (100, 220, 50, 50, 12), (220, 100, 60, 40, 30), (230, 230, 40, 40, 9),
    (380, 120, 50, 80, 15), (400, 300, 40, 40, 21), (520, 140, 40, 40, 6), (540, 300, 60, 60, 18)]
TREES = [(80, 450, 120, 120), (600, 500, 150, 200)]
MODEL_K = 0.75      # the stub model under-estimates buildings by 25 %
TREE_TRUE, TREE_MODEL = 18.0, 12.0
SUN_EL, SUN_AZ = 45.0, 135.0   # sun in the south-east: shadows fall to the north-west, length = height


def make(name, collapsed=(), new=(), cleared_trees=(), shift=(0, 0), georef=True):
    h = np.zeros((S, S), np.float32); lc = np.full((S, S), 0, np.uint8)
    rgb = np.zeros((S, S, 3), np.uint8); rgb[:] = (168, 152, 126)
    lc[:, 380:396] = 3; rgb[:, 380:396] = (92, 92, 96)          # a north-south road
    lc[440:456, :] = 3; rgb[440:456, :] = (92, 92, 96)           # an east-west road
    for k, (r0, c0, tr_, tc) in enumerate(TREES):
        if k in cleared_trees:
            lc[r0:r0 + tr_, c0:c0 + tc] = 0; rgb[r0:r0 + tr_, c0:c0 + tc] = (140, 112, 84)   # landslide scar
            continue
        lc[r0:r0 + tr_, c0:c0 + tc] = 4; h[r0:r0 + tr_, c0:c0 + tc] = TREE_MODEL
        rgb[r0:r0 + tr_, c0:c0 + tc] = (48, 96, 52)
    bl = list(BUILDINGS) + list(new)
    for k, (r0, c0, sr, sc, H) in enumerate(bl):
        if k in collapsed:
            lc[r0:r0 + sr, c0:c0 + sc] = 0; h[r0:r0 + sr, c0:c0 + sc] = 0.6; rgb[r0:r0 + sr, c0:c0 + sc] = (150, 138, 128)
            continue
        L = int(round(H / math.tan(math.radians(SUN_EL)) / GSD))       # shadow length in pixels, towards the north-west
        d = int(round(L / math.sqrt(2)))
        for t in range(1, d + 1):
            rr0, cc0 = r0 - t, c0 - t
            rgb[max(0, rr0):max(0, rr0 + sr), max(0, cc0):max(0, cc0 + sc)][
                (lc[max(0, rr0):max(0, rr0 + sr), max(0, cc0):max(0, cc0 + sc)] != 7)] = (34, 34, 40)
    for k, (r0, c0, sr, sc, H) in enumerate(bl):
        if k in collapsed:
            continue
        lc[r0:r0 + sr, c0:c0 + sc] = 7; h[r0:r0 + sr, c0:c0 + sc] = H * MODEL_K
        rgb[r0:r0 + sr, c0:c0 + sc] = (212, 208, 200)
    if shift != (0, 0):
        h, lc, rgb = (np.roll(np.roll(a, shift[0], 0), shift[1], 1) for a in (h, lc, rgb))
    rng = np.random.default_rng(1)
    u = (0.3 + 0.08 * h + rng.uniform(0, 0.2, h.shape)).astype(np.float32)
    path = os.path.join(app.SAMPLES, name + ('.tif' if georef else '.png'))
    if georef:
        prof = dict(driver='GTiff', height=S, width=S, count=3, dtype='uint8', crs=CRS,
                    transform=rasterio.transform.from_origin(X0, Y0, GSD, GSD), photometric='RGB')
        with rasterio.open(path, 'w', **prof) as dst:
            dst.write(np.moveaxis(rgb, -1, 0))
    else:
        from PIL import Image
        Image.fromarray(rgb).save(path)
    app.status[name] = {'state': 'running', 'progress': 0.5}
    app.finish_scene(name, path, h, u, lc, rgb)
    app.status[name] = {'state': 'done', 'progress': 1.0}


def photons():
    """ICESat-2 style photons: ground (cls 1) along a track and top of canopy (cls 3) over the trees."""
    from rasterio.warp import transform
    cols = np.arange(5, S - 5, 1).astype(float)
    pts = []
    for c in cols:
        r = 0.9 * c + 10
        if r >= S:
            continue
        ri, ci = int(r), int(c)
        tree = any(r0 <= ri < r0 + tr_ and c0 <= ci < c0 + tc for r0, c0, tr_, tc in TREES)
        pts.append((c, r, DTM[ri, ci], 1))
        if tree:
            pts.append((c, r, DTM[ri, ci] + TREE_TRUE, 3))
    c, r, z, cls = (np.array(v) for v in zip(*pts))
    x, y = X0 + c * GSD, Y0 - r * GSD
    lon, lat = transform(CRS, 'EPSG:4326', x.tolist(), y.tolist())
    n = len(c)
    return {'lon': np.array(lon), 'lat': np.array(lat), 'h': z + N_GEOID, 'cls': cls, 't': np.full(n, 1.6e9, np.int64),
            'track': np.ones(n, np.int64)}
terrain.icesat2_photons = lambda bounds: photons()

if __name__ == '__main__':
    if not os.path.exists(os.path.join(app.RESULTS, 'obsdb_test.tif')):
        make('town_before')
        make('town_after', collapsed=(0, 2), new=[(650, 120, 40, 50, 12)], cleared_trees=(0,), shift=(2, 1))
        make('town_png', georef=False)
        make('town_east')   # for mosaics: same image, shifted 300 m east
        with rasterio.open(os.path.join(app.SAMPLES, 'town_east.tif'), 'r+') as dst:
            dst.transform = rasterio.transform.from_origin(X0 + 300, Y0, GSD, GSD)
        for sfx in ('_height.tif', '_uncertainty.tif', '_landcover.tif'):
            with rasterio.open(os.path.join(app.RESULTS, 'town_east' + sfx), 'r+') as dst:
                dst.transform = rasterio.transform.from_origin(X0 + 300, Y0, GSD, GSD)
        m = json.load(open(os.path.join(app.RESULTS, 'town_east.json'))); m.pop('corners_lonlat', None); m.pop('center_lonlat', None)
        json.dump(m, open(os.path.join(app.RESULTS, 'town_east.json'), 'w'))
        app.ensure_extras('town_east', os.path.join(app.SAMPLES, 'town_east.tif'))
    # fixtures for the browser test: an observed flood mask (ground below +2.5 m = water) and a DEM file
    prof = dict(driver='GTiff', height=S, width=S, count=1, dtype='float32', crs=CRS, transform=rasterio.transform.from_origin(X0, Y0, GSD, GSD))
    with rasterio.open(os.path.join(app.RESULTS, 'obsmask_test.tif'), 'w', **dict(prof, dtype='uint8')) as dst:
        dst.write((DTM < DTM.min() + 2.5).astype(np.uint8), 1)
    with rasterio.open(os.path.join(app.RESULTS, 'obsdb_test.tif'), 'w', **prof) as dst:   # radar dB: water -22, land -8
        rng = np.random.default_rng(3)
        dst.write(np.where(DTM < DTM.min() + 2.5, -22, -8).astype(np.float32) + rng.normal(0, 1.5, (S, S)).astype(np.float32), 1)
    with rasterio.open(os.path.join(app.RESULTS, 'dem_test.tif'), 'w', **prof) as dst:
        dst.write(DTM, 1)
    app.enqueue_missing()
    from http.server import ThreadingHTTPServer
    print(f'harness on http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), app.Handler).serve_forever()
