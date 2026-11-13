# DepthWizard claims register (18 October 2026)

Every number and capability in the deck (v3 → v4), `README.md`, `docs/TECHNICAL.md` and `docs/USER_GUIDE.md` has a
row here. Values are copied from the JSON file in the *Source* column. Each JSON is written by the script named in its
report, and the command is in the matching `.md`. Paths are relative to the repository root.

- **Metrics:** e = ours − reference. MAE, RMSE, bias = mean(e), NMAD = 1.4826 · median |e − median(e)|, Pearson r.
- **Aggregation:** the value is the mean over tiles (GAMUS, ATL/ARG) or scenes (India), with a 95% percentile
  bootstrap CI over tiles or scenes (2000 resamples, `numpy.random.default_rng(0)`). "pooled" means all pixels or
  points together.
- **Status:**
  - **measured**: the value comes from the file in the Source column;
  - **planned**: not built or not measured, so it is worded "planned" wherever it appears;
  - **not claimed**: removed from the deck and docs, with the reason given.

Short names: `v2/` = `SynRS3D/demo/benchmark/v2/`, `bench/` = `SynRS3D/demo/benchmark/`.

## 1. Model and capabilities

| ID | Claim | Test set | n | Metric | Value | Source | Status |
|---|---|---|---|---|---|---|---|
| M1 | The height model is RS3DAda (Song et al., NeurIPS 2024): DINOv2 ViT-L/14 + DPT heads, with the released weights (`JTRNEO/RS3DAda`) and **no fine-tuning by us** | – | – | – | – | `SynRS3D/infer_height.py`, `SynRS3D/pretrain/` | measured (built) |
| M2 | 4-flip test-time augmentation lowers MAE a little | GAMUS 150 | 150 tiles | paired MAE, TTA − single | −0.064 m [−0.101, −0.035]; TTA better on 114/150 | `v2/gamus_v2.json` :: v2.tta_minus_single_mae | measured |
| M3 | The DepthWizard inference path (512 tile padded to 518, fp16, TTA) is no worse than the authors' `evaluation.py` | OGC ATL / ARG | 300 tiles each | paired whole-image MAE | ATL −0.091 m [−0.137, −0.041]; ARG −0.071 m [−0.089, −0.056] | `v2/geopose_v2.json` :: cities.*.paired_vs_official_whole_mae.dw | measured |
| M4 | The full app pipeline runs on an 8 GB laptop (Apple M3, MPS): one GeoTIFF scene end to end | chandigarh_sector17 | 1 scene | wall time | 42 s; terrain version 3; 28 blocks, each with a 90% interval | `v2/integrate_e2e.json` | measured |
| M5 | Runs offline after installation; CPU fallback | – | – | – | – | `Install.bat`, `install.ps1` | built, not timed (CPU speed not measured) |
| M6 | "A 1024 × 1024 image takes a few seconds on an NVIDIA GPU, several minutes on CPU" (USER_GUIDE) | – | – | – | – | – | not measured in v2; worded as indicative |
| M7 | GeoTIFF + GLB export; orbit / fly / street-level cameras; drawn-path flythrough; video recording | – | – | – | – | `SynRS3D/web/index.html` (`#selftest`) | built |
| M8 | Validation in the app against a raster, points or ICESat-2, with a held-out-pass table for ICESat-2 | – | – | – | – | `SynRS3D/validate.py`, `web/index.html` | built |
| M9 | Ground-control-point calibration (level / scale / tilt, leave-one-out error) | – | – | – | – | `SynRS3D/validate.py` (`#valtest`) | built, accuracy not benchmarked |
| M10 | Disaster tools: bathtub / connected flood, rain and river timeline, A* routing, helipad / camp finder | – | – | – | – | `web/index.html` (`#toolstest`) | built; scenario tools, not forecasts |
| P1 | DINOv3-SAT + DPT "challenger" with CHMv2 initialisation, "GAMUS-tuned" | – | – | – | – | – | planned, not built |
| P2 | Distilled small model on ONNX Runtime (CPU) | – | – | – | – | – | planned, not built |
| P3 | Tauri desktop app | – | – | – | – | – | planned, not built (the app is `.bat` launchers + browser window) |
| P4 | "Fine-tuning fits one cloud GPU" | – | – | – | – | – | not claimed (no fine-tuning was done or costed) |
| P5 | Sat3DGen street-level mesh | – | – | – | – | – | planned, not built |
| P6 | Line-of-sight / viewshed for relief staging | – | – | – | – | – | planned, not built |
| P7 | Off-nadir warning in the UI; training on off-nadir US3D data | – | – | – | – | – | planned, not built |
| P8 | Cartosat input and a CartoDEM v3 R1 comparison | – | – | – | – | `docs/DATA_REQUEST_cartosat.md` | planned (data requested, login-gated) |
| P9 | "Generic depth AI fails on top-down images" | – | – | – | – | – | not claimed (we never measured a generic depth model) |
| P10 | "License-clean, no non-commercial weights" | – | – | – | – | see licences below | not claimed (the RS3DAda training data, FABDEM and the demo imagery are non-commercial) |
| P11 | Model shortlist scores (/10) in the deck v3 chart | – | – | team judgement | – | – | not claimed (judgement, not a measurement; chart removed) |

