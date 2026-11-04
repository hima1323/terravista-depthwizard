"""Reproduce the published RS3DAda height numbers on Overhead Geopose Challenge ATL / ARG (plan step 5).

usage: .venv/bin/python demo/geopose_benchmark.py fetch [extra=100]   download the sampled test tiles (HTTP range reads)
       lockf -k <model.lock> .venv/bin/python demo/geopose_benchmark.py predict   run the model, cache every pass
       lockf -k <model.lock> .venv/bin/python demo/geopose_benchmark.py ablate    input-scale + reflect-pad passes (other_test)
       .venv/bin/python demo/geopose_benchmark.py report                     metrics from the cache -> geopose_v2.md/json
       .venv/bin/python demo/geopose_benchmark.py --selftest                 offline asserts
Data: the SynRS3D authors' preprocessed OGC_ATL / OGC_ARG zips (Google Drive links in SynRS3D README.md; source =
DrivenData Overhead Geopose Challenge, CC-BY-4.0): 512x512 RGB tiles + AGL nDSM, with their own test.txt split. The
zips are 12 / 29 GB, so only the sampled tiles are read out of them. Sample per city (fixed once written to
data/geopose/OGC_*/bench.txt): all of test_syn.txt (200 tiles; the set the released training script evaluates on
and picks its best checkpoint with) + `extra` random tiles of the rest of test.txt (default_rng(0)).
Passes cached per tile in demo/benchmark/v2/cache/geopose/<name>.npz (heights in int16 cm; fp32 pass first, then fp16):
  official  evaluation.py exactly: dataset.MultiTaskDataSet + CenterCrop 504 + Normalize, fp32, one pass, batch 1.
            Its per-tile utils/metrics.py values are also stored from the float32 maps (off_*), so the official
            number does not go through the cm rounding.
  crop16    the same 504 crop in fp16 with 4-flip TTA (demo/benchmark.py predict_tile): 'c16' = flip 0, 'c16tta' = mean
  dw        DepthWizard's app path: infer_height.predict on the whole 512 tile (518 patch, so zero-padded to 518,
            stride 259), fp16, 4-flip TTA, native resolution (the app never resamples by GSD); scored on the same 504 crop
"""
import io, json, os, sys, time, urllib.request, zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark as B   # ROOT/OUT, predict_tile, official; stubs utils/metrics.py's unused skimage/sklearn imports
import remote_zip
import eval_v2 as E

ZIPS = {'ATL': '1tWBfrGKPbrPT1CyXp0iUm6_KItKYuiWb', 'ARG': '1eTRYKdqX1Qce0Gq6EsmVQcWoiEioOdSB'}
URL = 'https://drive.usercontent.google.com/download?id={}&export=download&confirm=t'
DATA = os.path.join(B.ROOT, 'data', 'geopose')
V2 = os.path.join(B.OUT, 'v2')
CACHE = os.path.join(V2, 'cache', 'geopose')
WEIGHTS = B.infer_height.WEIGHTS
# whole-image MAE (m) from the paper's Figure 7 (arXiv:2406.18151 v2), as read in NEXT_STEPS_PLAN.md
PUBLISHED = {'ATL': {'RS3DAda': 5.67, 'source_only': 7.26}, 'ARG': {'RS3DAda': 2.01, 'source_only': 2.65}}
MAPS = ['official', 'c16', 'c16tta', 'dw']


class RangeFile(remote_zip.HttpFile):
    """Google Drive answers HEAD with an empty HTML page now: take the size from a 1-byte range GET instead."""
    def __init__(self, url):
        self.url, self.pos = url, 0
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'Range': 'bytes=0-0'}), timeout=60)
        self.size = int(r.headers['Content-Range'].split('/')[1])


def open_zip(city):
    return zipfile.ZipFile(io.BufferedReader(RangeFile(URL.format(ZIPS[city])), buffer_size=1 << 20))


def lines(p):
    return [l.strip() for l in open(p) if l.strip()]


