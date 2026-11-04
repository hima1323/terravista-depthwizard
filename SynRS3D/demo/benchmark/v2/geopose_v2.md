# RS3DAda on Overhead Geopose ATL / ARG (SynRS3D Target Domain 2): reproduction (plan step 5)

All numbers below come from `demo/geopose_benchmark.py report` and are stored in `demo/benchmark/v2/geopose_v2.json`.

## Headline: whole-image MAE, evaluation.py protocol, released weights

| City | Tiles | Ours, evaluation.py path (fp32) | 95% CI (tiles) | Paper RS3DAda | Paper source-only | Paper train-on-TD1 | Ours, DepthWizard path | Paper F1 (δ<1.25) | Ours F1 |
|---|---|---|---|---|---|---|---|---|---|
| ATL | 300 | 5.99 | [5.57, 6.43] | 5.67 | 7.26 | 4.95 | 5.90 | 0.39 | 0.41 |
| ARG | 300 | 1.94 | [1.86, 2.03] | 2.01 | 2.65 | 1.78 | 1.87 | 0.63 | 0.65 |

## Findings

- ATL: evaluation.py path 5.99 m [5.57, 6.43] vs paper 5.67 m (inside the 95% CI; test_syn 6.23, other_test 5.50). DepthWizard path minus evaluation.py: -0.091 m [-0.137, -0.041] per tile.
- ARG: evaluation.py path 1.94 m [1.86, 2.03] vs paper 2.01 m (inside the 95% CI; test_syn 1.95, other_test 1.92). DepthWizard path minus evaluation.py: -0.071 m [-0.089, -0.056] per tile.
- The DepthWizard inference path is not worse than the official one (the 4-flip TTA explains the gain); no infer_height.py patch is warranted by this benchmark. See the ablation for padding and input scale.
- Tall objects are strongly under-predicted on both cities (height-binned table): the same pattern as GAMUS, so it is the model, not DepthWizard's tiling.

## Ablation: which part of the DepthWizard path changes the error (official metrics, utils/metrics.py)

| City | Pass | MAE whole | RMSE whole | MAE high (>3 m, union) | RMSE high | F1 δ<1.25 | ΔMAE whole vs evaluation.py, per-tile mean [95% CI] |
|---|---|---|---|---|---|---|---|
| ATL | evaluation.py: 504 crop, fp32, 1 pass | 5.99 | 9.23 | 8.98 | 11.67 | 0.41 | – |
| ATL | 504 crop, fp16, 1 pass | 5.99 | 9.23 | 8.98 | 11.67 | 0.41 | +0.000 [-0.000, +0.001] |
| ATL | 504 crop, fp16, 4-flip TTA | 5.91 | 9.10 | 8.87 | 11.53 | 0.42 | -0.083 [-0.119, -0.044] |
| ATL | DepthWizard infer_height.predict: 512 tile padded to 518, fp16, TTA | 5.90 | 9.09 | 8.84 | 11.50 | 0.41 | -0.091 [-0.137, -0.041] |
| ARG | evaluation.py: 504 crop, fp32, 1 pass | 1.94 | 2.89 | 2.91 | 3.80 | 0.65 | – |
| ARG | 504 crop, fp16, 1 pass | 1.94 | 2.89 | 2.91 | 3.80 | 0.65 | +0.000 [+0.000, +0.000] |
| ARG | 504 crop, fp16, 4-flip TTA | 1.86 | 2.78 | 2.78 | 3.66 | 0.67 | -0.077 [-0.089, -0.067] |
| ARG | DepthWizard infer_height.predict: 512 tile padded to 518, fp16, TTA | 1.87 | 2.78 | 2.78 | 3.64 | 0.66 | -0.071 [-0.089, -0.056] |

## Subsets: test_syn.txt (the released training script picks its checkpoint on it) vs other test tiles

| City | Subset | Tiles | MAE whole, evaluation.py path | MAE whole, DepthWizard path |
|---|---|---|---|---|
| ATL | test_syn | 200 | 6.23 | 6.11 |
| ATL | other_test | 100 | 5.50 | 5.47 |
| ARG | test_syn | 200 | 1.95 | 1.88 |
| ARG | other_test | 100 | 1.92 | 1.84 |

## Ablation on the other_test tiles: input resampling and padding (official metrics)

Scale s: the 504 crop resampled by s before the model (s < 1 = coarser, as if GSD were larger), prediction resampled back; compared with the 504 fp16 single pass. reflect_tta: the DepthWizard pass with reflect instead of zero padding to 518; compared with the DepthWizard pass.

