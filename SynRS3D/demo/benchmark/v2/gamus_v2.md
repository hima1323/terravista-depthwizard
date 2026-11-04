# GAMUS, evaluation protocol v2

Commands (from `SynRS3D/`; metrics library `demo/eval_v2.py`, self-checks via `--selftest` on both scripts):

```
.venv/bin/python demo/gamus_v2.py --fetch-old45        # once: the 21 old-45 tiles not in the 150 (network)
/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/gamus_v2.py --predict-old45   # once: model
.venv/bin/python demo/gamus_v2.py                       # this report, from cached predictions only (~2 min, no model)
```

**Data source.** GAMUS (Xiong et al. 2023, arXiv:2305.14914, CC-BY-4.0, Hugging Face earthflow/GAMUS): "High-resolution orthophotos, semantic maps, and nDSM (height) are derived and processed from open Data DC catalog and open data in the Philadelphia region"; nDSM = LiDAR DSM minus LiDAR DTM; images "with a resolution of 0.33m". So the images are **aerial orthophotos at 0.33 m GSD, not satellite images**, and the reference is airborne LiDAR. The paper does not name the NYC imagery source or any acquisition dates (leaf state unknown). RS3DAda never saw GAMUS: it was trained on synthetic SynRS3D tiles with unlabeled target images from DFC18, DFC19 JAX/OMA, GeoNRW and Overhead Geopose ARG/ATL only (RS3DAda.sh).

**Test set (frozen in gamus_v2.json).** 150 tiles, 50 per city (DC, NYC, PHL), evenly spaced over the GAMUS test split (`gamus_benchmark.py 50`, `data/GAMUS_bench.txt`); 504x504 centre crop; reference = LiDAR nDSM; -5 m voids excluded, negatives clipped to 0. Cells: **mean over tiles [95% bootstrap CI over tiles] (pooled over pixels)**. TTA prediction unless stated.

## 1. Reproduction of the old headline

The README's 45 tiles are `gamus_benchmark.py 15` (np.linspace, 15 per city, over the 361 DC / 1000 NYC / 1500 PHL test tiles); the cached 150 are `gamus_benchmark.py 50`. 24 of the 45 are among the 150; the other 21 were downloaded and predicted here (MPS fp16; the old run was CUDA fp16). Old code path (official per-tile utils/metrics.py, raw reference with -5 m voids as 0 m).

| Tiles | City | Pass | MAE old → now | RMSE old → now | MAE >3 m old → now | RMSE >3 m old → now |
|---|---|---|---|---|---|---|
| 45 | ALL | tta | 4.01 → 4.01 | 5.90 → 5.90 | 6.71 → 6.71 | 8.08 → 8.08 |
| 45 | ALL | single | 4.05 → 4.05 | 5.97 → 5.97 | 6.78 → 6.78 | 8.18 → 8.18 |
| 45 | DC | tta | 3.82 → 3.82 | 6.15 → 6.15 | 6.72 → 6.72 | 8.43 → 8.43 |
| 45 | DC | single | 3.89 → 3.89 | 6.27 → 6.27 | 6.82 → 6.82 | 8.59 → 8.59 |
| 45 | NYC | tta | 5.60 → 5.60 | 7.39 → 7.39 | 8.23 → 8.23 | 9.40 → 9.40 |
| 45 | NYC | single | 5.66 → 5.66 | 7.48 → 7.48 | 8.35 → 8.35 | 9.53 → 9.53 |
| 45 | PHL | tta | 2.62 → 2.62 | 4.15 → 4.15 | 5.08 → 5.08 | 6.28 → 6.29 |
| 45 | PHL | single | 2.60 → 2.60 | 4.15 → 4.15 | 5.06 → 5.06 | 6.30 → 6.29 |
| 150 | ALL | tta | – → 3.88 | – → 5.56 | – → 6.60 | – → 7.84 |
| 150 | ALL | single | – → 3.94 | – → 5.67 | – → 6.71 | – → 7.99 |
| 150 | DC | tta | – → 5.08 | – → 7.19 | – → 7.93 | – → 9.39 |
| 150 | DC | single | – → 5.16 | – → 7.31 | – → 8.02 | – → 9.52 |
| 150 | NYC | tta | – → 4.69 | – → 6.34 | – → 7.87 | – → 9.14 |
| 150 | NYC | single | – → 4.75 | – → 6.42 | – → 7.96 | – → 9.25 |
| 150 | PHL | tta | – → 1.86 | – → 3.16 | – → 4.12 | – → 5.12 |
| 150 | PHL | single | – → 1.92 | – → 3.29 | – → 4.26 | – → 5.32 |

