# Indian landscapes vs NASA ICESat-2 and GEDI: evaluation protocol v2

Same 8 scenes and windows as `landscape_results.md` (two per landscape type), rebuilt on this machine without the app server (`demo/india_eval_v2.py`: fetch_scene, infer_height.predict, terrain.build_dtm, terrain.laser_correct, validate.compare_icesat2 - the functions the app calls). e = ours - reference; heights in m above EGM2008. Footprint sampling: ICESat-2 photon = disc of radius 6 m on our grid (median; 98th percentile for top-of-surface photons), ICESat-2 20 m segment = 10 m, GEDI = 12.5 m; "px" = the single pixel. r is computed after removing a least-squares plane (terrain/surface) or directly on heights above ground (nDSM).

## 1. Old protocol reproduced first (circular: terrain levelled on the same photons it is checked on)

| Scene | Photons old / now | Beam-tracks old / now | Surface MAE / RMSE / bias / r, old | same, rebuilt now | Terrain before levelling median / NMAD, old | same, now |
|---|---|---|---|---|---|---|
| chandigarh sector17 | 576 / 576 | 2 / 2 | 7.26 / 8.33 / -5.18 / 0.67 | 7.24 / 8.31 / -5.16 / 0.67 | +1.89 / 0.60 | +1.89 / 0.60 |
| delhi karol bagh | 2287 / 2287 | 10 / 10 | 4.84 / 5.70 / -0.56 / 0.54 | 4.85 / 5.70 / -0.56 / 0.54 | +1.96 / 1.98 | +1.96 / 1.98 |
| barmer desert village | 8832 / 8832 | 10 / 10 | 3.07 / 3.89 / +1.57 / 0.52 | 3.07 / 3.89 / +1.57 / 0.52 | -0.12 / 0.61 | -0.12 / 0.61 |
| anantapur dryland | 3381 / 3381 | 4 / 4 | 1.04 / 1.53 / +0.77 / -0.70 | 1.04 / 1.53 / +0.77 / -0.70 | -1.31 / 0.56 | -1.31 / 0.56 |
| shimla hills | 3091 / 3091 | 8 / 8 | 7.00 / 8.83 / -1.13 / 0.98 | 7.00 / 8.83 / -1.14 / 0.98 | +4.76 / 7.33 | +4.76 / 7.33 |
| gangtok hills | 1171 / 1171 | 6 / 6 | 6.76 / 8.95 / -1.46 / 0.88 | 6.76 / 8.95 / -1.46 / 0.88 | +9.43 / 2.79 | +9.43 / 2.79 |
| agumbe western ghats | 746 / 746 | 2 / 2 | 2.89 / 4.04 / +0.50 / 0.52 | 2.89 / 4.04 / +0.50 / 0.52 | +2.29 / 0.82 | +2.29 / 0.82 |
| silent valley forest | 1147 / 1147 | 2 / 2 | 15.51 / 20.91 / -10.29 / 0.86 | 15.51 / 20.91 / -10.30 / 0.85 | +46.58 / 7.66 | +46.59 / 7.65 |

"Beam-tracks" is what the old report called passes (rgt + cycle + beam). The old numbers are reproduced on this machine (MPS) within 0.03 m (largest difference 0.023 m), with the same photons, so the rebuild is the same experiment. For Chandigarh this needed today's live Esri image (= Wayback release R09, Vantor 2026-07-03); this machine's older demo sample (Wayback R07, GE01 2025-10-19) gives surface MAE 4.77 m instead of 7.26 m with the same photons and terrain (`india_oldprotocol_check.json`): one image change moves the number by 2.5 m.

## 2. Data per scene

| Scene | Landscape | Image date (source) | Image vs Esri Wayback R07 / R09 / live (mean abs DN diff) | ICESat-2 photons (ground; ground off OSM roofs) | Passes: levelling / validation | Dates | Held-out photons (ground) | Photons within 12 mo of image | GEDI shots: all / quality / power beam | OSM buildings; roof photons (% ATL08 "ground") |
|---|---|---|---|---|---|---|---|---|---|---|
| chandigarh sector17 | urban | 20260703 (Vantor LG02 (Vivid Mosaic Metro, 0.34 m, release Raster Basemaps 2026.R09)) | 32.4 / 0.0 / 0.0 | 576 (155; 113) | 1 / 1 (of 2) | 2020-05-08 to 2024-03-18 | 354 (0) | 0 | 66 / 19 / 18 | 233; 358 (12) |
| delhi karol bagh | urban | 20251023 (Vantor WV02 (Vivid Advanced, 0.5 m, release Raster Basemaps 2026.R03)) | 0.0 / 0.0 / 0.0 | 2,287 (692; 558) | 4 / 3 (of 7) | 2019-11-24 to 2026-01-26 | 1,272 (250) | 260 | 86 / 10 / 10 | 175; 756 (18) |
| barmer desert village | sparse | 20250313 (Vantor WV03 (Vivid, 0.31 m, release Raster Basemaps 2026.R05)) | 0.0 / 0.0 / 0.0 | 8,832 (3,502; 3,502) | 3 / 3 (of 6) | 2020-10-07 to 2025-12-09 | 4,364 (1,595) | 2,219 | 86 / 38 / 24 | 1; 0 (–) |
| anantapur dryland | sparse | 20251231 (Vantor LG01 (Vivid, 0.34 m, release Raster Basemaps 2026.R07)) | 0.0 / 0.0 / 0.0 | 3,381 (2,921; 2,921) | 1 / 1 (of 2) | 2018-10-16 to 2021-01-10 | 493 (493) | 0 | 111 / 38 / 33 | 5; 0 (–) |
| shimla hills | hilly | 20251105 (Vantor LG03 (Vivid, 0.34 m, release Raster Basemaps 2026.R07)) | 0.0 / 0.0 / 0.0 | 3,091 (696; 528) | 3 / 2 (of 5) | 2020-04-24 to 2023-08-30 | 1,543 (209) | 0 | 77 / 45 / 37 | 185; 694 (24) |
| gangtok hills | hilly | 20250927 (Vantor WV03 (Vivid, 0.31 m, release Raster Basemaps 2026.R07)) | 0.0 / 0.0 / 0.0 | 1,171 (493; 493) | 2 / 2 (of 4) | 2022-12-18 to 2025-06-14 | 132 (63) | 58 | 102 / 32 / 32 | 10; 0 (–) |
| agumbe western ghats | forested | 20251019 (Vantor LG02 (Vivid, 0.34 m, release Raster Basemaps 2026.R05)) | 0.0 / 0.0 / 0.0 | 746 (517; 517) | 0 / 0 (of 1) | 2022-09-21 to 2022-09-21 | 0 (0) | 0 | 66 / 0 / 0 | 3; 0 (–) |
| silent valley forest | forested | 20250122 (Vantor LG02 (Vivid, 0.34 m, release Raster Basemaps 2026.R05)) | 0.0 / 0.0 / 0.0 | 1,147 (774; 774) | 0 / 0 (of 1) | 2020-01-17 to 2020-01-17 | 0 (0) | 0 | 81 / 36 / 23 | 0; 0 (–) |