| City | Tiles | Pass | MAE whole | MAE high | F1 δ<1.25 | Base | Base MAE whole | ΔMAE per tile [95% CI] |
|---|---|---|---|---|---|---|---|---|
| ATL | 100 | s0.5 | 6.03 | 9.08 | 0.32 | c16 | 5.50 | +0.530 [+0.405, +0.666] |
| ATL | 100 | s0.75 | 5.68 | 8.83 | 0.38 | c16 | 5.50 | +0.182 [+0.130, +0.242] |
| ATL | 100 | s1.25 | 5.47 | 8.64 | 0.42 | c16 | 5.50 | -0.031 [-0.065, +0.006] |
| ATL | 100 | s1.5 | 5.47 | 8.66 | 0.42 | c16 | 5.50 | -0.032 [-0.069, +0.006] |
| ATL | 100 | reflect_tta | 5.48 | 8.65 | 0.41 | dw | 5.47 | +0.015 [-0.002, +0.032] |
| ARG | 100 | s0.5 | 2.23 | 3.11 | 0.57 | c16 | 1.92 | +0.307 [+0.233, +0.366] |
| ARG | 100 | s0.75 | 2.01 | 2.95 | 0.62 | c16 | 1.92 | +0.086 [+0.048, +0.117] |
| ARG | 100 | s1.25 | 1.89 | 2.92 | 0.66 | c16 | 1.92 | -0.031 [-0.051, -0.007] |
| ARG | 100 | s1.5 | 1.88 | 2.93 | 0.66 | c16 | 1.92 | -0.040 [-0.063, -0.017] |
| ARG | 100 | reflect_tta | 1.87 | 2.78 | 0.66 | dw | 1.84 | +0.029 [+0.014, +0.042] |

## v2 metrics (demo/eval_v2.py): per-tile mean [95% bootstrap CI over tiles] (pooled)

Prediction clipped at 0; e = ours - reference. Pooled median/NMAD/r use every 2nd row and column.

| City | Pass | Pixels | MAE | RMSE | Bias | NMAD | r | within ±1 m | within ±2 m |
|---|---|---|---|---|---|---|---|---|---|
| ATL | official | whole | 5.99 [5.57, 6.43] (5.99) | 9.23 [8.60, 9.88] (10.76) | -4.08 [-4.54, -3.66] (-4.08) | 4.85 [4.39, 5.31] (3.65) | 0.642 [0.622, 0.662] (0.694) | 0.37 [0.35, 0.39] (0.37) | 0.47 [0.45, 0.49] (0.47) |
| ATL | official | high | 8.97 [8.51, 9.44] (9.59) | 11.65 [10.97, 12.35] (13.85) | -6.45 [-6.96, -5.98] (-6.97) | 7.58 [7.23, 7.93] (9.41) | 0.402 [0.372, 0.434] (0.623) | 0.09 [0.08, 0.10] (0.08) | 0.17 [0.15, 0.18] (0.16) |
| ATL | dw | whole | 5.90 [5.48, 6.34] (5.90) | 9.09 [8.45, 9.74] (10.64) | -4.12 [-4.59, -3.71] (-4.12) | 4.81 [4.35, 5.25] (3.60) | 0.666 [0.646, 0.685] (0.708) | 0.37 [0.35, 0.39] (0.37) | 0.47 [0.45, 0.49] (0.47) |
| ATL | dw | high | 8.83 [8.37, 9.30] (9.45) | 11.48 [10.80, 12.16] (13.71) | -6.55 [-7.04, -6.08] (-7.08) | 7.39 [7.06, 7.74] (9.16) | 0.437 [0.408, 0.467] (0.639) | 0.09 [0.08, 0.10] (0.08) | 0.17 [0.16, 0.18] (0.16) |
| ARG | official | whole | 1.94 [1.86, 2.03] (1.94) | 2.89 [2.77, 3.02] (3.11) | -0.36 [-0.47, -0.26] (-0.37) | 1.81 [1.71, 1.91] (1.79) | 0.650 [0.630, 0.667] (0.672) | 0.45 [0.43, 0.47] (0.45) | 0.66 [0.64, 0.67] (0.66) |
| ARG | official | high | 2.96 [2.83, 3.09] (2.79) | 3.84 [3.67, 4.02] (3.90) | -0.99 [-1.19, -0.79] (-0.70) | 2.94 [2.83, 3.05] (3.14) | 0.377 [0.351, 0.402] (0.401) | 0.23 [0.22, 0.24] (0.25) | 0.45 [0.44, 0.47] (0.48) |
| ARG | dw | whole | 1.87 [1.79, 1.95] (1.87) | 2.78 [2.66, 2.90] (2.98) | -0.34 [-0.44, -0.24] (-0.34) | 1.74 [1.64, 1.83] (1.76) | 0.679 [0.661, 0.695] (0.701) | 0.45 [0.44, 0.47] (0.45) | 0.67 [0.66, 0.68] (0.67) |
| ARG | dw | high | 2.82 [2.70, 2.95] (2.66) | 3.67 [3.52, 3.84] (3.72) | -0.95 [-1.14, -0.75] (-0.68) | 2.79 [2.69, 2.89] (2.98) | 0.427 [0.403, 0.450] (0.449) | 0.24 [0.23, 0.25] (0.26) | 0.48 [0.46, 0.49] (0.50) |