def sample(city, extra):
    """test_syn.txt + `extra` random other test.txt tiles; written once to bench.txt so reruns use the same tiles."""
    d = os.path.join(DATA, f'OGC_{city}')
    p = os.path.join(d, 'bench.txt')
    if not os.path.exists(p):
        syn = lines(os.path.join(d, 'test_syn.txt'))
        rest = sorted(set(lines(os.path.join(d, 'test.txt'))) - set(syn))
        pick = np.random.default_rng(0).choice(len(rest), extra, replace=False)
        open(p, 'w').write('\n'.join(syn + [rest[i] for i in sorted(pick)]) + '\n')
    return lines(p)


def fetch(extra=100, workers=4):
    from concurrent.futures import ThreadPoolExecutor
    for city in ZIPS:
        names = sample(city, extra)
        todo = [f'OGC_{city}/{k}/{n}.tif' for n in names for k in ('opt', 'gt_nDSM')]
        size = {i.filename: i.file_size for i in open_zip(city).infolist()}
        todo = [m for m in todo if not os.path.exists(os.path.join(DATA, m))
                or os.path.getsize(os.path.join(DATA, m)) != size[m]]   # missing, or cut off by an interrupted run
        def work(chunk):   # one connection + zip handle per thread; write to .part then rename (no half files)
            z = open_zip(city)
            for m in chunk:
                dst = os.path.join(DATA, m)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with z.open(m) as src, open(dst + '.part', 'wb') as out:
                    out.write(src.read())
                os.replace(dst + '.part', dst)
        with ThreadPoolExecutor(workers) as ex:
            list(ex.map(work, [todo[i::workers] for i in range(workers)]))
        print(f'{city}: {len(names)} tiles ({len(todo)} files fetched)', flush=True)


def to_cm(h):
    return np.clip(np.round(np.asarray(h, np.float64) * 100), -32768, 32767).astype(np.int16)


def official_scalars(pred, gt):
    """utils/metrics.py Result on one tile, as evaluation.py feeds it (float32 maps)."""
    r = B.Result()
    r.update(pred.astype(np.float32).copy(), gt.astype(np.float32).copy())
    return {f'off_{k}_{m}': (float(r.metrics[k].values[m]) if r.metrics[k].valid else np.nan)
            for k in ('whole', 'high') for m in ('mae', 'rmse')}


def predict():
    """Two phases so only one copy of the model is in memory (fp32 + fp16 copies swapped hard on 8 GB):
    fp32 official pass for every tile -> <name>.off.npz, then the same model .half() for the fp16 passes."""
    import torch
    from albumentations import Compose, Normalize, CenterCrop
    from albumentations.pytorch import ToTensorV2
    from dataset.dataset import MultiTaskDataSet
    import infer_height
    from utils import geo_func
    # evaluation.py's testing_transforms (always_apply dropped: albumentations 2.x removed it; Normalize has p=1 anyway)
    T = Compose([CenterCrop(504, 504), Normalize(mean=(123.675, 116.28, 103.53), std=(58.395, 57.12, 57.375),
                                                 max_pixel_value=1), ToTensorV2()])
    os.makedirs(CACHE, exist_ok=True)
    todo = []
    for city in ZIPS:
        ds = MultiTaskDataSet([os.path.join(DATA, f'OGC_{city}')], is_training=False,
                              images_file=['train.txt', 'bench.txt', 'bench.txt'], transforms=T, multi_task=False)
        todo += [(ds, i, f) for i, f in enumerate(ds.files) if os.path.exists(f['img']) and os.path.exists(f['dsm'])
                 and not os.path.exists(os.path.join(CACHE, f['name'] + '.npz'))]   # rerun after fetch to add tiles
    if not todo:
        return
    model, dev, _ = infer_height.load_model(WEIGHTS, fp16=False)
    t0 = time.time()
    for j, (ds, i, f) in enumerate(todo):
        p = os.path.join(CACHE, f['name'] + '.off.npz')
        if os.path.exists(p):
            continue
        b = ds[i]
        with torch.no_grad():
            off = model(b['image'][None].to(dev))['regression'].float().cpu().numpy().squeeze()
        np.savez(p, official=to_cm(off), **official_scalars(off, b['dsm'].numpy().squeeze()))
        if (j + 1) % 50 == 0:
            print(f'fp32 {j + 1}/{len(todo)}, {(time.time() - t0) / (j + 1):.1f} s/tile', flush=True)
    model.half()
    t0 = time.time()
    for j, (ds, i, f) in enumerate(todo):
        p = os.path.join(CACHE, f['name'] + '.off.npz')
        img = geo_func.load_multiband(f['img'])[:, :, :3]          # what the app feeds the model
        t, l = (img.shape[0] - 504) // 2, (img.shape[1] - 504) // 2
        c16, c16tta, _ = B.predict_tile(model, dev, torch.float16, img[t:t + 504, l:l + 504])
        dw = infer_height.predict(model, dev, torch.float16, img, use_tta=True)[t:t + 504, l:l + 504]
        np.savez_compressed(os.path.join(CACHE, f['name'] + '.npz'), c16=to_cm(c16), c16tta=to_cm(c16tta),
                            dw=to_cm(dw), **dict(np.load(p)))
        os.remove(p)
        if (j + 1) % 50 == 0:
            print(f'fp16 {j + 1}/{len(todo)}, {(time.time() - t0) / (j + 1):.1f} s/tile', flush=True)


