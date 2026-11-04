# DTM base and laser levelling on held-out points (plan step 3)

All numbers: `demo/benchmark/v2/dtm_compare.json` and `dtm_silent_valley.json`, written by `demo/dtm_compare.py` (commands at the end). Scenes, photons, GEDI shots, OSM roofs and the pass split are those of `india_v2.md` (demo/india_eval_v2.py caches). MAE in metres; mean over scenes with a 95% bootstrap CI over scenes (2000 resamples), pooled = all points together. "wins" = scenes where MAE is lower than the old app (`glo30_clean.is2_median`: GLO-30 cleaned with our nDSM, ICESat-2 median offset), worst = largest per-scene MAE increase.

Harness check: the old app on held-out ICESat-2 ground gives 4.02 [1.88, 6.74] m, the same 4.02 m as india_v2.json `a.is2.ours_heldout.fp`; the GLO-30 rebuild through `terrain.build_dtm(source="glo30")` equals the cached terrain to 0.0 m in every scene (`dtm_cache/glo30_rebuild_maxdiff.json`).

## Result

- **Base: no change (Copernicus GLO-30 cleaned stays the default).** No base wins on all four held-out tests; FABDEM is better against GEDI ground and ICESat-2 photons in some scenes and worse against ICESat-2 ground and GEDI tops in others (tables 1, 4). FABDEM cleaned with our nDSM lowers the DSM under canopy (double removal), worse vs GEDI tops. FABDEM stays optional: a FABDEM tile in `demo/terrain/` is used automatically (existing behaviour), or `terrain.build_dtm(..., source=path)`; CC BY-NC-SA 4.0, never committed.
- **Denser levelling with GEDI: no gain on ICESat-2 held-out ground.** Adding GEDI ground to the levelling points, one vote per pass/orbit, Huber + tilt: all are within ±0.3 m of the old median on held-out ICESat-2 ground, and none wins most scenes (table 2). They look better on held-out GEDI ground, but that is the same sensor on both sides, and most of the gain is Silent Valley alone.
- **Levelling barely helps at all.** On held-out ICESat-2 ground, *no levelling* (3.86 m) is not worse than any levelling method; levelling removes the mean bias (+2.6 m -> about 0) but not the per-scene error, because offsets learned on one track do not hold on the next.
- **Shipped: a single-pass guard** (`terrain.LASER_MIN_PASSES = 2`), a safety fix motivated by Silent Valley, not a measured accuracy gain: `laser_correct` no longer shifts the terrain when all ground photons come from one pass. It is identical to the old app wherever 2+ passes level, so it only changes single-pass cases; on the held-out protocol those are the scenes whose levelling half is one pass (Chandigarh, Anantapur, Silent Valley). There it is better on every held-out set except Anantapur vs GEDI tops (+1.05 m); elsewhere it ties. The GEDI gains are almost all Silent Valley, the scene whose GEDI disagreement prompted the guard, so they are not independent evidence; without Silent Valley the guard is close to neutral. In the app it makes the Silent Valley ICESat-2 panel look much worse (table 6). Tables 3 and 6.
- **Silent Valley 47 m: a real local DEM error on one line, wrongly applied to the whole scene** (section 5).

## 1. Bases, no levelling (all points are independent)