45 tiles, pixel-pooled TTA, old → now: MAE 4.01 → 4.01, RMSE 7.21 → 7.21, bias -2.58 → -2.58, r 0.664 → 0.664; Spearman spread vs |error| (old method: argsort ranks, 200k random px) 0.56 → 0.56 (tie-aware ranks, all px: 0.56).

150 tiles, same old code path, pixel-pooled TTA: MAE 3.88, RMSE 7.38, bias -2.58, r 0.577; Spearman (old method) 0.58.

**Why 45 and 150 differ.** Same code, crop and model: the old 45-tile numbers are reproduced to within 0.01 m (MPS vs CUDA fp16 does not matter), so alignment is proven. The 150 tiles are a larger, different sample (only 24 tiles shared): overall official MAE 4.01 → 3.88, but per city DC 3.82 → 5.08, NYC 5.60 → 4.69, PHL 2.62 → 1.86, and pooled r 0.66 → 0.58. Fifteen tiles per city is too few to rank cities, hence the per-tile CIs below. v2 also excludes the -5 m no-return voids that the old code scored as 0 m.

## 2. Overall and per city (leave-one-city-out units)

| Set | Tiles | MAE (m) | RMSE (m) | Bias (m) | NMAD (m) | r | within ±2 m | Baseline nDSM=0 MAE |
|---|---|---|---|---|---|---|---|---|
| ALL, TTA | 150 | 3.90 [3.24, 4.66] (3.88) | 5.58 [4.82, 6.40] (7.39) | -2.61 [-3.41, -1.87] (-2.59) | 2.52 [2.09, 3.01] (1.51) | 0.61 [0.57, 0.65] (0.58) | 0.61 [0.57, 0.64] (0.61) | 5.65 [4.88, 6.50] (5.63) |
| ALL, single pass | 150 | 3.96 [3.30, 4.72] (3.95) | 5.69 [4.91, 6.50] (7.50) | -2.66 [-3.46, -1.91] (-2.64) | 2.58 [2.15, 3.08] (1.53) | 0.58 [0.54, 0.62] (0.56) | 0.60 [0.56, 0.64] (0.60) | – |
| DC | 50 | 5.16 [3.77, 6.75] (5.11) | 7.24 [5.81, 8.82] (9.01) | -3.96 [-5.68, -2.49] (-3.91) | 3.10 [2.32, 3.95] (2.25) | 0.59 [0.53, 0.64] (0.51) | 0.54 [0.48, 0.59] (0.54) | 7.22 [5.67, 8.97] (7.18) |
| NYC | 50 | 4.69 [3.49, 5.99] (4.69) | 6.34 [4.98, 7.76] (8.02) | -3.75 [-5.13, -2.49] (-3.75) | 3.38 [2.42, 4.32] (2.14) | 0.51 [0.43, 0.57] (0.43) | 0.55 [0.48, 0.63] (0.55) | 6.21 [4.85, 7.63] (6.21) |
| PHL | 50 | 1.86 [1.44, 2.39] (1.86) | 3.16 [2.45, 4.01] (4.29) | -0.13 [-0.54, 0.22] (-0.13) | 1.10 [0.83, 1.40] (0.71) | 0.73 [0.66, 0.80] (0.82) | 0.73 [0.69, 0.76] (0.73) | 3.51 [2.68, 4.63] (3.51) |

TTA minus single-pass MAE, paired per tile: -0.064 m [-0.101, -0.035]; TTA better on 114 of 150 tiles.

Baseline nDSM = 0 (terrain only, ours = 0 everywhere): r is undefined; its bias = -(mean reference height). Share within ±1 m: ours 0.50, baseline 0.50; within ±2 m: ours 0.61, baseline 0.54 (half the pixels are flat ground, where predicting 0 is already right).

