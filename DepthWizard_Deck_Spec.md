# DepthWizard (SIH26175): Deck Update Spec for Claude Code

> **How to use:** put this file in the same folder as `TerraVista_DepthWizard_SIH2026_WITH_GRAPHS.pptx`, open Claude Code there, and say:
> **"Follow DepthWizard_Deck_Spec.md exactly and build the updated deck."**
>
> **Revision note:** the DEM-calibration citation is now **Prompt2DEM** (arXiv 2507.09681), which uses a coarse 30 m SRTM DEM as its prior. Prior2DSM (arXiv 2604.02009) was dropped: it fills incomplete or outdated high-resolution DSMs, and its abstract does not say it works from a coarse DEM like CartoDEM. The Prompt2DEM numbers below were checked against the paper (Table 3).

---

## 0. Instructions for Claude Code

**Task:** update `TerraVista_DepthWizard_SIH2026_WITH_GRAPHS.pptx` and save it as `TerraVista_DepthWizard_SIH2026_v2.pptx`.

**Rules**
1. Edit a **copy** of the existing file with `python-pptx`. Keep the **6-slide SIH template**: TerraVista logo (top-left), SIH logo (top-right), title placeholders, blue footer bar, slide numbers, 16:9 (13.333 × 7.5 in).
2. Keep the existing look:
   - Titles: Aptos Display, 25 pt, bold, `#17273A`
   - Body: Aptos, 10.5–12 pt, `#24313F`
   - Card header bars: rounded rectangles, 0.33 in tall, white bold text, 11.8–12.8 pt
   - Card fill `#F4F7FB`, border `#D5DCE7`
   - Palette: blue `#2068AA` · teal `#228989` · green `#45885C` · orange `#D2742D` · footer `#0070C0` · grey `#5C6878`
3. **Reuse existing shapes** and change their text; don't rebuild slides. Only slide 3's pipeline strip needs one more box (resize all evenly).
4. **Charts:** native PowerPoint charts (python-pptx chart API), 8–9 pt axis text, 10 pt bold chart title.
   - Replace **all** existing charts marked "Est." or "Projected". They show invented numbers that judges can challenge.
   - Every chart gets a **source line** underneath (8 pt, grey `#5C6878`). Leave about 0.2 in for it and shrink the chart height if needed.
   - Anything not yet measured must say **TARGET**.
5. **No text overflow.** Use at most 5 bullets per card and at most 90 characters per bullet. Turn on word wrap. If text still doesn't fit, shrink the font by at most 1 pt; after that, shorten the wording but keep the meaning and any numbers.
6. Add the **speaker notes** from section 7 to each slide.
7. **Verify before finishing:**
   - Convert to PDF with `soffice --headless --convert-to pdf`.
   - Render PNGs with `pdftoppm -r 80 -png`.
   - Look at every slide, fix overlaps and overflow, then report what changed.
8. Do **not**:
   - mention Fast3R
   - say CHMv2 predicts building heights (it is a tree-canopy model)
   - cite Prior2DSM for CartoDEM / coarse-DEM calibration (use Prompt2DEM)
   - add any number that isn't in the fact sheet (section 8)

---

## 1. Slide 1: Title (keep as is)

- SMART INDIA HACKATHON 2026
- **Problem Statement ID:** SIH26175
- **Problem Statement Title:** Single-View Height Estimation and 3D Flythrough
- **Theme:** Disaster Management
- **PS Category:** Software
- **Team ID:** `[fill in registered Team ID]` ← still a placeholder
- **Team Name (Registered on portal):** TerraVista_iitrpr
- **Idea Title:** DepthWizard

---

## 2. Slide 2: IDEA TITLE

**Subtitle (19 pt bold):**
DepthWizard: One Satellite Image → Measured 3D Heights You Can Fly Through and Verify

**Flow strip:** 5 boxes, keep the existing colours left to right.

| Header | Box text |
|---|---|
| INPUT | PNG / JPG / TIFF / GeoTIFF |
| AI HEIGHT | Height above ground, every pixel |
| CALIBRATE | CartoDEM-guided real metres |
| VERIFY | ICESat-2 laser check + click-to-measure |
| FLY & ACT | 3D flythrough + flood / slope tools |

