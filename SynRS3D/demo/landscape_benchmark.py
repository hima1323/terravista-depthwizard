"""Accuracy across landscape types (SIH26175 asks for stability over urban, sparse, hilly and forested land) against
NASA ICESat-2 laser photons, on Indian scenes.

usage: .venv/Scripts/python demo/landscape_benchmark.py      (needs internet and the app running on 127.0.0.1:8000)
For each region below:
  1. ICESat-2 photons in a ~3 km box around it (terrain.icesat2_photons, cached) -> the ~0.5 km window with the
     most laser photons (laser tracks are kilometres apart, so a random window usually has none);
  2. that window as a georeferenced image (Esri World Imagery, ~0.5 m pixels, demo/fetch_scene.py);
  3. uploaded to the running app, which runs the height model, the terrain and the ICESat-2 levelling;
  4. the app's own laser check (POST /api/icesat2 = validate.compare_icesat2).
Reported per scene and pooled per landscape type:
  surface = our DSM vs all photons (ground, canopy, roofs), after the app levelled its terrain to the ground photons;
  terrain = our ground model vs ground photons *before* that levelling (an independent check of the terrain).
Caveat: the imagery and the laser passes are from different dates (2018-now); trees grow and buildings change.
Writes demo/benchmark/landscape_results.json and landscape_results.md.
"""
import json, os, sys, time, urllib.error, urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'demo'))
import terrain, validate
from fetch_scene import fetch

APP = 'http://127.0.0.1:8000'
OUT = os.path.join(ROOT, 'demo', 'benchmark')
TMP = os.path.join(OUT, 'landscape_tiles')
# (landscape, scene name, lat, lon): two regions per landscape type
REGIONS = [
    ('urban', 'chandigarh_sector17', 30.7398, 76.7827),
    ('urban', 'delhi_karol_bagh', 28.6519, 77.1909),
    ('sparse', 'barmer_desert_village', 25.7500, 71.3900),
    ('sparse', 'anantapur_dryland', 14.6800, 77.6000),
    ('hilly', 'shimla_hills', 31.1048, 77.1734),
    ('hilly', 'gangtok_hills', 27.3389, 88.6065),
    ('forested', 'agumbe_western_ghats', 13.5027, 75.0903),
    ('forested', 'silent_valley_forest', 11.0830, 76.4330),
]
BOX = 0.015    # degrees around each region searched for laser tracks (~3 km)


