"""Flood test on the May 2024 floods in Porto Alegre / Canoas (Brazil): does the flood we predict from a *pre-flood*
image (terrain + bathtub model, exactly as in the web viewer) match where the water really went?

usage: .venv/bin/python demo/flood_test.py   (after app.py has processed the '*_before' scenes listed in SCENES)
Reference: flood maps of IPH/UFRGS (Instituto de Pesquisas Hidraulicas), made on a 2010 LiDAR terrain model and
ignoring the flood walls/dikes, as ours does (most failed or were overtopped in May 2024):
  'Inundacao em 6 de Maio de 2024'   their flood extent for 6 May 2024 (Guaiba ~5.3 m)
  'simulada 5.0 m' / '5.5 m'         their bathtub simulations = the same model on LiDAR terrain (tests terrain only)
  metro map 'Simulacao cheia 500 cm' simplified 5.0 m simulation for the metro region (the only one covering Canoas)
Terrains compared (all EGM2008): raw GLO-30 (no model) | ours = GLO-30 cleaned with our heights | FABDEM (GLO-30
with buildings/forest removed by Hawker et al. 2022, CC BY-NC-SA 4.0; tiles in demo/flood_reference) | ours + ICESat-2
= the app's terrain, shifted to match NASA laser ground photons where a scene has enough (terrain.laser_correct).
Writes demo/benchmark/flood_test.md/json and flood_<scene>.png.
"""
import glob, json, os, sys, urllib.request
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject, transform, transform_bounds, transform_geom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import terrain

SAMPLES, RESULTS = os.path.join(ROOT, 'demo', 'samples'), os.path.join(ROOT, 'demo', 'results')
FLOOD_DIR, REF_DIR = os.path.join(ROOT, 'demo', 'test_images', 'flood'), os.path.join(ROOT, 'demo', 'flood_reference')
OUT = os.path.join(ROOT, 'demo', 'benchmark')
KML = {'poa': 'https://www.google.com/maps/d/kml?mid=1F2r9aE2ikmUPdplswcceL57m57tfWlQ&forcekml=1',
       'metro': 'https://www.google.com/maps/d/kml?mid=1yioyl2lr5xZOg3fV8i9OZV2t-5Jfa18&forcekml=1'}
# FABDEM tiles come from https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn/ via demo/remote_zip.py
FABDEM = sorted(glob.glob(os.path.join(REF_DIR, 'fabdem', '*.tif')))
# Guaiba at the Cais Maua gauge: 5.29 m on 5 May 20 h (IPH note), official record 5.35 m
LAYERS = {'poa': [('IPH flood extent, 6 May 2024', 'Inundação em 6 de Maio de 2024', 5.3),
                  ('IPH LiDAR simulation, 5.0 m', 'Inundação simulada com nível 500 cm (5.0 m)', 5.0),
                  ('IPH LiDAR simulation, 5.5 m', 'Inundação simulada com nível 550 cm (5.5m)', 5.5)],
          'metro': [('IPH simulation, 5.0 m (metro, simplified)', 'Simulação cheia 500 cm', 5.0)]}
SCENES = {  # processed 'before' scene -> (Maxar 'after' image, reference map)
    'brazil_porto_alegre_centre_before': ('brazil_porto_alegre_centre_after_2024-05-07.tif', 'poa'),
    'brazil_sarandi_before': ('brazil_porto_alegre_sarandi_after_2024-05-07.tif', 'poa'),
    'brazil_poa_edge_p01-23_before': ('brazil_poa_edge_p01-23_after_2024-05-07.tif', 'poa'),
    'brazil_poa_edge_p07-09_before': ('brazil_poa_edge_p07-09_after_2024-05-07.tif', 'poa'),
    'brazil_poa_edge_p11-13_before': ('brazil_poa_edge_p11-13_after_2024-05-07.tif', 'poa'),
    'brazil_poa_edge_p18-20_before': ('brazil_poa_edge_p18-20_after_2024-05-07.tif', 'poa'),
    'brazil_canoas_before': ('brazil_canoas_mathias_velho_after_2024-05-07.tif', 'metro')}
TERRAINS = ('raw GLO-30', 'ours', 'FABDEM', 'ours + ICESat-2')