**Card: HOW IT MEETS THE PROBLEM STATEMENT** (blue header)
- ✓ One optical image in: no stereo pair, LiDAR or InSAR needed
- ✓ PNG/JPG → relative DSM · GeoTIFF → absolute DSM in metres
- ✓ Upload → auto-process → fly through the reconstructed 3D terrain
- ✓ Click any building: estimated height ± uncertainty vs reference
- ✓ Complete suite: web app + offline desktop app, source code, docs

**Card: WHY DEPTHWIZARD IS DIFFERENT** (orange header)
- Satellite-trained height model; generic depth AI fails on top-down images
- Two accuracy boosters: CartoDEM calibration + ICESat-2 laser correction
- Trust layer: per-pixel uncertainty + live error report in the viewer
- Bird's-eye → street-level view in one click (Sat3DGen)
- Disaster tools on top: flood depth, landslide slopes, affected buildings

**INNOVATION & UNIQUENESS**: 4 chips, keep their positions:
`Satellite-native height AI` · `Real metres from CartoDEM` · `Laser-verified (ICESat-2)` · `Bird's-eye → street flythrough`

---

## 3. Slide 3: TECHNICAL APPROACH

**Subtitle:** Pipeline: Pixels → Height → Metres → Verified 3D

**Pipeline strip:** 6 boxes plus the small OUT box. Spread them evenly from x = 0.65 in to x = 11.7 in, with arrows between.

| Header | Box text |
|---|---|
| INPUT | RGB image (PNG / JPG / TIFF) |
| PREPROCESS | Read GSD + CRS · 512-px overlapping tiles |
| AI MODEL | RS3DAda (ViT-L + DPT) · challenger: DINOv3-SAT |
| HEIGHT | Height above ground + uncertainty map |
| CALIBRATE | CartoDEM / SRTM prior → metres (Prompt2DEM) |
| VERIFY | ICESat-2 correction + error report |
| OUT | DSM + 3D |

**Card: AI / ML** (blue)
- RS3DAda (NeurIPS 2024, MIT): released weights, trained for buildings + terrain
- Challenger: DINOv3 satellite ViT-L + DPT head (init. CHMv2), fine-tuned on GAMUS
- Keep whichever wins on the GAMUS test set (MAE / RMSE)
- Test-time augmentation → uncertainty map · Gaussian tile blending
- Distilled small model → ONNX Runtime on CPU

**Card: GEOSPATIAL** (teal)
- GDAL · Rasterio · PyProj; GeoTIFF float32 in and out
- DSM = terrain (CartoDEM / SRTM / Copernicus GLO-30) + predicted height
- Prompt2DEM (2025): coarse 30 m DEM prior + RGB → 30 cm metric heights
- ICESat-2 ATL03 / ATL08 laser points: correct bias + report RMSE
- One vertical datum for all sources (ICESat-2 heights are ellipsoidal)

**Card: APPLICATION & 3D VIEWER** (green)
- React + Three.js viewer; GLB mesh + terrain tiles
- Free-fly (WASD + mouse), draw-a-path auto-fly, MP4 export
- Street mode: Sat3DGen (ICLR 2026) street-level mesh
- Click-to-measure: height ± uncertainty at any point
- FastAPI + CLI; Tauri desktop app runs fully offline

**Charts row:** replace the 3 existing charts in the same positions.

**Chart A**
- Type: clustered column, teal
- Title: "Published: our calibration stages cut error (MAE %)"
- Bars:
  - Prompt2DEM vs SRTM prior (vegetated), "up to": **18**
  - ICESat-2 fix on RS3DAda: **30.9**
  - ICESat-2 fix on Depth Anything V2: **24.1**
- Source line: "Rafaeli et al., arXiv 2507.09681 (2025) · Song et al., ISPRS J. P&RS vol. 232 (2026)"

**Chart B**
- Type: column. Colour the first two bars orange and the third green.
- Title: "Published: generic depth AI struggles on satellites (DFC2019 MAE, m)"
- Bars:
  - Depth Anything V2 (zero-shot): **4.59**
  - VGGT: **4.11**
  - Satellite-fine-tuned (Sat3R): **2.82**
- Source line: "Sat3R, arXiv 2605.07264 (2026), multi-view benchmark"

**Chart C**
- Type: clustered column (MAE blue, RMSE orange)
- Title: "Published: error depends on terrain (m)"

  | Terrain | MAE | RMSE |
  |---|---|---|
  | Bare | 2.13 | 2.70 |
  | Urban | 2.38 | 3.26 |
  | Vegetated | 4.65 | 5.93 |