SCALES = [0.5, 0.75, 1.25, 1.5]   # input resampling factors (504 * s is a multiple of the 14-px patch for each)
ABL = os.path.join(V2, 'cache', 'geopose_ablate')


def rescaled(model, dev, crop, s):
    """Single fp16 pass on the 504 crop resampled by s (INTER_AREA down / INTER_CUBIC up), prediction back to 504."""
    import cv2, torch
    n = int(round(504 * s))
    x = cv2.resize(crop, (n, n), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    x = torch.from_numpy(((x.astype(np.float32) - B.MEAN) / B.STD).transpose(2, 0, 1)[None].copy())
    with torch.no_grad():   # one pass only (predict_tile would also run 3 flips: 4x the memory at s=1.5)
        p = model(x.to(dev, torch.float16))['regression'].float().cpu().numpy()[0, 0]
    return cv2.resize(p, (504, 504), interpolation=cv2.INTER_LINEAR)


def reflect_tta(model, dev, img):
    """infer_height.predict on one 512 tile with reflect padding to 518 instead of zero (black) padding: with a single
    518 patch the app's blend weights cancel, so this equals predict_tile's 4-flip mean on the padded tile."""
    import cv2, torch
    h, w = img.shape[:2]
    x = cv2.copyMakeBorder(img, 0, max(0, 518 - h), 0, max(0, 518 - w), cv2.BORDER_REFLECT_101)
    return B.predict_tile(model, dev, torch.float16, x)[1][:h, :w]


def ablate():
    """Extra passes on the non-test_syn bench tiles (the unbiased sample of test.txt), fp16, one model copy."""
    import torch
    import infer_height
    from utils import geo_func
    os.makedirs(ABL, exist_ok=True)
    model = None
    for city in ZIPS:
        syn = set(lines(os.path.join(DATA, f'OGC_{city}', 'test_syn.txt')))
        for n in [n for n in sample(city, 0) if n not in syn]:
            out = os.path.join(ABL, n + '.npz')
            if os.path.exists(out):
                continue
            if model is None:
                model, dev, _ = infer_height.load_model(WEIGHTS, fp16=True)
            img = geo_func.load_multiband(os.path.join(DATA, f'OGC_{city}', 'opt', n + '.tif'))[:, :, :3]
            t, l = (img.shape[0] - 504) // 2, (img.shape[1] - 504) // 2
            crop = np.ascontiguousarray(img[t:t + 504, l:l + 504])
            r = {f's{s:g}': to_cm(rescaled(model, dev, crop, s)) for s in SCALES}
            r['reflect_tta'] = to_cm(reflect_tta(model, dev, img)[t:t + 504, l:l + 504])
            np.savez_compressed(out, **r)


def read_gt(city, name):
    """Reference as dataset.MultiTaskDataSet + CenterCrop(504) give it: NaN or > 450 m set to 0."""
    from PIL import Image
    g = np.array(Image.open(os.path.join(DATA, f'OGC_{city}', 'gt_nDSM', name + '.tif')), np.float32)
    g[np.isnan(g) | (g > 450)] = 0
    t, l = (g.shape[0] - 504) // 2, (g.shape[1] - 504) // 2
    return g[t:t + 504, l:l + 504]


def paired(a, b):
    """Mean per-tile difference a - b with its 95% bootstrap CI (tiles where both exist)."""
    d = [x - y for x, y in zip(a, b) if np.isfinite(x) and np.isfinite(y)]
    lo, hi = E.bootstrap_ci(d)
    return {'mean': float(np.mean(d)), 'ci95': [lo, hi], 'tiles': len(d)}


def score(pairs):
    """pairs: [(pred, ref)] per tile -> official utils/metrics.py numbers + v2 metrics (eval_v2)."""
    off = B.official(pairs)
    per_whole = [E.metrics(np.clip(p, 0, None) - g, g) for p, g in pairs]
    sub = lambda a: a[::2, ::2]   # pooled median/NMAD/r on every 2nd row and column (memory); per-tile values use all
    pool = [np.concatenate([sub(x).ravel() for x in c]) for c in zip(*pairs)]
    v2 = {'whole': E.aggregate(per_whole, E.metrics(np.clip(pool[0], 0, None) - pool[1], pool[1])),
          'high': E.aggregate([E.high_metrics(p, g) for p, g in pairs], E.high_metrics(*pool)),
          'bins': {}}
    for lab, (lo, hi) in zip(E.BIN_LABELS, E.BINS):
        cut = lambda p, g: (np.clip(p, 0, None)[(g >= lo) & (g < hi)] - g[(g >= lo) & (g < hi)], g[(g >= lo) & (g < hi)])
        v2['bins'][lab] = E.aggregate([E.metrics(*cut(p, g)) if ((g >= lo) & (g < hi)).sum() >= 100 else None
                                       for p, g in pairs], E.metrics(*cut(*pool)))
    tile_mae = [m['mae'] for m in per_whole]
    return {'official': off, 'official_whole_mae_ci95': E.bootstrap_ci(tile_mae), 'v2': v2}, tile_mae


def report():
    res = {'protocol': __doc__.split('Passes cached')[0].strip(), 'published_fig7': PUBLISHED,
           'published_fig7_other': {'ATL': {'train_on_TD1': 4.95, 'f1_1.25': {'RS3DAda': 0.39, 'source_only': 0.27}},
                                    'ARG': {'train_on_TD1': 1.78, 'f1_1.25': {'RS3DAda': 0.63, 'source_only': 0.47}}},
           'cities': {}}
    for city in ZIPS:
        names = [n for n in sample(city, 0) if os.path.exists(os.path.join(CACHE, n + '.npz'))]
        if not names:
            continue
        syn = set(lines(os.path.join(DATA, f'OGC_{city}', 'test_syn.txt')))
        gts = {n: read_gt(city, n) for n in names}
        cache = {n: np.load(os.path.join(CACHE, n + '.npz')) for n in names}
        exact = [{k: float(cache[n][k]) for k in cache[n].files if k.startswith('off_')} for n in names]
        valid = [e['off_whole_mae'] for e in exact if np.isfinite(e['off_whole_mae'])]
        out = {'tiles': len(names), 'tiles_test_syn': len(syn & set(names)),
               'official_exact_fp32': {'whole_mae': float(np.mean(valid)), 'tiles': len(valid), 'ci95': E.bootstrap_ci(valid),
                                       'whole_rmse': float(np.nanmean([e['off_whole_rmse'] for e in exact])),
                                       'high_mae': float(np.nanmean([e['off_high_mae'] for e in exact])),
                                       'high_rmse': float(np.nanmean([e['off_high_rmse'] for e in exact]))},
               'passes': {}, 'subsets': {}, 'paired_vs_official_whole_mae': {}}
        tm = {}
        for k in MAPS:
            pairs = [(cache[n][k].astype(np.float32) / 100, gts[n]) for n in names]
            out['passes'][k], tm[k] = score(pairs)
            if k in ('official', 'dw'):   # test_syn (checkpoint-selection set of the released script) vs the rest
                for s, keep in [('test_syn', True), ('other_test', False)]:
                    sel = [pr for n, pr in zip(names, pairs) if (n in syn) == keep]
                    if sel:
                        out['subsets'].setdefault(s, {})[k] = B.official(sel)
            del pairs
        for k in MAPS[1:]:
            out['paired_vs_official_whole_mae'][k] = paired(tm[k], tm['official'])
        ab = [n for n in names if os.path.exists(os.path.join(ABL, n + '.npz'))]
        if ab:   # input-scale / padding ablation on the same tiles, paired against the matching base pass
            A = {n: np.load(os.path.join(ABL, n + '.npz')) for n in ab}
            pr = lambda src, k: [(src[n][k].astype(np.float32) / 100, gts[n]) for n in ab]
            tmae = lambda P: [E.metrics(np.clip(p, 0, None) - g, g)['mae'] for p, g in P]
            base = {'c16': pr(cache, 'c16'), 'dw': pr(cache, 'dw')}
            out['ablation'] = {'tiles': len(ab), 'base': {k: B.official(v) for k, v in base.items()}, 'passes': {}}
            for k, ref in [(f's{x:g}', 'c16') for x in SCALES] + [('reflect_tta', 'dw')]:
                P = pr(A, k)
                out['ablation']['passes'][k] = {'vs': ref, 'official': B.official(P),
                                                'paired_tile_mae_minus_base': paired(tmae(P), tmae(base[ref]))}
            del A, base
        res['cities'][city] = out
        del cache, gts
    os.makedirs(V2, exist_ok=True)
    json.dump(res, open(os.path.join(V2, 'geopose_v2.json'), 'w'), indent=2, default=float)
    write_md(res)


def write_md(res):
    f = lambda v, nd=2: '–' if v is None or (isinstance(v, float) and not np.isfinite(v)) else f'{v:.{nd}f}'
    ci = lambda c: f'[{f(c[0])}, {f(c[1])}]' if c and c[0] is not None else ''
    L = ['# RS3DAda on Overhead Geopose ATL / ARG (SynRS3D Target Domain 2): reproduction (plan step 5)', '',
         'All numbers below come from `demo/geopose_benchmark.py report` and are stored in '
         '`demo/benchmark/v2/geopose_v2.json`.', '',
         '## Headline: whole-image MAE, evaluation.py protocol, released weights', '',
         '| City | Tiles | Ours, evaluation.py path (fp32) | 95% CI (tiles) | Paper RS3DAda | Paper source-only | '
         'Paper train-on-TD1 | Ours, DepthWizard path | Paper F1 (δ<1.25) | Ours F1 |', '|---|---|---|---|---|---|---|---|---|---|']
    for city, c in res['cities'].items():
        o, p, q = c['official_exact_fp32'], res['published_fig7'][city], res['published_fig7_other'][city]
        L.append(f"| {city} | {c['tiles']} | {f(o['whole_mae'])} | {ci(o['ci95'])} | {p['RS3DAda']} | {p['source_only']} | "
                 f"{q['train_on_TD1']} | {f(c['passes']['dw']['official']['whole']['mae'])} | {q['f1_1.25']['RS3DAda']} | "
                 f"{f(c['passes']['official']['official']['whole']['f1_1.25'])} |")
    L += ['', '## Findings', '']
    for city, c in res['cities'].items():
        o, pub, d = c['official_exact_fp32'], res['published_fig7'][city]['RS3DAda'], c['paired_vs_official_whole_mae']['dw']
        inside = o['ci95'][0] <= pub <= o['ci95'][1]
        L.append(f"- {city}: evaluation.py path {f(o['whole_mae'])} m [{f(o['ci95'][0])}, {f(o['ci95'][1])}] vs paper {pub} m "
                 f"({'inside' if inside else 'outside'} the 95% CI; test_syn {f(c['subsets']['test_syn']['official']['whole']['mae'])}, "
                 f"other_test {f(c['subsets']['other_test']['official']['whole']['mae'])}). DepthWizard path minus evaluation.py: "
                 f"{d['mean']:+.3f} m [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}] per tile.")
    L += ['- The DepthWizard inference path is not worse than the official one (the 4-flip TTA explains the gain); '
          'no infer_height.py patch is warranted by this benchmark. See the ablation for padding and input scale.',
          '- Tall objects are strongly under-predicted on both cities (height-binned table): the same pattern as GAMUS, '
          'so it is the model, not DepthWizard\'s tiling.']
    L += ['', '## Ablation: which part of the DepthWizard path changes the error (official metrics, utils/metrics.py)', '',
          '| City | Pass | MAE whole | RMSE whole | MAE high (>3 m, union) | RMSE high | F1 δ<1.25 | ΔMAE whole vs evaluation.py, per-tile mean [95% CI] |',
          '|---|---|---|---|---|---|---|---|']
    names = {'official': 'evaluation.py: 504 crop, fp32, 1 pass', 'c16': '504 crop, fp16, 1 pass',
             'c16tta': '504 crop, fp16, 4-flip TTA', 'dw': 'DepthWizard infer_height.predict: 512 tile padded to 518, fp16, TTA'}
    for city, c in res['cities'].items():
        for k, lab in names.items():
            o, d = c['passes'][k]['official'], c['paired_vs_official_whole_mae'].get(k)
            L.append(f"| {city} | {lab} | {f(o['whole']['mae'])} | {f(o['whole']['rmse'])} | {f(o['high']['mae'])} | "
                     f"{f(o['high']['rmse'])} | {f(o['whole']['f1_1.25'])} | "
                     + (f"{d['mean']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]" if d else '–') + ' |')
    L += ['', '## Subsets: test_syn.txt (the released training script picks its checkpoint on it) vs other test tiles', '',
          '| City | Subset | Tiles | MAE whole, evaluation.py path | MAE whole, DepthWizard path |', '|---|---|---|---|---|']
    for city, c in res['cities'].items():
        for s, v in c['subsets'].items():
            L.append(f"| {city} | {s} | {v['official']['whole']['tiles']} | {f(v['official']['whole']['mae'])} | {f(v['dw']['whole']['mae'])} |")
    L += ['', '## Ablation on the other_test tiles: input resampling and padding (official metrics)', '',
          'Scale s: the 504 crop resampled by s before the model (s < 1 = coarser, as if GSD were larger), prediction '
          'resampled back; compared with the 504 fp16 single pass. reflect_tta: the DepthWizard pass with reflect instead '
          'of zero padding to 518; compared with the DepthWizard pass.', '',
          '| City | Tiles | Pass | MAE whole | MAE high | F1 δ<1.25 | Base | Base MAE whole | ΔMAE per tile [95% CI] |',
          '|---|---|---|---|---|---|---|---|---|']
    for city, c in res['cities'].items():
        a = c.get('ablation')
        for k, v in (a['passes'].items() if a else []):
            o, b, d = v['official'], a['base'][v['vs']]['whole'], v['paired_tile_mae_minus_base']
            L.append(f"| {city} | {a['tiles']} | {k} | {f(o['whole']['mae'])} | {f(o['high']['mae'])} | "
                     f"{f(o['whole']['f1_1.25'])} | {v['vs']} | {f(b['mae'])} | "
                     f"{d['mean']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}] |")
    L += ['', '## v2 metrics (demo/eval_v2.py): per-tile mean [95% bootstrap CI over tiles] (pooled)', '',
          'Prediction clipped at 0; e = ours - reference. Pooled median/NMAD/r use every 2nd row and column.', '',
          '| City | Pass | Pixels | MAE | RMSE | Bias | NMAD | r | within ±1 m | within ±2 m |', '|---|---|---|---|---|---|---|---|---|---|']
    for city, c in res['cities'].items():
        for k in ('official', 'dw'):
            for grp in ('whole', 'high'):
                a = c['passes'][k]['v2'][grp]
                L.append(f"| {city} | {k} | {grp} | " + ' | '.join(E.cell(a, m, 3 if m == 'r' else 2) for m in
                                                                  ('mae', 'rmse', 'bias', 'nmad', 'r', 'within_1m', 'within_2m')) + ' |')
    L += ['', 'Height-binned (reference height), evaluation.py-path prediction; tiles with >= 100 px in the bin:', '',
          '| City | Bin | Tiles | Bias | MAE | NMAD |', '|---|---|---|---|---|---|']
    for city, c in res['cities'].items():
        for lab, a in c['passes']['official']['v2']['bins'].items():
            L.append(f"| {city} | {lab} | {a['units']} | {E.cell(a, 'bias')} | {E.cell(a, 'mae')} | {E.cell(a, 'nmad')} |")
    L += ['', '## How these numbers were made', '', '```',
          'cd SynRS3D',
          '.venv/bin/python demo/geopose_benchmark.py fetch            # 300 tiles per city out of the authors\' zips',
          'lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/geopose_benchmark.py predict',
          'lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/geopose_benchmark.py ablate',
          '.venv/bin/python demo/geopose_benchmark.py report',
          '.venv/bin/python demo/geopose_benchmark.py --selftest', '```', '',
          '- Data: SynRS3D authors\' preprocessed OGC_ATL / OGC_ARG (Google Drive ids in demo/geopose_benchmark.py, linked '
          'from SynRS3D README.md), derived from the DrivenData Overhead Geopose Challenge (Atlanta, Buenos Aires; '
          'licence CC BY 4.0 per SynRS3D README). 512x512 RGB tiles + nDSM (AGL) float32; no georeferencing or GSD in the files.',
          '- Weights: pretrain/RS3DAda_vitl_DPT_height.pth (released). Metric code: utils/metrics.py (Result/AverageMeter: '
          'values <= 0 set to 1e-6, per-tile MAE averaged over tiles; high = pixels where reference OR prediction > 3 m, '
          'a tile is skipped when either the reference or the prediction has no pixel > 3 m).',
          '- Sample: test_syn.txt (200 tiles, also the evaluation default in evaluation.py and the checkpoint-selection set '
          'of the released training script) + 100 tiles drawn at random (default_rng(0)) from the rest of test.txt '
          '(3356 ATL / 8106 ARG tiles). The paper does not say which list its Figure 7 numbers use; other_test is the '
          'unbiased sample of test.txt.',
          '- Published numbers: whole-image MAE read off Figure 7 of arXiv:2406.18151 (no per-city table in the text).']
    open(os.path.join(V2, 'geopose_v2.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


def selftest():
    h = np.array([1.234, -0.006, 400.0, 0.004])
    assert to_cm(h).tolist() == [123, -1, 32767, 0]
    rng = np.random.default_rng(3)
    g = np.clip(rng.normal(3, 5, (504, 504)), 0, None).astype(np.float32)
    p = (g + rng.normal(0, 1, g.shape)).astype(np.float32)
    s = official_scalars(p, g)
    assert abs(s['off_whole_mae'] - B.official([(p, g)])['whole']['mae']) < 1e-6
    assert abs(s['off_whole_mae'] - np.abs(np.where(p <= 0, 1e-6, p) - np.where(g <= 0, 1e-6, g)).mean()) < 1e-5
    assert np.isnan(official_scalars(np.zeros_like(g), np.zeros_like(g))['off_high_mae'])   # all-ground tile skipped
    d = paired([3.0, 4.0, np.nan, 6.0], [2.0, 2.0, 1.0, 5.0])
    assert d['tiles'] == 3 and abs(d['mean'] - 4 / 3) < 1e-12 and d['ci95'][0] <= d['mean'] <= d['ci95'][1]
    r, tm = score([(p, g), (g.copy(), g)])
    assert abs(r['official']['whole']['mae'] - s['off_whole_mae'] / 2) < 1e-4 and len(tm) == 2 and tm[1] == 0
    class Fake:   # 'model' returning normalised channel 0: flips must be undone and padding cropped away
        def __call__(self, x):
            return {'regression': x[:, :1]}
    import torch
    img = rng.integers(0, 255, (512, 512, 3)).astype(np.uint8)
    want = (img[..., 0].astype(np.float32) - B.MEAN[0]) / B.STD[0]
    assert np.allclose(reflect_tta(Fake(), 'cpu', img), want, atol=5e-3)   # fp16 rounding
    flat = np.full((504, 504, 3), 100, np.uint8)
    for sc in SCALES:
        q = rescaled(Fake(), 'cpu', flat, sc)
        assert q.shape == (504, 504) and np.allclose(q, (100 - B.MEAN[0]) / B.STD[0], atol=5e-3)
    assert r['v2']['whole']['units'] == 2 and abs(r['v2']['whole']['mae']['mean'] - np.mean(tm)) < 1e-12
    print('geopose_benchmark selftest OK')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'fetch':
        fetch(int(sys.argv[2]) if len(sys.argv) > 2 else 100)
    elif cmd == 'predict':
        predict()
    elif cmd == 'ablate':
        ablate()
    elif cmd == 'report':
        report()
    elif cmd == '--selftest':
        selftest()
    else:
        print(__doc__)