A pass = one ICESat-2 reference ground track in one cycle (all 6 beams). Passes are sorted by time and alternate levelling / validation, starting with whichever phase gives the levelling passes more ground photons (validate.split_passes; never looks at errors); no pass is used for both. Unlevelled products (ours (i), raw GLO-30, FABDEM) fitted nothing to the photons and are checked on every pass; levelled products (ours (ii), levelled baselines, the circular (iii)) only on the validation passes. Single-pass scenes: (i) only.

## 3. Three protocols on the same held-out photons (scenes with 2+ passes)

(i) no levelling, (ii) levelled on the levelling passes only, (iii) circular: levelled on all passes including the validation ones (the old protocol). Footprint sampling. Single-pass scenes: (i) on all photons, (iii) for comparison.

| Scene | Terrain vs ground photons (n): MAE (i) / (ii) / (iii) | median (i) / (ii) / (iii) | NMAD (i) / (ii) | Surface vs all photons (n): MAE (i) / (ii) / (iii) | bias (i) / (ii) / (iii) |
|---|---|---|---|---|---|
| chandigarh sector17 | (0) – / – / – | – / – / – | – / – | (354) 6.58 / 8.65 / 8.47 | -6.58 / -8.65 / -8.47 |
| delhi karol bagh | (250) 1.36 / 1.01 / 0.85 | +1.69 / -0.54 / -0.27 | 0.85 / 0.85 | (1272) 4.91 / 4.97 / 4.94 | +1.24 / -0.99 / -0.72 |
| barmer desert village | (1595) 2.21 / 2.20 / 2.20 | -0.11 / +0.02 / +0.01 | 0.52 / 0.52 | (4364) 2.96 / 3.02 / 3.02 | +1.26 / +1.39 / +1.37 |
| anantapur dryland | (493) 1.49 / 2.96 / 2.80 | +1.70 / +3.17 / +3.01 | 0.19 / 0.19 | (493) 1.67 / 3.15 / 2.98 | +1.67 / +3.15 / +2.98 |
| shimla hills | (209) 5.85 / 4.66 / 4.69 | +4.16 / +0.00 / -0.60 | 4.65 / 4.65 | (1543) 6.95 / 6.12 / 6.15 | +3.30 / -0.86 / -1.46 |
| gangtok hills | (63) 8.38 / 9.26 / 9.26 | +1.31 / -8.15 / -8.12 | 1.92 / 1.92 | (132) 9.07 / 9.42 / 9.41 | +7.89 / -1.56 / -1.53 |
| agumbe western ghats (1 pass) | (517) 2.67 / – / 0.94 | +2.30 / – / +0.01 | 0.82 / – | (746) 3.95 / – / 2.87 | +2.76 / – / +0.47 |
| silent valley forest (1 pass) | (774) 41.32 / – / 9.06 | +46.64 / – / +0.05 | 7.63 / – | (1147) 36.84 / – / 15.53 | +36.37 / – / -10.22 |

## 4. Baselines at the same points (footprint sampling): MAE / bias (n)

### 4a. Terrain vs ICESat-2 ground photons (ATL08 ground, OSM roofs removed)

Unlevelled, all passes: our DTM straight from terrain.build_dtm, raw Copernicus GLO-30 (a DSM), FABDEM (bare earth). Levelled, validation passes only: each shifted by its own median offset to the levelling passes (terrain.laser_offset).