- Source line: "Prompt2DEM, arXiv 2507.09681 (2025) → we report accuracy per terrain type"

**Bottom tagline (16 pt bold):**
Built for both halves of the score: DSM accuracy (RMSE / MAE by terrain) + Rendering & UX (flythrough, measuring, offline)

---

## 4. Slide 4: FEASIBILITY AND VIABILITY

**Subtitle:** Built on Released Models, Free Data and Offline-Ready Software

**Card: FEASIBILITY**
- Working baseline on day 1: RS3DAda weights + inference script are public (MIT)
- Training data ready: GAMUS (PS-recommended), DFC2019/US3D, SynRS3D (69k synthetic images)
- Free terrain + truth data: CartoDEM (Bhuvan), SRTM, Copernicus GLO-30, ICESat-2
- Fine-tuning fits one cloud GPU; frozen-backbone option for low budgets

**Card: VIABILITY**
- Modular: swap the height model without touching calibration or the viewer
- Standard outputs (GeoTIFF DSM, GLB) open in QGIS, ArcGIS and Bhuvan workflows
- Offline: distilled ONNX model + Tauri desktop app + bundled demo data
- License-clean: MIT / Apache / DINOv3 license; no non-commercial weights

**CHALLENGE → RISK → MITIGATION:** reuse the 5 existing rows.

| Challenge | Risk | Mitigation |
|---|---|---|
| New image resolution (GSD) | Wrong height scale | Read GSD from metadata · resample · multi-resolution fine-tuning |
| One image can't see ground level | Heights off in metres | CartoDEM-guided calibration + ICESat-2 correction |
| Few tall buildings in training data | Tall buildings under-estimated | Oversample tall buildings · report error by height band |
| Tilted (off-nadir) images | Leaning buildings, shifted roofs | Off-nadir training data (US3D) · warning in UI |
| No GPU / no internet in the field | Tool unusable | ONNX CPU model · offline desktop app |

**Right-side chart:** replace the pie chart.
- Type: horizontal bar, blue. Set `reverse_order=True` on the category axis so the best model is on top.
- Title: "Model shortlist (team assessment, /10)"
- Bars, top to bottom:

  | Model | Score |
  |---|---|
  | RS3DAda | 9 |
  | DINOv3-SAT + GAMUS fine-tune | 8.5 |
  | TerraHeight-S | 7.5 |
  | BuildMamba (no weights yet) | 6.5 |
  | Depth2Elevation (no code) | 6 |
  | HTC-DC Net | 5.5 |
  | CHMv2 as-is (trees only) | 3 |

- Source line: "Score = fit to PS + public weights + reported accuracy + effort. Multi-view models (need several images) excluded."

---

## 5. Slide 5: IMPACT AND BENEFITS

**Subtitle:** From One Image to Faster, Verifiable Disaster Decisions

**Centre box:** DEPTHWIZARD · "Measured 3D from one image"

**Four quadrant cards**
- **DISASTER MANAGEMENT:** Flood-depth simulation · landslide-prone slopes · affected-building counts
  - Small italic line: *Example: raise water to 3 m → see which buildings go under*
- **URBAN PLANNING:** Building heights and volumes · 3D base maps where no LiDAR exists
- **REMOTE SENSING (ISRO):** More value from existing optical archives · fresh 3D from every new image, no stereo tasking
- **FIELD RESPONSE:** Fly-through + street view for team briefings · line-of-sight / viewshed for relief staging

**Mini-flow (centre):** keep the 3 steps.
1. HEIGHT MAP: per pixel
2. VERIFIED 3D: metres + ICESat-2
3. DECISION: flood / slope

**Strip under the mini-flow:** One optical image → measured, checked terrain context

**Bottom boxes**
- **ECONOMIC:** Reuse existing images instead of new LiDAR/stereo surveys for every event
- **SOCIAL:** Faster 3D damage picture; works offline in the field
- **ENVIRONMENTAL:** Terrain, slope and canopy context for flood, landslide and forest monitoring

**Footer banner:** ONE SATELLITE IMAGE → VERIFIED 3D → FASTER DECISIONS

---

## 6. Slide 6: RESEARCH AND REFERENCES

**Subtitle:** Research Foundation: 2024–2026 Models, Open Data, Independent Validation

