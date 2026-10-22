# DepthWizard: one satellite image to heights you can fly through and check

**SIH26175 · Single-View Height Estimation and 3D Flythrough** (ISRO, Disaster Management) · team TerraVista_iitrpr

DepthWizard takes a single optical satellite image and:
1. estimates the **height of every pixel** with RS3DAda, a published remote-sensing height model (released weights,
   not fine-tuned by us);
2. turns those heights into a **DSM**:
   - **relative** for PNG / JPG;
   - **absolute, in metres above sea level** for GeoTIFF, on a 30 m DEM with buildings and trees removed, levelled to
     NASA ICESat-2 laser ground points where 2 or more laser passes cross the scene and, if you have them, ground
     control points;
3. shows the result as a **3D terrain you can fly through**, where you can **check the heights against reference
   data** (LiDAR, a DSM, surveyed points, ICESat-2).

Everything runs locally in one app. For Disaster Management it adds flood scenarios, a rain and river-rise timeline,
evacuation routing, and helipad / relief-camp siting.

## Quick start (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) and tick *Add python.exe to PATH*.
2. Double-click **`Install.bat`** once. It sets up PyTorch (the GPU build if you have an NVIDIA card, otherwise the
   CPU build), the packages, the 1.5 GB model and a sample scene. It needs internet once.
3. Double-click **`DepthWizard.bat`**. The app opens in its own window.

