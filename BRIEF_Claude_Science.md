# DepthWizard: project brief

## The task
DepthWizard is team TerraVista's (IIT Ropar) entry for Smart India Hackathon 2026, problem **SIH26175, "Single-View Height Estimation and 3D Flythrough"**. The problem was set by ISRO under the Disaster Management theme. It asks for the following from **one optical satellite image** (PNG, JPG or GeoTIFF):

- a **relative DSM** for PNG/JPG and an **absolute DSM** (metres above sea level) for GeoTIFF;
- scale calibration from a low-resolution DEM or a few ground control points (GCPs);
- a 3D flythrough in which users check heights against reference data (RMSE, MAE, correlation), with results that hold across urban, sparse, hilly and forested land;
- a standalone, offline deliverable with documentation.

## What is built (working, local, offline)

**1. Height model.** We use **RS3DAda** (SynRS3D, Song et al., NeurIPS 2024): a DINOv2 ViT-L/14 encoder with DPT heads, plus an 8-class land-cover head.
- It runs on the **released weights with no fine-tuning**.
- Inference is tiled (518 px tiles, 50% overlap, Gaussian blending) with 4-flip test-time augmentation.
- The output is height above ground (nDSM) for every pixel.

**2. Absolute DSM** = DTM + nDSM, in metres above EGM2008.
- The DTM starts from Copernicus GLO-30 (or CartoDEM / SRTM), with roofs and canopy removed using our nDSM and land cover.
- It is then levelled to **NASA ICESat-2** ATL03/ATL08 ground photons, fetched through SlideRule.
- Levelling is refused when the photons come from a single laser pass. One pass is a single line, so a local DEM error along it would shift the whole scene.
- **GCP calibration:**
  - 1 point fixes the level;
  - 2 or more add a height scale;
  - 4 or more also correct a tilt.

  It reports a leave-one-out error, and with control points PNG/JPG can be made absolute too.

**3. In-app validation.**
- Users compare against a reference raster (DSM, nDSM or DTM, in any coordinate system or vertical datum), a CSV of surveyed points, or ICESat-2.
- It reports MAE, RMSE, r, bias, NMAD and the share within ±2 m, broken down by landscape, terrain and height band.
- For ICESat-2 it adds a **held-out-passes** check: levelling uses some passes and validation uses the others.

**4. Uncertainty.**
- Building blocks carry a 90% interval from split-conformal calibration on GAMUS LiDAR.
- The 4-flip spread is shown as a "consistency score". It is **not** an error bar.

**5. Disaster tools.** These are labelled as scenarios, not forecasts.
- **Before:** slopes in BIS IS 14496 classes, and how much ground and how many buildings each water rise would reach.
- **During:** a connected flood with a rain and river-rise timeline (Open-Meteo forecast or constant rain), plus routing that avoids deep water and steep ground.
- **Shelter:** helipad and relief-camp siting, using the ICAO clearance rule of thumb and the Sphere standard of 45 m² per person.
- **After:** a per-block impact report.

**6. App.**
- Stack: a Python stdlib HTTP server plus a React/TypeScript/Three.js frontend.
- It offers 3D flythrough with orbit, free-fly and street-level cameras, drawn-path flythrough with video recording, and GeoTIFF / glTF exports.
- It falls back to the CPU when there is no GPU, and has a Windows one-click installer.
- The UI was redesigned this week. There is now a Home landing page and a Scenes tab, and choosing or uploading a scene opens the six tools.

## Accuracy
All figures are zero-shot: nothing was trained or tuned on these test sets. Each is the mean over tiles or scenes with its 95% bootstrap CI, measured against a baseline at the same points.

| Test | Ours, MAE | Baseline |
|---|---|---|
| GAMUS vs airborne LiDAR, nDSM, 150 tiles (DC / NYC / Philadelphia; **aerial** 0.33 m imagery, leaf-off trees) | 3.90 m [3.24, 4.66] | flat ground: 5.65 m |
| GAMUS buildings, 90th-percentile height per building, 1,450 buildings | 3.57 m [3.08, 4.06] | 10.54 m |
| Overhead Geopose **satellite** imagery, Atlanta / Buenos Aires, 300 tiles each | 5.99 / 1.94 m | published RS3DAda: 5.67 / 2.01 m (both reproduce) |
| India, model vs ICESat-2 20 m segments, 8 scenes (2 each: urban, sparse, hilly, forested) | 4.85 m [3.04, 6.69], r 0.40 | height 0: 8.25 m |
| India, terrain vs **held-out** ICESat-2 ground, 5 scenes | 3.73 m [1.44, 6.69] | no levelling: 3.86 m |
| India, absolute DSM vs all ICESat-2 photons | 9.14 m | raw GLO-30 DSM: **8.06 m** (better than ours) |
| Flood scenario, Porto Alegre 2024, 4 windows, CSI | 0.79 with laser levelling | raw GLO-30: 0.20 |