| Base | DTM vs held-out ICESat-2 ground | DTM vs held-out GEDI ground | DSM vs held-out ICESat-2 photons (all classes) | DSM vs held-out GEDI top (ground + rh98) | ICESat-2 + GEDI ground, all points (8 scenes) |
|---|---|---|---|---|---|
| glo30_clean | 3.86 [1.58, 6.50] (2.43); wins 2/5 (worst +1.19) | 8.65 [3.17, 14.92] (9.34); wins 4/6 (worst +2.40) | 5.36 [3.31, 7.25] (4.20); wins 5/6 (worst +0.83) | 5.61 [3.41, 7.80] (5.88); wins 5/6 (worst +1.05) | 8.64 [2.64, 18.21] (pooled 5.92), bias +7.38 |
| glo30_raw | 4.96 [2.71, 7.06] (3.07); wins 2/5 (worst +5.21) | 9.78 [3.17, 17.40] (10.47); wins 4/6 (worst +3.66) | 5.67 [3.56, 7.78] (4.82); wins 2/6 (worst +2.66) | 4.51 [3.01, 6.32] (4.76); wins 4/6 (worst +0.82) | 9.34 [3.54, 18.41] (pooled 6.13), bias +8.49 |
| fabdem_raw | 4.15 [2.20, 6.76] (2.66); wins 3/5 (worst +1.84) | 7.45 [2.98, 12.45] (8.07); wins 3/6 (worst +0.81) | 4.97 [3.19, 6.82] (4.03); wins 4/6 (worst +0.37) | 6.55 [3.67, 9.33] (6.88); wins 5/6 (worst +1.20) | 7.58 [2.83, 15.78] (pooled 5.32), bias +5.69 |
| fabdem_clean | 3.82 [1.59, 6.32] (2.96); wins 3/5 (worst +1.05) | 7.39 [3.56, 11.72] (7.99); wins 3/6 (worst +1.62) | 5.40 [3.30, 7.38] (4.07); wins 5/6 (worst +0.77) | 7.77 [4.38, 11.05] (8.09); wins 3/6 (worst +1.33) | 7.61 [2.53, 16.33] (pooled 5.71), bias +5.18 |

Scenes per column: DTM vs held-out ICESat-2 ground: delhi_karol_bagh, barmer_desert_village, anantapur_dryland, shimla_hills, gangtok_hills; DTM vs held-out GEDI ground: chandigarh_sector17, barmer_desert_village, anantapur_dryland, shimla_hills, gangtok_hills, silent_valley_forest; DSM vs held-out ICESat-2 photons (all classes): chandigarh_sector17, delhi_karol_bagh, barmer_desert_village, anantapur_dryland, shimla_hills, gangtok_hills; DSM vs held-out GEDI top (ground + rh98): chandigarh_sector17, barmer_desert_village, anantapur_dryland, shimla_hills, gangtok_hills, silent_valley_forest.
CartoDEM v3 R1: not evaluated, login-gated (Bhuvan). Human steps: india_v2.md section 10; once tiles are in `v2/scenes/cartodem/`, `dtm_compare.py evaluate` adds base `cartodem_raw` automatically.

## 2. Levelling methods on the current base (glo30_clean), held-out points only

| Method | DTM vs held-out ICESat-2 ground | DTM vs held-out GEDI ground | DSM vs held-out ICESat-2 photons (all classes) | DSM vs held-out GEDI top (ground + rh98) |
|---|---|---|---|---|
| none | 3.86 [1.58, 6.50] (2.43), bias +2.58; wins 2/5 (worst +1.19) | 8.65 [3.17, 14.92] (9.34), bias +6.15; wins 4/6 (worst +2.40) | 5.36 [3.31, 7.25] (4.20), bias +1.46; wins 5/6 (worst +0.83) | 5.61 [3.41, 7.80] (5.88), bias -3.07; wins 5/6 (worst +1.05) |
| is2_median | 4.02 [1.88, 6.74] (2.60), bias -0.27; wins 0/5 (worst +0.00) | 9.26 [3.25, 16.65] (9.81), bias -3.97; wins 0/6 (worst +0.00) | 5.89 [3.95, 7.97] (4.27), bias -1.25; wins 0/6 (worst +0.00) | 14.39 [4.15, 29.63] (14.63), bias -13.18; wins 0/6 (worst +0.00) |
| is2_median_min2 | 3.73 [1.44, 6.69] (2.32), bias -0.57; wins 1/5 (worst +0.00) | 8.24 [3.14, 14.25] (8.80), bias +3.90; wins 3/6 (worst +0.00) | 5.30 [3.31, 7.26] (4.09), bias -1.16; wins 2/6 (worst +0.00) | 6.86 [3.58, 10.75] (7.21), bias -5.32; wins 2/6 (worst +1.05) |
| pooled_median | 4.24 [2.08, 6.92] (2.70), bias -0.89; wins 3/5 (worst +0.62) | 8.99 [3.25, 16.50] (9.48), bias -4.34; wins 5/6 (worst +0.01) | 5.96 [4.00, 7.96] (4.35), bias -1.76; wins 4/6 (worst +0.40) | 14.65 [4.28, 30.01] (15.00), bias -13.55; wins 4/6 (worst +1.87) |
| unit_median | 4.19 [1.70, 7.18] (2.59), bias -1.32; wins 2/5 (worst +1.78) | 6.43 [3.08, 10.02] (6.88), bias +0.01; wins 5/6 (worst +0.17) | 5.81 [3.68, 7.85] (4.38), bias -2.05; wins 4/6 (worst +1.27) | 10.24 [4.72, 16.62] (10.72), bias -9.21; wins 3/6 (worst +3.77) |
| huber | 4.18 [1.50, 7.22] (2.54), bias -1.77; wins 1/5 (worst +2.05) | 6.90 [3.22, 10.99] (7.34), bias -0.88; wins 4/6 (worst +0.41) | 5.71 [3.45, 7.93] (4.23), bias -2.37; wins 3/6 (worst +1.11) | 11.21 [4.88, 18.89] (11.75), bias -10.12; wins 3/6 (worst +4.90) |
| huber_min2 | 4.18 [1.50, 7.22] (2.54), bias -1.77; wins 1/5 (worst +2.05) | 6.90 [3.22, 10.99] (7.34), bias -0.88; wins 4/6 (worst +0.41) | 5.71 [3.45, 7.93] (4.23), bias -2.37; wins 3/6 (worst +1.11) | 11.21 [4.88, 18.89] (11.75), bias -10.12; wins 3/6 (worst +4.90) |

