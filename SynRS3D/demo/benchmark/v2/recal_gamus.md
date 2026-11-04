# Class-wise isotonic recalibration on GAMUS, leave-one-city-out (plan step 6b)

Command (from `SynRS3D/`):

```
.venv/bin/python demo/recalibration.py        # needs demo/uncertainty_calibration.py --predict (land-cover cache)
.venv/bin/python demo/recalibration.py --selftest
```

Data: the 150 frozen GAMUS tiles (demo/gamus_v2.py), 504x504 centre crop, 4-flip TTA, predicted land cover from the same
batch (demo/benchmark/v2/cache/gamus_lc). Fit: every finite pixel of the predicted class in the two training cities,
binned at 0.1 m of predicted height; scipy.optimize.isotonic_regression (L2, increasing) on the bin means weighted by
pixel counts ('isotonic_mean', primary). Secondary, reported only: the same on bin medians ('isotonic_median').
The curve is applied with infer_height.correct_heights (method 'curve': linear between knots, beyond the last knot the
last ratio). Scored on the held-out city with demo/eval_v2.py (mean over tiles [95% CI] (pooled)).
Ship rule (fixed before running): held-out per-tile mean MAE lower AND |per-tile mean bias| lower in the 10-20 m and
>20 m reference bins, in all three folds, for the primary variant. Only then calibration/recal.json is written.

**Ship rule** (fixed before running): held-out per-tile mean MAE lower AND |bias| lower in the 10-20 m and >20 m reference bins, in all three folds, primary variant (isotonic_mean). **Result: NOT shipped** (secondary isotonic_median would also fail; post-hoc buildings-only variant would also fail).

Cells: mean over held-out tiles [95% bootstrap CI] (pooled).

## Findings

- Held-out MAE raw -> isotonic_mean: DC 5.16 -> 4.44, NYC 4.69 -> 3.94, PHL 1.86 -> 2.87. It helps on DC and NYC and hurts PHL, so the rule fails.
- Most of the DC / NYC gain comes from trees: fitted on the leaf-off cities, the tree curve maps a 1 m tree prediction to 11.3 m (fit on DC + NYC); on leaf-on PHL that raises predicted-tree MAE 2.31 -> 9.50 m. The curve learns the leaf-off failure, not the model.
- The building curve is close to the identity (20 m predicted -> 21.1, 19.5, 18.1 m): E[reference | prediction] is already about right for predicted buildings, so recalibrating predicted heights cannot remove the bias seen per REFERENCE height bin (regression dilution: the tallest buildings are predicted lower than their true height, and the curve only sees the prediction).
- The post-hoc buildings-only variant therefore changes little and also fails. Nothing is shipped.

## Held-out DC (fitted on NYC + PHL)

| Variant | MAE | RMSE | Bias | High MAE (ref > 3 m) | High MAE (official union) | Building p90 MAE | Pred. building px MAE | Pred. tree px MAE | Rule |
|---|---|---|---|---|---|---|---|---|---|
| raw | 5.16 [3.77, 6.75] (5.11) | 7.24 [5.81, 8.82] (9.01) | -3.96 [-5.68, -2.49] (-3.91) | 8.07 [6.78, 9.53] (9.53) | 7.94 [6.65, 9.39] (9.25) | 4.35 [3.62, 5.15] (4.56) | 3.48 [2.83, 4.18] (4.03) | 7.80 [6.50, 9.31] (10.81) |  |
| isotonic_mean | 4.44 [3.40, 5.60] (4.41) | 6.32 [5.18, 7.54] (7.57) | -1.93 [-3.30, -0.78] (-1.89) | 6.41 [5.39, 7.56] (7.45) | 6.72 [5.76, 7.79] (7.50) | 4.24 [3.34, 5.35] (3.89) | 3.69 [2.97, 4.53] (4.32) | 6.34 [5.45, 7.35] (8.31) | pass |
| isotonic_median | 4.62 [3.48, 5.91] (4.59) | 6.59 [5.34, 7.93] (8.02) | -2.65 [-4.12, -1.39] (-2.60) | 6.91 [5.79, 8.17] (8.08) | 7.01 [5.93, 8.22] (7.93) | 4.38 [3.41, 5.63] (4.25) | 3.65 [2.93, 4.52] (4.31) | 6.49 [5.47, 7.70] (8.91) | pass |
| isotonic_mean_buildings_only (post hoc) | 5.22 [3.84, 6.79] (5.17) | 7.39 [5.95, 8.98] (9.14) | -3.74 [-5.50, -2.22] (-3.69) | 8.19 [6.88, 9.66] (9.64) | 8.09 [6.80, 9.54] (9.39) | 4.75 [3.81, 5.89] (4.66) | 3.69 [2.97, 4.53] (4.32) | 7.80 [6.50, 9.31] (10.81) | fail: MAE |

