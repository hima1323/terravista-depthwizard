# Height correction on DFC19: learned on training tiles, measured on untouched test tiles

200 training tiles, 200 test tiles; official metric (utils/metrics.py), TTA predictions. Land-cover variants skipped (land cover not cached for every tile).

Shipped: **none** (must lower MAE in all three splits).

| Split (learn → test) | Method | MAE whole | RMSE whole | MAE >3 m | RMSE >3 m | Bias 10–20 m | Bias >20 m |
|---|---|---|---|---|---|---|---|
| both cities -> both cities | raw | 2.22 | 3.83 | 4.90 | 6.20 | -5.22 | -8.02 |
| both cities -> both cities | curve, height only | 2.11 | 3.78 | 4.84 | 6.13 | -5.58 | -12.74 |
| both cities -> both cities | linear, height only | 2.25 | 3.87 | 4.91 | 6.21 | -4.51 | -6.48 |
| JAX -> OMA (other city) | raw | 1.73 | 3.12 | 4.70 | 5.83 | -4.57 | -5.03 |
| JAX -> OMA (other city) | curve, height only | 1.73 | 3.25 | 4.98 | 6.12 | -5.02 | -10.02 |
| JAX -> OMA (other city) | linear, height only | 1.82 | 3.26 | 4.88 | 6.01 | -3.57 | -2.12 |
| OMA -> JAX (other city) | raw | 2.70 | 4.54 | 5.09 | 6.55 | -5.49 | -9.29 |
| OMA -> JAX (other city) | curve, height only | 2.73 | 4.69 | 5.14 | 6.66 | -7.24 | -17.25 |
| OMA -> JAX (other city) | linear, height only | 2.87 | 4.72 | 5.12 | 6.51 | -5.65 | -17.82 |
