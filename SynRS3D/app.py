"""DepthWizard demo UI: browse test scenes, run RS3DAda, view height map in 2D / 3D, flood scenarios.
GeoTIFF scenes also get bare-ground terrain and an absolute DSM (metres above sea level) via terrain.py.

usage: .venv/bin/python app.py   ->   http://127.0.0.1:8000
Scenes live in demo/samples (any PNG/JPG/TIF); results are cached in demo/results.
"""
import argparse, glob, hashlib, json, os, queue, re, socket, threading, traceback, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from math import atan, cos, sinh

import cv2
import numpy as np
import rasterio
import rasterio.warp
from PIL import Image

import infer_height
import terrain
import tools
import validate
from utils import geo_func

ROOT = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(ROOT, 'demo', 'samples')
RESULTS = os.path.join(ROOT, 'demo', 'results')
WEB = os.path.join(ROOT, 'web', 'index.html')   # classic viewer, at /classic
APP = os.path.join(ROOT, 'web', 'app')          # React UI built from frontend/ (npm run build), at / and /app/
FIELD = os.path.join(ROOT, 'web', 'field.html')
VENDOR = os.path.join(ROOT, 'web', 'vendor')
APP_TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2',
             '.woff': 'font/woff', '.svg': 'image/svg+xml', '.png': 'image/png', '.json': 'application/json'}
EXTS = ('.tif', '.tiff', '.png', '.jpg', '.jpeg')
GRID = 512            # max side of the height grid sent to the browser
MAX_UPLOAD = 50 << 20
BUILDING = infer_height.LANDCOVER.index('buildings')
FLOOR_M = 3.0         # assumed storey height for floor estimates
SUFFIXES = ('', '_height', '_unc', '_uncertainty', '_landcover', '_bid', '_buildings', '_corr',
            '_height_corrected', '_dtm', '_dsm', '_lc', '_valerr', '_validation', '_dsm_gcp', '_dh', '_bidb', '_change',
            '_obsflood', '_wms', '_height_fixed', '_dsm_fixed', '_field', '_canopy')  # per-scene result files
TERRAIN_VERSION = 4  # bump to recompute terrain for every scene (2: ICESat-2 laser correction; 3: no laser shift from a single ICESat-2 pass, terrain.LASER_MIN_PASSES; 4: no levelling on photons over the model's buildings, terrain.roof_mask)
# Height correction learned on DFC2019 LiDAR (demo/height_correction.py); only present if it passed every test split
CHOSEN = os.path.join(ROOT, 'demo', 'benchmark', 'height_correction_chosen.json')
CORR = json.load(open(CHOSEN)) if os.path.exists(CHOSEN) else None
CORR_FP = hashlib.md5(json.dumps(CORR, sort_keys=True).encode()).hexdigest()[:8] if CORR else None
CONFORMAL = infer_height.load_conformal()  # calibrated 90% interval for building blocks (demo/uncertainty_calibration.py)

status = {}           # name -> {'state': queued|running|done|error, 'progress': 0..1, 'error': str}
jobs = queue.Queue()


def scene_files():
    return {os.path.splitext(f)[0]: os.path.join(SAMPLES, f)
            for f in sorted(os.listdir(SAMPLES)) if f.lower().endswith(EXTS)}