All bases × methods: `dtm_compare.json` same_scenes / vs_current. Levelling fits per scene: scenes.*.level_info (Silent Valley huber fitted a 57/-62 m/km tilt from 3 units: tilt fits on 2-3 lines are unstable).

## 3. Per scene: old app vs single-pass guard vs no levelling (MAE, glo30_clean)

| Scene | landscape | guard (ICESat-2 levelling passes >= 2?); levelling units (passes + GEDI orbits) | DTM vs held-out ICESat-2 ground | DTM vs held-out GEDI ground | DSM vs held-out ICESat-2 photons (all classes) | DSM vs held-out GEDI top (ground + rh98) |
|---|---|---|---|---|---|---|
| chandigarh_sector17 | urban | refused; 4 units | – | 3.01 / 2.84 / 2.84 (n 9) | 8.65 / 6.58 / 6.58 (n 354) | 5.65 / 4.04 / 4.04 (n 9) |
| delhi_karol_bagh | urban | shift +2.23; 4 units | 1.01 / 1.01 / 1.36 (n 250) | – | 4.97 / 4.97 / 4.91 (n 1272) | – |
| barmer_desert_village | sparse | shift -0.13; 6 units | 2.20 / 2.20 / 2.21 (n 1595) | 1.98 / 1.98 / 2.09 (n 15) | 3.02 / 3.02 / 2.96 (n 4364) | 1.35 / 1.35 / 1.35 (n 15) |
| anantapur_dryland | sparse | refused; 3 units | 2.96 / 1.49 / 1.49 (n 493) | 1.41 / 1.17 / 1.17 (n 16) | 3.15 / 1.67 / 1.67 (n 493) | 2.44 / 3.49 / 3.49 (n 16) |
| shimla_hills | hilly | shift +4.16; 6 units | 4.66 / 4.66 / 5.85 (n 209) | 13.29 / 13.29 / 15.69 (n 20) | 6.12 / 6.12 / 6.95 (n 1543) | 10.61 / 10.61 / 8.97 (n 20) |
| gangtok_hills | hilly | shift +9.45; 4 units | 9.26 / 9.26 / 8.38 (n 63) | 9.71 / 9.71 / 9.66 (n 15) | 9.42 / 9.42 / 9.07 (n 132) | 14.65 / 14.65 / 8.85 (n 15) |
| agumbe_western_ghats | forested | refused; 1 units | – | – | – | – |
| silent_valley_forest | forested | refused; 3 units | – | 26.15 / 20.44 / 20.44 (n 15) | – | 51.67 / 6.99 / 6.99 (n 15) |

Cells: old / guard / none. Agumbe has neither held-out ICESat-2 nor GEDI points (one pass, no quality GEDI shot); its old 2.3 m single-pass shift is now refused, unverifiable either way.

## 4. Per landscape (mean of the 2 scenes, [min, max]), no levelling