**Card: MODELS & METHODS**
- RS3DAda / SynRS3D: Song et al., NeurIPS 2024 (primary model)
- DINOv3 (Meta, 2025) + CHMv2 (Scientific Data, 2026): satellite backbone
- Prompt2DEM: Rafaeli et al., 2025, SRTM-prior metric heights (30 m → 30 cm)
- ICESat-2-guided correction: Song, Chen & Yokoya, ISPRS J. 2026
- Sat3DGen (ICLR 2026) · Benchmarks: BuildMamba 2026, Depth2Elevation (TGRS 2025), HTC-DC Net

**Card: DATASETS / VALIDATION / OFFICIAL SOURCES**
- GAMUS (recommended in PS) · DFC2019 / US3D · SynRS3D
- CartoDEM (ISRO Bhuvan) · SRTM 30 m · Copernicus DEM GLO-30
- ICESat-2 ATL03 / ATL08 (NASA Earthdata)
- ISRO Bhoonidhi / Bhuvan imagery · ISPRS Potsdam / Vaihingen
- Metrics: RMSE and MAE per terrain type and per height band

**Charts (measured, replacing the TARGET chart):** two charts side by side in the old chart's area.
Remove the decorative "EVIDENCE → DATA → …" header line to give them room.

- **Left:** "MEASURED: RS3DAda error vs LiDAR by land cover (m)", MAE + RMSE for Buildings / Trees / Ground / Water.
  Source line: "Our run: released RS3DAda, 200 DFC2019 test tiles (Jacksonville + Omaha). Official metric MAE 2.22 m / RMSE 3.83 m."
  (If the learned height correction passes the other-city test, this chart instead shows MAE by true-height band, raw vs corrected.)
- **Right:** "MEASURED: where our ± is high, real error is high (MAE, m)", real MAE for five equal groups of pixels sorted by predicted ±.
  Source line: "Same 200 test tiles; pixels split into 5 equal groups by predicted ± (spread of 4 flipped predictions). Rank correlation 0.62."

**Bottom chain:** 4 boxes, keep the layout.
MODELS: RS3DAda + DINOv3 → DATASETS: GAMUS + SynRS3D → TERRAIN REFERENCE: CartoDEM / SRTM / GLO-30 → VALIDATION: RMSE / MAE + ICESat-2

---

## 7. Speaker notes (add to each slide's notes)

**Slide 1:** We are TerraVista from IIT Ropar. Our idea, DepthWizard, answers SIH26175: single-view height estimation and 3D flythrough for disaster management.

**Slide 2:** One satellite image goes in and measured heights come out. Example: we upload a GeoTIFF of a flooded town. The model estimates every building's height above ground. CartoDEM turns that into real elevation in metres, and ICESat-2 laser points check it. The user flies through the town, clicks a building and sees its height with an uncertainty range. PNG/JPG inputs give relative heights; GeoTIFF inputs give metres, as the PS asks.

**Slide 3:** RS3DAda is our main model because it is released, trained for buildings and terrain, and a 2026 ISPRS study cut its error by about 31% with ICESat-2 correction. In parallel we fine-tune a DINOv3 satellite backbone on GAMUS and keep whichever scores better. Chart A: published gains from our two calibration stages. Prompt2DEM shows a coarse 30 m DEM plus a single image beats the DEM alone, by up to 18% MAE on vegetated terrain, which is the same idea as our CartoDEM step. Chart B: generic depth models do poorly on satellite images, which is why we use satellite-trained ones. Chart C: error changes with terrain, so we report accuracy per terrain type.

**Slide 4:** Everything we depend on is already public: model weights, GAMUS, CartoDEM, ICESat-2. Our biggest risks are wrong scale and wrong ground level; calibration plus laser correction handles both. The desktop app runs offline on a CPU for field teams.

**Slide 5:** Example: in the flood tool, raise the water to 3 m and the viewer highlights buildings below that level. Planners get building heights where no LiDAR exists, and ISRO gets more value from existing optical images.

**Slide 6:** Every method here is published and cited, and the charts are our own measurements: the released RS3DAda model on 200 DFC2019 test tiles against LiDAR, MAE 2.22 m, RMSE 3.83 m. Where our ± is highest the real error is about 7 times larger than where it is lowest, so the viewer can flag heights not to trust. Tall buildings are under-estimated, by about 8 m above 20 m. A simple global correction learned on separate tiles did not fix that in our tests, so we will correct heights with local ICESat-2 laser measurements, as the 2026 ISPRS study did. We will also repeat the measurement on GAMUS.

