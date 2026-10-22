"""Input-GSD check (plan step 6a): would resampling the input to a fixed ground sample distance help RS3DAda?

usage: /usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/gsd_sweep.py --predict [DC|NYC|PHL]
                       (model; ~25-30 min per city on a shared M3, run per city so other jobs can take the lock in between)
       .venv/bin/python demo/gsd_sweep.py              analysis from the cache -> demo/benchmark/v2/gsd_sweep.json/.md
       .venv/bin/python demo/gsd_sweep.py --selftest
Current behaviour: infer_height.predict and app.py never resample. The model sees the input pixels as they are; the GSD
is only used for building areas and the terrain grid. GAMUS images are 0.33 m aerial orthophotos (gamus_v2.json source).
Subsample: 5 tiles per city = every 10th tile per city of the frozen 150 (demo/gamus_v2.py test set); the other 135 tiles
are dropped for time (one tile with all settings took ~6-7 min on the shared M3, so 10 per city would exceed 3 h). Each full 1024x1024 tile is resampled to an effective GSD (cv2 INTER_AREA down, INTER_CUBIC up),
predicted with the app's path (infer_height.predict: 518 px tiles, 50% overlap, 4-flip TTA, fp16 MPS), the prediction is
resampled back to the 1024 grid (INTER_LINEAR) and scored on the 504x504 centre crop (the gamus_v2 pixels) against the LiDAR
nDSM (voids excluded, demo/eval_v2.py metrics, mean over tiles [95% bootstrap CI] (pooled)).
Settings: native 0.33 m (= current default), 0.30, 0.40, 0.50, 0.70 m; and a 'coarse source' run: the image first degraded
to 0.5 m (like the ~0.51-0.58 m Indian demo scenes) and then upsampled back to 0.33 m pixels before the model.
"""
import json, os, sys, time

os.environ.setdefault('TQDM_DISABLE', '1')
import cv2
import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark as B
import gamus_benchmark as G
import gamus_v2 as GV
import eval_v2 as E

V2 = os.path.join(B.OUT, 'v2')
CACHE = os.path.join(V2, 'cache', 'gsd')
NATIVE, FULL, CROP = 0.33, 1024, 504
# name -> (source GSD the image is first degraded to, GSD of the pixels the model sees)
SETTINGS = {'native 0.33': (NATIVE, NATIVE), '0.30': (NATIVE, 0.30), '0.40': (NATIVE, 0.40), '0.50': (NATIVE, 0.50),
            '0.70': (NATIVE, 0.70), '0.50 src -> 0.33': (0.50, NATIVE)}
CMD = '.venv/bin/python demo/gsd_sweep.py'


def tiles():
    names = GV.names150()
    return [n for c in ('DC', 'NYC', 'PHL') for n in [m for m in names if m.split('_')[0] == c][::10]]


def resize(a, size, interp=None):
    if a.shape[0] == size:
        return a
    return cv2.resize(a, (size, size), interpolation=interp if interp is not None else
                      (cv2.INTER_AREA if size < a.shape[0] else cv2.INTER_CUBIC))


def model_input(rgb, src, gsd):
    """Full native tile -> the pixels the model sees: degrade to src GSD, then resample to gsd."""
    a = resize(rgb, round(FULL * NATIVE / src))
    return resize(a, round(FULL * NATIVE / gsd))


def back(pred):
    """Prediction on the model grid -> 1024 native grid -> centre crop (same pixels as gamus_benchmark.read)."""
    t = (FULL - CROP) // 2
    return resize(pred.astype(np.float32), FULL, cv2.INTER_LINEAR)[t:t + CROP, t:t + CROP]


def full(kind, n):
    with h5py.File(G.path(kind, n)) as h:
        a = h['image'][:]
    assert a.shape[:2] == (FULL, FULL), (n, a.shape)
    return a


def predict(city=None):
    import infer_height
    os.makedirs(CACHE, exist_ok=True)
    todo = [n for n in tiles() if (city is None or n.startswith(city + '_')) and not os.path.exists(os.path.join(CACHE, n + '.npz'))]
    if not todo:
        return print('gsd cache complete for', city or 'all cities')
    model, device, dtype = infer_height.load_model(os.path.join(B.ROOT, 'pretrain', 'RS3DAda_vitl_DPT_height.pth'), fp16=True)
    t0 = time.time()
    for i, n in enumerate(todo, 1):
        rgb = full('images', n)
        out = {}
        for k, (src, gsd) in SETTINGS.items():
            x = model_input(rgb, src, gsd)
            out[k] = back(infer_height.predict(model, device, dtype, x, use_tta=True)).astype(np.float16)
        np.savez_compressed(os.path.join(CACHE, n + '.npz'), **{k.replace(' ', '_'): v for k, v in out.items()})
        print(f'[{i}/{len(todo)}] {n} ({time.time() - t0:.0f} s)', flush=True)