## Known weaknesses (measured)
- **Tall objects come out too low** on every test set: by 15–18 m above 20 m, and by −7.6 m at 10–20 m on GAMUS. This is the main weakness.
- **Forest terrain is about 20 m off** for every DEM, and ours is the worst there.
- **At laser footprints our absolute DSM does not beat the 30 m Copernicus DSM.** What the image adds is detail at 0.5 m.
- **Laser levelling removes bias, not typical error.** Bias goes from +2.58 to −0.27 m, while MAE is 4.02 m against 3.86 m without levelling.
- **The 90% interval** covers 83–97% of blocks on a held-out city and 71% on Indian roofs. It misses most buildings over 10 m (only 14–30% covered above 20 m).
- **Only 2 Indian scenes per landscape**, so claims of stability across landscapes are weak.

## Tried and not shipped
- **Isotonic height recalibration** made Philadelphia worse (MAE 1.86 → 2.87 m).
- **Resampling the input** to another resolution (GSD sweep) did not help.
- **FABDEM as the default terrain:** no terrain base won every test (it is better in hills).
- **GEDI-densified levelling** gave no gain.
- **An earlier bias correction learned on DFC2019** did not help. DFC2019 is also inside RS3DAda's adaptation data, so it is not zero-shot.

## Not yet validated
- Cartosat imagery and CartoDEM. A data request to NRSC is drafted but not sent.
- Leaf-on canopy.
- Interval coverage outside US cities.
- Floor counts (height ÷ 3 m), GCP accuracy and processing times.
- The disaster tools, apart from the one flood test.

## Constraints
- **Development machine:** Apple M3 with 8 GB RAM, so only one model process can run at a time. A teammate works on Windows.
- **The app must run offline on a laptop CPU.** It only needs the internet to fetch terrain, ICESat-2 data and the rain forecast for a new scene.
- **There is no GPU for training.** Fine-tuning would mean unsupervised, RS3DAda-style adaptation on Indian tiles using a cloud GPU.
- **Licences:** FABDEM and the Esri / Maxar demo imagery are non-commercial.
- **Data already available:**
  - GAMUS (CC-BY-4.0) and DFC2019;
  - Overhead Geopose Atlanta / Buenos Aires;
  - ICESat-2 photon caches for the test scenes;
  - processed scenes for Bengaluru, Chandigarh, Delhi, Guwahati, IIT Ropar, Mumbai, Shimla and Porto Alegre.

## Open questions where help is wanted
1. **Fixing the tall-object bias** without fine-tuning, for example:
   - shadow length combined with the sun elevation in the image metadata;
   - a priors-based correction per land-cover class;
   - a canopy-height model such as Meta's HighResCanopyHeight for tree pixels.

   It must not make low objects worse, which is how isotonic recalibration failed.
2. **Better terrain under forest and in hills:**
   - which DTM base or fusion to use (GLO-30, FABDEM, CartoDEM, GEDI ground);
   - how to level a scene robustly with sparse laser passes.
3. **Uncertainty with honest coverage for tall buildings**, for example conformal intervals by height band, or intervals conditioned on land cover and context.
4. **A drainage-aware flood model**, such as HAND via pysheds or WhiteboxTools. It should be validated on one real Indian event (Assam, Wayanad 2024, Himachal 2023) against a Sentinel-1 or NRSC flood extent, using CSI.
5. **An evaluation design that stands up to ISRO judges:**
   - more Indian scenes per landscape;
   - how to handle laser footprints of about 11 m (ICESat-2) and 25 m (GEDI) against 0.5 m pixels;
   - date mismatch between image and laser;
   - ATL08 classing roof photons as ground.
6. **What to claim and how to word it** in a 3-minute demo and slide deck.

## Where things are (repository)
- `README.md`: accuracy tables.
- `docs/CLAIMS.md`: one row per published number.
- `docs/TECHNICAL.md`, `docs/USER_GUIDE.md`.
- `SynRS3D/demo/benchmark/v2/*.md`: per-benchmark reports with commands.
- `SynRS3D/infer_height.py`, `terrain.py`, `validate.py`, `app.py`.
- `SynRS3D/frontend/`: the user interface.