| Scene | ours (i) | GLO-30 | FABDEM | ours (ii) | GLO-30 levelled | FABDEM levelled |
|---|---|---|---|---|---|---|
| chandigarh sector17 | 2.04 / +2.04 (113) | 4.47 / +4.47 (113) | 2.12 / +2.12 (113) | – | – | – |
| delhi karol bagh | 2.68 / +1.75 (558) | 6.09 / +5.81 (558) | 3.49 / +2.78 (558) | 1.01 / -0.99 (250) | 2.32 / +0.78 (250) | 0.63 / -0.33 (250) |
| barmer desert village | 2.08 / -1.76 (3502) | 2.20 / -0.25 (3502) | 2.17 / -2.02 (3502) | 2.20 / -1.83 (1595) | 2.15 / -1.08 (1595) | 2.39 / -2.00 (1595) |
| anantapur dryland | 1.44 / -0.84 (2921) | 1.41 / -0.73 (2921) | 1.46 / -0.78 (2921) | 2.96 / +2.96 (493) | 2.91 / +2.91 (493) | 3.17 / +3.17 (493) |
| shimla hills | 6.80 / +5.42 (528) | 7.10 / +6.55 (528) | 5.26 / +1.96 (528) | 4.66 / -0.42 (209) | 3.61 / +0.07 (209) | 4.60 / +0.83 (209) |
| gangtok hills | 10.04 / +10.03 (493) | 11.31 / +11.24 (493) | 6.22 / +3.58 (493) | 9.26 / -1.09 (63) | 9.94 / -3.39 (63) | 9.90 / -3.73 (63) |
| agumbe western ghats | 2.67 / +2.58 (517) | 2.41 / +2.41 (517) | 3.98 / +3.94 (517) | – | – | – |
| silent valley forest | 41.32 / +41.32 (774) | 39.53 / +39.52 (774) | 35.76 / +35.40 (774) | – | – | – |

### 4b. Surface vs all ICESat-2 photons

| Scene | our DSM (i) | GLO-30 | FABDEM (nDSM = 0) | our DTM only (i) | our DSM (ii) | GLO-30 levelled | our DTM only (ii) |
|---|---|---|---|---|---|---|---|
| chandigarh sector17 | 6.00 / -2.89 (576) | 4.67 / -2.27 (576) | 9.86 / -8.85 (576) | 11.14 / -10.07 (576) | 8.65 / -8.65 (354) | 8.42 / -8.42 (354) | 17.62 / -17.62 (354) |
| delhi karol bagh | 4.94 / +1.41 (2287) | 5.28 / -0.39 (2287) | 6.74 / -4.69 (2287) | 7.32 / -6.02 (2287) | 4.97 / -0.99 (1272) | 7.08 / -6.20 (1272) | 9.19 / -9.18 (1272) |
| barmer desert village | 2.86 / +1.37 (8832) | 3.23 / -2.39 (8832) | 4.26 / -4.20 (8832) | 4.03 / -3.90 (8832) | 3.02 / +1.39 (4364) | 3.42 / -3.01 (4364) | 3.78 / -3.65 (4364) |
| anantapur dryland | 1.34 / -0.55 (3381) | 1.35 / -0.55 (3381) | 1.40 / -0.60 (3381) | 1.37 / -0.67 (3381) | 3.15 / +3.15 (493) | 2.91 / +2.91 (493) | 2.96 / +2.96 (493) |
| shimla hills | 7.65 / +3.65 (3091) | 6.44 / +0.42 (3091) | 8.10 / -4.20 (3091) | 6.95 / -0.78 (3091) | 6.12 / -0.86 (1543) | 6.96 / -5.45 (1543) | 7.28 / -5.37 (1543) |
| gangtok hills | 9.49 / +7.92 (1171) | 9.05 / +6.32 (1171) | 7.60 / -1.70 (1171) | 8.41 / +4.57 (1171) | 9.42 / -1.56 (132) | 10.53 / -6.39 (132) | 10.80 / -5.32 (132) |
| agumbe western ghats | 3.95 / +2.76 (746) | 2.54 / +1.10 (746) | 3.86 / +2.08 (746) | 3.26 / +0.59 (746) | – | – | – |
| silent valley forest | 36.84 / +36.37 (1147) | 31.88 / +31.48 (1147) | 29.97 / +28.01 (1147) | 33.96 / +33.28 (1147) | – | – | – |

### 4c. Terrain vs GEDI ground (elev_lowestmode, 12.5 m footprint median), independent of every ICESat-2 levelling

| Scene | ours (i) | ours (ii) | ours (iii) | GLO-30 | FABDEM |
|---|---|---|---|---|---|
| chandigarh sector17 | 5.97 / -4.01 (19) | 6.09 / -6.07 (19) | 5.94 / -5.90 (19) | 8.04 / -0.46 (19) | 5.96 / -3.84 (19) |
| delhi karol bagh | 3.06 / +2.09 (10) | 1.53 / -0.15 (10) | 1.62 / +0.13 (10) | 7.66 / +7.66 (10) | 2.55 / +2.43 (10) |
| barmer desert village | 1.51 / -0.60 (38) | 1.50 / -0.47 (38) | 1.50 / -0.49 (38) | 1.46 / +0.46 (38) | 1.54 / -0.92 (38) |
| anantapur dryland | 1.34 / -0.59 (38) | 1.56 / +0.88 (38) | 1.50 / +0.72 (38) | 1.59 / -0.08 (38) | 1.77 / -1.46 (38) |
| shimla hills | 13.47 / +12.40 (45) | 11.32 / +8.24 (45) | 11.09 / +7.64 (45) | 13.85 / +13.04 (45) | 11.32 / +8.57 (45) |
| gangtok hills | 9.93 / +7.31 (32) | 9.20 / -2.14 (32) | 9.19 / -2.11 (32) | 10.60 / +10.21 (32) | 7.97 / +1.76 (32) |
| agumbe western ghats | – | – | – | – | – |
| silent valley forest | 18.45 / +17.46 (36) | – | 29.13 / -29.13 (36) | 20.94 / +19.95 (36) | 15.23 / +12.12 (36) |

CartoDEM v3 R1 is not included: it is behind a Bhuvan login (section 10).

## 5. Error budget per scene

(a) DTM vs ground; (b) nDSM vs laser-only height above ground (no DEM involved, all passes; p98 over the footprint); (c) DSM vs all photons and vs top-of-surface photons (ATL08 top of canopy or OSM roof; p98 over the footprint). MAE / bias, n in brackets; (i) = all passes, (ii) = held-out passes.

