"""N5: ICESat-2 roof-photon filter, before/after on every levelled demo scene.

For each scene the terrain is rebuilt twice the way the app builds it (app.ensure_terrain): once with the roof rule off
(terrain.roof_photons -> nothing), once with it on, and validate.compare_icesat2 is run on each. Leaves the scenes with
the rule on (the app's state). Writes demo/benchmark/v2/roof_filter_n5.json and prints a markdown table.

    cd SynRS3D && PYTHONPATH=. .venv/bin/python demo/roof_filter_n5.py
"""
import json, os
import numpy as np
import app, terrain, validate as V

SCENES = ['chandigarh_sector17', 'bengaluru_electronic_city', 'delhi_central', 'mumbai_highrise',
          'brazil_porto_alegre_centre_before', 'brazil_sarandi_before', 'brazil_poa_edge_p07-09_before']
OUT = os.path.join(app.ROOT, 'demo', 'benchmark', 'v2', 'roof_filter_n5.json')


def run(name):
    meta_f = os.path.join(app.RESULTS, name + '.json')
    meta = json.load(open(meta_f))
    meta.setdefault('terrain', {})['version'] = -1          # force ensure_terrain to rebuild
    json.dump(meta, open(meta_f, 'w'))
    app.ensure_terrain(name, os.path.join(app.SAMPLES, name + '.tif'))
    r = V.compare_icesat2(V.Scene(name, os.path.join(app.SAMPLES, name + '.tif')))
    ho, laser = r.get('held_out', {}), json.load(open(meta_f))['terrain'].get('laser') or {}
    return {'levelling_shift_m': -laser['offset_m'] if 'offset_m' in laser else None, 'levelling_note': laser.get('none'),
            'roof_photons_removed': r.get('roof_photons_removed', 0), 'ground_photons': r['ground_photons'],
            'terrain_vs_ground': r['terrain_vs_ground'], 'held_out_terrain_footprint': ho.get('terrain_vs_ground_footprint'),
            'held_out_roof_note': ho.get('roof_note'), 'roofs_vs_photons_footprint': ho.get('roofs_vs_photons_footprint')}


def main():
    real, res = terrain.roof_photons, {}
    for n in SCENES:
        terrain.roof_photons = lambda on_building, above: np.zeros(len(above), bool)
        before = run(n)
        terrain.roof_photons = real
        res[n] = {'before': before, 'after': run(n)}
        print(n, 'done', flush=True)
    res['_rule'] = {'ROOF_BUFFER_M': terrain.ROOF_BUFFER_M, 'ROOF_MIN_M': terrain.ROOF_MIN_M}
    json.dump(res, open(OUT, 'w'), indent=1)
    f = lambda m: '—' if not m else f"{m['mae']:.2f} ({m['bias']:+.2f}, n={m['n']})"
    print('\n| Scene | Ground photons | Removed as roofs | Held-out terrain MAE (bias, n), before | after |\n|---|---|---|---|---|')
    for n in SCENES:
        b, a = res[n]['before'], res[n]['after']
        print(f"| {n} | {b['ground_photons']} | {a['roof_photons_removed']} | {f(b['held_out_terrain_footprint'])} | "
              f"{f(a['held_out_terrain_footprint']) if a['held_out_terrain_footprint'] else 'none: ' + (a['held_out_roof_note'] or '')[:40]} |")


if __name__ == '__main__':
    main()