Linux / macOS / manual setup: [docs/TECHNICAL.md](docs/TECHNICAL.md#manual-installation).
How to use it: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## What SIH26175 asks for, and where it is

| Requirement | In DepthWizard |
|---|---|
| Single-view optical RGB input: PNG, JPG, TIFF | Upload in the app, or `infer_height.py` on the command line |
| PNG/JPG → relative DSM | `<scene>_height.tif`: height above ground |
| GeoTIFF → absolute DSM in metres from its coordinate system | `<scene>_dsm.tif`: m above mean sea level (EGM2008), same coordinate system as the input |
| Pre-trained monocular depth backbone | RS3DAda: DINOv2 ViT-L/14 + DPT, trained for remote sensing (Song et al., NeurIPS 2024); released weights, no fine-tuning |
| Scale calibration with a low-resolution DEM | Copernicus GLO-30, or CartoDEM / SRTM placed in `demo/terrain`; roofs and canopy removed with the model's heights and land cover; levelled to NASA ICESat-2 laser ground photons |
| Scale calibration with minimal GCPs | **Validate & calibrate → Ground control points**: 1 point fixes the level, 2+ the height scale, 4+ the tilt; leave-one-out error; calibrated DSM GeoTIFF. Also makes PNG/JPG absolute |
| Image projected on the 3D mesh (Three.js) | Explore → 3D view |
| First-person navigation from any aerial viewpoint | Orbit, free fly (WASD), street level, drawn-path flythrough, video recording |
| Analyse structural heights and slopes | Click any building: height with a 90% interval calibrated on GAMUS LiDAR (US cities; covers 83–97% per held-out city overall, but only 49–67% of real 10–20 m blocks in DC / NYC and 14–30% above 20 m; 71% on Indian ICESat-2 roofs), floors (3 m each, not validated). Slope layer with the BIS IS 14496 classes |
| Upload imagery → view terrain → **validate heights against reference datasets** | **Validate & calibrate** mode: reference raster (DSM / nDSM / DTM, any coordinate system and vertical datum), surveyed points, or ICESat-2 |
| RMSE, MAE, **correlation**; stability across **urban, sparse, hilly, forested** | In the app per scene (ICESat-2 also on held-out passes), and in the benchmarks below |
| Standalone deployment, one unified module | `Install.bat` + `DepthWizard.bat`; runs offline after installation; CPU fallback |
| Source code + technical documentation | This repository · [docs/TECHNICAL.md](docs/TECHNICAL.md) · [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |

## Accuracy

All numbers were measured on this code with the released RS3DAda weights. Nothing was trained or tuned on these test
sets. Each value is the **mean over tiles or scenes [95% bootstrap CI]**; "pooled" is all pixels or points together.
Every number has a row in the claims register, [docs/CLAIMS.md](docs/CLAIMS.md). The reports and the commands that
produce them are in `SynRS3D/demo/benchmark/v2/`.

### Height above ground vs airborne LiDAR: GAMUS (zero-shot)

150 frozen GAMUS test tiles, 50 each from Washington DC, New York and Philadelphia ([gamus_v2.md](SynRS3D/demo/benchmark/v2/gamus_v2.md)).
GAMUS images are **aerial orthophotos at 0.33 m, not satellite images**, and the DC and NYC trees are leafless.
RS3DAda never saw GAMUS. The baseline predicts flat ground (height 0) everywhere.

| | Ours: MAE | Flat-ground baseline: MAE |
|---|---|---|
| **All pixels** | **3.90 m [3.24, 4.66]** (pooled 3.88) | 5.65 m [4.88, 6.50] |
| Buildings, 90th-percentile height per building (1,450 buildings) | 3.57 m [3.08, 4.06], bias −1.37 m | 10.54 m |
| Urban (buildings, roads) | 2.90 m [2.34, 3.63] | 5.66 m |
| Forested (trees, mostly leafless) | 6.67 m [5.92, 7.45] | 8.70 m |
| Sparse / open ground | 0.96 m [0.85, 1.09] | **0.55 m** (the baseline is better) |
| Pixels with LiDAR height > 3 m | 6.65 m [5.90, 7.44], bias −5.27 m | 11.10 m |

The other metrics, all pixels: RMSE 5.58 m (pooled 7.39), bias −2.61 m, NMAD 2.52 m, and r on height above ground 0.61
(pooled 0.58). By city, MAE is 5.16 m in DC, 4.69 m in NYC and 1.86 m in Philadelphia.

**Tall objects come out too low.** The bias is +0.65 m at 0–3 m, −1.86 m at 3–10 m, −7.62 m at 10–20 m and −16.26 m
above 20 m.

### Satellite imagery: Overhead Geopose, Atlanta and Buenos Aires (zero-shot)

300 test tiles per city, with the authors' evaluation protocol ([geopose_v2.md](SynRS3D/demo/benchmark/v2/geopose_v2.md)).

| | Ours: whole-image MAE | Published RS3DAda | Published source-only |
|---|---|---|---|
| Atlanta (ATL) | 5.99 m [5.57, 6.43] | 5.67 m | 7.26 m |
| Buenos Aires (ARG) | 1.94 m [1.86, 2.03] | 2.01 m | 2.65 m |

- **The published numbers reproduce.** Both lie inside our 95% CIs.
- **DepthWizard's inference path is slightly better than the authors' script** (ATL 5.90 m, ARG 1.87 m), and the
  gain comes from the 4-flip TTA.
- **The same tall-object bias shows up here:** ATL −16.8 m and ARG −15.3 m above 20 m.

DFC2019 (Jacksonville, Omaha) is **not** zero-shot: RS3DAda adapted on its unlabelled images.

### Indian landscapes vs NASA ICESat-2 and GEDI lasers

The test set is 8 scenes, two per landscape: urban Chandigarh and Delhi, sparse Barmer and Anantapur, hilly Shimla and
Gangtok, forested Agumbe and Silent Valley ([india_v2.md](SynRS3D/demo/benchmark/v2/india_v2.md)). ICESat-2 passes are
split into levelling passes and validation passes, and **no photon is used for both**. Every result is shown next to a
baseline at the same points.

| Test | Ours: MAE | Baseline: MAE |
|---|---|---|
| Height model alone vs ICESat-2 20 m segment heights (8 scenes) | **4.85 m [3.04, 6.69]**, r 0.40 | height 0: 8.25 m |
| Height model alone vs GEDI rh98 canopy / roof height (7 scenes) | 9.93 m [4.86, 15.42] | height 0: 16.89 m |
| Terrain vs held-out ICESat-2 ground, as the app runs now (5 scenes) | 3.73 m [1.44, 6.69] | no levelling: 3.86 m |
| Terrain vs ICESat-2 ground, urban (2 scenes) | 2.36 m | raw GLO-30: 5.28 m, FABDEM: 2.80 m |
| Absolute DSM vs GEDI canopy / roof tops (7 scenes) | 5.97 m [4.16, 7.79] | raw GLO-30 DSM: 8.39 m |
| Absolute DSM vs all ICESat-2 photons, unlevelled (8 scenes) | 9.14 m [3.85, 17.56] | raw GLO-30 DSM: **8.06 m** |

**What the numbers say:**
- **The height model clearly beats "no height"** against both lasers. Tall objects are too low here as well: the bias
  is −18.3 m above 20 m.
- **Our building removal fixes the terrain in towns.** In hills FABDEM is better (5.74 vs 8.42 m). In forest every DEM
  is about 20 m off, and ours is the worst.
- **At laser footprints our absolute DSM is not more accurate than the 30 m Copernicus DSM**, except against GEDI
  canopy and roof tops. What the image adds is detail at 0.5 m.
- **Laser levelling removes the average offset, not the typical error.** The bias goes from +2.58 to −0.27 m, but
  MAE is 4.02 m against 3.86 m without levelling.
- **The old "r = 0.98 in hills" measured the hillside, not the model.** With the terrain plane removed, r is 0.26 for
  terrain and 0.43 for the surface.

**Silent Valley.** The old 46 m terrain offset came from a single laser pass running along one forested valley floor.
The 30 m radar DEMs fill that valley in, so the offset is correct on that line and wrong on the slopes. GEDI agrees
with ICESat-2 where they meet closely (+1.1 m). The app now refuses to level from one pass
([dtm_v2.md](SynRS3D/demo/benchmark/v2/dtm_v2.md)). This is a safety fix, not an accuracy gain. Its own laser check
there now shows the unlevelled terrain, 36.8 m surface MAE on that one line, while the DSM error against held-out GEDI
tops drops from 51.7 to 7.0 m.

### Uncertainty

- **Building blocks carry a 90% interval** calibrated by split-conformal on GAMUS LiDAR
  ([uncertainty_calibration.md](SynRS3D/demo/benchmark/v2/uncertainty_calibration.md)).
  - **On a held-out city it covers 83–97% of blocks**, which misses the ±3 pp target.
  - **It is about ±6 m wide**, and it misses most tall buildings: in DC / NYC only 67% / 49% of real 10–20 m blocks
    and 14–30% above 20 m.
  - **On Indian roofs it covers 71%.**
- **The per-pixel flip spread is a consistency score, not an error bar.** It ranks errors on flat ground (Spearman 0.44
  per tile), but not on tall objects (−0.03) or trees (0.03).
- **Not shipped:** an isotonic height recalibration made Philadelphia worse (MAE 1.86 → 2.87 m), and resampling the
  input to another resolution did not help.

### Flood scenario test

**Porto Alegre, May 2024.** A bathtub flood from the pre-flood image, in 4 small windows with laser ground points, was
compared with the IPH/UFRGS flood extent ([flood_test.md](SynRS3D/demo/benchmark/flood_test.md)).
- **CSI by terrain:** raw GLO-30 0.20, ours 0.30, FABDEM 0.32, ours with ICESat-2 levelling 0.79.
- **This is a scenario test, not a forecast.** The levelling was done before the single-pass guard; one of the 4
  windows has one laser pass and would not be levelled now.

### Not yet validated

- Cartosat imagery and CartoDEM ([data request](docs/DATA_REQUEST_cartosat.md));
- leaf-on tree canopy;
- interval coverage outside US cities and for buildings over 10 m;
- floor counts, GCP accuracy and processing times;
- the disaster tools, apart from the one flood test.

## Repository layout

```
Install.bat, install.ps1, DepthWizard.bat   setup and launcher (Windows)
docs/                                       user guide, technical documentation, claims register, Cartosat data request
SynRS3D/
  app.py, infer_height.py, terrain.py, validate.py    the pipeline and local server
  calibration/conformal.json                          the building-interval table (from demo/uncertainty_calibration.py)
  web/index.html                                      the viewer (three.js bundled)
  demo/                                               benchmarks and data helpers; reports in demo/benchmark/v2/
deck_work/, DepthWizard_Deck_Spec.md        SIH presentation material (current deck: v4)
```

## Credits and licences

The full licence table is in [docs/CLAIMS.md](docs/CLAIMS.md#licences-of-what-we-use).


- **Model code and weights:** RS3DAda / SynRS3D, J. Song et al., NeurIPS 2024, MIT licence (`SynRS3D/LICENSE`).
  The weights were trained on the SynRS3D dataset (CC BY-NC 4.0), so check that before any commercial use.
- **DINOv2:** Meta AI, Apache-2.0.
- **three.js:** MIT.
- **Data used at runtime:**
  - Copernicus GLO-30 DEM: © DLR / Airbus, provided by ESA;
  - NASA ICESat-2 ATL03 / ATL08 via SlideRule;
  - Open-Meteo forecasts;
  - demo imagery from Esri World Imagery and Maxar Open Data (CC BY-NC 4.0), for demonstration only.
- **Evaluation only:** GAMUS (CC BY 4.0), Overhead Geopose (CC BY 4.0), FABDEM (CC BY-NC-SA 4.0, never committed),
  NASA GEDI L2A, OpenStreetMap buildings (ODbL).