| Scene | (a) ICESat-2 ground (i) | (a) ICESat-2 ground (ii) | (a) GEDI ground (i) | (b) ICESat-2 segments, r | (b) GEDI rh98, r | (c) all photons (i) | (c) all photons (ii) | (c) top photons (i) | (c) GEDI top (i) |
|---|---|---|---|---|---|---|---|---|---|
| chandigarh sector17 | 2.04 / +2.04 (113) | – | 5.97 / -4.01 (19) | 3.78 / -1.85 (19), 0.70 | 5.67 / -3.48 (19), 0.11 | 6.00 / -2.89 (576) | 8.65 / -8.65 (354) | 3.51 / -2.98 (387) | 8.49 / -7.48 (19) |
| delhi karol bagh | 2.68 / +1.75 (558) | 1.01 / -0.99 (250) | 3.06 / +2.09 (10) | 5.20 / -0.54 (69), 0.41 | 5.63 / -4.52 (10), 0.09 | 4.94 / +1.41 (2287) | 4.97 / -0.99 (1272) | 4.01 / +0.57 (1115) | 3.70 / -2.44 (10) |
| barmer desert village | 2.08 / -1.76 (3502) | 2.20 / -1.83 (1595) | 1.51 / -0.60 (38) | 2.88 / +1.49 (242), 0.48 | 2.95 / +0.34 (38), 0.51 | 2.86 / +1.37 (8832) | 3.02 / +1.39 (4364) | 3.45 / +2.83 (3153) | 2.25 / -0.26 (38) |
| anantapur dryland | 1.44 / -0.84 (2921) | 2.96 / +2.96 (493) | 1.34 / -0.59 (38) | 0.24 / +0.20 (58), 0.06 | 2.81 / -0.88 (38), 0.65 | 1.34 / -0.55 (3381) | 3.15 / +3.15 (493) | 1.20 / +1.20 (270) | 3.14 / -1.45 (38) |
| shimla hills | 6.80 / +5.42 (528) | 4.66 / -0.42 (209) | 13.47 / +12.40 (45) | 9.55 / -7.50 (105), 0.16 | 18.96 / -18.76 (45), 0.27 | 7.65 / +3.65 (3091) | 6.12 / -0.86 (1543) | 6.92 / +2.75 (1230) | 8.54 / -3.56 (45) |
| gangtok hills | 10.04 / +10.03 (493) | 9.26 / -1.09 (63) | 9.93 / +7.31 (32) | 6.95 / -2.74 (38), 0.37 | 11.45 / -11.16 (32), 0.06 | 9.49 / +7.92 (1171) | 9.42 / -1.56 (132) | 4.33 / +1.25 (212) | 7.35 / -1.45 (32) |
| agumbe western ghats | 2.67 / +2.58 (517) | – | – | 3.54 / -3.23 (16), 0.76 | –, – | 3.95 / +2.76 (746) | – | 4.21 / -3.83 (52) | – |
| silent valley forest | 41.32 / +41.32 (774) | – | 18.45 / +17.46 (36) | 6.67 / -3.77 (27), 0.28 | 22.07 / -22.07 (36), 0.38 | 36.84 / +36.37 (1147) | – | 17.85 / +17.31 (86) | 8.32 / -1.75 (36) |

(b) by reference (laser) height, ICESat-2 20 m segments, all scenes pooled:

| Height bin | n | MAE | bias | baseline nDSM = 0: MAE |
|---|---|---|---|---|
| 0-3 m | 173 | 2.95 | +2.86 | 0.74 |
| 3-10 m | 228 | 2.65 | +1.00 | 6.78 |
| 10-20 m | 133 | 6.00 | -5.53 | 14.02 |
| 20-inf m | 40 | 18.31 | -18.31 | 25.63 |

'High' (eval_v2.high_metrics: reference or ours > 3 m), ICESat-2 segments pooled: 489 | 5.36 | 7.44 | -1.54 | 5.64 | 0.117 (n | MAE | RMSE | bias | NMAD | r).
GEDI rh98 by bin (all scenes pooled): 0-3 m: n 14, MAE 3.11, bias -0.31; 3-10 m: n 62, MAE 2.85, bias +0.47; 10-20 m: n 67, MAE 6.13, bias -5.75; 20-inf m: n 75, MAE 23.55, bias -23.55.

## 6. Per landscape: mean over its 2 scenes (range)

With two scenes a bootstrap confidence interval is not meaningful, so the range (min…max) is shown instead.

| Landscape | Terrain MAE ours (i) | GLO-30 | FABDEM | Surface MAE ours (i) | our DTM only (i) | GLO-30 (DSM) | Surface MAE ours (ii) | (b) nDSM MAE (ICESat-2 seg.) | (b) nDSM bias | (b) r |
|---|---|---|---|---|---|---|---|---|---|---|
| urban | 2.36 (2.04…2.68) | 5.28 (4.47…6.09) | 2.80 (2.12…3.49) | 5.47 (4.94…6.00) | 9.23 (7.32…11.14) | 4.98 (4.67…5.28) | 6.81 (4.97…8.65) | 4.49 (3.78…5.20) | -1.19 (-1.85…-0.54) | 0.556 (0.407…0.705) |
| sparse | 1.76 (1.44…2.08) | 1.80 (1.41…2.20) | 1.82 (1.46…2.17) | 2.10 (1.34…2.86) | 2.70 (1.37…4.03) | 2.29 (1.35…3.23) | 3.08 (3.02…3.15) | 1.56 (0.24…2.88) | 0.84 (0.20…1.49) | 0.271 (0.061…0.481) |
| hilly | 8.42 (6.80…10.04) | 9.20 (7.10…11.31) | 5.74 (5.26…6.22) | 8.57 (7.65…9.49) | 7.68 (6.95…8.41) | 7.75 (6.44…9.05) | 7.77 (6.12…9.42) | 8.25 (6.95…9.55) | -5.12 (-7.50…-2.74) | 0.267 (0.164…0.370) |
| forested | 21.99 (2.67…41.32) | 20.97 (2.41…39.53) | 19.87 (3.98…35.76) | 20.40 (3.95…36.84) | 18.61 (3.26…33.96) | 17.21 (2.54…31.88) | – | 5.10 (3.54…6.67) | -3.50 (-3.77…-3.23) | 0.521 (0.282…0.760) |