# IPH note (NT_inundacao_validacao.pdf, table 1): dry/wet edge points surveyed on 5 May 2024, Guaiba at 5.29 m
EDGE_LEVEL = 5.29
EDGE_POINTS = [(-51.21088, -30.02345), (-51.20933, -30.02177), (-51.20613, -30.01764), (-51.20558, -30.01719),
               (-51.20222, -30.01526), (-51.20072, -30.01481), (-51.19766, -30.01419), (-51.19700, -30.01421),
               (-51.19587, -30.01269), (-51.19435, -30.01013), (-51.19210, -30.00792), (-51.19199, -30.00695),
               (-51.19016, -30.00627), (-51.18769, -30.00529), (-51.18257, -30.00711), (-51.17866, -30.00704),
               (-51.17646, -30.00655), (-51.17526, -30.00530), (-51.17649, -30.00339), (-51.17789, -30.00330),
               (-51.20750, -30.02000), (-51.20900, -30.02198), (-51.21077, -30.02352), (-51.21571, -30.02639),
               (-51.21914, -30.02505), (-51.22252, -30.02680), (-51.22564, -30.02860), (-51.22790, -30.02920),
               (-51.22596, -30.04320)]
K = '{http://www.opengis.net/kml/2.2}'


def kml_layers(key):
    """{folder name: [GeoJSON polygon (lon/lat) with holes]} of an IPH My Maps export (downloaded once)."""
    path = os.path.join(REF_DIR, f'iph_{key}.kml')
    if not os.path.exists(path):
        os.makedirs(REF_DIR, exist_ok=True)
        urllib.request.urlretrieve(KML[key], path)
    ring = lambda el: [tuple(map(float, p.split(',')[:2])) for p in el.text.split()]
    out = {}
    for folder in ET.parse(path).getroot().iter(K + 'Folder'):
        out[folder.find(K + 'name').text] = [
            {'type': 'Polygon', 'coordinates': [ring(pg.find(f'{K}outerBoundaryIs/{K}LinearRing/{K}coordinates'))]
             + [ring(c) for c in pg.findall(f'{K}innerBoundaryIs/{K}LinearRing/{K}coordinates')]}
            for pg in folder.iter(K + 'Polygon')]
    return out


def burn(polys, lonlat_bounds, crs, tr, shape):
    x0, y0, x1, y1 = lonlat_bounds
    hit = [g for g in polys if (xs := [p[0] for p in g['coordinates'][0]]) and (ys := [p[1] for p in g['coordinates'][0]])
           and min(xs) <= x1 and max(xs) >= x0 and min(ys) <= y1 and max(ys) >= y0]
    if not hit:
        return np.zeros(shape, bool)
    return rasterize(((transform_geom('EPSG:4326', crs, g), 1) for g in hit), out_shape=shape, transform=tr,
                     fill=0, dtype='uint8').astype(bool)


def dem_on_grid(paths, crs, tr, shape):
    """Mosaic of DEM tiles, bilinearly resampled onto the scene grid (NaN where no tile)."""
    out = np.full(shape, np.nan, np.float32)
    with rasterio.Env(**terrain.GDAL_ENV):
        for p in paths:
            with rasterio.open(p) as src:
                part = np.full(shape, np.nan, np.float32)
                reproject(rasterio.band(src, 1), part, src_nodata=src.nodata, dst_nodata=np.nan, dst_transform=tr,
                          dst_crs=crs, resampling=Resampling.bilinear)
            out = np.where(np.isnan(out), part, out)
    return out


def scores(pred, ref):
    tp, fp, fn = int((pred & ref).sum()), int((pred & ~ref).sum()), int((~pred & ref).sum())
    return {'tp': tp, 'fp': fp, 'fn': fn, 'wet_pct': 100 * pred.mean(), 'agree_pct': 100 * (pred == ref).mean(),
            'csi': tp / (tp + fp + fn) if tp + fp + fn else 1.0, 'hit': tp / (tp + fn) if tp + fn else None,
            'false_alarm': fp / (tp + fp) if tp + fp else None}


def best_level(dem, ref):
    """Water level at which this terrain's flood map best matches the reference (max CSI); only meaningful if the
    reference is partly wet. Minus the reference level, it is the terrain's effective vertical offset there."""
    if not 0.02 < ref.mean() < 0.98:
        return None
    levels = np.arange(np.floor(np.nanmin(dem)), np.ceil(np.nanmax(dem)) + 0.05, 0.05)
    csi = [scores(dem < L, ref)['csi'] for L in levels]
    return float(levels[int(np.argmax(csi))]), float(max(csi))