## 3. High (> 3 m) metrics

| Definition | Prediction | MAE (m) | RMSE (m) | Bias (m) | r | Pixels (pooled) |
|---|---|---|---|---|---|---|
| ref or ours > 3 m (utils/metrics.py) | tta | 6.53 [5.80, 7.31] (7.56) | 7.73 [6.95, 8.56] (10.60) | -4.39 [-5.35, -3.55] (-5.60) | 0.26 [0.20, 0.32] (0.38) | 18,372,653 |
| ref or ours > 3 m (utils/metrics.py) | single | 6.64 [5.91, 7.42] (7.67) | 7.88 [7.10, 8.71] (10.75) | -4.46 [-5.40, -3.62] (-5.69) | 0.22 [0.16, 0.28] (0.35) | 18,403,306 |
| ref or ours > 3 m (utils/metrics.py) | zero_baseline | 11.10 [10.15, 12.10] (12.61) | 12.09 [11.02, 13.22] (15.41) | -11.10 [-12.10, -10.15] (-12.61) | – | 16,492,127 |
| ref > 3 m | tta | 6.65 [5.90, 7.44] (7.95) | 7.86 [7.05, 8.70] (11.05) | -5.27 [-6.22, -4.40] (-6.71) | 0.30 [0.25, 0.35] (0.39) | 16,492,127 |
| ref > 3 m | single | 6.78 [6.03, 7.58] (8.08) | 8.03 [7.20, 8.88] (11.21) | -5.39 [-6.36, -4.51] (-6.82) | 0.26 [0.21, 0.31] (0.37) | 16,492,127 |
| ref > 3 m | zero_baseline | 11.10 [10.15, 12.10] (12.61) | 12.09 [11.02, 13.22] (15.41) | -11.10 [-12.10, -10.15] (-12.61) | – | 16,492,127 |

## 4. Per landscape / land-cover class (tiles with >= 500 px of the class)

| Group | Tiles | MAE (m) | Bias (m) | NMAD (m) | r | Baseline MAE | Pixels (pooled) |
|---|---|---|---|---|---|---|---|
| landscape: urban (buildings, roads) | 137 | 2.90 [2.34, 3.63] (2.80) | -1.19 [-1.93, -0.56] (-0.91) | 2.07 [1.66, 2.58] (1.70) | 0.63 [0.57, 0.68] (0.80) | 5.66 [4.79, 6.71] (6.34) | 13,657,475 |
| landscape: forested (trees) | 141 | 6.67 [5.92, 7.45] (10.10) | -5.92 [-6.78, -5.09] (-9.46) | 4.31 [3.94, 4.66] (9.54) | 0.31 [0.27, 0.34] (0.09) | 8.70 [7.86, 9.54] (12.38) | 9,668,143 |
| landscape: sparse / open (ground, low vegetation) | 148 | 0.96 [0.85, 1.09] (0.71) | 0.49 [0.40, 0.60] (0.36) | 0.55 [0.46, 0.65] (0.21) | 0.29 [0.26, 0.31] (0.51) | 0.55 [0.45, 0.66] (0.41) | 12,346,089 |
| landscape: water | 19 | 2.16 [0.68, 3.96] (0.38) | -1.45 [-3.14, -0.06] (0.21) | 2.39 [0.41, 4.70] (0.15) | 0.13 [0.01, 0.23] (0.19) | 2.11 [0.50, 4.13] (0.12) | 719,917 |
| class: ground | 103 | 0.86 [0.71, 1.04] (0.69) | 0.44 [0.29, 0.61] (0.30) | 0.35 [0.28, 0.43] (0.19) | 0.28 [0.24, 0.33] (0.57) | 0.46 [0.33, 0.63] (0.47) | 6,002,001 |
| class: low vegetation | 148 | 1.05 [0.93, 1.18] (0.74) | 0.55 [0.46, 0.66] (0.41) | 0.65 [0.56, 0.73] (0.24) | 0.26 [0.23, 0.29] (0.40) | 0.59 [0.51, 0.69] (0.36) | 6,344,088 |
| class: buildings | 114 | 3.55 [3.02, 4.18] (3.75) | -0.77 [-1.45, -0.14] (-0.83) | 2.81 [2.42, 3.27] (3.40) | 0.54 [0.50, 0.57] (0.78) | 9.08 [7.90, 10.53] (10.24) | 7,467,923 |
| class: water | 19 | 2.16 [0.68, 3.96] (0.38) | -1.45 [-3.14, -0.06] (0.21) | 2.39 [0.41, 4.70] (0.15) | 0.13 [0.01, 0.23] (0.19) | 2.11 [0.50, 4.13] (0.12) | 719,917 |
| class: road | 134 | 1.82 [1.28, 2.50] (1.65) | -1.07 [-1.77, -0.52] (-1.01) | 0.71 [0.49, 1.01] (0.24) | 0.25 [0.21, 0.28] (0.38) | 1.72 [1.16, 2.45] (1.64) | 6,189,552 |
| class: trees | 141 | 6.67 [5.92, 7.45] (10.10) | -5.92 [-6.78, -5.09] (-9.46) | 4.31 [3.94, 4.66] (9.54) | 0.31 [0.27, 0.34] (0.09) | 8.70 [7.86, 9.54] (12.38) | 9,668,143 |
| class: unlabelled (0) | 42 | 1.40 [1.19, 1.63] (1.69) | 0.56 [0.39, 0.75] (0.49) | 0.98 [0.79, 1.18] (1.23) | 0.39 [0.31, 0.47] (0.58) | 1.08 [0.82, 1.35] (1.56) | 1,631,099 |