Height-binned (reference height), evaluation.py-path prediction; tiles with >= 100 px in the bin:

| City | Bin | Tiles | Bias | MAE | NMAD |
|---|---|---|---|---|---|
| ATL | 0-3 m | 300 | 1.31 [1.16, 1.49] (1.06) | 1.51 [1.36, 1.68] (1.27) | 0.82 [0.75, 0.89] (0.44) |
| ATL | 3-10 m | 299 | -2.17 [-2.37, -1.96] (-1.93) | 3.63 [3.48, 3.78] (3.43) | 2.97 [2.85, 3.10] (3.34) |
| ATL | 10-20 m | 298 | -8.11 [-8.53, -7.66] (-8.30) | 9.50 [9.25, 9.73] (9.60) | 4.29 [4.05, 4.58] (4.54) |
| ATL | 20-inf m | 288 | -16.80 [-17.61, -15.94] (-17.78) | 18.37 [17.69, 19.07] (19.67) | 6.55 [5.77, 7.32] (6.45) |
| ARG | 0-3 m | 300 | 0.99 [0.90, 1.06] (0.81) | 1.29 [1.22, 1.35] (1.14) | 1.02 [0.95, 1.08] (0.76) |
| ARG | 3-10 m | 296 | -0.89 [-1.01, -0.77] (-0.66) | 2.12 [2.04, 2.19] (1.99) | 2.20 [2.14, 2.26] (2.34) |
| ARG | 10-20 m | 292 | -5.59 [-5.87, -5.28] (-5.68) | 6.02 [5.77, 6.26] (6.17) | 2.96 [2.80, 3.15] (3.69) |
| ARG | 20-inf m | 144 | -15.25 [-16.89, -13.71] (-14.02) | 16.16 [14.87, 17.58] (14.63) | 3.95 [3.18, 4.88] (4.20) |

## How these numbers were made

```
cd SynRS3D
.venv/bin/python demo/geopose_benchmark.py fetch            # 300 tiles per city out of the authors' zips
lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/geopose_benchmark.py predict
lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/geopose_benchmark.py ablate
.venv/bin/python demo/geopose_benchmark.py report
.venv/bin/python demo/geopose_benchmark.py --selftest
```

- Data: SynRS3D authors' preprocessed OGC_ATL / OGC_ARG (Google Drive ids in demo/geopose_benchmark.py, linked from SynRS3D README.md), derived from the DrivenData Overhead Geopose Challenge (Atlanta, Buenos Aires; licence CC BY 4.0 per SynRS3D README). 512x512 RGB tiles + nDSM (AGL) float32; no georeferencing or GSD in the files.
- Weights: pretrain/RS3DAda_vitl_DPT_height.pth (released). Metric code: utils/metrics.py (Result/AverageMeter: values <= 0 set to 1e-6, per-tile MAE averaged over tiles; high = pixels where reference OR prediction > 3 m, a tile is skipped when either the reference or the prediction has no pixel > 3 m).
- Sample: test_syn.txt (200 tiles, also the evaluation default in evaluation.py and the checkpoint-selection set of the released training script) + 100 tiles drawn at random (default_rng(0)) from the rest of test.txt (3356 ATL / 8106 ARG tiles). The paper does not say which list its Figure 7 numbers use; other_test is the unbiased sample of test.txt.
- Published numbers: whole-image MAE read off Figure 7 of arXiv:2406.18151 (no per-city table in the text).