---

## 8. Fact sheet: the only numbers allowed on the slides

| Claim | Value | Source |
|---|---|---|
| RS3DAda weights + inference script public, MIT license | ViT-L DPT height model | https://github.com/JTRNEO/SynRS3D |
| SynRS3D synthetic training set | 69,667 images, GSD 0.05–1 m | https://arxiv.org/abs/2406.18151 |
| ICESat-2 correction on RS3DAda | MAE −30.9% | Song, Chen, Yokoya, ISPRS J. P&RS vol. 232, Feb 2026: https://www.sciencedirect.com/science/article/abs/pii/S0924271625004885 · arXiv 2505.06905 |
| ICESat-2 correction on Depth Anything V2 | MAE −24.1% | same |
| Prompt2DEM: coarse DEM prior → metric heights | SRTM 30 m prior + 0.6 m NAIP RGB → 30 cm DEM; MAE vs SRTM alone: vegetated 5.66 → 4.65 m (**−18%**), urban 2.77 → 2.38 m, bare 2.22 → 2.13 m. Tested in the USA, not India | Rafaeli, Svoray, Nahlieli, arXiv 2507.09681 (Table 3) · https://osherr1996.github.io/prompt2dem_propage/ |
| Prompt2DEM MAE / RMSE (m): bare, urban, vegetated | 2.13/2.70 · 2.38/3.26 · 4.65/5.93 (checked against Table 3) | arXiv 2507.09681 |
| CHMv2 is a canopy (tree) height model, DINOv3 satellite ViT-L + DPT | trained on airborne-LiDAR canopy heights | https://huggingface.co/facebook/dinov3-vitl16-chmv2-dpt-head · arXiv 2603.06382 |
| DFC2019 MAE (m): DA-V2 zero-shot / VGGT / Sat3R | 4.59 / 4.11 / 2.82 | Sat3R, arXiv 2605.07264 |
| Depth2Elevation on GAMUS | MAE 1.99 m, RMSE 3.49 m | IEEE TGRS 2025 (numbers seen via https://huggingface.co/benfox6515/TerraHeight-S; **verify in the paper before presenting**) |
| BuildMamba RMSE vs HTC-DC Net | DFC19 1.06 vs 1.23 m · DFC23 1.77 vs 2.59 m; no code | arXiv 2603.08523 |
| Sat3DGen: single satellite image → street-level 3D, MIT, weights on HF | — | https://github.com/qianmingduowan/Sat3DGen |
| PS scoring | DSM accuracy 50% · Rendering & UX 50% | SIH26175 statement |
| **Measured by us:** RS3DAda on DFC2019 vs LiDAR | MAE **2.22 m** / RMSE **3.83 m** (4-flip TTA); single pass 2.30 / 3.94 m; pixels > 3 m: 4.90 / 6.20 m | 200 random test tiles (100 Jacksonville + 100 Omaha), repo's own metric code, 504 px centre crop; `SynRS3D/demo/benchmark/results.md` |
| **Measured:** error by land cover (MAE / RMSE, pixel-pooled) | buildings 4.83 / 9.36 · trees 4.82 / 6.28 · ground 0.75 / 1.97 · water 0.42 / 1.99 m | same run |
| **Measured:** tall structures under-estimated (mean bias) | −5.2 m for 10–20 m, −8.0 m above 20 m; trees −3.9 m | same run |
| **Measured:** uncertainty (±) flags error | real MAE 0.70 m in the lowest-± fifth of pixels → 5.14 m in the highest (≈7×); rank correlation 0.62 | same run |
| **Measured (for Q&A, not on slides):** a global height re-mapping does not fix tall buildings | learned on 200 DFC2019 training tiles: in-domain MAE 2.22 → 2.11 m, but bias above 20 m worsens −8.0 → −12.7 m; learned in one city, tested in the other: 1.73 → 1.73 m and 2.70 → 2.73 m (no gain) | `SynRS3D/demo/benchmark/correction.md`. Why: among pixels predicted "12 m" most really are ~12 m, so any average-based curve pulls the rare towers further down. Tall buildings need local measured heights in the same scene (ICESat-2), as in Song et al. 2026 |
| **Measured:** RS3DAda on GAMUS (PS-recommended) vs LiDAR, released model with **no GAMUS training** | 150 test tiles (50 each: Washington DC, New York, Philadelphia), 504 px centre crop, official metric: MAE **3.88 m** / RMSE **5.56 m** (4-flip TTA; single pass 3.94 / 5.67); MAE by city DC 5.08 · New York 4.69 · Philadelphia 1.86 m. By land cover (MAE / RMSE, m): ground 0.69 / 2.15 · road 1.65 / 4.33 · buildings 3.75 / 6.18 · trees 10.10 / 12.93 (trees read 9.5 m too low; in the DC / New York photos many trees are leafless). Depth2Elevation's 1.99 / 3.49 m is a model *trained* on GAMUS, so not a like-for-like comparison | `SynRS3D/demo/benchmark/gamus_results.md` · data https://huggingface.co/datasets/earthflow/GAMUS (CC-BY-4.0) |
| **Measured:** flood map on the May 2024 Porto Alegre flood (CSI vs the IPH-UFRGS LiDAR flood map for 6 May 2024, water 5.3 m; 1 = perfect) | 6 test areas of 320 m: raw GLO-30 0.18 · ours (buildings removed with our heights) 0.47 · FABDEM 0.48. The 4 areas with ICESat-2 data: raw 0.20 · ours 0.30 · FABDEM 0.32 · **ours + ICESat-2 levelling 0.79** (downtown 0.08 → 0.54; flood-edge areas 0.00 → 0.71 and 0.02 → 0.92) | `SynRS3D/demo/benchmark/flood_test.md` · reference https://www.ufrgs.br/iph/mapa-da-inundacao-em-porto-alegre/ · pre-flood images Maxar Open Data (CC BY-NC 4.0) |
| **Measured:** ground height at 14 surveyed flood-edge points (true value = water level 5.29 m) | mean abs error: raw GLO-30 3.73 m · ours 1.74 m · FABDEM 2.13 m; laser-levelled 1.42 m (8 points with laser data). After levelling, the water level that best reproduces the real flood is within 0.5 m of the gauge reading | same; IPH-UFRGS technical note (29 field points, 5 May 2024) |
| **Measured:** terrain vs NASA ICESat-2 laser ground points | photons in 10 of 14 demo scenes; in the 9 with ≥ 50 ground photons the typical offset (median of |bias|) is 2.8 m for raw GLO-30 and 1.6 m for ours; spread (NMAD) 1.7 → 0.6 m. The app then shifts each terrain by its measured offset (Indian scenes: Bengaluru, Chandigarh, Delhi, IIT Ropar, Mumbai) | `SynRS3D/demo/benchmark/icesat2_check.md` (ATL03 + ATL08 via NASA SlideRule) |
| **Built in the prototype** (the ✓ items on slides 2–3) | offline web app (three.js bundled) · free-fly WASD · draw-a-path auto-fly · street-level camera · fly-through saved as MP4 · flood tool with building counts · landslide slope layer (BIS IS 14496-2 classes) · GLB + GeoTIFF export · ICESat-2 levelling · uncertainty map. **Not built (TARGET):** Tauri desktop app, ONNX CPU model, Sat3DGen street mesh, DINOv3-SAT challenger, Prompt2DEM, tested CartoDEM input | `SynRS3D/web/index.html`, `SynRS3D/app.py`, `SynRS3D/terrain.py` |
| **Not ours, do not quote:** "DepthWizard M1" on GAMUS | MAE 3.31 m / RMSE 6.28 m, reported in a public repo for a model with a Depth Anything V2 prior; not produced by this pipeline | https://github.com/jayyyyqwq/resheightnet |
| ~~Prior2DSM~~ (**not used**) | Up to −46% RMSE, but it completes **incomplete/outdated high-res DSMs**; not shown to work from a coarse DEM. Do not cite for CartoDEM calibration | arXiv 2604.02009 |

---

## 9. Team to-do before submitting
- [ ] Fill in the **Team ID** on slide 1.
- [ ] Check the Depth2Elevation numbers in the original paper.
- [x] Slide 6 TARGET chart replaced with measured results (DFC2019, 200 test tiles).
- [x] Repeat the measurement on GAMUS (PS-recommended) and against ICESat-2 over Indian cities (v3 deck).
- [x] Optional: if a viewer prototype exists, swap one chart for a screenshot of the flythrough (judges score UX at 50%) (v3, slide 3).
- [ ] Add CartoDEM tiles from Bhuvan for the Indian demo cities (drop-in supported, not yet tested).