## 5. Bias by reference height bin

| Bin | Tiles | Bias TTA (m) | MAE TTA (m) | Bias single (m) | Pixels |
|---|---|---|---|---|---|
| 0-3 m | 150 | 0.65 [0.57, 0.74] (0.56) | 0.88 [0.80, 0.97] (0.76) | 0.65 [0.57, 0.74] (0.56) | 21,530,425 |
| 3-10 m | 145 | -1.86 [-2.26, -1.43] (-1.36) | 3.44 [3.20, 3.71] (2.96) | -1.89 [-2.31, -1.44] (-1.42) | 8,482,430 |
| 10-20 m | 134 | -7.62 [-8.37, -6.82] (-8.82) | 8.47 [7.87, 9.05] (9.44) | -7.82 [-8.56, -7.03] (-8.96) | 5,242,702 |
| 20-inf m | 76 | -16.26 [-17.76, -14.64] (-19.09) | 17.19 [15.99, 18.35] (20.44) | -16.56 [-18.12, -14.97] (-19.36) | 2,767,166 |

## 6. Building level (90th percentile height per building)

1,450 buildings = connected components of the reference building class with >= 20 px, in 115 tiles (median 2321 px; terraced rows merge into one component).

| Set | MAE (m) | RMSE (m) | Bias (m) | NMAD (m) | r | within ±2 m |
|---|---|---|---|---|---|---|
| ALL, TTA | 3.57 [3.08, 4.06] (3.21) | 4.35 [3.77, 4.96] (4.75) | -1.37 [-1.99, -0.79] (-1.69) | 2.77 [2.30, 3.33] (3.05) | 0.50 [0.41, 0.58] (0.66) | 0.44 [0.39, 0.49] (0.46) |
| ALL, baseline nDSM=0 | 10.54 [9.17, 12.30] (9.57) | 11.20 [9.78, 12.92] (11.10) | -10.54 [-12.30, -9.17] (-9.57) | 2.78 [2.20, 3.45] (2.62) | – | 0.01 [0.00, 0.02] (0.01) |
| DC | 4.35 [3.62, 5.15] (4.56) | 5.47 [4.57, 6.44] (6.52) | -1.36 [-2.40, -0.21] (-2.78) | 3.68 [2.79, 4.75] (4.20) | 0.38 [0.21, 0.53] (0.57) | 0.40 [0.31, 0.48] (0.38) |
| NYC | 2.87 [2.32, 3.48] (2.67) | 3.33 [2.73, 3.97] (3.61) | -1.87 [-2.71, -1.06] (-1.93) | 1.61 [1.25, 2.01] (2.56) | 0.62 [0.51, 0.73] (0.64) | 0.44 [0.34, 0.55] (0.47) |
| PHL | 3.28 [2.44, 4.28] (2.43) | 3.94 [2.96, 5.12] (3.52) | -1.04 [-2.18, -0.03] (-0.47) | 2.65 [1.80, 3.73] (2.79) | 0.52 [0.38, 0.65] (0.81) | 0.48 [0.41, 0.56] (0.53) |

