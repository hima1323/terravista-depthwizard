# RS3DAda on GAMUS (LiDAR ground truth)

GAMUS test split (Hugging Face earthflow/GAMUS), evenly spaced tiles per city, 504x504 centre crop, LiDAR nDSM ground truth, official utils/metrics.py; fp16 on CUDA GPU.

| Tiles | Pass | MAE whole (m) | RMSE whole (m) | MAE >3 m (m) | RMSE >3 m (m) |
|---|---|---|---|---|---|
| ALL (45) | single pass | 4.05 | 5.97 | 6.78 | 8.18 |
| ALL (45) | tta | 4.01 | 5.90 | 6.71 | 8.08 |
| DC (15) | single pass | 3.89 | 6.27 | 6.82 | 8.59 |
| DC (15) | tta | 3.82 | 6.15 | 6.72 | 8.43 |
| NYC (15) | single pass | 5.66 | 7.48 | 8.35 | 9.53 |
| NYC (15) | tta | 5.60 | 7.39 | 8.23 | 9.40 |
| PHL (15) | single pass | 2.60 | 4.15 | 5.06 | 6.30 |
| PHL (15) | tta | 2.62 | 4.15 | 5.08 | 6.28 |

Pixel-pooled, TTA prediction (r = Pearson correlation with the LiDAR heights):

| Group | MAE (m) | RMSE (m) | Bias (m) | r | Pixels |
|---|---|---|---|---|---|
| all pixels | 4.01 | 7.21 | -2.58 | 0.664 | 11,430,720 |
| urban (buildings, roads) | 2.83 | 5.57 | -0.57 | 0.852 | 4,445,048 |
| forested (trees) | 8.96 | 11.37 | -8.46 | 0.232 | 3,358,587 |
| sparse / open (ground, low vegetation) | 0.82 | 2.54 | +0.43 | 0.573 | 2,987,935 |
| water | 0.61 | 1.96 | +0.01 | 0.436 | 70,832 |
| ground | 0.73 | 2.94 | +0.41 | 0.617 | 1,479,655 |
| low vegetation | 0.90 | 2.09 | +0.44 | 0.485 | 1,508,280 |
| buildings | 3.93 | 6.75 | -0.28 | 0.836 | 2,400,658 |
| water | 0.61 | 1.96 | +0.01 | 0.436 | 70,832 |
| road | 1.55 | 3.73 | -0.92 | 0.553 | 2,044,390 |
| trees | 8.96 | 11.37 | -8.46 | 0.232 | 3,358,587 |
| 0-3 m | 0.78 | 1.81 | +0.53 | 0.281 | 5,992,794 |
| 3-10 m | 3.26 | 4.51 | -1.37 | 0.189 | 2,982,021 |
| 10-20 m | 10.41 | 11.33 | -9.76 | -0.064 | 1,622,872 |
| 20-inf m | 17.52 | 19.15 | -15.31 | 0.776 | 833,033 |

Uncertainty (± = spread of the 4 flips) vs real error, Spearman rank correlation: 0.56