## 2. Height above ground vs airborne LiDAR: GAMUS (zero-shot)

GAMUS imagery is **aerial orthophotos at 0.33 m, not satellite**. DC and NYC trees are leaf-off (visual check; there is
no metadata). RS3DAda never saw GAMUS, so "zero-shot" is fair here.

| ID | Claim | Test set | n | Metric | Value (95% CI) | Source | Status |
|---|---|---|---|---|---|---|---|
| G1 | Overall nDSM MAE, TTA | GAMUS 150 frozen (50 per city: DC, NYC, PHL) | 150 tiles | MAE per tile | **3.90 m [3.24, 4.66]** (pooled 3.88) | `v2/gamus_v2.json` :: v2.overall.tta.mae | measured |
| G2 | Flat-ground baseline (nDSM = 0) on the same tiles | GAMUS 150 | 150 tiles | MAE per tile | 5.65 m [4.88, 6.50] (pooled 5.63) | `v2/gamus_v2.json` :: v2.overall.zero_baseline.mae | measured |
| G3 | RMSE / bias / NMAD / r on nDSM | GAMUS 150 | 150 tiles | per tile (pooled) | RMSE 5.58 [4.82, 6.40] (7.39); bias −2.61 [−3.41, −1.87]; NMAD 2.52 [2.09, 3.01]; r 0.61 [0.57, 0.65] (0.58) | `v2/gamus_v2.json` :: v2.overall.tta | measured |
| G4 | Share within ±1 m / ±2 m, ours vs baseline | GAMUS 150 | 150 tiles | share of pixels | ±1 m 0.50 vs 0.50; ±2 m 0.61 vs 0.54 | `v2/gamus_v2.json` :: v2.overall | measured |
| G5 | Per city MAE | GAMUS 150 | 50 tiles each | MAE per tile | DC 5.16 [3.77, 6.75]; NYC 4.69 [3.49, 5.99]; PHL 1.86 [1.44, 2.39] | `v2/gamus_v2.json` :: v2.per_city | measured |
| G6 | "High" pixels (reference > 3 m) | GAMUS 150 | 147 tiles | MAE, bias | MAE 6.65 [5.90, 7.44], bias −5.27; baseline 11.10 [10.15, 12.10]; utils/metrics.py union definition 6.53 [5.80, 7.31] | `v2/gamus_v2.json` :: v2.high | measured |
| G7 | Bias by reference height bin | GAMUS 150 | 150 / 145 / 134 / 76 tiles | bias per tile | 0–3 m +0.65; 3–10 m −1.86; 10–20 m −7.62 (pooled −8.82); > 20 m −16.26 (pooled −19.09) | `v2/gamus_v2.json` :: v2.height_bins | measured |
| G8 | Building heights (90th percentile per building) | GAMUS 150 | 1,450 buildings, 115 tiles | MAE per tile | 3.57 m [3.08, 4.06]; bias −1.37; baseline 10.54 | `v2/gamus_v2.json` :: v2.buildings | measured |
| G9 | By landscape, ours vs baseline | GAMUS 150 | 137 / 141 / 148 tiles | MAE per tile | urban 2.90 [2.34, 3.63] vs 5.66; forested 6.67 [5.92, 7.45] vs 8.70; sparse / open 0.96 [0.85, 1.09] vs 0.55 (**worse than the baseline**) | `v2/gamus_v2.json` :: v2.per_group | measured |
| G10 | By class (deck chart): buildings / trees / road / ground, ours vs nDSM = 0 | GAMUS 150 | 114 / 141 / 134 / 103 tiles | MAE per tile | 3.55 vs 9.08; 6.67 vs 8.70; 1.82 vs 1.72; 0.86 vs 0.46 | `v2/gamus_v2.json` :: v2.per_group['class: *'] | measured |
| G11 | Trees: canopy predicted at a fraction of its true height | GAMUS 121 tree tiles | 49 / 40 / 32 tiles | mean ours / mean reference | DC 0.20, NYC 0.18, PHL 0.60 | `v2/gamus_v2.json` :: v2.trees_leaf.canopy_height_and_ratio | measured |
| G12 | Old README headline reproduced on the same 45 tiles | GAMUS old-45 | 45 tiles | official MAE / RMSE | 4.01 / 5.90 m (identical to the old run) | `v2/gamus_v2.json` :: reproduction.old45 | measured (superseded by G1) |
| G13 | Deck v3 "official MAE 3.88 / RMSE 5.56 m on 150 tiles" | GAMUS 150 | 150 tiles | official utils/metrics.py, TTA | 3.88 / 5.56 m | `v2/gamus_v2.json` :: v2.official_150.ALL | measured (superseded by G1, which has a CI) |
| G14 | Old README "r 0.66, urban 2.83 m, trees 8.96 m" (45 tiles, pooled) | GAMUS old-45 | 45 tiles | pooled | – | `bench/gamus_results.json` | not claimed (replaced by G1–G10) |

