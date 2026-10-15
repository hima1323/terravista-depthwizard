"""Laser check: our absolute heights vs NASA ICESat-2 photons (ATL03, classified by ATL08), per demo scene.

usage: .venv/bin/python demo/icesat2_check.py      (needs internet; photons are cached in demo/benchmark/icesat2/)
Photons come from the public SlideRule service (no login, terrain.icesat2_photons): high-confidence photons inside
each georeferenced scene, all passes 2018-now. The app shifts each terrain by the median laser offset (>= 50 ground
photons); here we report the terrain error *before* that shift, and the surface (DSM) error after it. ICESat-2 heights are ellipsoidal (WGS84); we subtract the EGM2008 geoid undulation stored with
each scene's terrain, so everything is in metres above mean sea level (EGM2008).
  ground photons (ATL08 class 1)       vs our terrain (DTM) and, as a baseline, the raw Copernicus GLO-30
  all photons (ground + canopy + top)  vs our surface model (DSM = terrain + model heights)
Robust statistics: median = bias, NMAD = spread (1.4826 x median absolute deviation), since footprints (~11 m)
straddle roof edges and trees. Writes demo/benchmark/icesat2_check.md/json and icesat2_<scene>.png profiles.
"""
import json, os, sys

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from rasterio.warp import transform, transform_bounds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import terrain

SAMPLES, RESULTS = os.path.join(ROOT, 'demo', 'samples'), os.path.join(ROOT, 'demo', 'results')
OUT = os.path.join(ROOT, 'demo', 'benchmark')


def stats(r):
    r = r[np.isfinite(r)]
    if len(r) < 10:
        return None
    med = float(np.median(r))
    return {'n': int(len(r)), 'median': med, 'nmad': float(1.4826 * np.median(np.abs(r - med))),
            'rmse': float(np.sqrt(np.mean(r ** 2))), 'within_2m_pct': float(100 * np.mean(np.abs(r) <= 2))}


def sample(path, xs, ys):
    xs, ys = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
    with rasterio.Env(**terrain.GDAL_ENV), rasterio.open(path) as src:
        v = np.array([p[0] for p in src.sample(zip(xs, ys))], np.float64)
        b = src.bounds   # the lon/lat query box is a bit larger than a projected image: outside reads as 0
        v[(xs < b.left) | (xs > b.right) | (ys < b.bottom) | (ys > b.top)] = np.nan
        return np.where(v == src.nodata, np.nan, v) if src.nodata is not None else v