def ground_gsd(path):
    """Metres per pixel on the ground, or None if the image has no georeferencing."""
    with rasterio.open(path) as src:
        if not src.crs:
            return None
        res, (_, cy) = src.transform.a, src.xy(src.height // 2, src.width // 2)
        if src.crs.to_epsg() == 3857:
            return res * cos(atan(sinh(cy / 6378137)))
        if src.crs.is_geographic:
            return res * 111320 * cos(cy * 3.14159265 / 180)
        return res


def extract_buildings(h, u, lc, gsd, rgb):
    """Building blocks = land-cover 'buildings' pixels at least 2 m tall, split into instances by a watershed that
    grows ~2 m-deep cores outwards and stops at roof edges in the photo. Attached buildings stay one block.
    Returns (id image, list of per-block stats), blocks under 20 m² dropped."""
    mask = ((lc == BUILDING) & (h >= 2)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))  # drop 1-2 px speckle
    cores = (cv2.distanceTransform(mask, cv2.DIST_L2, 5) >= 2.0 / gsd).astype(np.uint8)
    _, core_lbl = cv2.connectedComponents(cores, connectivity=4)
    markers = core_lbl.astype(np.int32) + 1          # 1 = background, 2.. = cores, 0 = to be assigned
    markers[mask == 0] = 1
    markers[(mask == 1) & (cores == 0)] = 0
    cv2.watershed(np.ascontiguousarray(rgb[:, :, 2::-1]), markers)  # BGR photo; boundaries become -1
    labels = np.clip(markers - 1, 0, None).ravel()
    order = np.argsort(labels, kind='stable')
    counts = np.bincount(labels)
    starts = np.cumsum(counts) - counts
    H, W = h.shape
    hf, uf = h.ravel(), u.ravel()
    ids = np.zeros(H * W, np.float32)
    out = []
    for k in range(1, len(counts)):
        pix = order[starts[k]:starts[k] + counts[k]]
        if len(pix) * gsd * gsd < 20:
            continue
        hk = hf[pix]
        height = float(np.median(hk))
        if height < 2:
            continue
        unc = round(float(np.median(uf[pix])), 2)
        out.append({'id': len(out) + 1, 'area_m2': round(len(pix) * gsd * gsd, 1),
                    'height_m': round(height, 2), 'height_p90': round(float(np.percentile(hk, 90)), 2),
                    'unc_m': unc, 'ci90': block_ci(round(height, 2), unc), 'floors': max(1, round(height / FLOOR_M)),
                    'cx': round(float((pix % W).mean()) / W, 4), 'cy': round(float((pix // W).mean()) / H, 4)})
        ids[pix] = len(out)
    return ids.reshape(H, W), out


def block_ci(height, unc):
    ci = infer_height.building_interval(height, unc, CONFORMAL)
    return [round(ci[0], 1), round(ci[1], 1)] if ci else None


def ensure_intervals(name):
    """Add / refresh the calibrated 90% interval of each building block in saved results (no model run needed)."""
    bf = os.path.join(RESULTS, name + '_buildings.json')
    if not os.path.exists(bf):
        return
    blocks = json.load(open(bf))
    new = [block_ci(b['height_m'], b['unc_m']) for b in blocks]
    if any(b.get('ci90') != c for b, c in zip(blocks, new)):
        for b, c in zip(blocks, new):
            b['ci90'] = c
        json.dump(blocks, open(bf, 'w'))


def ensure_corrected(name, path):
    """Add corrected heights from the saved height + land-cover rasters (no model run needed)."""
    meta_f = os.path.join(RESULTS, name + '.json')
    meta = json.load(open(meta_f))
    if not CORR or meta.get('corrected', {}).get('fp') == CORR_FP:
        return
    h = rasterio.open(os.path.join(RESULTS, name + '_height.tif')).read(1)
    lc = rasterio.open(os.path.join(RESULTS, name + '_landcover.tif')).read(1).astype(np.uint8)
    hc = infer_height.correct_heights(h, lc, CORR)
    infer_height.save_tiff_with_geo_info(path, os.path.join(RESULTS, name + '_height_corrected.tif'), hc)
    gw, gh = meta['grid_w'], meta['grid_h']
    grid = np.asarray(Image.fromarray(hc, 'F').resize((gw, gh), Image.BILINEAR), np.float32)
    grid.astype('<f4').tofile(os.path.join(RESULTS, name + '_corr.f32'))
    bid = np.fromfile(os.path.join(RESULTS, name + '_bid.f32'), '<f4').reshape(gh, gw)
    bf = os.path.join(RESULTS, name + '_buildings.json')
    blocks = json.load(open(bf))
    for b in blocks:  # block height after correction = median of its corrected grid cells
        sel = bid == b['id']
        b['height_corr_m'] = round(float(np.median(grid[sel])), 2) if sel.any() else b['height_m']
    json.dump(blocks, open(bf, 'w'))
    meta['corrected'] = {'fp': CORR_FP, 'method': CORR['method'], 'source': CORR.get('source', ''),
                         'max': float(hc.max()), 'p99': float(np.percentile(hc, 99))}
    json.dump(meta, open(meta_f, 'w'))


def ensure_terrain(name, path, force=False):
    """Absolute heights: bare-ground terrain (DTM) under the scene and DSM = DTM + height above ground, both in
    metres above mean sea level (EGM2008). Uses the saved rasters (no model run). Non-georeferenced images keep
    relative heights; a failed download is retried on the next start."""
    meta_f = os.path.join(RESULTS, name + '.json')
    meta = json.load(open(meta_f))
    t = meta.get('terrain', {})
    if not force and t.get('version') == TERRAIN_VERSION and 'error' not in t and 'unavailable' not in (t.get('laser') or {}).get('none', ''):
        return
    h = rasterio.open(os.path.join(RESULTS, name + '_height.tif')).read(1)
    lc = rasterio.open(os.path.join(RESULTS, name + '_landcover.tif')).read(1).astype(np.uint8)
    try:
        dtm, info = terrain.build_dtm(path, h, infer_height.ground_mask(h, lc),
                                       source=os.path.join(terrain.USER_DEM_DIR, meta['terrain_prefer']) if meta.get('terrain_prefer') else None)
    except Exception as e:  # offline, or no DEM for this area
        dtm, info = None, {'error': f'terrain unavailable: {e}'}
    info['version'] = TERRAIN_VERSION
    if dtm is not None:  # level-check against NASA ICESat-2 laser ground photons (shift, where there are enough)
        dtm, info['laser'] = terrain.laser_correct(path, dtm, info.get('geoid_undulation_m'), h, lc)
        tags = dict(VERTICAL_DATUM=terrain.DATUM, UNITS='metre', TERRAIN_SOURCE=info['source'])
        terrain.save_with_tags(path, os.path.join(RESULTS, name + '_dtm.tif'), dtm,
                               infer_height.save_tiff_with_geo_info, CONTENT='bare-ground terrain (DTM)', **tags)
        terrain.save_with_tags(path, os.path.join(RESULTS, name + '_dsm.tif'), dtm + np.clip(h, 0, None),
                               infer_height.save_tiff_with_geo_info, CONTENT='surface model (DSM) = DTM + height', **tags)
        gw, gh = meta['grid_w'], meta['grid_h']
        grid = np.asarray(Image.fromarray(dtm, 'F').resize((gw, gh), Image.BILINEAR), np.float32)
        grid.astype('<f4').tofile(os.path.join(RESULTS, name + '_dtm.f32'))
        bid = np.fromfile(os.path.join(RESULTS, name + '_bid.f32'), '<f4').reshape(gh, gw)
        bf = os.path.join(RESULTS, name + '_buildings.json')
        blocks = json.load(open(bf))
        for b in blocks:  # the block's ground level = median terrain under it
            sel = bid == b['id']
            b['ground_m'] = round(float(np.median(grid[sel])), 2) if sel.any() else float(np.median(grid))
        json.dump(blocks, open(bf, 'w'))
        info.update(grid_min=float(grid.min()), grid_max=float(grid.max()))
    meta['terrain'] = info
    json.dump(meta, open(meta_f, 'w'))


def ensure_extras(name, path):
    """Land-cover grid for the browser (route costs, rain runoff) and the scene centre in lon/lat (rain forecast).
    Uses the saved rasters (no model run)."""
    meta_f = os.path.join(RESULTS, name + '.json')
    meta = json.load(open(meta_f))
    lc_f = os.path.join(RESULTS, name + '_lc.f32')
    if not os.path.exists(lc_f):
        lc = rasterio.open(os.path.join(RESULTS, name + '_landcover.tif')).read(1).astype(np.float32)
        grid = np.asarray(Image.fromarray(lc, 'F').resize((meta['grid_w'], meta['grid_h']), Image.NEAREST), np.float32)
        grid.astype('<f4').tofile(lc_f)
    dtm_tif, dtm_f = os.path.join(RESULTS, name + '_dtm.tif'), os.path.join(RESULTS, name + '_dtm.f32')
    if os.path.exists(dtm_tif) and not os.path.exists(dtm_f):   # browser grid of a terrain built elsewhere (e.g. a cloned demo)
        dtm = rasterio.open(dtm_tif).read(1).astype(np.float32)
        grid = np.asarray(Image.fromarray(dtm, 'F').resize((meta['grid_w'], meta['grid_h']), Image.BILINEAR), np.float32)
        grid.astype('<f4').tofile(dtm_f)
    if 'corners_lonlat' not in meta:   # image corners, for drone plans and lon/lat read-outs in the viewer
        meta['corners_lonlat'] = tools.corners_lonlat(path)
        json.dump(meta, open(meta_f, 'w'))
    if 'center_lonlat' not in meta:
        with rasterio.open(path) as src:
            ll = None
            if src.crs:
                x, y = src.xy(src.height // 2, src.width // 2)
                lon, lat = rasterio.warp.transform(src.crs, 'EPSG:4326', [x], [y])
                ll = [round(lon[0], 6), round(lat[0], 6)]
        meta['center_lonlat'] = ll
        json.dump(meta, open(meta_f, 'w'))


def ensure_photo(name, path):
    out = os.path.join(RESULTS, name + '.jpg')
    if not os.path.exists(out):
        Image.fromarray(geo_func.load_multiband(path)[:, :, :3]).save(out, quality=88)


def finish_scene(name, path, h, u, lc, rgb, grid=GRID):
    """Everything after the model run: result GeoTIFFs, building blocks, browser grids, metadata, terrain, extras.
    Shared by the model worker and mosaics (which merge saved results instead of running the model)."""
    infer_height.save_tiff_with_geo_info(path, os.path.join(RESULTS, name + '_height.tif'), h)
    infer_height.save_tiff_with_geo_info(path, os.path.join(RESULTS, name + '_uncertainty.tif'), u)
    infer_height.save_tiff_with_geo_info(path, os.path.join(RESULTS, name + '_landcover.tif'), lc.astype(np.float32))
    gsd = ground_gsd(path)
    bid, buildings = extract_buildings(h, u, lc, gsd or 0.5, rgb[:, :, :3])
    json.dump(buildings, open(os.path.join(RESULTS, name + '_buildings.json'), 'w'))
    H, W = h.shape
    s = min(1.0, grid / max(H, W))
    gw, gh = max(1, round(W * s)), max(1, round(H * s))
    for arr, suffix, rs in [(h, '', Image.BILINEAR), (u, '_unc', Image.BILINEAR), (bid, '_bid', Image.NEAREST)]:
        g = np.asarray(Image.fromarray(arr.astype(np.float32), 'F').resize((gw, gh), rs), np.float32)
        g.astype('<f4').tofile(os.path.join(RESULTS, name + suffix + '.f32'))
    meta = {'grid_w': gw, 'grid_h': gh, 'width': W, 'height': H, 'gsd': gsd or 0.5, 'gsd_assumed': gsd is None,
            'max': float(h.max()), 'p99': float(np.percentile(h, 99)), 'mean': float(h.mean()),
            'built_pct': float((h > 3).mean() * 100),
            'unc_mean': float(u.mean()), 'unc_p95': float(np.percentile(u, 95)),
            'unc_built': float(u[h > 3].mean()) if (h > 3).any() else 0.0,
            'buildings': len(buildings), 'floor_m': FLOOR_M}
    json.dump(meta, open(os.path.join(RESULTS, name + '.json'), 'w'))
    ensure_photo(name, path)
    ensure_corrected(name, path)
    ensure_terrain(name, path)
    ensure_extras(name, path)


def worker():
    model = None  # loaded on the first job, so a server with everything cached starts instantly and stays light
    while True:
        name = jobs.get()
        path = scene_files().get(name)
        st = status[name]
        if model is None:
            try:
                model, device, dtype = infer_height.load_model(infer_height.WEIGHTS, fp16=True)
                print(f'model ready on {device}', flush=True)
            except (ImportError, OSError) as e:   # demo hosting (e.g. Replit): no PyTorch or no weights
                print(f'height model unavailable: {e}', flush=True)
                st.update(state='error', error='This server runs in demo mode: the height model is not installed here, '
                          'so only the scenes already processed can be opened. Run DepthWizard on your own computer '
                          '(see README) to process new images.')
                continue
        try:
            st['state'] = 'running'
            img = geo_func.load_multiband(path)
            out = infer_height.predict(model, device, dtype, img, use_tta=True, full=True,
                                       progress=lambda d, t: st.update(progress=d / t))
            finish_scene(name, path, out['height'], out['std'], out['landcover'], img)
            st.update(state='done', progress=1.0)
        except Exception as e:
            traceback.print_exc()
            st.update(state='error', error=str(e))


def build_mosaic(name, names, grid):
    """Merge processed georeferenced scenes into a new scene <name> (image + model outputs; no model run)."""
    st = status[name]
    try:
        files = scene_files()
        rgb, h, u, lc, profile = tools.mosaic_arrays([(files[n], n) for n in names])
        st['progress'] = 0.4
        path = os.path.join(SAMPLES, name + '.tif')
        with rasterio.open(path, 'w', **profile) as dst:
            dst.write(np.moveaxis(rgb, -1, 0))
        finish_scene(name, path, h.astype(np.float32), u.astype(np.float32), lc, rgb, grid)
        meta_f = os.path.join(RESULTS, name + '.json')
        meta = json.load(open(meta_f))
        meta['mosaic_of'] = names
        json.dump(meta, open(meta_f, 'w'))
        st.update(state='done', progress=1.0)
    except Exception as e:
        traceback.print_exc()
        st.update(state='error', error=str(e))


def enqueue_missing():
    for name, path in scene_files().items():
        if name in status:
            continue
        ensure_photo(name, path)
        meta = os.path.join(RESULTS, name + '.json')
        if os.path.exists(meta) and 'buildings' in json.load(open(meta)):  # older results lack newer outputs
            ensure_intervals(name)
            ensure_corrected(name, path)
            ensure_terrain(name, path)
            ensure_extras(name, path)
            status[name] = {'state': 'done', 'progress': 1.0}
        else:
            status[name] = {'state': 'queued', 'progress': 0.0}
            jobs.put(name)


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype='application/json'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == '/healthz':   # for uptime / keep-alive pings
            return self.send(200, {'ok': True, 'scenes': len(scene_files())})
        built = os.path.isfile(os.path.join(APP, 'index.html'))
        if path == '/classic' or (path == '/' and not built):
            return self.send(200, open(WEB, 'rb').read(), 'text/html; charset=utf-8')
        if self.path.split('?')[0] == '/field':   # phone page for collecting GNSS / GPS control points in the field
            return self.send(200, open(FIELD, 'rb').read(), 'text/html; charset=utf-8')
        if self.path.startswith(('/api/export', '/api/field')):
            return self.get_api()
        if path in ('/', '/app', '/app/'):
            return self.send(200, open(os.path.join(APP, 'index.html'), 'rb').read(), APP_TYPES['.html'])
        m = re.fullmatch(r'/app/([\w./-]+)', path)
        if m and '..' not in m[1] and os.path.isfile(os.path.join(APP, m[1])):
            return self.send(200, open(os.path.join(APP, m[1]), 'rb').read(), APP_TYPES.get(os.path.splitext(m[1])[1], 'application/octet-stream'))
        if self.path == '/api/scenes':
            out = []
            for name in scene_files():
                st = dict(status.get(name, {'state': 'queued', 'progress': 0}))
                meta = os.path.join(RESULTS, name + '.json')
                if st['state'] == 'done' and os.path.exists(meta):
                    st['meta'] = json.load(open(meta))
                out.append({'name': name, **st})
            return self.send(200, out)
        m = re.fullmatch(r'/results/([\w-]+)\.(jpg|png|f32|json|tif)', urllib.parse.urlsplit(self.path).path)
        if m:
            f = os.path.join(RESULTS, f'{m[1]}.{m[2]}')
            if os.path.exists(f):
                ctype = {'jpg': 'image/jpeg', 'png': 'image/png', 'json': 'application/json', 'tif': 'image/tiff'}.get(m[2], 'application/octet-stream')
                return self.send(200, open(f, 'rb').read(), ctype)
        m = re.fullmatch(r'/vendor/([\w./-]+\.js)', self.path)  # three.js, bundled so the demo runs offline
        if m and '..' not in m[1] and os.path.isfile(os.path.join(VENDOR, m[1])):
            return self.send(200, open(os.path.join(VENDOR, m[1]), 'rb').read(), 'text/javascript')
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        if self.path.startswith(('/api/validate', '/api/icesat2', '/api/gcp', '/api/gedi')):
            return self.validation_api()
        if not self.path.startswith('/api/upload'):
            return self.tools_api()
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        m = re.fullmatch(r'/api/upload\?name=([^&]+)(&.*)?', self.path)
        size = int(self.headers.get('Content-Length', 0))
        if not m or not 0 < size <= MAX_UPLOAD:
            return self.send(400, {'error': 'bad request or file over 50 MB'})
        base, ext = os.path.splitext(urllib.parse.unquote(m[1]).lower())
        name = re.sub(r'[^\w-]+', '_', base)[:60].strip('_') or 'upload'
        if ext not in EXTS:
            return self.send(400, {'error': 'use PNG, JPG or GeoTIFF'})
        path = os.path.join(SAMPLES, name + ext)
        with open(path, 'wb') as f:
            f.write(self.rfile.read(size))
        side = os.path.join(SAMPLES, name + '.bands.json')   # band order chosen in the upload form (auto = from the file)
        if q.get('bands') in ('rgb', 'bgr'):
            json.dump({'order': q['bands']}, open(side, 'w'))
        elif os.path.exists(side):
            os.remove(side)
        for f in os.listdir(RESULTS):  # drop stale results from an earlier upload with this name
            if os.path.splitext(f)[0] in {name + sfx for sfx in SUFFIXES}:
                os.remove(os.path.join(RESULTS, f))
        try:
            status.pop(name, None)
            enqueue_missing()
        except Exception as e:  # unreadable image
            os.remove(path)
            return self.send(400, {'error': f'could not read image: {e}'})
        self.send(200, {'name': name})

    def validation_api(self):
        """POST /api/validate?name=&kind=dsm|ndsm|dtm|points&datum=egm2008|egm96|ellipsoid&file=  (body: raster or CSV)
             /api/icesat2?name=      laser check
             /api/gcp?name=          (body: {"points": [{u, v, z}]}, or {"clear": true})
        Results are kept per scene in <scene>_validation.json (one entry per check), GCP fit in the scene metadata."""
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        name, size = q.get('name', ''), int(self.headers.get('Content-Length', 0))
        path = scene_files().get(name)
        if not path or status.get(name, {}).get('state') != 'done':
            return self.send(400, {'error': 'unknown or unprocessed scene'})
        if size > MAX_UPLOAD:
            return self.send(400, {'error': 'file over 50 MB'})
        body = self.rfile.read(size) if size else b''
        val_f = os.path.join(RESULTS, name + '_validation.json')
        saved = json.load(open(val_f)) if os.path.exists(val_f) else {}
        try:
            scene = validate.Scene(name, path)
            if self.path.startswith('/api/gcp'):
                req = json.loads(body or b'{}')
                meta_f = os.path.join(RESULTS, name + '.json')
                meta = json.load(open(meta_f))
                if req.get('clear'):
                    meta.pop('gcp', None)
                    out_f = os.path.join(RESULTS, name + '_dsm_gcp.tif')
                    if os.path.exists(out_f):
                        os.remove(out_f)
                    json.dump(meta, open(meta_f, 'w'))
                    return self.send(200, {'cleared': True})
                fit = validate.fit_gcp(scene, req.get('points', []))
                terrain.save_with_tags(path, os.path.join(RESULTS, name + '_dsm_gcp.tif'), validate.apply_gcp(scene, fit),
                                       infer_height.save_tiff_with_geo_info, CONTENT='surface model calibrated with ground control points',
                                       UNITS='metre', GCP_TERMS=','.join(fit['terms']))
                meta['gcp'] = fit
                json.dump(meta, open(meta_f, 'w'))
                return self.send(200, fit)
            if self.path.startswith('/api/icesat2'):
                res = validate.compare_icesat2(scene)
                key = 'icesat2'
            elif self.path.startswith('/api/gedi'):
                res = validate.compare_gedi(scene)
                key = 'gedi'
            else:
                kind, datum = q.get('kind', 'dsm'), q.get('datum', 'egm2008')
                fname = re.sub(r'[^\w.-]+', '_', q.get('file', 'reference'))[:80]
                if not body:
                    return self.send(400, {'error': 'no file'})
                if kind == 'points' or fname.lower().endswith(('.csv', '.txt')):
                    res, key = validate.compare_points(scene, validate.read_points(body.decode('utf-8-sig')), datum), 'points'
                else:
                    os.makedirs(validate.REFERENCE, exist_ok=True)
                    ref = os.path.join(validate.REFERENCE, f'{name}__{fname}')
                    open(ref, 'wb').write(body)
                    res, key = validate.compare_raster(scene, ref, kind, datum), 'raster'
            saved[key] = res
            json.dump(saved, open(val_f, 'w'))
            return self.send(200, {'key': key, **res})
        except Exception as e:
            traceback.print_exc()
            return self.send(400, {'error': f'{type(e).__name__}: {e}'})

    def scene_q(self):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        name = q.get('name', '')
        path = scene_files().get(name)
        if not path or status.get(name, {}).get('state') != 'done':
            raise ValueError('unknown or unprocessed scene')
        return q, name, path

    def get_api(self):
        """GET /api/export?name=&fmt=geojson|cityjson   building footprints / LOD1 solids
               /api/field?name=                         points sent by the field page"""
        route = urllib.parse.urlsplit(self.path).path
        try:
            q, name, path = self.scene_q()
            if route == '/api/export':
                fmt = q.get('fmt', 'geojson')
                doc = tools.cityjson(name, path) if fmt == 'cityjson' else tools.geojson(name, path)
                body = json.dumps(doc).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Disposition', f'attachment; filename="{name}_{"city.json" if fmt == "cityjson" else "footprints.geojson"}"')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if route == '/api/field':
                f = os.path.join(RESULTS, name + '_field.json')
                return self.send(200, json.load(open(f)) if os.path.exists(f) else [])
        except Exception as e:
            traceback.print_exc()
            return self.send(400, {'error': f'{type(e).__name__}: {e}'})
        self.send(404, {'error': 'not found'})

    def tools_api(self):
        """POST /api/change?name=&before=          before/after height change (name = the after scene)
                /api/obsflood?name=&kind=&threshold=&file=   observed flood raster (body)
                /api/mosaic                            {"names": [...], "name": "...", "grid": 512|1024}
                /api/heightfix?name=                   {"fit": "trees"} | {"buildings": k, "trees": k} | {"clear": true}
                /api/conformal?name=                   {"source": "raster|points|icesat2", "level": "0.90"} | {"clear": true}
                /api/wms?name=                         {"url", "layers", "styles"}
                /api/dem?name=&datum=&file=            a DEM GeoTIFF (body) to use as this scene's terrain | ?clear=1
                /api/field?name=                       {"points": [{lat, lon, alt, acc, note, t}]} from the field page
                /api/gnss?name=&datum=[&source=field]  GNSS points (CSV / GPX body, or the field page's) -> u, v, z"""
        size = int(self.headers.get('Content-Length', 0))
        if size > MAX_UPLOAD:
            return self.send(400, {'error': 'file over 50 MB'})
        body = self.rfile.read(size) if size else b''
        route = urllib.parse.urlsplit(self.path).path
        try:
            if route == '/api/mosaic':
                req = json.loads(body or b'{}')
                names = [n for n in req.get('names', []) if status.get(n, {}).get('state') == 'done']
                if len(names) < 2:
                    raise ValueError('choose at least two processed scenes')
                out = re.sub(r'[^\w-]+', '_', req.get('name') or 'mosaic')[:60].strip('_') or 'mosaic'
                if out in scene_files() or out in status:
                    raise ValueError(f'a scene called {out} already exists')
                status[out] = {'state': 'running', 'progress': 0.1}
                threading.Thread(target=build_mosaic, args=(out, names, int(req.get('grid', GRID))), daemon=True).start()
                return self.send(200, {'name': out})
            q, name, path = self.scene_q()
            meta_f = os.path.join(RESULTS, name + '.json')
            meta = json.load(open(meta_f))
            fname = re.sub(r'[^\w.-]+', '_', q.get('file', 'upload'))[:80]
            req = json.loads(body or b'{}') if route in ('/api/heightfix', '/api/conformal', '/api/wms', '/api/field') else None
            if route == '/api/canopy':   # Meta's global canopy height map for this scene (trees)
                res = tools.canopy_for_scene(name, path, infer_height.save_tiff_with_geo_info, meta['grid_w'], meta['grid_h'])
                meta['canopy'] = res
                json.dump(meta, open(meta_f, 'w'))
                return self.send(200, res)
            if route == '/api/change':
                before = q.get('before', '')
                if before == name or status.get(before, {}).get('state') != 'done':
                    raise ValueError('choose a different, processed scene as the before image')
                res = tools.change(name, path, before, scene_files()[before])
                json.dump(res, open(os.path.join(RESULTS, name + '_change.json'), 'w'))
                return self.send(200, res)
            if route == '/api/obsflood':
                if not body:
                    raise ValueError('no file')
                os.makedirs(validate.REFERENCE, exist_ok=True)
                ref = os.path.join(validate.REFERENCE, f'{name}__obs_{fname}')
                open(ref, 'wb').write(body)
                res = tools.observed_flood(name, path, ref, q.get('kind', 'auto'), q.get('threshold'))
                meta['obsflood'] = res
                json.dump(meta, open(meta_f, 'w'))
                return self.send(200, res)
            if route == '/api/heightfix':
                if req.get('fit') == 'trees':
                    if req.get('source') == 'gedi':   # GEDI rh98 vs the model on tree footprints
                        g = validate.compare_gedi(validate.Scene(name, path))
                        if not g.get('tree_fit'):
                            raise ValueError(g.get('note') or f"{g.get('tree_shots', 0)} usable GEDI tree footprints (need 30)")
                        return self.send(200, dict(g['tree_fit'], source='gedi', trees_model=g['trees_model'], trees_canopy_map=g['trees_canopy_map']))
                    return self.send(200, tools.fit_tree_scale(validate.Scene(name, path)))
                canopy_trees = req.get('trees_source') == 'canopy'
                sc = {'buildings': float(req.get('buildings', 1)), 'trees': 1.0 if canopy_trees else float(req.get('trees', 1))}
                if req.get('clear') or (not canopy_trees and all(abs(v - 1) < 1e-6 for v in sc.values())):
                    meta.pop('class_scale', None)
                    for sfx in ('_height_fixed.tif', '_dsm_fixed.tif'):
                        if os.path.exists(os.path.join(RESULTS, name + sfx)):
                            os.remove(os.path.join(RESULTS, name + sfx))
                    json.dump(meta, open(meta_f, 'w'))
                    return self.send(200, {'cleared': True})
                if not all(0.3 <= v <= 4 for v in sc.values()):
                    raise ValueError('height scales must be between 0.3 and 4')
                info = tools.apply_class_scale(name, path, sc, infer_height.save_tiff_with_geo_info, canopy=canopy_trees)
                meta['class_scale'] = dict(sc, source=req.get('source', {}), trees_source='canopy' if canopy_trees else 'scale', **info)
                json.dump(meta, open(meta_f, 'w'))
                return self.send(200, meta['class_scale'])
            if route == '/api/conformal':
                if req.get('clear'):
                    meta.pop('conformal', None)
                    json.dump(meta, open(meta_f, 'w'))
                    return self.send(200, {'cleared': True})
                val_f = os.path.join(RESULTS, name + '_validation.json')
                saved = json.load(open(val_f)) if os.path.exists(val_f) else {}
                c = (saved.get(req.get('source')) or {}).get('conformal')
                lv = req.get('level', '0.90')
                if not c or lv not in c['levels']:
                    raise ValueError('run that validation first (it provides the calibration)')
                meta['conformal'] = dict(c['levels'][lv], level=lv, u0=c['u0'], n=c['n'], source=req.get('source'))
                json.dump(meta, open(meta_f, 'w'))
                return self.send(200, meta['conformal'])
            if route == '/api/wms':
                res = tools.wms_overlay(name, path, req.get('url', ''), req.get('layers', ''), req.get('styles', ''))
                meta['wms'] = res
                json.dump(meta, open(meta_f, 'w'))
                return self.send(200, res)
            if route == '/api/dem':
                for old in glob.glob(os.path.join(terrain.USER_DEM_DIR, f'{name}__*.tif')):   # one uploaded DEM per scene
                    os.remove(old)
                if q.get('clear'):
                    meta.pop('terrain_prefer', None)
                else:
                    if not body:
                        raise ValueError('no file')
                    base = os.path.splitext(fname)[0]
                    if q.get('datum') == 'egm96' and 'egm96' not in base.lower():
                        base += '_egm96'
                    os.makedirs(terrain.USER_DEM_DIR, exist_ok=True)
                    dem = os.path.join(terrain.USER_DEM_DIR, f'{name}__{base}.tif')
                    open(dem, 'wb').write(body)
                    with rasterio.open(dem) as src, rasterio.open(path) as img:
                        ok = bool(src.crs) and img.crs is not None
                        if ok:   # the DEM must cover the whole scene
                            dw, ds, de, dn = rasterio.warp.transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
                            iw, is_, ie, in_ = rasterio.warp.transform_bounds(img.crs, 'EPSG:4326', *img.bounds)
                            ok = dw <= iw and ds <= is_ and de >= ie and dn >= in_
                    if not ok:
                        os.remove(dem)
                        raise ValueError('the DEM needs a coordinate system and must cover the whole scene')
                    meta['terrain_prefer'] = os.path.basename(dem)
                json.dump(meta, open(meta_f, 'w'))
                ensure_terrain(name, path, force=True)
                return self.send(200, json.load(open(meta_f)).get('terrain', {}))
            if route == '/api/field':
                f = os.path.join(RESULTS, name + '_field.json')
                pts = json.load(open(f)) if os.path.exists(f) else []
                new = [p for p in req.get('points', []) if isinstance(p, dict) and 'lat' in p and 'lon' in p]
                pts += new
                json.dump(pts, open(f, 'w'))
                return self.send(200, {'added': len(new), 'total': len(pts)})
            if route == '/api/gnss':
                sc = validate.Scene(name, path)
                if q.get('source') == 'field':   # typed benchmark heights are sea level; phone / GNSS heights ellipsoidal
                    f = os.path.join(RESULTS, name + '_field.json')
                    raw = json.load(open(f)) if os.path.exists(f) else []
                    pt = lambda p, z: {'lon': p['lon'], 'lat': p['lat'], 'z': float(z), 'note': p.get('note', '')}
                    groups = [([pt(p, p['known']) for p in raw if p.get('known') is not None], 'egm2008'),
                              ([pt(p, p['alt']) for p in raw if p.get('known') is None and p.get('alt') is not None], 'ellipsoid')]
                else:
                    groups = [(tools.parse_gnss(body.decode('utf-8-sig')), q.get('datum', 'egm2008'))]
                out = {'points': [], 'outside': 0}
                for pts, datum in groups:
                    if pts:
                        res = tools.gnss_points(sc, pts, datum)
                        out['points'] += res['points']
                        out['outside'] += res['outside']
                if not out['points'] and not out['outside']:
                    raise ValueError('no points with a height found')
                return self.send(200, out)
        except Exception as e:
            traceback.print_exc()
            return self.send(400, {'error': f'{type(e).__name__}: {e}'})
        self.send(404, {'error': 'not found'})

    def log_message(self, *a):
        pass


def keep_alive(url, every=300):
    """Ping this app's public address every 5 minutes (KEEPALIVE_URL), so a host that sleeps idle apps
    (Replit and similar) keeps it awake. Errors are ignored: the next ping tries again."""
    import time, urllib.request
    target = url.rstrip('/') + '/healthz'
    while True:
        time.sleep(every)
        try:
            urllib.request.urlopen(target, timeout=60).read()
        except Exception as e:
            print(f'keep-alive ping failed: {e}', flush=True)


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('10.255.255.255', 1))
            return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='DepthWizard local server')
    ap.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8000)))
    ap.add_argument('--host', default=os.environ.get('DW_HOST', '127.0.0.1'),
                    help='address to listen on; 0.0.0.0 for hosting (Replit, a server) so others can open it')
    ap.add_argument('--lan', action='store_true', help='also listen on the local network, so a phone on the same Wi-Fi '
                    'can open the field page (anyone on that network can then reach the app)')
    args = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    enqueue_missing()
    threading.Thread(target=worker, daemon=True).start()
    if os.environ.get('KEEPALIVE_URL'):
        threading.Thread(target=keep_alive, args=(os.environ['KEEPALIVE_URL'],), daemon=True).start()
        print(f'keep-alive: pinging {os.environ["KEEPALIVE_URL"]} every 5 minutes', flush=True)
    host = '0.0.0.0' if args.lan else args.host
    print(f'DepthWizard on http://{"127.0.0.1" if host == "0.0.0.0" else host}:{args.port} (listening on {host})', flush=True)
    if args.lan:
        print(f'Field page for phones on this network: http://{lan_ip()}:{args.port}/field', flush=True)
    ThreadingHTTPServer((host, args.port), Handler).serve_forever()