## 3. Satellite imagery: Overhead Geopose ATL / ARG (zero-shot, SynRS3D Target Domain 2)

| ID | Claim | Test set | n | Metric | Value (95% CI) | Source | Status |
|---|---|---|---|---|---|---|---|
| A1 | Published RS3DAda numbers reproduced, Atlanta | OGC ATL: 200 test_syn + 100 random test tiles | 300 tiles | whole-image MAE (evaluation.py path) | **5.99 m [5.57, 6.43]** vs paper 5.67 (source-only 7.26) | `v2/geopose_v2.json` :: cities.ATL.official_exact_fp32.whole_mae | measured |
| A2 | Same, Buenos Aires | OGC ARG, same sampling | 300 tiles | whole-image MAE | **1.94 m [1.86, 2.03]** vs paper 2.01 (source-only 2.65) | `v2/geopose_v2.json` :: cities.ARG.official_exact_fp32.whole_mae | measured |
| A3 | DepthWizard path on the same tiles | OGC ATL / ARG | 300 tiles each | whole-image MAE | ATL 5.90, ARG 1.87 | `v2/geopose_v2.json` :: cities.*.passes.dw.official.whole.mae | measured |
| A4 | Tall objects under-predicted on satellite imagery too | OGC ATL / ARG | 288–300 tiles per bin | bias by reference height | ATL 10–20 m −8.11, > 20 m −16.80; ARG −5.59, −15.25 | `v2/geopose_v2.json` :: cities.*.passes.official.v2.bins | measured |
| A5 | Paper "TD2 High MAE 7.23 m" | – | – | – | – | no source in the repo | not claimed |

The paper values (5.67, 2.01, 7.26, 2.65) were read off Figure 7 of arXiv:2406.18151. The paper does not say which
tile list it averages over. On our ATL sample the choice matters: test_syn 6.23 m, other tiles 5.50 m.

## 4. DFC2019 (in RS3DAda's adaptation domain, not zero-shot)

| ID | Claim | Test set | n | Metric | Value | Source | Status |
|---|---|---|---|---|---|---|---|
| D1 | Deck v3: "200 DFC2019 test tiles, MAE 2.22 m / RMSE 3.83 m" | DFC2019 JAX + OMA test | 200 tiles | official MAE / RMSE, TTA | 2.22 / 3.83 m | `bench/results.json` :: ALL.tta.whole | measured in v1; **not zero-shot** (RS3DAda adapted on unlabelled JAX / OMA images); removed from the deck |
| D2 | Deck v3: "where ± is highest, real error is ~7× larger; rank correlation 0.62" | DFC2019 | 200 tiles | quintiles of flip spread | – | `bench/results.json` | not claimed (pooled pixels, adaptation domain; the v2 test U1 says the spread does not rank errors on tall objects) |
| D3 | Deck v3 notes: "a global correction learned on separate tiles did not fix tall buildings" | DFC2019 | 200 + 200 tiles | MAE by split | shipped: none | `bench/correction.json` | measured in v1 (consistent with R1) |

