# DepthWizard: one satellite image to heights you can fly through and check

**SIH26175 · Single-View Height Estimation and 3D Flythrough** (ISRO, Disaster Management) · team TerraVista_iitrpr

DepthWizard takes a single optical satellite image and:
1. estimates the **height of every pixel** with a satellite-trained AI model;
2. turns those heights into a **DSM**:
   - **relative** for PNG / JPG;
   - **absolute, in metres above sea level** for GeoTIFF, calibrated with a 30 m DEM, NASA ICESat-2 laser points
     and, if you have them, ground control points;
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
| Pre-trained monocular depth backbone | RS3DAda: DINOv2 ViT-L + DPT, trained for remote sensing (NeurIPS 2024) |
| Scale calibration with a low-resolution DEM | Copernicus GLO-30, or CartoDEM / SRTM placed in `demo/terrain`; roofs and canopy removed with the model's heights and land cover; levelled to NASA ICESat-2 laser ground photons |
| Scale calibration with minimal GCPs | **Validate & calibrate → Ground control points**: 1 point fixes the level, 2+ the height scale, 4+ the tilt; leave-one-out error; calibrated DSM GeoTIFF. Also makes PNG/JPG absolute |
| Image projected on the 3D mesh (Three.js) | Explore → 3D view |
| First-person navigation from any aerial viewpoint | Orbit, free fly (WASD), street level, drawn-path flythrough, video recording |
| Analyse structural heights and slopes | Click any building: height ± uncertainty, floors. Slope layer with the BIS IS 14496 classes |
| Upload imagery → view terrain → **validate heights against reference datasets** | **Validate & calibrate** mode: reference raster (DSM / nDSM / DTM, any coordinate system and vertical datum), surveyed points, or ICESat-2 |
| RMSE, MAE, **correlation**; stability across **urban, sparse, hilly, forested** | In the app per scene, and in the benchmarks below |
| Standalone deployment, one unified module | `Install.bat` + `DepthWizard.bat`; runs offline after installation; CPU fallback |
| Source code + technical documentation | This repository · [docs/TECHNICAL.md](docs/TECHNICAL.md) · [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |

## Accuracy

All numbers were measured on this code with the released RS3DAda weights; nothing was trained on these test sets.
The reports, with full tables, are in `SynRS3D/demo/benchmark/`, and the scripts re-run them.

### Against airborne LiDAR: GAMUS test tiles (Washington DC, New York, Philadelphia)

45 tiles, about 11.4 million pixels, compared as height above ground (`demo/gamus_benchmark.py 15`).

| | MAE | RMSE | Bias | Correlation r |
|---|---|---|---|---|
| **All pixels** | **4.01 m** | 7.21 m (5.90 m with the official per-tile metric) | −2.58 m | **0.66** |
| Urban (buildings, roads) | 2.83 m | 5.57 m | −0.57 m | 0.85 |
| Sparse / open ground | 0.82 m | 2.54 m | +0.43 m | 0.57 |
| Forested (trees) | 8.96 m | 11.37 m | −8.46 m | 0.23 |

### Across Indian landscape types: NASA ICESat-2 laser photons

Eight Indian scenes, two per landscape type. Each is centred on ICESat-2 tracks and processed by the app
(`demo/landscape_benchmark.py`). The comparison is our absolute DSM against the laser photon heights.

| Landscape | Scenes | Photons | MAE | RMSE | Bias | r (within scenes) |
|---|---|---|---|---|---|---|
| Urban | Chandigarh, Delhi | 2,863 | 5.33 m | 6.32 m | −1.49 m | 0.51 |
| Sparse | Barmer (desert village), Anantapur (dryland) | 5,000 | **2.06 m** | 2.96 m | +1.19 m | 0.47 |
| Hilly | Shimla, Gangtok | 3,671 | 6.93 m | 8.87 m | −1.14 m | 0.98 |
| Forested | Agumbe, Silent Valley (Western Ghats) | 1,893 | 10.54 m | 16.47 m | −6.04 m | 0.80 |

**What the numbers say:**
- **Open and sparse land and low buildings work well.** In flat sparse land there is little height to correlate,
  which is why r is low there.
- **Tall buildings and tree canopies are under-estimated.** This is the main weakness.
- **Dense rainforest terrain is the hardest case.** Under Silent Valley's canopy, the 30 m DEM is about 46 m off
  before laser levelling.
- **Laser levelling helps the terrain a lot.** It lands within about 0.6 m (median spread) on flat scenes.

Full per-scene tables are in `SynRS3D/demo/benchmark/landscape_results.md`.

## Repository layout

```
Install.bat, install.ps1, DepthWizard.bat   setup and launcher (Windows)
docs/                                       user guide, technical documentation
SynRS3D/
  app.py, infer_height.py, terrain.py, validate.py    the pipeline and local server
  web/index.html                                      the viewer (three.js bundled)
  demo/                                               benchmarks and data helpers
deck_work/, DepthWizard_Deck_Spec.md        SIH presentation material
```

## Credits and licences

- **Model code and weights:** RS3DAda / SynRS3D, J. Song et al., NeurIPS 2024, MIT licence (`SynRS3D/LICENSE`).
- **DINOv2:** Meta AI, Apache-2.0.
- **three.js:** MIT.
- **Data used at runtime:**
  - Copernicus GLO-30 DEM: © DLR / Airbus, provided by ESA;
  - NASA ICESat-2 ATL03 / ATL08 via SlideRule;
  - Open-Meteo forecasts;
  - demo imagery from Esri World Imagery and Maxar Open Data (CC BY-NC 4.0), for demonstration only.