Bias by reference height bin (tiles with >= 500 px in the bin):

| Variant | 0-3 m | 3-10 m | 10-20 m | 20-inf m |
|---|---|---|---|---|
| raw | 0.46 [0.35, 0.58] (0.43) | -2.59 [-3.05, -2.12] (-2.19) | -8.32 [-9.34, -7.16] (-8.50) | -15.68 [-18.16, -12.81] (-19.78) |
| isotonic_mean | 1.50 [1.18, 1.85] (1.13) | -0.33 [-0.76, 0.09] (-0.06) | -4.84 [-5.75, -3.72] (-5.00) | -11.18 [-13.60, -8.33] (-14.27) |
| isotonic_median | 1.08 [0.85, 1.34] (0.82) | -1.22 [-1.62, -0.82] (-0.92) | -6.12 [-7.10, -4.94] (-6.30) | -12.58 [-15.20, -9.52] (-15.62) |
| isotonic_mean_buildings_only (post hoc) | 0.48 [0.37, 0.61] (0.45) | -2.46 [-2.95, -1.96] (-2.05) | -8.01 [-9.19, -6.55] (-8.20) | -14.83 [-17.75, -11.44] (-18.57) |

Primary curve, predicted buildings: 1 m -> 1.1, 3 m -> 2.8, 5 m -> 5.4, 10 m -> 10.3, 15 m -> 14.8, 20 m -> 21.1, 30 m -> 34.8.
Primary curve, predicted trees: 1 m -> 9.4, 3 m -> 9.5, 5 m -> 9.5, 10 m -> 11.0, 15 m -> 11.0.

## Held-out NYC (fitted on DC + PHL)

| Variant | MAE | RMSE | Bias | High MAE (ref > 3 m) | High MAE (official union) | Building p90 MAE | Pred. building px MAE | Pred. tree px MAE | Rule |
|---|---|---|---|---|---|---|---|---|---|
| raw | 4.69 [3.49, 5.99] (4.69) | 6.34 [4.98, 7.76] (8.02) | -3.75 [-5.13, -2.49] (-3.75) | 7.89 [6.63, 9.24] (9.18) | 7.56 [6.28, 8.88] (8.66) | 2.87 [2.32, 3.48] (2.67) | 2.52 [2.02, 3.03] (2.93) | 7.22 [6.03, 8.50] (9.68) |  |
| isotonic_mean | 3.94 [3.16, 4.76] (3.94) | 5.30 [4.44, 6.20] (6.13) | -1.02 [-1.83, -0.29] (-1.02) | 5.33 [4.60, 6.09] (5.98) | 5.98 [5.29, 6.64] (6.44) | 2.84 [2.30, 3.42] (2.69) | 2.64 [2.14, 3.17] (3.03) | 6.71 [6.15, 7.26] (7.54) | pass |
| isotonic_median | 4.10 [3.16, 5.12] (4.10) | 5.48 [4.43, 6.60] (6.67) | -2.26 [-3.30, -1.34] (-2.26) | 6.18 [5.26, 7.18] (7.12) | 6.17 [5.34, 6.98] (6.92) | 2.94 [2.37, 3.55] (2.73) | 2.52 [1.95, 3.12] (3.02) | 6.36 [5.54, 7.22] (8.01) | pass |
| isotonic_mean_buildings_only (post hoc) | 4.71 [3.51, 6.01] (4.71) | 6.37 [5.00, 7.81] (8.04) | -3.74 [-5.12, -2.50] (-3.74) | 7.89 [6.64, 9.26] (9.19) | 7.58 [6.27, 8.88] (8.66) | 2.82 [2.23, 3.46] (2.60) | 2.64 [2.14, 3.17] (3.03) | 7.22 [6.03, 8.50] (9.68) | fail: MAE, 10-20 m, 20-inf m |

Bias by reference height bin (tiles with >= 500 px in the bin):