def load(n):
    c = np.load(os.path.join(CACHE, n + '.npz'))
    return {k: np.clip(c[k.replace(' ', '_')].astype(np.float32), 0, None) for k in SETTINGS}


def analyse():
    names = [n for n in tiles() if os.path.exists(os.path.join(CACHE, n + '.npz'))]
    P = {n: load(n) for n in names}
    Gt = {n: GV.clean(GV.read('heights', n).astype(np.float32)) for n in names}
    city = lambda n: n.split('_')[0]
    res = {'command': CMD, 'tiles': [{'tile': n, 'city': city(n)} for n in names], 'settings': {k: {'source_gsd_m': s, 'model_gsd_m': g,
           'model_px': round(FULL * NATIVE / g)} for k, (s, g) in SETTINGS.items()}, 'native_gsd_m': NATIVE, 'by_city': {}}
    for cname in ('ALL', 'DC', 'NYC', 'PHL'):
        sel = [n for n in names if cname == 'ALL' or city(n) == cname]
        if not sel:
            continue
        r = {'tiles': len(sel)}
        for k in SETTINGS:
            mae = [E.metrics(P[n][k] - Gt[n], Gt[n])['mae'] for n in sel]
            r[k] = {'whole': E.evaluate([(P[n][k] - Gt[n], Gt[n]) for n in sel]),
                    'high_ref3': E.aggregate([E.high_metrics(P[n][k], Gt[n], union=False) for n in sel],
                                             E.high_metrics(np.concatenate([P[n][k].ravel() for n in sel]),
                                                            np.concatenate([Gt[n].ravel() for n in sel]), union=False)),
                    'bins_pooled': E.binned_bias(np.concatenate([P[n][k].ravel() for n in sel]), np.concatenate([Gt[n].ravel() for n in sel])),
                    'bins_tile_mean_bias': {lbl: (lambda v: {'mean': float(np.mean(v)), 'ci95': list(E.bootstrap_ci(v)), 'tiles': len(v)} if v else None)(
                        [m['bias'] for n in sel for g in [Gt[n]] for m in [E.metrics((P[n][k] - g)[(g >= lo) & (g < hi)])] if m and m['n'] >= GV.MIN_PX])
                        for lbl, (lo, hi) in zip(E.BIN_LABELS, E.BINS)}}
            for base in (['native 0.33'] if k != 'native 0.33' else []) + (['0.50'] if SETTINGS[k][0] != NATIVE else []):
                d = np.array(mae) - np.array([E.metrics(P[n][base] - Gt[n], Gt[n])['mae'] for n in sel])
                r[k]['mae_minus_' + base.split()[0]] = {'mean': float(d.mean()), 'ci95': list(E.bootstrap_ci(d)), 'tiles_better': int((d < 0).sum())}
        r['best_by_mae'] = min(SETTINGS, key=lambda k: r[k]['whole']['mae']['mean'])
        r['best_native_grid_only'] = min([k for k in SETTINGS if SETTINGS[k][0] == NATIVE], key=lambda k: r[k]['whole']['mae']['mean'])
        res['by_city'][cname] = r
    cities = [c for c in ('DC', 'NYC', 'PHL') if c in res['by_city']]
    wins = {k: [c for c in cities if res['by_city'][c][k]['whole']['mae']['mean'] < res['by_city'][c]['native 0.33']['whole']['mae']['mean']]
            for k in SETTINGS if SETTINGS[k][0] == NATIVE and k != 'native 0.33'}
    coarse = {k: [c for c in cities if res['by_city'][c][k]['whole']['mae']['mean'] < res['by_city'][c]['0.50']['whole']['mae']['mean']]
              for k in SETTINGS if SETTINGS[k][0] != NATIVE}
    res['decision'] = {'beats_native_mae_in': wins, 'coarse_upsampling_beats_0.50_mae_in': coarse,
                       'change_default': [k for k, v in wins.items() if len(v) == 3] + [k for k, v in coarse.items() if len(v) == 3]}
    json.dump(res, open(os.path.join(V2, 'gsd_sweep.json'), 'w'), indent=1)
    write_md(res)
    return res


