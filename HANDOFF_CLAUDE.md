# DepthWizard handoff for Claude Code

Status as of **18 Oct 2026, 15:20 IST**. Read all of this before touching the repo: another Claude Code session may still be editing it (section 7).

---

## 1. The project in one paragraph

**DepthWizard** is team **TerraVista_iitrpr**'s (IIT Ropar) entry for **Smart India Hackathon 2026, problem SIH26175: "Single-View Height Estimation and 3D Flythrough"** (ISRO, Disaster Management theme). From one optical satellite image it:
- estimates per-pixel height above ground (nDSM) with the released **RS3DAda** model (SynRS3D, Song et al., NeurIPS 2024: DINOv2 ViT-L/14 encoder + DPT heads, plus an 8-class land-cover head). There is **no fine-tuning**;
- builds an absolute DSM for GeoTIFFs: DSM = DTM + nDSM, in m above EGM2008. The DTM is Copernicus GLO-30 (or CartoDEM/SRTM), cleaned of roofs and canopy using our nDSM, then levelled to NASA ICESat-2 ground photons. Ground control point (GCP) calibration is optional;
- shows the result in a Three.js 3D flythrough with in-app validation (MAE, RMSE, r against a reference raster, CSV points or ICESat-2);
- adds disaster tools: connected flooding, a rain/river timeline, evacuation routing, helipad and relief-camp siting.

It runs locally and offline after install, with CPU fallback. Windows users start it with `Install.bat` then `DepthWizard.bat`.

The problem statement asks for:
- a relative DSM from PNG/JPG and an absolute DSM from GeoTIFF;
- calibration with a low-res DEM or minimal GCPs;
- a flythrough in which users validate heights against reference data, reporting RMSE, MAE and correlation, stable across urban, sparse, hilly and forested land;
- a standalone deliverable with docs.

## 2. Repo, git and authorship rules

| | |
|---|---|
| Local path | `/Users/prince_13/Documents/iit/sem5/hs202/untitled folder` (note the space: quote it) |
| Remote | `https://github.com/hima1323/terravista-depthwizard` (**private**), branch `main` |
| Collaborators | `hima1323` (owner), `shlok165` (pushed the 15 Oct features) |
| Commits | `047c0c1` Initial commit (hima1323) → `ab086df`, `a0d9007` (shlok165) |

**Authorship rule (the user asked for this explicitly):** Claude must NOT appear as a contributor. Commit as the user, with no `Co-Authored-By: Claude` trailer and no "Generated with Claude Code" line:
```
git -c user.name=hima1323 -c user.email=himanshupatel1323@gmail.com commit -m "..."
```
Do not commit or push unless the user asks. The work in section 7 is deliberately left **uncommitted** for the user to review.

**Upstream clone:** `SynRS3D/` was a clone of `github.com/JTRNEO/SynRS3D`. Its `.git` was moved to `./.synrs3d-upstream.git` (gitignored) so it isn't pushed as a nested repo. To restore it: `mv .synrs3d-upstream.git SynRS3D/.git`.

**.gitignore highlights:**
- Not in git: `SynRS3D/.venv/`, `SynRS3D/pretrain/` (1.4 GB weights), `SynRS3D/data/` (2.1 GB datasets) and `SynRS3D/demo/*/` (big demo data).
- `demo/*.py` IS tracked.
- `demo/benchmark/*.md` and `*_results.json` are tracked; everything else under `demo/benchmark/` is ignored, **including the new `demo/benchmark/v2/` folder**. If the v2 reports should be published, add `!SynRS3D/demo/benchmark/v2/` plus `*.md`/`*.json` rules, or copy the final reports up one level.
- Four local reports are untracked and not yet committed: `SynRS3D/demo/benchmark/{correction,flood_test,icesat2_check,results}.md`. Ask the user.

## 3. Layout