## 5. Indian scenes vs NASA ICESat-2 and GEDI (held-out-pass protocol)

There are 8 scenes, two per landscape: Chandigarh, Delhi, Barmer, Anantapur, Shimla, Gangtok, Agumbe and Silent Valley.
ICESat-2 passes alternate between levelling and validation, and no photon is used for both. The images are Esri / Vantor
basemaps at 0.31–0.5 m.

| ID | Claim | Test set | n | Metric | Value (95% CI) | Source | Status |
|---|---|---|---|---|---|---|---|
| I1 | Height model alone (no DEM): nDSM vs ICESat-2 20 m segment heights, ours vs nDSM = 0 | 8 Indian scenes | 8 scenes (574 segments) | MAE per scene | **4.85 m [3.04, 6.69]** vs 8.25 [5.57, 10.68]; r 0.40 [0.25, 0.56] | `v2/india_v2.json` :: aggregate.all_scenes['b.is2_seg.ours.fp98' / 'b.is2_seg.zero.fp98'] | measured |
| I2 | nDSM vs GEDI rh98, ours vs nDSM = 0 | 7 scenes with GEDI | 7 scenes (218 shots) | MAE per scene | 9.93 m [4.86, 15.42] vs 16.89 [10.94, 22.87] | `v2/india_v2.json` :: aggregate.all_scenes['b.gedi.*.fp98'] | measured |
| I3 | Tall objects too low (ICESat-2 segments, reference > 20 m) | 8 scenes | 40 segments | bias, pooled | −18.31 m | `v2/india_v2.json` :: aggregate.bins | measured |
| I4 | Terrain vs held-out ICESat-2 ground: no levelling / levelled on other passes / old circular | 5 scenes with 2+ passes | 5 scenes | MAE per scene | 3.86 [1.58, 6.50] / 4.02 [1.88, 6.74] / 3.96 [1.78, 6.68]; bias +2.58 → −0.27 | `v2/india_v2.json` :: aggregate.same_scenes | measured |
| I5 | Terrain, current app (single-pass guard) vs held-out ICESat-2 ground | 5 scenes | 5 scenes | MAE per scene | 3.73 m [1.44, 6.69] (old app 4.02) | `v2/dtm_guard_summary.json` :: sets['dtm.is2val'].all | measured |
| I6 | Terrain vs ICESat-2 ground, unlevelled: ours / raw GLO-30 / FABDEM | 8 scenes | 8 scenes | MAE per scene | 8.63 [2.57, 18.53] / 9.31 [3.43, 18.56] / 7.56 [2.69, 16.03] | `v2/india_v2.json` :: aggregate.all_scenes['a.is2.*'] | measured |
| I7 | Terrain by landscape, ours / GLO-30 / FABDEM (2 scenes each, so no CI) | 8 scenes | 2 scenes per row | mean MAE | urban 2.36 / 5.28 / 2.80; sparse 1.76 / 1.80 / 1.82; hilly 8.42 / 9.20 / 5.74; forested 21.99 / 20.97 / 19.87 (ours worst) | `v2/india_v2.json` :: by_landscape | measured |
| I8 | Absolute DSM vs all ICESat-2 photons, unlevelled: ours vs raw GLO-30 DSM | 8 scenes | 8 scenes | MAE per scene | 9.14 [3.85, 17.56] vs 8.06 [3.44, 15.32] (**ours loses**; also in towns 5.47 vs 4.98 and hills 8.57 vs 7.75) | `v2/india_v2.json` :: aggregate.all_scenes['c.is2_all.*'], by_landscape | measured |
| I9 | Absolute DSM vs GEDI canopy / roof tops: ours vs raw GLO-30 | 7 scenes | 7 scenes | MAE per scene | 5.97 [4.16, 7.79] vs 8.39 [7.00, 9.98] | `v2/india_v2.json` :: aggregate.all_scenes['c.gedi_top.*'] | measured |
| I10 | DSM vs held-out ICESat-2 photons, old app → current app (guard) | 6 scenes | 6 scenes | MAE per scene | 5.89 [3.95, 7.97] → 5.30 [3.31, 7.26] | `v2/dtm_compare.json`, `v2/dtm_guard_summary.json` | measured |
| I11 | Correlation after removing the terrain plane (old "r 0.98 in hills" was the hillside) | 8 scenes | 8 scenes | r per scene | terrain 0.26 [0.06, 0.51]; surface 0.43 [0.26, 0.62] | `v2/india_v2.json` :: aggregate.all_scenes['a.is2.ours_none.fp' / 'c.is2_all.ours_none.fp'].r | measured |
| I12 | Old protocol reproduced on this machine | 8 scenes | 8 scenes | max abs difference | within 0.03 m (largest 0.023 m) | `v2/india_v2.json` :: scenes.*.old_protocol | measured |
| I13 | Old README table (urban 5.33 / sparse 2.06 / hilly 6.93 / forested 10.54 m; hilly r 0.98) | 8 scenes | – | circular | – | `bench/landscape_results.json` | not claimed (levelled and checked on the same photons; r on absolute elevation) |
| I14 | Old deck notes: "raw DEM 2.8 m off at laser ground points in 9 demo scenes, 1.6 m after building removal" | 9 demo scenes | – | pooled | – | `bench/icesat2_check.json` | not claimed (replaced by I6, I7) |
| I15 | In-app held-out check, Chandigarh: every held-out "ground" photon is a roof | chandigarh_sector17 | 35 footprints | MAE | terrain 15.20 m, bias −15.20 (roof photons, not ground) | `v2/integrate_e2e.json` :: held_out | measured (known defect, see limitations) |