def write_md(res):
    c = E.cell
    L = ['# Input-GSD sweep on GAMUS (plan step 6a)', '', 'Commands (from `SynRS3D/`):', '', '```',
         '/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/gsd_sweep.py --predict DC   # and NYC, PHL (model)',
         f'{CMD}            # this report from the cache', '```', '',
         '**Current behaviour.** `infer_height.predict` and `app.py` never resample the input: the model sees the image pixels '
         'as delivered. The GSD is used only for building areas and the terrain grid. GAMUS is 0.33 m aerial imagery.', '',
         f"**Subsample.** {len(res['tiles'])} tiles (every 10th per city of the frozen 150; 135 dropped for time). Full 1024 px tile "
         "resampled, predicted with the app path (518 px tiles, 50% overlap, 4-flip TTA), prediction resampled back, scored "
         "on the 504 px centre crop. Cells: mean over tiles [95% bootstrap CI] (pooled). The native row uses the app path on "
         "the full tile, so it differs slightly from gamus_v2.json (centre crop alone).", '']
    for cname, r in res['by_city'].items():
        L += [f"## {cname} ({r['tiles']} tiles)", '', '| Model input | Model px | MAE (m) | MAE - native (m), tiles better | High MAE, ref > 3 m | '
              'Bias 0-3 | Bias 3-10 | Bias 10-20 | Bias > 20 (pooled) |', '|---|---|---|---|---|---|---|---|---|']
        for k in SETTINGS:
            e, d = r[k], r[k].get('mae_minus_native')
            dd = '–' if not d else f"{d['mean']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}], {d['tiles_better']}/{r['tiles']}"
            bb = ' | '.join('–' if not e['bins_pooled'][b] else f"{e['bins_pooled'][b]['bias']:+.2f}" for b in E.BIN_LABELS)
            L.append(f"| {k} m | {res['settings'][k]['model_px']} | {c(e['whole'], 'mae')} | {dd} | {c(e['high_ref3'], 'mae')} | {bb} |")
        L += ['', f"Lowest MAE: **{r['best_by_mae']}**; among settings from the native image: {r['best_native_grid_only']}.", '']
    dcs = res['decision']
    L += ['## Decision', '', 'Rule: change infer_height\'s default only if the new setting has a lower per-tile mean MAE than the '
          'current behaviour in all three cities.', '',
          '- Resampled native imagery beats native in: ' + '; '.join(f"{k}: {', '.join(v) or 'none'}" for k, v in dcs['beats_native_mae_in'].items()),
          '- Upsampling a 0.5 m source beats feeding it at 0.5 m in: ' + '; '.join(f"{k}: {', '.join(v) or 'none'}" for k, v in dcs['coarse_upsampling_beats_0.50_mae_in'].items())
          + ' (MAE difference vs the 0.50 m run, per city: ' + '; '.join(f"{c} {d['mean']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}], {d['tiles_better']}/{r['tiles']} tiles better"
                                                                  for c, r in res['by_city'].items() if c != 'ALL' for k in SETTINGS if SETTINGS[k][0] != NATIVE for d in [r[k]['mae_minus_0.50']]) + ')',
          f"- Settings that pass the rule: {', '.join(dcs['change_default']) or 'none'}."]
    open(os.path.join(V2, 'gsd_sweep.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


def selftest():
    rgb = (np.random.default_rng(0).random((FULL, FULL, 3)) * 255).astype(np.uint8)
    assert model_input(rgb, NATIVE, NATIVE) is rgb and model_input(rgb, NATIVE, 0.66).shape == (512, 512, 3)
    assert model_input(rgb, 0.5, NATIVE).shape == (FULL, FULL, 3) and model_input(rgb, 0.5, 0.4).shape == (845, 845, 3)
    ramp = np.tile(np.arange(FULL, dtype=np.float32), (FULL, 1))
    b = back(resize(ramp, 512, cv2.INTER_AREA))       # down and back: a linear ramp survives up to edge effects
    assert b.shape == (CROP, CROP) and np.abs(b - ramp[260:764, 260:764]).max() < 1.0
    assert np.array_equal(back(ramp), ramp[260:764, 260:764])
    t = tiles()
    assert len(t) == 15 and all(sum(n.startswith(c + '_') for n in t) == 5 for c in ('DC', 'NYC', 'PHL'))
    print('gsd_sweep selftest OK')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--selftest':
        selftest()
    elif a and a[0] == '--predict':
        predict(a[1] if len(a) > 1 else None)
    else:
        analyse()