| Variant | 0-3 m | 3-10 m | 10-20 m | 20-inf m |
|---|---|---|---|---|
| raw | 0.81 [0.66, 0.95] (0.63) | -2.98 [-3.54, -2.47] (-2.09) | -9.89 [-10.89, -8.83] (-10.64) | -17.03 [-18.66, -15.27] (-19.33) |
| isotonic_mean | 2.99 [2.34, 3.65] (2.03) | 0.39 [-0.10, 0.85] (0.55) | -5.31 [-5.80, -4.84] (-5.58) | -11.56 [-12.57, -10.48] (-13.27) |
| isotonic_median | 1.90 [1.49, 2.31] (1.30) | -1.08 [-1.48, -0.72] (-0.60) | -7.26 [-7.88, -6.66] (-7.75) | -13.64 [-14.86, -12.36] (-15.87) |
| isotonic_mean_buildings_only (post hoc) | 0.85 [0.69, 1.00] (0.67) | -2.91 [-3.48, -2.39] (-2.02) | -10.01 [-10.96, -9.01] (-10.75) | -17.11 [-18.71, -15.37] (-19.43) |

Primary curve, predicted buildings: 1 m -> 1.5, 3 m -> 3.2, 5 m -> 5.4, 10 m -> 9.2, 15 m -> 13.0, 20 m -> 19.5, 30 m -> 33.9.
Primary curve, predicted trees: 1 m -> 9.4, 3 m -> 10.4, 5 m -> 10.9, 10 m -> 15.1, 15 m -> 23.4.

## Held-out PHL (fitted on DC + NYC)

| Variant | MAE | RMSE | Bias | High MAE (ref > 3 m) | High MAE (official union) | Building p90 MAE | Pred. building px MAE | Pred. tree px MAE | Rule |
|---|---|---|---|---|---|---|---|---|---|
| raw | 1.86 [1.44, 2.39] (1.86) | 3.16 [2.45, 4.01] (4.29) | -0.13 [-0.54, 0.22] (-0.13) | 4.07 [3.14, 5.06] (3.95) | 4.14 [3.29, 5.04] (3.98) | 3.28 [2.44, 4.28] (2.43) | 3.32 [2.34, 4.58] (3.18) | 2.31 [2.07, 2.55] (2.68) |  |
| isotonic_mean | 2.87 [2.28, 3.57] (2.87) | 4.69 [3.82, 5.71] (5.78) | 1.11 [0.55, 1.67] (1.11) | 5.11 [4.07, 6.25] (4.84) | 5.96 [4.99, 7.01] (5.94) | 4.55 [2.79, 6.95] (2.89) | 3.67 [2.54, 5.12] (3.54) | 9.50 [9.10, 9.87] (9.73) | fail: MAE, 20-inf m |
| isotonic_median | 2.68 [2.12, 3.34] (2.68) | 4.49 [3.66, 5.46] (5.55) | 0.81 [0.30, 1.33] (0.81) | 5.01 [3.98, 6.11] (4.71) | 5.75 [4.79, 6.76] (5.74) | 4.50 [2.82, 6.74] (2.89) | 3.47 [2.36, 4.87] (3.29) | 8.60 [8.16, 9.01] (8.97) | fail: MAE, 20-inf m |
| isotonic_mean_buildings_only (post hoc) | 1.99 [1.51, 2.60] (1.99) | 3.35 [2.54, 4.34] (4.70) | -0.04 [-0.60, 0.41] (-0.04) | 4.28 [3.23, 5.42] (4.20) | 4.37 [3.42, 5.41] (4.24) | 4.39 [2.63, 6.84] (2.65) | 3.67 [2.54, 5.12] (3.54) | 2.31 [2.07, 2.55] (2.68) | fail: MAE, 20-inf m |

Bias by reference height bin (tiles with >= 500 px in the bin):

| Variant | 0-3 m | 3-10 m | 10-20 m | 20-inf m |
|---|---|---|---|---|
| raw | 0.68 [0.52, 0.84] (0.61) | -0.05 [-0.75, 0.74] (-0.14) | -4.34 [-5.73, -2.84] (-4.00) | -15.86 [-20.99, -10.44] (-13.95) |
| isotonic_mean | 1.83 [1.42, 2.30] (1.71) | 2.51 [1.76, 3.28] (2.11) | -1.63 [-2.94, -0.24] (-2.27) | -17.51 [-22.29, -12.37] (-23.51) |
| isotonic_median | 1.55 [1.16, 1.98] (1.45) | 2.03 [1.26, 2.84] (1.61) | -1.93 [-3.27, -0.45] (-2.67) | -17.46 [-22.06, -12.42] (-22.08) |
| isotonic_mean_buildings_only (post hoc) | 0.78 [0.61, 0.96] (0.70) | 0.49 [-0.20, 1.25] (0.51) | -3.76 [-5.26, -2.17] (-3.33) | -18.22 [-22.96, -12.94] (-23.70) |