## 7. All 8 scenes: mean over scenes [95% bootstrap CI over scenes, 2000 resamples] (pooled over all points)

| Comparison | scenes | MAE | RMSE | bias | NMAD | r |
|---|---|---|---|---|---|---|
| (a) terrain vs ICESat-2 ground, ours (i) no levelling (all passes) | 8 | 8.63 [2.57, 18.53] (5.86) | 9.69 [3.09, 19.97] (13.12) | 7.57 [0.94, 17.79] (3.58) | 2.76 [0.99, 4.85] (2.42) | 0.26 [0.06, 0.51] (0.48) |
| (a) terrain, ours (i) on held-out passes only | 5 | 3.86 [1.58, 6.50] (2.43) | 5.52 [2.12, 9.62] (4.41) | 2.58 [-0.13, 5.59] (-0.30) | 1.63 [0.45, 3.21] (0.91) | 0.22 [0.00, 0.59] (0.79) |
| (a) terrain, ours (ii) held-out levelling | 5 | 4.02 [1.88, 6.74] (2.60) | 4.96 [2.61, 7.77] (4.19) | -0.27 [-1.38, 1.38] (-0.71) | 1.63 [0.45, 3.21] (1.08) | 0.22 [0.00, 0.59] (0.82) |
| (a) terrain, ours (iii) circular | 7 | 4.26 [1.99, 6.92] (3.63) | 5.62 [2.66, 9.00] (6.92) | -0.98 [-2.72, 0.67] (-1.53) | 2.37 [0.73, 4.32] (2.41) | 0.25 [0.03, 0.53] (0.66) |
| (a) terrain, raw GLO-30 | 8 | 9.31 [3.43, 18.56] (6.05) | 10.26 [3.96, 19.98] (12.78) | 8.63 [2.24, 18.30] (4.42) | 2.79 [1.44, 4.41] (3.34) | 0.44 [0.26, 0.64] (0.52) |
| (a) terrain, raw FABDEM | 8 | 7.56 [2.69, 16.03] (5.28) | 8.40 [3.20, 17.17] (11.39) | 5.87 [0.52, 14.74] (2.62) | 2.43 [0.74, 4.43] (2.28) | 0.35 [0.14, 0.58] (0.53) |
| (a) terrain, GLO-30 held-out levelled | 5 | 4.19 [2.37, 7.12] (2.61) | 4.85 [2.92, 7.70] (3.68) | -0.14 [-2.01, 1.69] (-0.11) | 2.02 [0.98, 2.98] (1.94) | 0.33 [0.02, 0.64] (0.86) |
| (a) terrain, FABDEM held-out levelled | 5 | 4.14 [1.84, 7.21] (2.73) | 5.04 [2.53, 8.11] (4.45) | -0.41 [-2.47, 1.67] (-0.68) | 2.27 [0.45, 4.26] (1.06) | 0.31 [-0.02, 0.70] (0.79) |
| (a) terrain vs GEDI ground, ours (i) | 7 | 7.67 [3.39, 12.29] (8.44) | 10.96 [5.47, 16.66] (13.78) | 4.87 [-0.42, 10.19] (6.05) | 6.41 [2.72, 11.02] (4.77) | 0.36 [0.02, 0.75] (0.85) |
| (a) terrain vs GEDI ground, FABDEM | 7 | 6.62 [3.24, 10.31] (7.24) | 9.76 [4.71, 15.00] (12.05) | 2.66 [-1.03, 6.79] (3.39) | 6.22 [2.42, 11.01] (5.26) | 0.47 [0.15, 0.78] (0.87) |
| (b) nDSM vs ICESat-2 segment height, ours (p98) | 8 | 4.85 [3.04, 6.69] (4.61) | 6.04 [3.91, 8.36] (6.87) | -2.24 [-4.11, -0.53] (-1.30) | 6.14 [3.43, 8.99] (4.80) | 0.40 [0.25, 0.56] (0.37) |
| (b) same, single pixel | 8 | 5.53 [3.61, 7.50] (5.20) | 6.97 [4.51, 9.55] (7.75) | -4.63 [-6.49, -2.88] (-4.00) | 6.28 [3.75, 8.89] (4.64) | 0.44 [0.26, 0.61] (0.39) |
| (b) same, baseline nDSM = 0 | 8 | 8.25 [5.57, 10.68] (7.95) | 10.09 [6.72, 13.10] (10.71) | -8.25 [-10.68, -5.57] (-7.95) | 6.66 [4.07, 9.21] (6.79) | – |
| (b) same, baseline GLO-30 - FABDEM | 8 | 6.82 [4.61, 8.84] (6.18) | 7.94 [5.35, 10.47] (8.17) | -4.67 [-6.58, -2.65] (-4.70) | 6.77 [3.66, 9.96] (6.06) | 0.26 [0.03, 0.48] (0.38) |
| (b) nDSM vs GEDI rh98, ours (p98) | 7 | 9.93 [4.86, 15.42] (11.00) | 11.49 [5.65, 17.65] (15.36) | -8.65 [-14.97, -2.72] (-9.76) | 6.61 [3.72, 9.54] (10.66) | 0.30 [0.14, 0.46] (0.20) |
| (b) GEDI rh98, baseline nDSM = 0 | 7 | 16.89 [10.94, 22.87] (17.26) | 18.16 [11.81, 24.68] (21.04) | -16.89 [-22.87, -10.94] (-17.26) | 6.41 [3.38, 9.48] (12.94) | – |
| (c) DSM vs all photons, ours (i) | 8 | 9.14 [3.85, 17.56] (5.87) | 10.59 [4.63, 19.79] (11.05) | 6.26 [0.36, 15.48] (3.59) | 6.67 [3.41, 10.99] (4.31) | 0.43 [0.26, 0.62] (0.71) |
| (c) same, single pixel | 8 | 9.18 [3.94, 17.56] (5.93) | 10.66 [4.75, 19.81] (11.06) | 6.22 [0.24, 15.45] (3.61) | 6.86 [3.59, 11.08] (4.43) | 0.43 [0.26, 0.62] (0.71) |
| (c) DSM vs all photons, ours (i) on held-out passes only | 6 | 5.36 [3.31, 7.25] (4.20) | 6.67 [3.89, 9.56] (5.59) | 1.46 [-2.25, 4.64] (1.43) | 4.21 [1.90, 6.51] (4.31) | 0.33 [0.08, 0.62] (0.87) |
| (c) DSM vs all photons, ours (ii) | 6 | 5.89 [3.95, 7.97] (4.27) | 6.70 [4.56, 8.88] (5.50) | -1.25 [-4.32, 1.38] (0.21) | 4.21 [1.90, 6.51] (4.32) | 0.33 [0.08, 0.62] (0.86) |
| (c) DSM vs all photons, ours (iii) circular | 8 | 6.67 [4.09, 9.74] (5.43) | 8.11 [4.88, 12.24] (8.70) | -2.20 [-5.47, 0.57] (-1.02) | 5.94 [2.54, 10.49] (5.20) | 0.36 [0.17, 0.58] (0.72) |
| (c) all photons, our DTM only (i) | 8 | 9.56 [4.50, 17.13] (6.41) | 11.24 [5.55, 19.56] (10.99) | 2.13 [-4.60, 11.79] (-0.69) | 6.40 [3.17, 10.14] (4.83) | 0.27 [0.08, 0.51] (0.69) |
| (c) all photons, raw GLO-30 | 8 | 8.06 [3.44, 15.32] (5.50) | 9.45 [4.12, 17.72] (10.03) | 4.22 [-0.98, 12.50] (0.97) | 7.01 [3.52, 11.42] (4.44) | 0.46 [0.29, 0.65] (0.74) |
| (c) all photons, FABDEM | 8 | 8.97 [4.55, 15.56] (6.34) | 10.42 [5.43, 17.65] (10.21) | 0.73 [-4.76, 9.05] (-1.71) | 6.20 [3.04, 9.44] (5.51) | 0.31 [0.11, 0.53] (0.73) |
| (c) top photons p98, ours (i) | 8 | 5.69 [3.20, 9.47] (4.34) | 7.07 [3.89, 11.76] (6.10) | 2.39 [-1.05, 7.13] (2.10) | 4.61 [2.08, 8.00] (4.20) | 0.39 [0.17, 0.63] (0.88) |
| (c) top photons, raw GLO-30 | 8 | 5.77 [3.83, 8.34] (4.99) | 7.10 [4.36, 10.82] (6.30) | -0.83 [-3.90, 3.48] (-3.03) | 3.72 [1.93, 6.06] (3.44) | 0.43 [0.19, 0.66] (0.89) |
| (c) GEDI top p98, ours (i) | 7 | 5.97 [4.16, 7.79] (6.06) | 8.68 [5.44, 12.73] (9.57) | -2.63 [-4.51, -1.32] (-2.30) | 6.00 [3.73, 8.57] (5.58) | 0.55 [0.29, 0.82] (0.90) |
| (c) GEDI top, raw GLO-30 | 7 | 8.39 [7.00, 9.98] (8.05) | 10.75 [8.15, 14.46] (10.86) | -6.93 [-9.09, -5.14] (-6.33) | 5.37 [2.69, 8.47] (5.11) | 0.57 [0.31, 0.82] (0.91) |