| Landscape | Base | DTM vs all ICESat-2 + GEDI ground: MAE | bias | NMAD |
|---|---|---|---|---|
| urban | glo30_clean | 2.64 [2.60, 2.68] | 1.46 [1.17, 1.76] | 1.28 [0.52, 2.03] |
| urban | glo30_raw | 5.55 [4.98, 6.11] | 4.80 [3.76, 5.84] | 2.30 [2.20, 2.40] |
| urban | fabdem_raw | 3.07 [2.67, 3.47] | 2.02 [1.26, 2.77] | 0.76 [0.33, 1.19] |
| urban | fabdem_clean | 1.85 [1.75, 1.95] | 0.39 [0.20, 0.59] | 1.37 [0.63, 2.11] |
| sparse | glo30_clean | 1.76 [1.44, 2.07] | -1.29 [-1.74, -0.84] | 0.59 [0.57, 0.61] |
| sparse | glo30_raw | 1.80 [1.41, 2.19] | -0.48 [-0.72, -0.25] | 0.87 [0.48, 1.26] |
| sparse | fabdem_raw | 1.82 [1.46, 2.17] | -1.40 [-2.01, -0.79] | 0.52 [0.46, 0.57] |
| sparse | fabdem_clean | 2.29 [1.53, 3.04] | -1.99 [-3.04, -0.94] | 0.65 [0.47, 0.82] |
| hilly | glo30_clean | 8.68 [7.33, 10.04] | 7.92 [5.97, 9.87] | 5.43 [3.33, 7.52] |
| hilly | glo30_raw | 9.45 [7.63, 11.27] | 9.12 [7.06, 11.18] | 4.43 [3.19, 5.67] |
| hilly | fabdem_raw | 6.03 [5.74, 6.33] | 2.98 [2.48, 3.47] | 4.81 [3.39, 6.23] |
| hilly | fabdem_clean | 6.00 [5.80, 6.20] | 2.21 [1.38, 3.05] | 5.75 [3.01, 8.49] |
| forested | glo30_clean | 21.49 [2.67, 40.30] | 21.42 [2.58, 40.26] | 4.62 [0.82, 8.42] |
| forested | glo30_raw | 20.55 [2.41, 38.70] | 20.53 [2.41, 38.65] | 4.53 [0.92, 8.15] |
| forested | fabdem_raw | 19.41 [3.98, 34.85] | 19.15 [3.94, 34.36] | 4.12 [0.35, 7.89] |
| forested | fabdem_clean | 20.31 [3.94, 36.69] | 20.11 [3.86, 36.35] | 4.27 [0.48, 8.06] |

## 5. Silent Valley: what the 47 m offset is

- One ICESat-2 pass (2020-01-17, night 100%, 93% of photons on the strong beam, ATL08 ground h_te_uncertainty median 1.9 m): good-quality data, nothing points to a bad pass.
- Datum is not it: geoid height -91.96 m is applied to ICESat-2 and GEDI alike (both WGS84 ellipsoid); EGM96 vs EGM2008 differ by -0.09 m here; GLO-30 and FABDEM are both EGM2008.
- The track is one line, 148 m east-west by 589 m north-south in a 600 m scene. Along it (south to north, 40 m bins) our terrain minus ground goes +29, +36, +44, +51, +52, +50, +40, +5, +25, +26, +23, +9, +4, -0 m: the southern 300 m (where 85% of the ground photons are) follow a valley floor at 835-845 m that GLO-30 and FABDEM place 20-50 m higher; in the north the DEMs agree to a few metres. 94% of ground photons are > 20 m below our terrain.
- GEDI agrees with ICESat-2 where they meet closely: at the one close crossover (5 m apart, 10 photons) they differ by +1.1 m. The other 2 crossovers rest on one ICESat-2 photon each, 24 m apart: +40.7 m, 25 m apart: -3.3 m (they disagree with each other, so they are weak evidence either way); GEDI shots near the track have our terrain 25 m above GEDI ground (n 3), away from it 13 m (n 33).
- **Cause:** the 30 m radar DEMs fill in a narrow forested valley (Copernicus is a canopy-influenced X-band surface; FABDEM removes part of the canopy but not the valley fill). The pass happens to run along that valley, so its median (+46.6 m) is right on that line and wrong for the slopes, where the DEM is ~13 m high. A constant shift from one line moved the whole scene 47 m down. The terrain there is still ~13 m too high on the slopes without levelling. Unlevelled vs held-out GEDI ground in Silent Valley, MAE: glo30_clean 20.4, glo30_raw 25.6, fabdem_raw 16.8, fabdem_clean 14.8 m: FABDEM helps a little, nothing fixes it.