Primary curve, predicted buildings: 1 m -> 1.6, 3 m -> 3.2, 5 m -> 6.0, 10 m -> 11.1, 15 m -> 15.0, 20 m -> 18.1, 30 m -> 31.7.
Primary curve, predicted trees: 1 m -> 11.3, 3 m -> 12.3, 5 m -> 13.7, 10 m -> 17.3, 15 m -> 23.7.

## India transfer check (plan step 6c): ICESat-2 photons inside OSM building footprints

App scenes in `demo/results` with an ICESat-2 photon cache (bengaluru_electronic_city, chandigarh_sector17, delhi_central, iit_ropar, mumbai_highrise, shimla_hill_town) plus the india_eval_v2 scenes with predictions (demo/benchmark/v2/scenes, read only). Per OSM building with >= 3 photons inside: reference = median photon height inside - ground, ground = median ATL08 ground photon outside all footprints within 75 m carried to the building along our DTM's slope (fallback: our DTM + geoid undulation); ours = median predicted nDSM at those photon pixels. Curve: GAMUS isotonic_mean fitted on all three cities (NOT shipped; diagnostic). Units = scenes. **96 buildings: >= 30 buildings (the step-6c threshold), but few scenes: see CIs.**

| Scene | OSM buildings | Photons in scene | Roof photons in OSM | Ground photons outside OSM | Buildings with photons |
|---|---|---|---|---|---|
| bengaluru_electronic_city | 59 | 2627 | 803 | 763 | 16 |
| chandigarh_sector17 | 233 | 576 | 358 | 113 | 6 |
| delhi_central | 87 | 866 | 178 | 237 | 8 |
| iit_ropar | 19 | 690 | 20 | 471 | 1 |
| mumbai_highrise | 53 | 964 | 133 | 384 | 10 |
| shimla_hill_town | 331 | 163 | 48 | 25 | 4 |
| agumbe_western_ghats | 3 | 746 | 0 | 517 | 0 |
| anantapur_dryland | 5 | 3381 | 0 | 2921 | 0 |
| barmer_desert_village | 1 | 8832 | 0 | 3502 | 0 |
| delhi_karol_bagh | 175 | 2287 | 756 | 558 | 23 |
| gangtok_hills | 10 | 1171 | 0 | 493 | 0 |
| shimla_hills | 185 | 3091 | 694 | 528 | 28 |
| silent_valley_forest | 0 | 1147 | 0 | 774 | 0 |

| Model height | MAE | Bias | NMAD | r |
|---|---|---|---|---|
| raw, at roof photons | 5.28 [4.06, 6.59] (4.63) | -0.89 [-3.25, 1.88] (-1.69) | 5.18 [3.26, 7.10] (4.86) | 0.48 [0.11, 0.74] (0.68) |
| GAMUS curve, at roof photons | 5.16 [4.03, 6.35] (4.54) | 0.03 [-2.27, 2.57] (-0.29) | 5.12 [3.17, 7.00] (5.34) | 0.42 [0.04, 0.71] (0.63) |
| raw, footprint median | 6.30 [4.37, 8.64] (4.91) | -0.23 [-3.16, 3.87] (-1.69) | 5.19 [3.16, 7.35] (5.07) | 0.26 [-0.13, 0.60] (0.61) |

Calibrated building interval (calibration/conformal.json, footprint median and median spread as the block values) against the photon roof height: 68%: coverage 46% of 96 buildings (scene mean 38%, mean width 7.3 m); 90%: coverage 71% of 96 buildings (scene mean 57%, mean width 14.1 m); 95%: coverage 84% of 96 buildings (scene mean 82%, mean width 18.1 m). Caveat: this uses OSM footprints and the median roof photon, while the GAMUS calibration used the app's blocks and the LiDAR 90th percentile inside each block, so the reference definitions differ.

Pooled bias by reference (photon) height: 0-3 m: n 9, raw +4.95, curve +6.27; 3-10 m: n 33, raw +0.07, curve +1.55; 10-20 m: n 41, raw -4.73, curve -3.42; 20-inf m: n 5, raw -13.65, curve -13.21

## Context

DFC19 (demo/benchmark/correction.md): curve and linear height-only corrections also failed the MAE rule there; DFC19 is inside RS3DAda's adaptation domain (Target Domain 1), GAMUS is not.