def profile(name, d, ours_dsm, ours_dtm, glo):
    """Heights along the pass with the most photons: photons as dots, our DSM/DTM and raw GLO-30 as lines."""
    k = np.bincount(np.unique(d['track'], return_inverse=True)[1]).argmax()
    sel = d['track'] == np.unique(d['track'])[k]
    # distance along track (m) from the first photon
    lat0 = d['lat'][sel].mean()
    x = np.hypot((d['lon'][sel] - d['lon'][sel].min()) * 111320 * np.cos(np.radians(lat0)), (d['lat'][sel] - d['lat'][sel].min()) * 110540)
    o = np.argsort(x)
    x, cls = x[o], d['cls'][sel][o]
    hs = {k: v[sel][o] for k, v in [('h', d['h_msl']), ('dsm', ours_dsm), ('dtm', ours_dtm), ('glo', glo)]}
    W, H, L, B, T, R = 1100, 520, 70, 50, 60, 20
    ok = np.concatenate([v[np.isfinite(v)] for v in hs.values()])
    lo, hi = np.percentile(ok, 1) - 2, np.percentile(ok, 99.5) + 4
    X = lambda v: L + (v - x.min()) / max(1, x.max() - x.min()) * (W - L - R)
    Y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    img = Image.new('RGB', (W, H), 'white')
    dr = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('Arial.ttf', 15)
    except OSError:
        font = ImageFont.load_default()
    for v in np.linspace(lo, hi, 6):
        dr.line([(L, Y(v)), (W - R, Y(v))], fill=(232, 232, 232)); dr.text((6, Y(v) - 8), f'{v:.0f} m', fill='gray', font=font)
    for key, col, wdt in [('glo', (160, 160, 160), 2), ('dtm', (46, 160, 67), 3), ('dsm', (30, 110, 255), 2)]:
        v = hs[key]
        pts = [(X(a), Y(b)) for a, b in zip(x, v) if np.isfinite(b)]
        if len(pts) > 1:
            dr.line(pts, fill=col, width=wdt)
    for c, col in [(2, (120, 170, 60)), (3, (20, 90, 20)), (1, (200, 40, 40))]:
        for a, b in zip(x[cls == c], hs['h'][cls == c]):
            dr.ellipse([X(a) - 2, Y(b) - 2, X(a) + 2, Y(b) + 2], fill=col)
    dr.text((L, 8), f'{name.replace("_", " ")}: ICESat-2 pass {np.datetime_as_string(np.datetime64(int(d["t"][sel][0]), "s"), "D")}'
                    f' vs DepthWizard (heights in m above sea level, EGM2008)', fill='black', font=font)
    dr.text((L, 30), 'dots: laser photons (red = ground, green = canopy / roofs)   lines: blue = our DSM, green = our terrain '
                     '(laser-levelled), grey = raw GLO-30', fill=(80, 80, 80), font=font)
    dr.text((W // 2 - 60, H - 28), 'distance along the laser track (m)', fill='gray', font=font)
    for v in np.linspace(x.min(), x.max(), 5):
        dr.text((X(v) - 10, H - B + 6), f'{v:.0f}', fill='gray', font=font)
    img.save(os.path.join(OUT, f'icesat2_{name}.png'))


def main():
    res = {}
    for f in sorted(os.listdir(SAMPLES)):
        name = os.path.splitext(f)[0]
        meta_f = os.path.join(RESULTS, name + '.json')
        if not os.path.exists(os.path.join(RESULTS, name + '_dtm.tif')) or not os.path.exists(meta_f):
            continue
        tinfo = json.load(open(meta_f))['terrain']
        N, off = tinfo.get('geoid_undulation_m'), tinfo.get('laser', {}).get('offset_m')
        if N is None:
            continue
        with rasterio.open(os.path.join(SAMPLES, f)) as s:
            crs, bounds = s.crs, transform_bounds(s.crs, 'EPSG:4326', *s.bounds)
        d = terrain.icesat2_photons(bounds)
        if not len(d['h']):
            res[name] = {'photons': 0}
            print(f'{name}: no ICESat-2 photons', flush=True)
            continue
        d['h_msl'] = d['h'] - N                                    # ellipsoidal -> EGM2008 (N = geoid undulation)
        xs, ys = transform('EPSG:4326', crs, d['lon'].tolist(), d['lat'].tolist())
        saved = sample(os.path.join(RESULTS, name + '_dtm.tif'), xs, ys)             # the app's terrain (after the laser shift)
        dtm = saved + (off or 0)                                                      # terrain before the laser shift
        dsm = sample(os.path.join(RESULTS, name + '_dsm.tif'), xs, ys)                # product, after it
        glo = np.full(len(xs), np.nan)
        for p, _, _ in terrain._sources(bounds):                  # raw GLO-30 (EGM2008) as the no-model baseline
            v = sample(p, d['lon'], d['lat'])
            glo = np.where(np.isnan(glo), v, glo)
        g = d['cls'] == 1
        res[name] = {'photons': int(len(d['h'])), 'ground_photons': int(g.sum()), 'passes': int(len(np.unique(d['track']))),
                     'dates': sorted({str(np.datetime64(int(t), 's'))[:10] for t in d['t']}),
                     'terrain_ours': stats(dtm[g] - d['h_msl'][g]), 'terrain_raw_glo30': stats(glo[g] - d['h_msl'][g]),
                     'surface_ours': stats(dsm - d['h_msl']), 'laser_shift_m': None if off is None else -off}
        profile(name, d, dsm, saved, glo)
        print(f"{name}: {res[name]['photons']} photons ({res[name]['ground_photons']} ground), {res[name]['passes']} beams/passes", flush=True)
    json.dump(res, open(os.path.join(OUT, 'icesat2_check.json'), 'w'), indent=2)
    write_md(res)


def write_md(res):
    f = lambda s, k, fmt='{:+.2f}': '–' if not s else fmt.format(s[k])
    L = ['# Laser check: DepthWizard heights vs NASA ICESat-2', '',
         'High-confidence ICESat-2 photons (ATL03, classified by ATL08) inside each scene, all passes since 2018, via '
         'the public SlideRule service. Heights converted to metres above mean sea level (EGM2008). Error = our value '
         '− laser. Median = bias, NMAD = robust spread.', '',
         '| Scene | Photons (ground) | Passes | Terrain error before laser shift: ours, median / NMAD | Terrain error: raw GLO-30, '
         'median / NMAD | Laser shift applied by the app | Surface (DSM, after shift) error: median / NMAD | DSM within ±2 m |',
         '|---|---|---|---|---|---|---|---|']
    rows = {k: v for k, v in res.items() if v.get('photons')}
    for name, r in rows.items():
        t, g, s = r['terrain_ours'], r['terrain_raw_glo30'], r['surface_ours']
        L.append(f"| {name.replace('_', ' ')} | {r['photons']} ({r['ground_photons']}) | {r['passes']} | "
                 f"{f(t, 'median')} / {f(t, 'nmad', '{:.2f}')} m | {f(g, 'median')} / {f(g, 'nmad', '{:.2f}')} m | "
                 f"{'–' if r['laser_shift_m'] is None else format(r['laser_shift_m'], '+.2f') + ' m'} | "
                 f"{f(s, 'median')} / {f(s, 'nmad', '{:.2f}')} m | {f(s, 'within_2m_pct', '{:.0f}%')} |")
    none = [k for k, v in res.items() if not v.get('photons')]
    if none:
        L += ['', 'No ICESat-2 photons inside: ' + ', '.join(n.replace('_', ' ') for n in none) + ' (scenes are ~0.3–0.6 km wide; '
              'laser tracks are kilometres apart).']
    L += ['', 'Footprints are ~11 m wide, so photons at roof edges and in trees mix heights; the median and NMAD are '
          'robust to that. ATL08 ground labels can be wrong in dense cities.']
    open(os.path.join(OUT, 'icesat2_check.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    assert stats(np.array([1.0] * 20))['nmad'] == 0 and stats(np.array([1.0] * 5)) is None
    main()
