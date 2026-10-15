# Accuracy by landscape type vs NASA ICESat-2 (Indian scenes)

Each scene: the ~0.5 km window with the most ICESat-2 laser photons near the region, Esri World Imagery (~0.5 m pixels), processed by the app; photons from all passes 2018–now via SlideRule. Heights in m above sea level (EGM2008). Surface = our DSM vs all photons (after the app levelled its terrain to the ground photons). Terrain = our ground model vs ground photons before that levelling (independent).

## Pooled surface accuracy per landscape type

Up to 2,500 photons per scene. r is computed after removing each scene mean height, so it measures agreement within scenes; in hilly scenes it is high largely because the hillsides themselves vary by tens of metres.

| Landscape | Photons | MAE (m) | RMSE (m) | Bias (m) | NMAD (m) | r (within scenes) |
|---|---|---|---|---|---|---|
| urban | 2,863 | 5.33 | 6.32 | -1.49 | 7.29 | 0.514 |
| sparse | 5,000 | 2.06 | 2.96 | +1.19 | 2.05 | 0.473 |
| hilly | 3,671 | 6.93 | 8.87 | -1.14 | 8.61 | 0.976 |
| forested | 1,893 | 10.54 | 16.47 | -6.04 | 10.17 | 0.801 |
| all | 13,427 | 5.28 | 8.46 | -1.04 | 4.94 | 0.932 |

## Per scene

| Scene | Landscape | Photons (ground) | Passes | Surface MAE / RMSE / bias / r | Terrain before levelling: median / NMAD / MAE |
|---|---|---|---|---|---|
| chandigarh sector17 | urban | 576 (155) | 2 | 7.26 / 8.33 / -5.18 / 0.67 | +1.89 / 0.60 / 5.01 |
| delhi karol bagh | urban | 2287 (692) | 10 | 4.84 / 5.70 / -0.56 / 0.54 | +1.96 / 1.98 / 3.31 |
| barmer desert village | sparse | 8832 (3502) | 10 | 3.07 / 3.89 / +1.57 / 0.52 | -0.12 / 0.61 / 2.08 |
| anantapur dryland | sparse | 3381 (2921) | 4 | 1.04 / 1.53 / +0.77 / -0.70 | -1.31 / 0.56 / 1.44 |
| shimla hills | hilly | 3091 (696) | 8 | 7.00 / 8.83 / -1.13 / 0.98 | +4.76 / 7.33 / 6.62 |
| gangtok hills | hilly | 1171 (493) | 6 | 6.76 / 8.95 / -1.46 / 0.88 | +9.43 / 2.79 / 10.04 |
| agumbe western ghats | forested | 746 (517) | 2 | 2.89 / 4.04 / +0.50 / 0.52 | +2.29 / 0.82 / 2.67 |
| silent valley forest | forested | 1147 (774) | 2 | 15.51 / 20.91 / -10.29 / 0.86 | +46.58 / 7.66 / 41.27 |

Laser footprints are ~11 m wide, so photons on roof edges and in tree crowns mix heights; NMAD and the median are robust to that. The imagery and the laser passes are from different dates.