The three protocols on the same scenes (those with a held-out check):

| Comparison | scenes | MAE | RMSE | bias | NMAD |
|---|---|---|---|---|---|
| terrain (i) no levelling: delhi karol bagh, barmer desert village, anantapur dryland, shimla hills, gangtok hills | 5 | 3.86 [1.58, 6.50] (2.43) | 5.52 [2.12, 9.62] (4.41) | 2.58 [-0.13, 5.59] (-0.30) | 1.63 [0.45, 3.21] (0.91) |
| terrain (ii) held-out levelling: delhi karol bagh, barmer desert village, anantapur dryland, shimla hills, gangtok hills | 5 | 4.02 [1.88, 6.74] (2.60) | 4.96 [2.61, 7.77] (4.19) | -0.27 [-1.38, 1.38] (-0.71) | 1.63 [0.45, 3.21] (1.08) |
| terrain (iii) circular: delhi karol bagh, barmer desert village, anantapur dryland, shimla hills, gangtok hills | 5 | 3.96 [1.78, 6.68] (2.56) | 4.91 [2.48, 7.77] (4.18) | -0.37 [-1.39, 1.27] (-0.77) | 1.63 [0.45, 3.21] (0.99) |
| surface (i) no levelling: chandigarh sector17, delhi karol bagh, barmer desert village, anantapur dryland, shimla hills, gangtok hills | 6 | 5.36 [3.31, 7.25] (4.20) | 6.67 [3.89, 9.56] (5.59) | 1.46 [-2.25, 4.64] (1.43) | 4.21 [1.90, 6.51] (4.31) |
| surface (ii) held-out levelling: chandigarh sector17, delhi karol bagh, barmer desert village, anantapur dryland, shimla hills, gangtok hills | 6 | 5.89 [3.95, 7.97] (4.27) | 6.70 [4.56, 8.88] (5.50) | -1.25 [-4.32, 1.38] (0.21) | 4.21 [1.90, 6.51] (4.32) |
| surface (iii) circular: chandigarh sector17, delhi karol bagh, barmer desert village, anantapur dryland, shimla hills, gangtok hills | 6 | 5.83 [3.85, 7.87] (4.25) | 6.66 [4.51, 8.79] (5.50) | -1.30 [-4.25, 1.23] (0.13) | 4.21 [1.90, 6.51] (4.37) |

