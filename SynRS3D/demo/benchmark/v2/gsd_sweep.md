# Input-GSD sweep on GAMUS (plan step 6a)

Commands (from `SynRS3D/`):

```
/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/gsd_sweep.py --predict DC   # and NYC, PHL (model)
.venv/bin/python demo/gsd_sweep.py            # this report from the cache
```

**Current behaviour.** `infer_height.predict` and `app.py` never resample the input: the model sees the image pixels as delivered. The GSD is used only for building areas and the terrain grid. GAMUS is 0.33 m aerial imagery.

**Subsample.** 15 tiles (every 10th per city of the frozen 150; 135 dropped for time). Full 1024 px tile resampled, predicted with the app path (518 px tiles, 50% overlap, 4-flip TTA), prediction resampled back, scored on the 504 px centre crop. Cells: mean over tiles [95% bootstrap CI] (pooled). The native row uses the app path on the full tile, so it differs slightly from gamus_v2.json (centre crop alone).

## ALL (15 tiles)

| Model input | Model px | MAE (m) | MAE - native (m), tiles better | High MAE, ref > 3 m | Bias 0-3 | Bias 3-10 | Bias 10-20 | Bias > 20 (pooled) |
|---|---|---|---|---|---|---|---|---|
| native 0.33 m | 1024 | 3.15 [2.13, 4.35] (3.14) | – | 5.64 [4.19, 7.40] (6.03) | +0.77 | -0.84 | -7.25 | -11.09 |
| 0.30 m | 1126 | 3.22 [2.18, 4.39] (3.22) | +0.072 [+0.001, +0.164], 5/15 | 5.78 [4.33, 7.55] (6.19) | +0.78 | -0.57 | -6.99 | -10.43 |
| 0.40 m | 845 | 3.08 [2.09, 4.26] (3.08) | -0.064 [-0.234, +0.056], 5/15 | 5.51 [4.09, 7.20] (5.86) | +0.79 | -1.15 | -7.62 | -12.71 |
| 0.50 m | 676 | 3.15 [2.15, 4.36] (3.15) | +0.008 [-0.133, +0.127], 4/15 | 5.64 [4.18, 7.36] (5.98) | +0.82 | -1.59 | -8.10 | -12.15 |
| 0.70 m | 483 | 3.25 [2.25, 4.47] (3.25) | +0.104 [-0.143, +0.308], 4/15 | 5.79 [4.38, 7.45] (6.16) | +0.86 | -2.03 | -8.72 | -12.91 |
| 0.50 src -> 0.33 m | 1024 | 3.12 [2.12, 4.32] (3.12) | -0.028 [-0.107, +0.018], 5/15 | 5.58 [4.15, 7.30] (5.96) | +0.78 | -0.91 | -7.37 | -11.90 |

Lowest MAE: **0.40**; among settings from the native image: 0.40.

## DC (5 tiles)

| Model input | Model px | MAE (m) | MAE - native (m), tiles better | High MAE, ref > 3 m | Bias 0-3 | Bias 3-10 | Bias 10-20 | Bias > 20 (pooled) |
|---|---|---|---|---|---|---|---|---|
| native 0.33 m | 1024 | 4.15 [1.94, 6.43] (4.15) | – | 7.70 [4.82, 10.43] (9.07) | +0.65 | -1.68 | -7.76 | -7.74 |
| 0.30 m | 1126 | 4.23 [1.95, 6.51] (4.22) | +0.078 [-0.019, +0.245], 1/5 | 7.88 [5.01, 10.76] (9.27) | +0.65 | -1.52 | -7.70 | -6.82 |
| 0.40 m | 845 | 3.98 [1.87, 6.04] (3.98) | -0.167 [-0.646, +0.107], 1/5 | 7.38 [4.85, 10.06] (8.66) | +0.65 | -1.86 | -8.02 | -10.13 |
| 0.50 m | 676 | 4.13 [1.93, 6.27] (4.12) | -0.021 [-0.331, +0.177], 1/5 | 7.64 [5.11, 10.17] (8.95) | +0.71 | -2.03 | -8.39 | -9.26 |
| 0.70 m | 483 | 4.10 [1.95, 6.36] (4.09) | -0.053 [-0.690, +0.369], 1/5 | 7.54 [4.91, 10.31] (8.85) | +0.72 | -2.27 | -8.91 | -10.35 |
| 0.50 src -> 0.33 m | 1024 | 4.05 [1.89, 6.23] (4.05) | -0.096 [-0.319, +0.023], 2/5 | 7.51 [4.72, 10.11] (8.85) | +0.64 | -1.73 | -7.92 | -8.88 |