```
README.md, docs/TECHNICAL.md, docs/USER_GUIDE.md      user-facing docs (current numbers = v1, see section 5)
15-10-2026 updates.md                                 changelog style to copy
Install.bat, install.ps1, DepthWizard.bat             Windows setup/launcher
DepthWizard_Deck_Spec.md                              style rules for the SIH deck (fonts, colours, <=5 bullets/card, <=90 chars)
deck_work/                                            SIH pitch deck: TerraVista_DepthWizard_SIH2026_v3.pptx (latest), build_v3.py, renders
SynRS3D/
  app.py            local server (stdlib http): upload, processing queue, results, validation API (port 8000)
  infer_height.py   tiled inference (518 px, 50% overlap, Gaussian blend), 4-flip TTA, flip-spread "uncertainty", land cover
  terrain.py        DTM: glo30_tile, geoid_shift, build_dtm, icesat2_photons (SlideRule, cached), laser_offset, laser_correct
  validate.py       compare vs reference raster / points / ICESat-2; GCP calibration
  web/index.html    entire viewer (three.js bundled in web/vendor)
  models/, utils/   RS3DAda network (DPT_DINOv2), metrics.py (official metrics), geo_func.py
  evaluation.py     upstream official evaluation script
  demo/             benchmark.py (DFC19), gamus_benchmark.py, landscape_benchmark.py (India vs ICESat-2, uses the app over HTTP),
                    icesat2_check.py, flood_test.py, height_correction.py, fetch_scene.py (Esri World Imagery tiles), fetch_maxar.py
  pretrain/RS3DAda_vitl_DPT_height.pth   released weights (not in git)
```

## 4. Machine and environment (this Mac)

- Apple **M3, 8 GB RAM**, 8 cores, macOS (Darwin 25.5). Python venv: `SynRS3D/.venv/bin/python` (3.13, torch 2.14, MPS available).
- Installed: numpy, scipy (≥1.12, has `scipy.optimize.isotonic_regression`), rasterio, pyproj, h5py, opencv-python-headless, pillow, requests, **sliderule 5.6**, python-pptx.
- **Only one RS3DAda process at a time** (8 GB RAM). The running workflow wraps model runs in `/usr/bin/lockf -k -t 14400 <scratchpad>/model.lock <cmd>`. If you run the model while it is active, use the same lock file:
  ```
  /private/tmp/claude-501/-Users-prince-13-Documents-iit-sem5-hs202-untitled-folder/5edadaea-3798-48fe-a262-2baa455d1936/scratchpad/model.lock
  ```
- No LibreOffice (`soffice`) and no `pdftoppm`. **Keynote** is installed (shown as "Keynote Creator Studio"), so slides could be exported through `osascript`. `brew` is available.
- No Earthdata login in `~/.netrc`. GEDI and ICESat-2 should come through SlideRule, which needs no login.
- `gh` is logged in as **hima1323**.
- Teammate shlok165 works on **Windows** (`.venv\Scripts\python`). Their earlier landscape benchmark outputs are not on this Mac.

## 5. Data, caches and current (v1) numbers

**Cached data on this Mac:**
- **GAMUS** (LiDAR nDSM, Washington DC / New York / Philadelphia, CC-BY-4.0, HuggingFace `earthflow/GAMUS`):
  - 150 test tiles listed in `SynRS3D/data/GAMUS_bench.txt`;
  - h5 files in `data/GAMUS/{images,heights,classes}/test/`;
  - cached predictions in `demo/benchmark/gamus/pred/<tile>.npz`, with keys `single`, `tta`, `std` (504×504 centre crop, float16). These have **no land cover**.
  - Class codes: 1 ground, 2 low vegetation, 3 buildings, 4 water, 5 road, 6 trees.
- **DFC2019 JAX/OMA:** `data/DFC19*`; predictions in `demo/benchmark/{pred,full}/*.npz` (`full` has `h`, `u`, `lc`). This data is **inside RS3DAda's adaptation domain, so it is NOT zero-shot**.
- **ICESat-2 photon caches:** `demo/benchmark/icesat2/<bbox>.npz` with `lon`, `lat`, `h` (ellipsoidal), `cls` (ATL08 class), `t`, and `track` = rgt·1e5 + cycle·100 + spot.
- **Processed scenes:** `demo/results/<scene>_{height,dsm,dtm,landcover,uncertainty}.tif` + json for Bengaluru, Chandigarh, Delhi, Guwahati, IIT Ropar, Mumbai, Shimla and the Brazil flood scenes. The 8 landscape-benchmark scenes are not on this Mac.