Pooled over buildings, by reference building height (90th pct):

| Building height | Buildings | Bias (m) | MAE (m) |
|---|---|---|---|
| 0-3 m | 53 | +1.76 | 2.04 |
| 3-10 m | 931 | -0.49 | 1.93 |
| 10-20 m | 409 | -3.91 | 5.13 |
| 20-inf m | 57 | -8.66 | 11.54 |

## 7. Trees: leaf-on vs leaf-off (RGB proxy, judged unreliable)

Proxy: per tile mean ExG = (2G-R-B)/(R+G+B) over reference tree pixels > 3 m; tiles with >= 5000 such px; Otsu threshold on the per-tile values. Threshold -0.029 (Otsu eta = 0.71; 1 = perfectly two-mode). 121 tiles qualify: 79 'proxy-on', 42 'proxy-off'; by city DC 8 on / 41 off, NYC 39 on / 1 off, PHL 32 on / 0 off. Spearman across tiles of tree ExG vs tree bias: 0.66; tree ExG vs grass ExG: 0.81. Histogram (stacked by city): `gamus_v2_exg_hist.png`; spot-checks: `gamus_v2_exg_tiles.png` (lowest / around threshold / highest), `gamus_v2_trees_greenest.png` (canopy crops of the 4 greenest tiles per city).

**Verdict: the proxy is not a reliable leaf-on/leaf-off split; it mostly encodes the city.** Manual spot-check of the contact sheets (Claude reading the PNGs, 2026-10-18): DC and NYC trees are bare in every sampled tile, including the 4 greenest per city (bare crowns with long shadows over brown or green lawns). PHL looks like spring green-up: forest crowns budding (PHL_5262, PHL_5448) and some street/yard trees in leaf (PHL_4465, PHL_4205). ExG also follows each city's colour balance (DC brown, NYC blue-grey) and lawn green-up (tree vs grass ExG rho above). So 'proxy-off' is in effect DC, and the across-tile ExG-vs-bias rho shrinks within each city (confound table). PHL trees are also much shorter in the reference, so its better tree score cannot be credited to foliage alone. Fair statement: GAMUS tree numbers are mostly leaf-off / early-spring trees seen in RGB, the hardest case for single-image height, and do not measure leaf-on canopy.

| Tree pixels (class 6) in | Tiles | MAE (m) | Bias (m) | NMAD (m) | r | Pixels (pooled) |
|---|---|---|---|---|---|---|
| all tiles | 141 | 6.67 [5.92, 7.45] (10.10) | -5.92 [-6.78, -5.09] (-9.46) | 4.31 [3.94, 4.66] (9.54) | 0.31 [0.27, 0.34] (0.09) | 9,668,143 |
| tree tiles | 121 | 7.34 [6.55, 8.25] (10.17) | -6.53 [-7.55, -5.64] (-9.53) | 4.72 [4.37, 5.08] (9.55) | 0.34 [0.30, 0.37] (0.08) | 9,580,914 |
| proxy on | 79 | 6.05 [5.23, 6.90] (8.46) | -4.87 [-5.90, -3.87] (-7.51) | 4.60 [4.15, 5.07] (9.43) | 0.33 [0.29, 0.36] (0.06) | 6,187,852 |
| proxy off | 42 | 9.77 [8.36, 11.41] (13.27) | -9.65 [-11.31, -8.19] (-13.20) | 4.93 [4.39, 5.47] (9.55) | 0.35 [0.29, 0.40] (0.12) | 3,393,062 |
| DC, proxy on | 8 | 7.33 [5.68, 8.73] (8.20) | -7.27 [-8.71, -5.57] (-8.15) | 4.19 [3.05, 5.32] (5.16) | 0.49 [0.41, 0.57] (0.51) | 389,236 |
| DC, proxy off | 41 | 9.63 [8.21, 11.22] (13.08) | -9.51 [-11.11, -8.08] (-13.02) | 4.91 [4.39, 5.48] (9.07) | 0.35 [0.29, 0.41] (0.12) | 3,139,046 |
| NYC, proxy on | 39 | 8.59 [7.50, 9.84] (10.50) | -7.95 [-9.26, -6.79] (-9.96) | 6.13 [5.64, 6.64] (9.41) | 0.27 [0.23, 0.31] (0.12) | 4,266,579 |
| NYC, proxy off | 1 | 15.62 (15.62) | -15.42 (-15.42) | 5.41 (5.41) | 0.09 (0.09) | 254,016 |
| PHL, proxy on | 32 | 2.64 [2.38, 2.90] (2.86) | -0.51 [-1.06, 0.05] (-0.55) | 2.84 [2.62, 3.08] (3.20) | 0.36 [0.30, 0.42] (0.19) | 1,532,037 |