## 8. All dates vs within 12 months of the image date (unlevelled products, all passes)

| Scene | Image date | Terrain: n, MAE ours (i) all dates → ±12 mo | GLO-30 all → ±12 mo | Surface: n, MAE ours (i) all → ±12 mo | bias all → ±12 mo |
|---|---|---|---|---|---|
| chandigarh sector17 | 20260703 | 113: 2.04 → 0: – | 4.47 → – | 576: 6.00 → 0: – | -2.89 → – |
| delhi karol bagh | 20251023 | 558: 2.68 → 73: 4.78 | 6.09 → 5.91 | 2287: 4.94 → 260: 4.29 | +1.41 → -1.21 |
| barmer desert village | 20250313 | 3502: 2.08 → 746: 1.25 | 2.20 → 1.94 | 8832: 2.86 → 2219: 2.99 | +1.37 → +1.56 |
| anantapur dryland | 20251231 | 2921: 1.44 → 0: – | 1.41 → – | 3381: 1.34 → 0: – | -0.55 → – |
| shimla hills | 20251105 | 528: 6.80 → 0: – | 7.10 → – | 3091: 7.65 → 0: – | +3.65 → – |
| gangtok hills | 20250927 | 493: 10.04 → 26: 19.35 | 11.31 → 19.14 | 1171: 9.49 → 58: 15.37 | +7.92 → +12.88 |
| agumbe western ghats | 20251019 | 517: 2.67 → 0: – | 2.41 → – | 746: 3.95 → 0: – | +2.76 → – |
| silent valley forest | 20250122 | 774: 41.32 → 0: – | 39.53 → – | 1147: 36.84 → 0: – | +36.37 → – |

## 9. Silent Valley diagnostics (for the DTM track; not fixed here)

| Unit | id | date | role | photons | ground | strong-beam photons | night | solar elev. | cloud flag | ATL08 h_te_uncertainty | n_te_photons | ground h p5…p95 | DTM(i) − ground median / NMAD | GLO-30 − ground | FABDEM − ground |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pass | 325006 | 2020-01-17 | only pass | 1147 | 774 | 1071 | 1.00 | -11.0 | 1 | 1.9 | 214 | 836…898 | +46.6 / 7.6 | +46.9 | +39.8 |
| beam | 32500601 | 2020-01-17 | only pass | 1071 | 762 | 1071 | 1.00 | -11.0 | 1 | 1.9 | 394 | 836…870 | +46.7 / 7.4 | +47.0 | +40.0 |
| beam | 32500602 | 2020-01-17 | only pass | 76 | 12 | 0 | 1.00 | -11.0 | 1 | – | 5 | 874…912 | +18.2 / 3.3 | +26.7 | +17.4 |

GEDI in the scene: 81 shots, 36 quality (23 power beam); our DTM (i) vs GEDI ground: 36 | 14.17 | 12.25 (n | median | NMAD); GLO-30 vs GEDI ground: 36 | 19.77 | 12.45.

## What this means

