# RS3DAda on DFC19 (200 test tiles)

DFC19 test tiles (512x512, center-cropped to 504 as in evaluation.py), LiDAR nDSM ground truth; fp16 on Apple MPS

## Official metrics (repo utils/metrics.py, per-tile average)

| Subset | Mode | MAE whole (m) | RMSE whole (m) | MAE high >3 m | RMSE high >3 m | F1 (δ<1.25) |
|---|---|---|---|---|---|---|
| ALL (200) | single_pass | 2.30 | 3.94 | 5.04 | 6.36 | 0.46 |
| ALL (200) | tta | 2.22 | 3.83 | 4.90 | 6.20 | 0.47 |
| JAX (100) | single_pass | 2.80 | 4.67 | 5.23 | 6.71 | 0.53 |
| JAX (100) | tta | 2.70 | 4.54 | 5.09 | 6.55 | 0.53 |
| OMA (100) | single_pass | 1.80 | 3.22 | 4.83 | 5.98 | 0.39 |
| OMA (100) | tta | 1.73 | 3.12 | 4.70 | 5.83 | 0.40 |

## By land cover (LiDAR class), pixel-pooled, TTA

| Group | MAE (m) | RMSE (m) | Bias pred−true (m) | Pixels |
|---|---|---|---|---|
| ground | 0.75 | 1.97 | +0.29 | 31,090,589 |
| trees | 4.82 | 6.28 | -3.88 | 8,774,396 |
| buildings | 4.83 | 9.36 | +0.03 | 7,543,237 |
| water | 0.42 | 1.99 | -0.13 | 1,902,102 |
| bridge | 9.37 | 10.59 | -9.36 | 820,123 |

## By true height band, pixel-pooled, TTA

| Group | MAE (m) | RMSE (m) | Bias pred−true (m) | Pixels |
|---|---|---|---|---|
| 0-3 m | 0.67 | 1.67 | +0.49 | 33,575,043 |
| 3-10 m | 3.07 | 4.19 | -1.13 | 10,789,840 |
| 10-20 m | 7.49 | 8.85 | -5.22 | 5,099,000 |
| 20-inf m | 14.22 | 20.55 | -8.02 | 1,339,317 |

## Does the ± (TTA spread) predict real error? Pixels binned by uncertainty

Spearman rank correlation, uncertainty vs absolute error: **0.62**

| Uncertainty quintile | Mean ± (m) | Real MAE (m) | Pixels |
|---|---|---|---|
| 0.00-0.10 m | 0.07 | 0.70 | 10,158,894 |
| 0.10-0.15 m | 0.12 | 0.88 | 10,157,758 |
| 0.15-0.25 m | 0.19 | 1.49 | 10,152,450 |
| 0.25-0.54 m | 0.38 | 2.88 | 10,172,243 |
| 0.54-21.81 m | 1.43 | 5.14 | 10,161,855 |