Confound check, pooled over canopy pixels (class 6, ref > 3 m) of the qualifying tiles:

| Group | Tiles | Mean reference canopy height (m) | Mean ours / mean reference | Within-city Spearman ExG vs tree bias |
|---|---|---|---|---|
| proxy_on | 79 | 13.1 | 0.23 | – |
| proxy_off | 42 | 16.3 | 0.19 | – |
| DC | 49 | 15.7 | 0.20 | 0.17 |
| NYC | 40 | 14.9 | 0.18 | 0.45 |
| PHL | 32 | 6.6 | 0.60 | 0.23 |

## 8. Uncertainty (4-flip spread) as a ranking of |error|

| Pixels | Tiles | Spearman rho, mean over tiles [CI] | Pooled |
|---|---|---|---|
| all pixels | 150 | 0.44 [0.40, 0.47] | 0.58 |
| high (ref or ours > 3 m) | 145 | -0.03 [-0.06, 0.01] | -0.10 |
| high (ref > 3 m) | 145 | -0.03 [-0.06, 0.01] | -0.11 |
| flat (ref and ours < 1 m) | 150 | 0.31 [0.29, 0.33] | 0.29 |
| class: ground | 103 | 0.47 [0.43, 0.51] | 0.52 |
| class: low vegetation | 148 | 0.42 [0.39, 0.45] | 0.52 |
| class: buildings | 114 | 0.11 [0.08, 0.15] | 0.30 |
| class: water | 19 | 0.19 [0.11, 0.27] | 0.25 |
| class: road | 134 | 0.37 [0.34, 0.40] | 0.49 |
| class: trees | 141 | 0.03 [0.00, 0.05] | -0.01 |

## How to word it

Say: "On 150 held-out GAMUS tiles (Washington DC, New York, Philadelphia; 0.33 m aerial orthophotos with an airborne-LiDAR reference, never seen in training), height above ground from a single RGB image has a mean per-tile MAE of 3.9 m (95% CI 3.2-4.7), against 5.6 m for a flat-ground (nDSM = 0) baseline. Building heights (90th percentile per building, 1,450 buildings) have MAE 3.6 m (95% CI 3.1-4.1), bias -1.4 m. Tall objects are under-estimated: on pixels above 3 m the bias is -5.3 m and growing with height; leaf-off trees are the weakest class (MAE 6.7 m)." Do not call GAMUS a satellite test: it is aerial imagery at 0.33 m GSD, about as sharp as pan-sharpened Cartosat-3 (~0.25-0.3 m) and much finer than other ISRO RGB, with aerial (not satellite) viewing geometry, haze and MTF; a satellite claim needs a satellite test set (Overhead Geopose / WorldView, plan step 5). Lead with per-tile MAE/NMAD and CIs, not pooled r (pooled r mixes flat ground and towers). Call the 4-flip spread a 'consistency score': its rank correlation with |error| is 0.44 per tile overall but -0.03 on pixels where LiDAR or the model is above 3 m (-0.03 where LiDAR is above 3 m) and +0.03 on trees, so it flags errors on flat ground and edges, not on the tall objects where the big errors are; it is not an error bar.