def figure(name, before, after, dems, ref, level, label):
    S = 512
    small = lambda a: cv2.resize(a, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32)
    mask = lambda m: cv2.resize(m.astype(np.uint8), (S, S), interpolation=cv2.INTER_NEAREST).astype(bool)
    refs = mask(ref)
    edge = cv2.morphologyEx(refs.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    p1, p2 = small(before), small(after)
    ours = mask(dems['ours'] < level)
    p1[ours] = 0.5 * p1[ours] + 0.5 * np.array([30, 110, 255])
    panels = [p1, p2]
    for t in ('ours', 'FABDEM'):
        wet = mask(dems[t] < level)
        p = small(before).mean(2, keepdims=True).repeat(3, 2) * 0.35 + 150
        for sel, c in [(wet & refs, (30, 110, 255)), (wet & ~refs, (255, 150, 0)), (~wet & refs, (220, 30, 30))]:
            p[sel] = c
        panels.append(p)
    for p in (p1, p2):
        p[edge] = (255, 230, 0)
    canvas = Image.new('RGB', (4 * S, S + 58), 'white')
    canvas.paste(Image.fromarray(np.concatenate(panels, 1).clip(0, 255).astype(np.uint8)), (0, 58))
    try:
        font = ImageFont.truetype('Arial.ttf', 17)
    except OSError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(canvas)
    for i, t in enumerate([f'BEFORE (2 Feb 2024) + our flood at {level:.2f} m', 'AFTER (Maxar, 7 May 2024)',
                           'our terrain vs IPH', 'FABDEM vs IPH']):
        d.text((i * S + 8, 6), t, fill='black', font=font)
    d.text((8, 32), f'yellow line = edge of {label}.   Right panels: blue = both wet, orange = only model wet, '
                    'red = only IPH wet, grey = both dry', fill=(90, 80, 0), font=font)
    canvas.save(os.path.join(OUT, f'flood_{name}.png'))


def main():
    assert abs(scores(np.array([1, 1, 0, 0], bool), np.array([1, 0, 1, 0], bool))['csi'] - 1 / 3) < 1e-9
    maps = {k: kml_layers(k) for k in KML}
    res = {}
    for name, (after_file, key) in SCENES.items():
        with rasterio.open(os.path.join(SAMPLES, name + '.tif')) as s:
            crs, tr, shape = s.crs, s.transform, (s.height, s.width)
            before = s.read([1, 2, 3]).transpose(1, 2, 0)
            bounds = transform_bounds(crs, 'EPSG:4326', *s.bounds)
        with rasterio.open(os.path.join(FLOOD_DIR, after_file)) as a:  # onto the before grid (different image)
            after = np.zeros((3,) + shape, np.uint8)
            reproject(a.read([1, 2, 3]), after, src_transform=a.transform, src_crs=a.crs, dst_transform=tr,
                      dst_crs=crs, resampling=Resampling.bilinear)
            after = after.transpose(1, 2, 0)
        # the app's terrain (_dtm.tif) includes the ICESat-2 laser shift where there were enough photons; 'ours' = before it
        off = json.load(open(os.path.join(RESULTS, name + '.json')))['terrain'].get('laser', {}).get('offset_m')
        saved = rasterio.open(os.path.join(RESULTS, name + '_dtm.tif')).read(1)
        dems = {'raw GLO-30': dem_on_grid([p for p, _, _ in terrain._sources(bounds)], crs, tr, shape),
                'ours': saved + (off or 0),
                'FABDEM': dem_on_grid(FABDEM, crs, tr, shape)}
        if off is not None:
            dems['ours + ICESat-2'] = saved
        blocks = json.load(open(os.path.join(RESULTS, name + '_buildings.json')))
        r = {'ground_m': {t: [float(np.nanmin(z)), float(np.nanmax(z))] for t, z in dems.items()}, 'layers': {}}
        for i, (label, folder, level) in enumerate(LAYERS[key]):
            ref = burn(maps[key][folder], bounds, crs, tr, shape)
            wet = dems['ours'] < level
            e = {'level': level, 'ref_wet_pct': 100 * ref.mean(),
                 'depth_mean': float((level - dems['ours'])[wet].mean()) if wet.any() else 0.0,
                 'blocks': {st: sum(1 for b in blocks if st == ('submerged' if level > b['ground_m'] + b['height_m']
                                    else 'partly' if level > b['ground_m'] else 'dry')) for st in ('submerged', 'partly', 'dry')}}
            for t, z in dems.items():
                e[t] = dict(scores(z < level, ref), best=best_level(z, ref))
            r['layers'][label] = e
            if i == 0:
                figure(name, before, after, dems, ref, level, label)
        xs, ys = transform('EPSG:4326', crs, [p[0] for p in EDGE_POINTS], [p[1] for p in EDGE_POINTS])
        r['edge_points'] = []
        for n, (x, y) in enumerate(zip(xs, ys), 1):
            row, col = rasterio.transform.rowcol(tr, x, y)
            if 0 <= row < shape[0] and 0 <= col < shape[1]:
                r['edge_points'].append({'point': n, **{t: float(z[row, col]) for t, z in dems.items()}})
        res[name] = r
    json.dump(res, open(os.path.join(OUT, 'flood_test.json'), 'w'), indent=2)
    write_md(res)


def write_md(res):
    short = lambda n: n.replace('brazil_', '').replace('_before', '')
    f = lambda v, fmt='{:.2f}': '–' if v is None else fmt.format(v)
    L = ['# Flood test: May 2024 floods, Porto Alegre / Canoas (Brazil)', '',
         'Flood = ground below the water level (bathtub, as in the web viewer), predicted from the **pre-flood** image '
         '(Maxar, 2 Feb 2024). Reference = IPH/UFRGS flood maps on 2010 LiDAR terrain. Everything ignores the flood '
         'walls and dikes (most failed or were overtopped). CSI = both wet / either wet (1 = perfect). Terrains: '
         '**raw GLO-30** (no model), **ours** = GLO-30 cleaned with our heights (what the app uses), **FABDEM** '
         '(GLO-30 with buildings/forest removed by a LiDAR-trained model; Hawker et al. 2022).', '']
    first = lambda r: next(iter(r['layers'].items()))
    def pooled(t, only=None):
        rs = [first(r)[1] for n, r in res.items() if first(r)[0].startswith('IPH flood extent') and (only is None or n in only)]
        tp, fp, fn = (sum(e[t][k] for e in rs) for k in ('tp', 'fp', 'fn'))
        return tp / (tp + fp + fn), len(rs)
    laser = [n for n in res if 'ours + ICESat-2' in first(res[n])[1] and first(res[n])[0].startswith('IPH flood extent')]
    L += ['**Pooled over the Porto Alegre scenes (IPH 6 May extent, level 5.30 m) — CSI:** ' + ', '.join(
        f'{t} {pooled(t)[0]:.2f}' for t in TERRAINS[:3]), '']
    if laser:
        L += [f'**With the ICESat-2 bias correction** (the {len(laser)} of those scenes that have laser ground photons) — CSI: '
              + ', '.join(f'{t} {pooled(t, laser)[0]:.2f}' for t in TERRAINS), '']
    L += [
        '| Scene | Reference | Level | Ref wet | Wet: raw / ours / FABDEM | CSI raw GLO-30 | CSI ours | CSI FABDEM | '
        'CSI ours + ICESat-2 | Best-fit level: ours / FABDEM | Our mean depth | Blocks sub/partly/dry |', '|' + '---|' * 12]
    for name, r in res.items():
        for label, e in r['layers'].items():
            bl = lambda t: f"{e[t]['best'][0]:.2f}" if e[t]['best'] else '–'
            L.append(f"| {short(name)} | {label} | {e['level']:.2f} m | {e['ref_wet_pct']:.0f}% | "
                     + ' / '.join(f"{e[t]['wet_pct']:.0f}%" for t in TERRAINS[:3]) + ' | '
                     + ' | '.join(f"{e[t]['csi']:.2f}" if t in e else '–' for t in TERRAINS)
                     + f" | {bl('ours')} / {bl('FABDEM')} m | {e['depth_mean']:.1f} m | "
                       f"{e['blocks']['submerged']}/{e['blocks']['partly']}/{e['blocks']['dry']} |")
    pts = [(n, p) for n, r in res.items() for p in r['edge_points']]
    if pts:
        L += ['', f'**Surveyed flood-edge points** (IPH note, 5 May 2024, Guaíba {EDGE_LEVEL} m): the ground there '
              'should equal the water level. Error = terrain − water level.', '',
              '| Scene | Point | raw GLO-30 | ours | FABDEM | ours + ICESat-2 |', '|---|---|---|---|---|---|']
        L += [f"| {short(n)} | {p['point']} | " + ' | '.join(f"{p[t] - EDGE_LEVEL:+.2f} m" if t in p else '–' for t in TERRAINS) + ' |'
              for n, p in pts]
        for label, sel in [(f'all {len(pts)} points', pts), (f'the {sum("ours + ICESat-2" in p for _, p in pts)} points with laser data',
                                                               [(n, p) for n, p in pts if 'ours + ICESat-2' in p])]:
            err = {t: np.array([p[t] - EDGE_LEVEL for _, p in sel if t in p]) for t in TERRAINS}
            L.append(f'| **mean (mean abs), {label}** | | ' + ' | '.join(
                f'**{err[t].mean():+.2f} ({np.abs(err[t]).mean():.2f}) m**' if len(err[t]) == len(sel) else '–' for t in TERRAINS) + ' |')
    L += ['', 'Scenes are 320 m × 320 m windows (four centred on surveyed edge points), so this is a spot check, not '
          'a city-wide score. Water levels are gauge readings, terrains are EGM2008; datums may differ by a few '
          'decimetres. The Canoas reference is IPH\'s simplified metro estimate.']
    open(os.path.join(OUT, 'flood_test.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