## 6. Terrain (DTM) and levelling

| ID | Claim | Test set | n | Metric | Value (95% CI) | Source | Status |
|---|---|---|---|---|---|---|---|
| T1 | No DTM base wins every held-out test; GLO-30 cleaned stays the default (DTM vs held-out ICESat-2 ground: GLO-30 cleaned / raw / FABDEM raw / FABDEM cleaned) | 5 scenes | 5 scenes | MAE per scene | 3.86 / 4.96 / 4.15 / 3.82 | `v2/dtm_compare.json` :: same_scenes['dtm.is2val'] | measured |
| T2 | Denser levelling with GEDI does not help on held-out ICESat-2 ground (pooled median / unit median / Huber) | 5 scenes | 5 scenes | MAE per scene | 4.24 / 4.19 / 4.18 vs 4.02 old median, 3.86 no levelling | `v2/dtm_compare.json` :: same_scenes['dtm.is2val'] | measured; not shipped |
| T3 | Single-pass guard: no laser shift from ground photons of one pass | 8 scenes | 8 scenes | app path | 6/6 multi-pass offsets unchanged; Agumbe +2.29 m and Silent Valley +46.59 m refused | `v2/dtm_guard_check.json`, `v2/dtm_e2e_app_run.json` | measured (shipped) |
| T4 | The guard is a safety fix, not an accuracy gain: without Silent Valley, GEDI tops / GEDI ground before → after | 5 scenes | 5 scenes | MAE per scene | 6.94 → 6.83; 5.88 → 5.80 | `v2/dtm_guard_summary.json` :: sets.*.without_silent_valley | measured |
| T5 | Silent Valley: the 47 m offset is a real DEM error along one valley line, wrongly applied to the whole scene | silent_valley_forest | 774 ground photons, 36 GEDI shots | share of photons > 20 m below our terrain; close ICESat-2/GEDI crossover | 94%; +1.1 m (5 m apart; the other two crossovers, one photon each, +40.7 and −3.3 m); EGM96 − EGM2008 −0.09 m | `v2/dtm_silent_valley.json` | measured |
| T6 | What the in-app ICESat-2 panel now shows for Silent Valley (unlevelled), and the held-out GEDI tops | silent_valley_forest | 1,147 / 774 photons | MAE | surface 15.51 → 36.76 m, terrain 9.06 → 41.27 m; DSM vs held-out GEDI tops 51.67 → 6.99 m | `v2/dtm_guard_summary.json` :: silent_valley_in_app; sets['dsm.gedival_top'].per_scene_mae | measured |
| T8 | N5 roof-photon rule (22 Oct): an ICESat-2 "ground" photon on a model building pixel (+2 m) and > 3 m above the other ground photons is a roof, and is left out of levelling and terrain checks. In-app held-out terrain MAE (footprint), before → after: Chandigarh 15.28 → no check (all 35 held-out "ground" photons were roofs); Bengaluru 0.76 → 0.59; Delhi 1.47 → 1.38; Mumbai 1.31 → 1.31; Porto Alegre centre 4.30 → 2.63; Sarandi 0.68 → 0.68; POA p07-09 2.15 → 2.38 (levelling moved 0.04 m; the removed roofs had hidden a terrain-too-high bias) | 7 levelled demo scenes | 7 scenes | held-out terrain MAE per scene | see claim | `v2/roof_filter_n5.json` (`SynRS3D/demo/roof_filter_n5.py`) | measured (shipped); demo scenes, not the India test set; Chandigarh is now unlevelled (its real ground comes from one pass, T3) |
| T7 | Old README "laser levelling lands within ~0.6 m on flat scenes" | – | – | circular | – | `bench/landscape_results.json` | not claimed (levelling removes bias, not MAE: I4) |