Lowest MAE: **0.40**; among settings from the native image: 0.40.

## NYC (5 tiles)

| Model input | Model px | MAE (m) | MAE - native (m), tiles better | High MAE, ref > 3 m | Bias 0-3 | Bias 3-10 | Bias 10-20 | Bias > 20 (pooled) |
|---|---|---|---|---|---|---|---|---|
| native 0.33 m | 1024 | 3.56 [2.13, 5.54] (3.56) | – | 5.78 [3.54, 8.65] (5.97) | +0.92 | -0.87 | -10.45 | -18.91 |
| 0.30 m | 1126 | 3.58 [2.18, 5.53] (3.58) | +0.018 [-0.023, +0.082], 3/5 | 5.82 [3.64, 8.68] (6.02) | +0.90 | -0.73 | -10.41 | -18.87 |
| 0.40 m | 845 | 3.59 [2.13, 5.52] (3.59) | +0.023 [-0.053, +0.090], 2/5 | 5.81 [3.56, 8.56] (5.98) | +0.97 | -1.11 | -10.52 | -18.87 |
| 0.50 m | 676 | 3.58 [2.09, 5.48] (3.58) | +0.021 [-0.190, +0.180], 1/5 | 5.80 [3.41, 8.54] (5.93) | +1.02 | -1.50 | -10.57 | -18.86 |
| 0.70 m | 483 | 3.73 [2.15, 5.65] (3.73) | +0.165 [-0.130, +0.390], 1/5 | 6.07 [3.58, 8.80] (6.17) | +1.06 | -1.94 | -10.98 | -19.03 |
| 0.50 src -> 0.33 m | 1024 | 3.59 [2.15, 5.56] (3.59) | +0.026 [+0.020, +0.032], 0/5 | 5.82 [3.58, 8.68] (6.00) | +0.94 | -0.89 | -10.47 | -18.97 |

Lowest MAE: **native 0.33**; among settings from the native image: native 0.33.

## PHL (5 tiles)

| Model input | Model px | MAE (m) | MAE - native (m), tiles better | High MAE, ref > 3 m | Bias 0-3 | Bias 3-10 | Bias 10-20 | Bias > 20 (pooled) |
|---|---|---|---|---|---|---|---|---|
| native 0.33 m | 1024 | 1.72 [1.13, 2.31] (1.72) | – | 3.45 [2.37, 4.42] (3.00) | +0.75 | -0.28 | -2.20 | -12.53 |
| 0.30 m | 1126 | 1.84 [1.17, 2.57] (1.84) | +0.120 [-0.014, +0.332], 1/5 | 3.62 [2.64, 4.44] (3.25) | +0.80 | +0.22 | -1.40 | -11.84 |
| 0.40 m | 845 | 1.68 [1.14, 2.19] (1.68) | -0.047 [-0.219, +0.057], 2/5 | 3.34 [2.18, 4.46] (2.83) | +0.78 | -0.75 | -3.13 | -12.50 |
| 0.50 m | 676 | 1.75 [1.16, 2.28] (1.75) | +0.024 [-0.207, +0.222], 2/5 | 3.48 [2.37, 4.60] (3.01) | +0.78 | -1.43 | -4.34 | -14.00 |
| 0.70 m | 483 | 1.92 [1.20, 2.53] (1.92) | +0.199 [-0.026, +0.468], 2/5 | 3.75 [2.80, 4.75] (3.36) | +0.83 | -1.99 | -5.39 | -12.84 |
| 0.50 src -> 0.33 m | 1024 | 1.71 [1.13, 2.29] (1.71) | -0.014 [-0.047, +0.012], 3/5 | 3.41 [2.31, 4.41] (2.95) | +0.77 | -0.41 | -2.43 | -13.20 |

Lowest MAE: **0.40**; among settings from the native image: 0.40.

## Decision

Rule: change infer_height's default only if the new setting has a lower per-tile mean MAE than the current behaviour in all three cities.

- Resampled native imagery beats native in: 0.30: none; 0.40: DC, PHL; 0.50: DC; 0.70: DC
- Upsampling a 0.5 m source beats feeding it at 0.5 m in: 0.50 src -> 0.33: DC, PHL (MAE difference vs the 0.50 m run, per city: DC -0.075 [-0.157, +0.015], 4/5 tiles better; NYC +0.005 [-0.149, +0.213], 3/5 tiles better; PHL -0.038 [-0.209, +0.159], 3/5 tiles better)
- Settings that pass the rule: none.