## 6. End-to-end absolute DSM (DSM = DTM + nDSM), held-out protocol, before vs after this change

| Held-out set | before (old app) | after (guard) | wins | scenes |
|---|---|---|---|---|
| DSM vs held-out ICESat-2 photons (all classes) | 5.89 [3.95, 7.97] (4.27) | 5.30 [3.31, 7.26] (4.09) | 2/6 (worst +0.00) | 6 |
| DSM vs held-out GEDI top (ground + rh98) | 14.39 [4.15, 29.63] (14.63) | 6.86 [3.58, 10.75] (7.21) | 2/6 (worst +1.05) | 6 |
| DTM vs held-out ICESat-2 ground | 4.02 [1.88, 6.74] (2.60) | 3.73 [1.44, 6.69] (2.32) | 1/5 (worst +0.00) | 5 |
| DTM vs held-out GEDI ground | 9.26 [3.25, 16.65] (9.81) | 8.24 [3.14, 14.25] (8.80) | 3/6 (worst +0.00) | 6 |

Without Silent Valley (the scene that motivated the guard; mean over the remaining scenes [95% CI], `dtm_guard_summary.json`):

| Held-out set | before | after | scenes |
|---|---|---|---|
| DSM vs held-out ICESat-2 photons (all classes) | 5.89 [3.95, 7.97] | 5.30 [3.31, 7.26] | 6 |
| DSM vs held-out GEDI top (ground + rh98) | 6.94 [2.65, 11.40] | 6.83 [2.75, 11.61] | 5 |
| DTM vs held-out ICESat-2 ground | 4.02 [1.88, 6.74] | 3.73 [1.44, 6.69] | 5 |
| DTM vs held-out GEDI ground | 5.88 [1.96, 10.31] | 5.80 [1.83, 10.31] | 5 |

The improvement is concentrated in the single-pass cases (Silent Valley above all); in the other scenes the guard changes nothing or (Anantapur vs GEDI tops) is worse. n of scenes is small and CIs overlap: this is a safety fix, not a measured accuracy gain in general.

**What the app user now sees in Silent Valley.** The in-app ICESat-2 panel (validate.compare_icesat2) checks against the only laser line, which is the one line where the DEM is wrong. Before the guard it showed surface MAE 15.5 m (circular: levelled on those photons); after it, surface 36.8 m and terrain 41.3 m (was 9.1 m circular): the terrain is ~47 m too high along that line, as it always was before levelling. At the same time DSM vs held-out GEDI tops goes 51.7 -> 7.0 m on the held-out GEDI orbits across the scene. For every single-pass scene the in-app laser number now describes the unlevelled terrain; `compare_icesat2` adds a `laser_note` saying so.

## Commands

From `SynRS3D/` (no model run except the end-to-end check, under the shared model lock):

```
.venv/bin/python demo/dtm_compare.py --selftest && .venv/bin/python terrain.py
.venv/bin/python demo/dtm_compare.py build      # FABDEM cleaned + GLO-30 rebuild check -> v2/dtm_cache/
.venv/bin/python demo/dtm_compare.py evaluate   # -> v2/dtm_compare.json (~8 min)
.venv/bin/python demo/dtm_compare.py silent     # -> v2/dtm_silent_valley.json
.venv/bin/python demo/dtm_compare.py report     # -> v2/dtm_v2.md
/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock .venv/bin/python demo/dtm_compare.py e2e <scratch dir>   # app.worker on one GeoTIFF -> v2/dtm_e2e_app_run.json
```

App path check without the model: `terrain.laser_correct` on every cached scene (dtm_guard_check.json) shifts the 6 multi-pass scenes exactly as before and refuses the Agumbe (+2.3 m) and Silent Valley (+46.6 m) single-pass shifts, with the reason in `info['laser']['none']`. `python -c "import terrain, app"` passes. Full model run of the app path (`e2e`, `dtm_e2e_app_run.json`): silent_valley_forest done in 152 s, laser: ground photons from 1 ICESat-2 pass (need 2): one line across the scene; its offset (+46.6 m) is not applied; terrain version 2 (still 2: cached scenes keep their old shift until app.TERRAIN_VERSION is bumped).