## 7. Uncertainty

| ID | Claim | Test set | n | Metric | Value (95% CI) | Source | Status |
|---|---|---|---|---|---|---|---|
| U1 | The 4-flip spread ("consistency score") ranks errors on flat ground and edges, not on tall objects | GAMUS 150 | 150 / 145 / 141 tiles | Spearman, spread vs abs(error), per tile (pooled) | all pixels 0.44 [0.40, 0.47] (0.58); reference > 3 m −0.03 [−0.06, 0.01] (−0.11); trees 0.03 [0.00, 0.05] | `v2/gamus_v2.json` :: v2.uncertainty_spearman | measured |
| U2 | Old docs "Spearman ρ = 0.56 on GAMUS" | GAMUS old-45 | 45 tiles | pooled, old method | 0.56 (reproduced) | `v2/gamus_v2.json` :: reproduction | not claimed (pooled; hides U1) |
| U3 | Pixel 90% split-conformal interval, held-out city (target ±3 pp) | GAMUS 150, leave-one-city-out | 153,285 samples | coverage | DC 81.4%, NYC 91.3%, PHL 96.1% (**target missed**) | `v2/uncertainty_calibration.json` :: pixel | measured; not shipped as a pixel map |
| U4 | Building-block 90% interval (shipped in the viewer), held-out city | GAMUS 150, leave-one-city-out | 959 blocks | coverage; mean width | DC 86.6%, NYC 83.3%, PHL 97.0%; mean width 11.6–14.3 m (about ±6 m, clipped at 0) | `v2/uncertainty_calibration.json` :: building.symmetric | measured (shipped) |
| U5 | The block interval misses tall buildings | GAMUS 150, leave-one-city-out | 959 blocks | coverage by LiDAR height | 3–10 m: DC 100%, NYC 99%, PHL 100%; 10–20 m: DC 67% (n 101), NYC 49% (n 57), PHL 96% (n 93); > 20 m: DC 14% (n 22), NYC 30% (n 10), PHL 25% (n 8) | `v2/uncertainty_calibration.json` :: building.symmetric.*.test['0.9'].by['reference height bin'] | measured |
| U6 | Block interval on Indian roofs (OSM footprints, median roof photon; a different reference definition from U4) | 8 Indian scenes | 96 buildings | coverage | 90%: 71% (scene mean 57%) | `v2/recal_gamus.json` :: india.interval_coverage | measured |
| U7 | Block spread vs abs(error) | GAMUS 150 | 959 blocks | Spearman | 0.00 | `v2/uncertainty_calibration.json` :: building_accuracy | measured |
| U8 | "Calibrated uncertainty ±" for the per-pixel map | – | – | – | – | – | not claimed (renamed "consistency score") |

## 8. Tall-object correction and input resolution