**v1 numbers (README, 15 Oct; these are what the plan below critiques):**
- **GAMUS vs LiDAR**, 45 tiles, nDSM:

  | Subset | MAE | RMSE | Bias | r |
  |---|---|---|---|---|
  | All | 4.01 | 7.21 | −2.58 | 0.66 |
  | Urban | 2.83 | — | — | 0.85 |
  | Sparse | 0.82 | — | — | — |
  | Forest | 8.96 | — | −8.46 | 0.23 |

- **Indian scenes vs ICESat-2** (`demo/benchmark/landscape_results.md`):

  | Landscape | MAE (m) | r |
  |---|---|---|
  | Urban | 5.33 | — |
  | Sparse | 2.06 | — |
  | Hilly | 6.93 | 0.98 (driven by relief) |
  | Forest | 10.54 | — |

  Silent Valley's terrain is about **+46 m** off before levelling.
- Bias for 10–20 m objects is −9.8 m. The flip-spread "uncertainty" has Spearman ρ = 0.56 against error.
- An earlier attempt at height correction on DFC19 gave no gain (`demo/benchmark/correction.md`).
- Flood scenario test, Porto Alegre 2024: CSI 0.30 → 0.79 (`demo/benchmark/flood_test.md`).

**Deck v3 mismatch (must fix):**
- Slides 3, 4 and 6 claim a "Challenger: DINOv3-SAT + DPT (CHMv2 init), GAMUS-tuned", a "Distilled small model → ONNX Runtime on CPU", "next: ONNX CPU model + Tauri desktop app" and "Fine-tuning fits one cloud GPU".
- None of this is built. The built model is RS3DAda with released weights.

## 6. The plan (from an external review; impact and effort figures are judgement)

**Bottom line:**
- The biggest risk is credibility, not accuracy: the deck doesn't match the software, and the Indian validation is circular because the same ICESat-2 photons level the DSM and validate it.
- The cheapest accuracy gain is terrain.
- After that: calibrated uncertainty, reproducing published numbers, then tall-object bias.
- Fine-tuning comes last.

**Facts already checked:**
- RS3DAda adapts with unlabeled images from Houston (DFC2018), JAX/OMA (DFC2019), GeoNRW and Potsdam. ATL and ARG (Overhead Geopose), Nagoya, Tokyo and Vaihingen are evaluation-only.
- GAMUS is in neither list, so "zero-shot" is valid only for GAMUS and ATL/ARG.
- Published whole-image MAE: RS3DAda ATL 5.67 / ARG 2.01 m; source-only 7.26 / 2.65 m. Training GSD is 0.09–1 m; the authors' demos ran at 0.35 m.
- FABDEM (non-commercial licence) reports forest MAE 5.15 → 2.88 m against Copernicus.

| # | Step | Effort (pd) | Status |
|---|---|---|---|
| 1 | Align deck and docs with the built system; claims register | 0.5–1 | in workflow (runs last) |
| 2 | Evaluation protocol v2 (non-circular, baselines, CIs) | 2–3 | in workflow |
| 3 | Better DTM base + denser laser levelling (FABDEM/CartoDEM, GEDI ground, tilt) | 1.5–2 | in workflow |
| 4 | Calibrated uncertainty (conformal intervals) | 1 | in workflow |
| 5 | Reproduce published RS3DAda numbers on ATL/ARG | 1–1.5 | in workflow |
| 6 | Tall-object recalibration (isotonic) + input-GSD sweep + India transfer check | 1.5–2 | in workflow |
| 7 | Canopy-height model (Meta HighResCanopyHeight) for tree pixels | 3–4 | not started |
| 8 | Drainage-aware flood (HAND via pysheds/WhiteboxTools) + one real Indian event checked against Sentinel-1/NRSC extent (CSI) | 3–5 | not started |
| 9 | ≥5 Indian scenes per landscape, incl. flood plains and coast | 2–3 | not started (optional in workflow) |
| 10 | Cartosat input (pansharpen PAN+MX). **Send the data request on day 1** (the workflow drafts `docs/DATA_REQUEST_cartosat.md`; a human sends it) | 2–3 | blocked on data |
| 11 | 3-minute demo around one real Indian event (Himachal 2023, Teesta GLOF 2023, Wayanad 2024, Joshimath) | 1–2 | not started |
| 12 | Fine-tuning: only RS3DAda-style unsupervised adaptation on Indian tiles with a server GPU, or with ISRO reference DSMs | 7–14 | not started |