def api(path, body=None, method='POST', timeout=900):
    req = urllib.request.Request(APP + path, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def best_window(lat, lon):
    """Centre of the ~0.45 km window with the most ICESat-2 photons (ground photons count double)."""
    p = terrain.icesat2_photons((lon - BOX, lat - BOX, lon + BOX, lat + BOX))
    if not len(p['h']):
        return lat, lon, 0
    half_lon, half_lat = 0.0022, 0.0022 * np.cos(np.radians(lat))
    w = np.where(p['cls'] == 1, 2.0, 1.0)
    best, score = (lat, lon), -1
    for clat in np.arange(lat - BOX + half_lat, lat + BOX - half_lat, 0.0005):
        for clon in np.arange(lon - BOX + half_lon, lon + BOX - half_lon, 0.0005):
            s = w[(np.abs(p['lat'] - clat) < half_lat) & (np.abs(p['lon'] - clon) < half_lon)].sum()
            if s > score:
                best, score = (float(clat), float(clon)), s
    return best[0], best[1], int(score)


def process(name, lat, lon):
    """Make sure the app has processed this scene; returns its ICESat-2 check."""
    scenes = {s['name']: s for s in api('/api/scenes', method='GET')}
    if name not in scenes:
        os.makedirs(TMP, exist_ok=True)
        path = fetch(name, lat, lon, TMP)
        api(f'/api/upload?name={name}.tif', open(path, 'rb').read())
    while True:
        s = {s['name']: s for s in api('/api/scenes', method='GET')}.get(name, {})
        if s.get('state') in ('done', 'error'):
            break
        time.sleep(5)
    if s['state'] == 'error':
        return {'error': s.get('error')}
    return api(f'/api/icesat2?name={name}')


def pooled(results):
    """All photon pairs of these scenes together. Each scene's mean reference height is subtracted from both ours and
    the reference first: errors are unchanged, but r then measures agreement *within* scenes instead of the trivial
    agreement between a 100 m desert and a 2,000 m hill town."""
    ok = [r for r in results if r.get('photons')]
    if not ok:
        return None
    off = [np.nanmean(r['photons_xy']['h']) for r in ok]
    ours = np.concatenate([np.asarray(r['photons_xy']['ours']) - o for r, o in zip(ok, off)])
    ref = np.concatenate([np.asarray(r['photons_xy']['h']) - o for r, o in zip(ok, off)])
    return validate.metrics(ours, ref)


def main():
    res = {}
    for land, name, lat, lon in REGIONS:
        if name == 'chandigarh_sector17':     # already a demo scene
            clat, clon, score = lat, lon, None
        else:
            clat, clon, score = best_window(lat, lon)
        print(f'{land:9s} {name}: window {clat:.5f}, {clon:.5f} (laser score {score})', flush=True)
        r = process(name, clat, clon)
        r.update(landscape=land, lat=clat, lon=clon)
        res[name] = r
        m = r.get('surface_vs_all')
        print(f'   photons {r.get("photons")}, surface MAE {m["mae"]:.2f} m, RMSE {m["rmse"]:.2f} m, r {m["r"]}' if m
              else f'   {r.get("error") or r.get("note") or "no statistics"}', flush=True)
    summary = {land: pooled([r for r in res.values() if r['landscape'] == land]) for land in dict.fromkeys(x[0] for x in REGIONS)}
    summary['all'] = pooled(list(res.values()))
    json.dump({'scenes': {k: {kk: vv for kk, vv in v.items() if kk not in ('photons_xy', 'scatter')} for k, v in res.items()},
               'pooled_surface_by_landscape': summary}, open(os.path.join(OUT, 'landscape_results.json'), 'w'), indent=2)
    write_md(res, summary)


def write_md(res, summary):
    f = lambda m, k, fmt='{:.2f}': '–' if not m or m.get(k) is None else fmt.format(m[k])
    L = ['# Accuracy by landscape type vs NASA ICESat-2 (Indian scenes)', '',
         'Each scene: the ~0.5 km window with the most ICESat-2 laser photons near the region, Esri World Imagery '
         '(~0.5 m pixels), processed by the app; photons from all passes 2018–now via SlideRule. Heights in m above '
         'sea level (EGM2008). Surface = our DSM vs all photons (after the app levelled its terrain to the ground '
         'photons). Terrain = our ground model vs ground photons before that levelling (independent).', '',
         '## Pooled surface accuracy per landscape type', '',
         'Up to 2,500 photons per scene. r is computed after removing each scene mean height, so it measures agreement '
         'within scenes; in hilly scenes it is high largely because the hillsides themselves vary by tens of metres.', '',
         '| Landscape | Photons | MAE (m) | RMSE (m) | Bias (m) | NMAD (m) | r (within scenes) |', '|---|---|---|---|---|---|---|']
    for land, m in summary.items():
        L.append(f"| {land} | {f(m, 'n', '{:,}')} | {f(m, 'mae')} | {f(m, 'rmse')} | {f(m, 'bias', '{:+.2f}')} | {f(m, 'nmad')} | {f(m, 'r', '{:.3f}')} |")
    L += ['', '## Per scene', '',
          '| Scene | Landscape | Photons (ground) | Passes | Surface MAE / RMSE / bias / r | Terrain before levelling: median / NMAD / MAE |',
          '|---|---|---|---|---|---|']
    for name, r in res.items():
        s, t = r.get('surface_vs_all'), r.get('terrain_vs_ground')
        if not r.get('photons'):
            L.append(f"| {name.replace('_', ' ')} | {r['landscape']} | 0 | – | {r.get('error') or r.get('note', '')} | – |")
            continue
        L.append(f"| {name.replace('_', ' ')} | {r['landscape']} | {r['photons']} ({r['ground_photons']}) | {r['passes']} | "
                 f"{f(s, 'mae')} / {f(s, 'rmse')} / {f(s, 'bias', '{:+.2f}')} / {f(s, 'r')} | "
                 f"{f(t, 'median', '{:+.2f}')} / {f(t, 'nmad')} / {f(t, 'mae')} |")
    L += ['', 'Laser footprints are ~11 m wide, so photons on roof edges and in tree crowns mix heights; NMAD and the '
          'median are robust to that. The imagery and the laser passes are from different dates.']
    open(os.path.join(OUT, 'landscape_results.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