| ID | Claim | Test set | n | Metric | Value (95% CI) | Source | Status |
|---|---|---|---|---|---|---|---|
| R1 | Isotonic height recalibration fails on one held-out city, so it is not shipped | GAMUS 150, leave-one-city-out | 150 tiles, 3 folds | MAE raw → recalibrated | DC 5.16 → 4.44; NYC 4.69 → 3.94; PHL 1.86 → 2.87 | `v2/recal_gamus.json` :: folds, ship | measured; not shipped |
| R2 | Resampling the input to another GSD does not help (native 0.33 m vs 0.40 m) | GAMUS, every 10th tile per city | 15 tiles (135 dropped for time) | MAE per tile | 3.15 vs 3.08; difference −0.064 [−0.234, +0.056]; 0.40 m better on 5/15 tiles | `v2/gsd_sweep.json` :: by_city.ALL['0.40'], decision | measured; default unchanged |
| R3 | A coarser input hurts on satellite tiles (scale 0.75) | OGC ATL / ARG | 100 tiles each | paired MAE change | +0.18 / +0.09 m | `v2/geopose_v2.json` :: cities.*.ablation.passes | measured |

## 9. Flood scenario test (Porto Alegre / Canoas, May 2024)

| ID | Claim | Test set | n | Metric | Value | Source | Status |
|---|---|---|---|---|---|---|---|
| F1 | Bathtub flood from the **pre-flood** image vs the IPH/UFRGS 6 May 2024 extent, in the scenes with ICESat-2 ground photons: raw GLO-30 / ours / FABDEM / ours + ICESat-2 levelling | 4 windows of 320 × 320 m | 4 scenes, pooled pixels | CSI | 0.20 / 0.30 / 0.32 / **0.79** | `bench/flood_test.json` (pooled by `demo/flood_test.py` into `bench/flood_test.md`) | measured, **scenario test**, not a forecast |
| F2 | Same, all 7 Porto Alegre windows, no levelling: raw / ours / FABDEM | 7 windows | 7 scenes, pooled | CSI | 0.18 / 0.47 / 0.48 | `bench/flood_test.md` | measured (scenario test) |

Caveats for F1: the windows are small (a spot check, not a city-wide score). The levelling was done with the old app,
before the single-pass guard. In one of the four windows (poa_edge_p01-23) all laser photons come from one date, so the
current app would not level it. F1 was not re-run after the guard.

## Not yet validated

- **Cartosat imagery and CartoDEM v3 R1.** Both are login-gated. Data request: `docs/DATA_REQUEST_cartosat.md`.
- **Leaf-on tree canopy.** GAMUS DC and NYC trees are leaf-off. India has only 2 forest scenes, and Silent Valley's
  median predicted height is 4.6 m where GEDI measures 27.5 m (`v2/india_v2.md` section "What this means").
- **Coverage per landscape in India.** There are only 2 scenes per landscape. Most laser passes are years away from
  the image date.
- **Floor counts** (3 m per floor), **GCP calibration accuracy**, CPU and GPU **processing times**, and the
  **disaster tools** apart from the one flood scenario test.
- **Interval coverage outside US cities**, and for buildings taller than 10 m (U5, U6).
- **The flood test with the current single-pass guard** (F1 caveat).

## Licences of what we use

| Item | Licence / terms | How we use it |
|---|---|---|
| RS3DAda / SynRS3D code | MIT (`SynRS3D/LICENSE`) | the model code |
| RS3DAda weights (`JTRNEO/RS3DAda`) | Hugging Face model card: MIT. They were trained on the SynRS3D dataset, which is CC BY-NC 4.0, so check before any commercial use | inference only |
| DINOv2 (Meta) | Apache-2.0 | the encoder |
| three.js | MIT | the viewer (bundled) |
| GAMUS | CC BY 4.0 | evaluation only |
| Overhead Geopose Challenge (ATL / ARG) | CC BY 4.0 | evaluation only |
| Copernicus DEM GLO-30 | © DLR / Airbus, provided by ESA under the Copernicus DEM licence (free, with attribution) | runtime terrain |
| FABDEM V1-2 | CC BY-NC-SA 4.0, non-commercial | evaluation only, optional terrain; never committed |
| NASA ICESat-2 (ATL03 / ATL08) and GEDI L2A | NASA open data, no restrictions; cite the products | levelling, validation |
| OpenStreetMap buildings | ODbL | roof masks for validation |
| Esri World Imagery (Vantor / Maxar basemap) | Esri terms of use; demonstration only, no redistribution | demo scenes, India evaluation |
| Maxar Open Data (Porto Alegre) | CC BY-NC 4.0, non-commercial | flood scenario test |
| Open-Meteo | CC BY 4.0 (non-commercial API) | rain forecast in the timeline |
| CartoDEM / Cartosat (NRSC) | NRSC data policy | not used yet (requested) |