**What a reviewer could challenge (the v2 work addresses each):**
- Circular ICESat-2 levelling and validation.
- r on absolute elevation.
- No baselines (raw Copernicus is already a DSM).
- Pixel-pooled statistics.
- 0.5 m pixels against ~11 m (ICESat-2) and ~25 m (GEDI) laser footprints.
- ATL08 classes over roofs.
- Leaf-off GAMUS trees.
- Image and laser dates differ.
- "±" is not calibrated.
- Floor count = height / 3 m.
- "Zero-shot" wording.
- GAMUS may be aerial, not satellite.
- PNG/JPG scale depends on an assumed GSD.
- Silent Valley 46 m.
- Disaster tools are scenarios.
- Licences (Esri/Maxar demo imagery and FABDEM are non-commercial).

**What can be claimed now:**
- Offline on a laptop CPU.
- GAMUS zero-shot MAE, with CI and GAMUS source stated.

**What cannot be claimed yet:**
- Indian absolute accuracy (until re-measured on held-out passes).
- Stability across terrain (only 2 scenes per landscape).
- Calibrated ±.
- DINOv3, CHMv2 or fine-tuning.
- Flood *prediction* (it's a scenario tool).
- Cartosat support.

## 7. Work in progress: a multi-agent workflow (do not collide with it)

The original session `5edadaea-3798-48fe-a262-2baa455d1936` is running workflow **`depthwizard-do-first`**, run `wf_22dec678-a26`, task `wycbw3kf2`. It was restarted at 15:04 after a session restart; the first three agents started over.
- Script: `~/.claude/projects/-Users-prince-13-Documents-iit-sem5-hs202-untitled-folder/5edadaea-3798-48fe-a262-2baa455d1936/workflows/scripts/depthwizard-do-first-wf_22dec678-a26.js`
- Journal and agent transcripts: `~/.claude/projects/-Users-prince-13-Documents-iit-sem5-hs202-untitled-folder/5edadaea-3798-48fe-a262-2baa455d1936/subagents/workflows/wf_22dec678-a26/`. Lines in `journal.jsonl` mark agents as started or finished.
- Progress bar: `python3 /private/tmp/claude-501/-Users-prince-13-Documents-iit-sem5-hs202-untitled-folder/5edadaea-3798-48fe-a262-2baa455d1936/scratchpad/progress.py [--watch 10]`. The scratchpad is wiped when a session restarts. The plan copy the agents read is at `<scratchpad>/NEXT_STEPS_PLAN.md`, and section 6 above is the same content.
- **Resume only works from the original session.** If that session is gone, re-run the unfinished tasks yourself from the specs below. Check first which outputs already exist under `SynRS3D/demo/benchmark/v2/`.

Status at 15:20:

| Phase | Agents | State |
|---|---|---|
| Build | gamus-eval, atl-arg-repro, india-eval | running (restarted 15:04) |
| Build | uncertainty-recal (after gamus-eval), dtm (after india-eval) | queued |
| Verify | one adversarial verifier per track, then a fixer only if critical or major issues are found | queued |
| Integrate | applies cross-track patches; app smoke test | queued |
| Docs | step 1 (below) | queued |
| Check | every number in docs/deck → CLAIMS.md row → JSON | queued |

**While it runs, don't edit files it owns** (listed per task below). Leave `README.md`, `docs/`, `deck_work/` and `18-10-2026 updates.md` alone until the Docs phase has finished.

### Shared conventions (all tasks)

- **Outputs:** new outputs go under `SynRS3D/demo/benchmark/v2/`. Never delete or overwrite existing results or caches.
- **Reproducibility:** every reported number must be written to a JSON file by a script, with the exact command recorded in the `.md` report. Report results that got worse.
- **Blocked work:** if data is login-gated, stop that sub-task and write down what a human must do.
- **Scripts:** a docstring with usage, numpy/stdlib first, and an assert-based `--selftest` that runs offline.
- **Metrics:**
  - e = ours − reference. Report MAE, RMSE, bias = mean(e), median, NMAD = 1.4826·median|e − median e|, Pearson r and the share within ±1 m / ±2 m.
  - "High" = reference > 3 m; use `utils/metrics.py` if it defines this.
  - Bins on reference height: [0,3), [3,10), [10,20), [20,∞).
  - Compute per tile or scene, then take the mean with a 95% percentile bootstrap over tiles or scenes (2000 resamples, `default_rng(0)`). Report the pixel-pooled value next to it, labelled "pooled".
  - r goes on nDSM or detrended heights, never on absolute elevation.
- **Shared library:** `SynRS3D/demo/eval_v2.py` provides metrics, high_metrics, binned_bias, bootstrap_ci, aggregate, building_level, footprint_sample and spearman. Import it.

### Task specs

**A. gamus-eval (step 2, GAMUS side)**
- Owns `demo/eval_v2.py` and `demo/gamus_v2.py`; writes `v2/gamus_v2.{md,json,png}`.
- Steps, all from cached predictions with no model run:
  - Reproduce the v1 headline first: MAE 4.01 on 45 tiles (15 per city).
  - Freeze the 150-tile list by city.
  - Report per-tile mean with CI and pooled values, per city (the leave-one-city-out folds), per landscape, High, binned bias, building-level 90th-percentile errors, and single vs TTA.
  - Add a baseline with nDSM = 0.
  - Split leaf-on and leaf-off trees with an ExG proxy, histogram saved.
  - Report Spearman ρ of `std` against |e| per class.
  - State GAMUS's image source and GSD (aerial or satellite) from the dataset card or paper.
- Partial files from the first run exist (`v2/gamus_old45_pred`, `gamus_old45_predict.log`).

**B. uncertainty-recal (steps 4 and 6)**
- Owns `demo/uncertainty_calibration.py`, `demo/recalibration.py`, `demo/gsd_sweep.py`, `SynRS3D/calibration/*.json`, `infer_height.py`, `app.py` and `web/index.html` (readout text only).
- **Step 4, conformal intervals:**
  - Normalised split-conformal, score = |e| / (spread + c).
  - Mondrian groups use only inference-time quantities: predicted height bin and **predicted** land cover. That means running the model once over the 150 GAMUS tiles under the lock, cached in `v2/cache/`.
  - Score by block. Calibrate on 2 cities, test on the 3rd.
  - Report coverage at 68/90/95% (target ±3 pp), widths and a reliability plot. Do the same at building level.
  - Ship `calibration/conformal.json`, and make the building click show a "90% interval (calibrated on GAMUS, US cities)".
  - Rename the pixel spread to "consistency score" unless calibrated.
- **Step 6a, GSD sweep:** test 0.3, 0.4, 0.5 and 0.7 m on 10 tiles per city. Change the default only if it wins in all 3 cities.
- **Step 6b, isotonic recalibration:** `scipy.optimize.isotonic_regression` for predicted building and predicted tree pixels separately, leave-one-city-out. Ship it only if held-out MAE improves AND |bias| drops in the 10–20 and >20 m bins in all 3 folds.
- **Step 6c, India transfer check:** ICESat-2 roof photons inside OSM footprints for the Indian scenes in `demo/results`. Fewer than 30 buildings means inconclusive.

**C. atl-arg-repro (step 5)**
- Owns `demo/geopose_benchmark.py` and `data/geopose/`; writes `v2/geopose_*`.
- Find the Overhead Geopose ATL/ARG test RGB + AGL data and SynRS3D's split. Sources to try: upstream README links, the paper appendix, DrivenData, IEEE DataPort, HF mirrors. Limits: 45 minutes of searching and ≤15 GB.
- If the data is login-gated, write down the human steps and try Nagoya, Tokyo or Vaihingen instead.
- Run both `evaluation.py` and DepthWizard's own pipeline, and compare against 5.67 / 2.01.
- If our pipeline is worse, ablate GSD, normalisation, tiling, crop, nodata and fp16, then write an `infer_height.py` patch as a follow-up.
- Partial files exist (`demo/geopose_benchmark.py`, `v2/cache/geopose`, `v2/geopose_*.log`).

**D. india-eval (step 2, India side)**
- Owns `demo/india_eval_v2.py`, `validate.py` and `demo/fetch_scene.py` (additive changes only); writes `v2/india_*` and `v2/scenes/`.
- Rebuild the 8 landscape scenes from `REGIONS` in `demo/landscape_benchmark.py` without the app server, reusing app.py's processing functions. Roughly reproduce the v1 numbers first.
- Look up each scene's Esri imagery date and apply a ±12-month laser filter.
- **Pass split:** group by rgt+cycle into levelling and validation passes, never both. Report three variants: no levelling, held-out, and the old circular one.
- Add **GEDI L2A through SlideRule** (quality_flag = 1, `elev_lowestmode` for ground, rh98, beam type).
- Baselines at the same points: raw GLO-30, our DTM only, FABDEM (public source, non-commercial, don't commit it) and CartoDEM (probably login-gated, so report it).
- Error budget: DTM vs ground; nDSM vs laser-only height; DSM vs all photons.
- Footprint-scale sampling plus single-pixel values. Use OSM footprints to label roof photons.
- Per-landscape mean and range (2 scenes is too few for a CI).
- Record Silent Valley's photon statistics.
- Add the held-out pass split and footprint sampling to `validate.compare_icesat2`, backward-compatible.

**E. dtm (step 3, after D)**
- Owns `terrain.py` and `demo/dtm_compare.py`; writes `v2/dtm_*`.
- Compare DTM bases on held-out ground points: Copernicus cleaned (current), FABDEM, FABDEM cleaned, CartoDEM.
- Level with ICESat-2 levelling passes plus GEDI ground: robust fit, offset + tilt only with ≥3 passes.
- Find the cause of the Silent Valley 46 m offset.
- Integrate the winner only if it wins on held-out points in most scenes. Keep signatures backward-compatible, with FABDEM optional and Copernicus as fallback.

**F. Integrate:** apply the cross-track patches that are backed by measurements. Run imports, self-tests and one end-to-end GeoTIFF run, start the app and curl it, then check that the JS in `web/index.html` parses.

**G. Docs (step 1)**
- Owns `README.md`, `docs/TECHNICAL.md`, `docs/USER_GUIDE.md`, the new `docs/CLAIMS.md`, the new `docs/DATA_REQUEST_cartosat.md`, the new `18-10-2026 updates.md`, and the new `deck_work/build_v4.py` → `TerraVista_DepthWizard_SIH2026_v4.pptx`. v3 stays untouched.
- `CLAIMS.md`: one row per claim (claim | test set | n | metric | value with CI | source file | status), plus a "not yet validated" list and a licences table.
- Deck v4: remove or mark as planned the DINOv3, CHMv2, ONNX, Tauri and fine-tuning claims. Make every number trace to `CLAIMS.md`. Don't call DFC2019 zero-shot. Label the flood CSI as a scenario. Follow `DepthWizard_Deck_Spec.md` section 0, and render through Keynote to check for overflow.
- The data request is a draft only; never send it.

**H. Check:** every number in the docs and deck must match a `CLAIMS.md` row and its JSON. Fix mismatches in place.

## 8. Gotchas

- The path contains a space; always quote it.
- Run Python from `SynRS3D/` (`import app, infer_height, terrain, validate`).
- `demo/landscape_benchmark.py` expects the app running on `127.0.0.1:8000` and uses Windows paths in its docstring.
- ICESat-2 `h` is ellipsoidal. Convert to EGM2008 with `terrain.geoid_shift`. GLO-30 is already EGM2008.
- Only one model process at a time on 8 GB (use the lock). Running two ViT-L processes will swap.
- `demo/benchmark/v2/` is gitignored (section 2).
- The scratchpad under `/private/tmp/...` is wiped when a session restarts. Keep anything important in the repo.

## 9. Open questions for the user (ask, don't guess)

1. SIH evaluation dates and deadline, and how many teammates or GPUs are available. This decides whether steps 7–12 fit.
2. Whether to commit and push the v2 work and the 4 untracked benchmark reports, and whether `demo/benchmark/v2/` reports should be tracked.
3. Who sends the Cartosat/CartoDEM request (`docs/DATA_REQUEST_cartosat.md` once drafted).
4. Whether any Indian reference data (LiDAR, CartoDEM access, Bhuvan login) is available. It changes steps 3, 9, 10 and 12.