- **The old numbers are real but partly circular.** They reproduce to 0.03 m. Where a scene has two or more laser passes, levelling the terrain on some passes and checking it on the others gives terrain MAE 4.02 m against 3.86 m without levelling and 3.96 m with the old circular protocol (mean of 5 scenes). Levelling removes the average offset (bias +2.58 -> -0.27 m) but does not lower the typical error, because a shift learnt on one track a few hundred metres away does not hold on the next one: in Gangtok the passes disagree with the same terrain by 0.5 to 24.8 m, in Anantapur by 3.2 m. Surface MAE on held-out photons: 5.89 m levelled vs 5.36 m not.
- **Single-pass scenes cannot be checked after levelling.** In Agumbe and Silent Valley every photon comes from one pass, so the old terrain/surface numbers there are pure self-fit. Silent Valley's surface MAE is 36.8 m before levelling (old, circular: 15.5 m). The 47 m shift comes from one night pass (93% of its photons on the strong beam). GEDI disagrees: its ground lies 14 m below our unlevelled terrain, and the levelled terrain ends up 32 m below GEDI ground. One of the two lasers is wrong there; a single pass should not be allowed to move the terrain by tens of metres.
- **Against public DEMs, at the same points.** Terrain (all 8 scenes, mean MAE): ours 8.63 m, raw GLO-30 9.31 m, FABDEM 7.56 m. Our building/tree removal clearly beats raw GLO-30 in towns (2.36 vs 5.28 m) and edges FABDEM there (2.80 m); on sparse land all three are equal (~1.8 m); in the hills FABDEM is better (5.74 vs ours 8.42 m); in forest every product is about 20 m off and ours is the worst (ours 21.99, GLO-30 20.97, FABDEM 19.87 m; Silent Valley dominates). Surface: our DSM 9.14 m vs raw GLO-30 8.06 m vs our terrain alone 9.56 m (mean MAE vs all photons): at laser footprints our absolute DSM is not more accurate than the 30 m Copernicus DSM except on sparse land (2.10 vs 2.29 m; towns 5.47 vs 4.98, hills 8.57 vs 7.75 m: ours loses); against GEDI canopy/roof tops it is (5.97 vs 8.39 m). What the image adds is detail at 0.5 m, which a 30 m DSM cannot have, not better absolute heights at the footprints.
- **The height model itself (no DEM in the loop).** Against laser-only heights above ground our nDSM has MAE 4.85 m (ICESat-2 20 m segments) and 9.93 m (GEDI rh98), versus 8.25 / 16.89 m for predicting zero and 6.82 m for GLO-30 minus FABDEM; r = 0.40. It is too high on low ground (+2.9 m below 3 m) and too low on tall objects (-5.5 m at 10-20 m, -18.3 m above 20 m; GEDI -23.6 m above 20 m). Tall forest is the main failure: in Silent Valley (90% trees) the median predicted height is 4.6 m (99th percentile 8.6 m) where GEDI measures a median rh98 of 27.5 m.
- **Correlation.** After removing the terrain plane, r between our heights and the laser is 0.26 (terrain) and 0.43 (surface), not the 0.93-0.98 the old report's absolute-elevation r suggested for hilly scenes: that was the hillside, not the model.
- **Uncertainty.** The two scenes of a landscape can differ enormously (forested terrain MAE 2.7 m in Agumbe, 41.3 m in Silent Valley), so per-landscape values are means with their range, not confidence intervals; the 8-scene bootstrap intervals are wide. Most laser passes are years older or younger than the image; only 2 scenes have 100+ photons within 12 months of it, and that subset does not change the picture consistently (section 8).

## 10. Data sources, and what a human must do for CartoDEM

- **FABDEM V1-2** (Hawker et al. 2022, CC BY-NC-SA 4.0, non-commercial: used for evaluation only, the tiles stay in the git-ignored `v2/scenes/fabdem/`). data.bris.ac.uk reset every connection from this machine, so the 1-degree tiles came from the HuggingFace mirror `pavelzaitsau/fabdem-v12` (a third-party copy of the Bristol release, not checksum-verified against Bristol). Datum EGM2008, like GLO-30.
- **Copernicus GLO-30** read window-only from the AWS open-data bucket (as terrain.py does).
- **GEDI L2A** v002 via SlideRule `gedi02ap` (public, no login), all shots in the scene; kept: L2 quality_flag = 1 and degrade_flag = 0; ground = elev_lowestmode, top = elev_lowestmode + rh98; WGS84 ellipsoid -> EGM2008 with the same geoid height as the ICESat-2 photons (terrain.geoid_shift). GEDI horizontal geolocation error is ~10 m.
- **OSM buildings** via Overpass (`way/relation[building]`, out geom), rasterised on the scene grid: photons inside a footprint are roof photons (Cai et al. 2024: ATL08 classes over roofs are unreliable), kept out of every validation ground set; the levelling offsets (terrain.laser_offset on the levelling passes) use every ATL08 ground photon, roofs included, exactly as the app does.
- **Esri imagery date**: World_Imagery MapServer identify, Citations layer, zoom 18 (live); for Chandigarh the demo image the old run used matches Esri Wayback release R07 pixel for pixel, dated from that release's metadata service.
- **CartoDEM v3 R1 (not used: login-gated).** A human must: (1) register a free account at https://bhuvan.nrsc.gov.in (Sign Up; needs an e-mail address); (2) log in at https://bhuvan-app3.nrsc.gov.in/data/download/index.php; (3) choose Satellite/Sensor = CartoDEM, Version = 3 R1, and select the 1-degree tiles N30E076 (Chandigarh), N28E077 (Delhi), N25E071 (Barmer), N14E077 (Anantapur), N31E077 (Shimla), N27E088 (Gangtok), N13E075 (Agumbe), N11E076 (Silent Valley); (4) unzip the GeoTIFFs into `SynRS3D/demo/benchmark/v2/scenes/cartodem/`; (5) rerun `demo/india_eval_v2.py evaluate`. They are picked up automatically as baseline `cartodem` (EGM96 -> EGM2008 via terrain.geoid_shift). Licence: NRSC data policy, do not commit them.

## Commands

From `SynRS3D/` (the model step under the shared model lock):

```
.venv/bin/python demo/india_eval_v2.py --selftest && .venv/bin/python validate.py
.venv/bin/python demo/india_eval_v2.py prepare      # network: windows, images, dates, ICESat-2, GEDI, OSM, FABDEM
/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/india_eval_v2.py predict
.venv/bin/python demo/india_eval_v2.py terrain
.venv/bin/python demo/india_eval_v2.py evaluate     # -> demo/benchmark/v2/india_v2.json + india_v2.md
.venv/bin/python demo/india_eval_v2.py report       # -> india_v2.md again from india_v2.json (wording only)
# Chandigarh imagery check (section 1), run once before the live image became the scene:
/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/india_eval_v2.py predict chandigarh_sector17_live
.venv/bin/python demo/india_eval_v2.py terrain chandigarh_sector17_live && .venv/bin/python demo/india_eval_v2.py oldcheck chandigarh_sector17_live chandigarh_sector17
```

Window recomputation (landscape_benchmark.best_window) ran for Delhi, Barmer and Anantapur and gave the old windows exactly; for Shimla, Gangtok, Agumbe and Silent Valley it was skipped to stay in the time budget (a 3 km SlideRule request took ~25 min) and the old windows were used. Optional plan step 9 (extra scenes per landscape) was not done.
