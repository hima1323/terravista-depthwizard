# DepthWizard technical documentation

Problem statement **SIH26175**: single-view height estimation and 3D flythrough.
The problem statement asks for three things:
- **relative DSM** for PNG/JPG images, and **absolute DSM** for GeoTIFF images;
- **scale calibration** with a low-resolution DEM or with ground control points;
- a navigable 3D flythrough where users **validate heights against reference data**.

## 1. Architecture

```
SynRS3D/
  app.py            local web server (Python standard library): upload, processing queue, results, validation API
  infer_height.py   the height model: tiled inference, 4-flip test-time augmentation, uncertainty, land cover
  terrain.py        bare-ground terrain (DTM) under GeoTIFFs: DEM fetch, building/canopy removal, ICESat-2 levelling
  validate.py       comparison with reference rasters / points / ICESat-2; ground-control-point calibration
  models/           DPT_DINOv2 network (RS3DAda); DINOv2 code loaded from pretrain/dinov2 (offline) or GitHub
  web/index.html    the whole viewer (three.js, bundled in web/vendor so it runs offline)
  demo/             benchmarks (GAMUS, DFC2019, ICESat-2, landscapes), scene download helpers, flood test
  pretrain/         model weights + DINOv2 code (installed by install.ps1, not in git)
Install.bat / install.ps1   one-time setup        DepthWizard.bat   start server + open the app window
```

All the processing runs on the local machine, and the viewer is a single HTML page served by `app.py`. Only three
data sources are fetched over the internet, once, and then cached:
- terrain (Copernicus GLO-30 on AWS),
- ICESat-2 photons (NASA SlideRule),
- rain forecasts (Open-Meteo).

## 2. Processing pipeline (one image)

1. **Read the image** (`utils/geo_func.load_multiband`): PNG / JPG / TIFF / GeoTIFF, first 3 bands. The ground sample
   distance (GSD) comes from the coordinate system: projected, Web Mercator (latitude-corrected) or geographic. Without
   one, 0.5 m is assumed.
2. **Height model** (`infer_height.predict`). **RS3DAda** (Song et al., NeurIPS 2024, MIT licence) is a DINOv2 ViT-L/14
   encoder with DPT decoders. One head regresses **height above ground** (nDSM, metres); a second head predicts **8
   land-cover classes**.
   - **Tiling:** 518 px tiles, 50 % overlap, blended with a Gaussian weight so tile seams don't show.
   - **Test-time augmentation (TTA):** 4 flips; the prediction is their mean.
   - **Uncertainty:** the per-pixel spread of the 4 flips. It ranks the error with Spearman ρ = 0.56 on GAMUS. It is a
     self-consistency measure, not a calibrated error bar.
   - **Precision:** fp16 on GPU, fp32 on CPU.
3. **Building blocks** (`app.extract_buildings`): building pixels at least 2 m tall, split by a watershed.
   - **Per block:** median height, 90th percentile, uncertainty, area and floors (3 m per floor).
4. **Terrain** (`terrain.build_dtm`, GeoTIFF only).
   - **Source:** a DEM placed in `demo/terrain/` (e.g. CartoDEM or SRTM, shifted from EGM96 to EGM2008), otherwise
     Copernicus GLO-30.
   - **Cleaning:** 30 m DEMs are *surface* models that include roofs and canopy. Each cell is corrected by the
     model's own mean height there, weighted by how much of the cell is open ground. Gaps are filled harmonically.
   - **Laser levelling:** `terrain.laser_correct` shifts the terrain by the median offset to **NASA ICESat-2** ATL03
     ground photons (classified by ATL08), when the scene has at least 50 of them.
5. **Absolute DSM:** DSM = DTM + max(0, nDSM), in metres above mean sea level (EGM2008), written as a GeoTIFF with the
   input's coordinate system.
6. **Browser grids:** height, uncertainty, building ids, terrain and land cover are downsampled to at most 512 × 512
   float32 grids (`*.f32`) for the viewer.

**Outputs per scene** (`SynRS3D/demo/results/`):

| File | Content |
|---|---|
| `<scene>_height.tif` | relative DSM / nDSM, float32 m (georeferenced if the input was) |
| `<scene>_dsm.tif`, `_dtm.tif` | absolute surface / bare ground, m above sea level (EGM2008), GeoTIFF only |
| `<scene>_dsm_gcp.tif` | DSM calibrated with ground control points (after a GCP fit) |
| `<scene>_uncertainty.tif`, `_landcover.tif` | ± spread of the 4 flips; land-cover class per pixel |
| `<scene>_buildings.json`, `<scene>.json` | building blocks; scene metadata (GSD, statistics, terrain info, GCP fit) |
| `<scene>_validation.json`, `_valerr.f32` | last validation per type; error grid for the viewer |

**Command line** (no viewer):
```
.venv\Scripts\python infer_height.py --data_dir image.tif --output_path height.tif --use_tta \
    --uncertainty_path unc.tif --dsm_path dsm.tif
```

## 3. Validation (`validate.py`)

**Reference raster.**
- **Georeferenced reference:** reprojected bilinearly onto the scene's pixel grid.
- **Either one not georeferenced:** resized to the image, which assumes both cover the same area.
- **Vertical datum:** converted to EGM2008. EGM96 uses a PROJ geoid grid; the ellipsoid uses the scene's geoid
  undulation.
- **Compared product:** our DSM, nDSM or DTM, matching the reference type.
- **Relative scenes:** compared after the least-squares line reference ≈ a + s·ours.

**Points.** A CSV with `lon,lat,z` or `col,row,z`. Our value is the median of the 3 × 3 pixels around each point.

**ICESat-2.**
- **Photons:** all ICESat-2 photons inside the scene from all passes since 2018, high confidence only, with ATL08
  ground / canopy / top-of-canopy classes.
- **Surface check:** our DSM against all photons.
- **Terrain check:** our terrain *before* the laser levelling against the ground photons, so this check is
  independent of the levelling.

**Metrics.**
- n, MAE, RMSE, bias (mean of ours − reference), median, NMAD = 1.4826 · median |e − median|, **Pearson r**, and the
  share within ±1 m and ±2 m;
- the same with the mean bias removed (raster only).

**Breakdowns:**
- **landscape**, from the model's land cover per pixel: urban (buildings, roads, paved), forested (trees),
  sparse / open (bare, grass, fields), water;
- **terrain slope**, from our DTM: flat < 5°, rolling 5–15°, hilly > 15°;
- **height band**.

## 4. Ground control point calibration

Model: **z = G + a + bx·u + by·v + s·H**
- G = our terrain (0 without one), H = our height above ground;
- u, v = position in the image, from −0.5 to 0.5;
- fitted by least squares.

The terms grow with the evidence:

| Points | Terms fitted |
|---|---|
| 1 | a (level) |
| 2 or more, differing in height by ≥ 3 m | a and s (height scale) |
| 4 or more (5 with s) | a, s and the tilt bx, by |

**Safeguards and outputs:**
- **Implausible scale:** a fitted scale outside 0.3–3 is rejected, and s stays 1.
- **Reported:** RMSE at the points before and after, and **leave-one-out** RMSE (each point predicted by the fit
  without it).
- **Applied to:** the full-resolution GeoTIFF (`_dsm_gcp.tif`) and, in the browser, the terrain and heights of every
  view.

## 5. Viewer (`web/index.html`)

three.js r170, no build step. The terrain mesh is 512 × 512 vertices. Its heights come from the terrain plus the
height above ground, times the exaggeration factor. The photo is the texture; steep building walls are shaded grey,
because a top-down photo has no facade pixels.

**Cameras:**
- orbit, free fly and street level, with collision against buildings;
- spline flythrough along drawn paths;
- MediaRecorder video capture.

**The three modes:**

| Mode | What it contains |
|---|---|
| **Explore** | Height layers, 3D, downloads |
| **Validate & calibrate** | The validation and GCP cards, error map, ICESat-2 / point dots |
| **Disaster tools** | Flood (bathtub or connected priority-flood), rain/river timeline (level-pool volume model), A* routing, helipad / camp finder (exact distance transform) |

**Self-tests run in the page:**
- `#selftest`: the core viewer;
- `#toolstest`: the disaster tools;
- `#valtest`: validation and a GCP round trip.

The results are written into the page title, so a headless browser can check them.

## 6. HTTP API (`app.py`, http://127.0.0.1:8000)

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | the viewer |
| GET | `/api/scenes` | scenes with processing state and metadata |
| GET | `/results/<file>` | result files (GeoTIFF, JSON, f32 grids, JPEG) |
| POST | `/api/upload?name=<file>` | add an image (body = file, ≤ 50 MB); queued for processing |
| POST | `/api/validate?name=&kind=dsm\|ndsm\|dtm\|points&datum=egm2008\|egm96\|ellipsoid&file=` | compare with a reference raster or CSV (body) |
| POST | `/api/icesat2?name=` | compare with ICESat-2 photons |
| POST | `/api/gcp?name=` | body `{"points": [{"u", "v", "z"}]}` fits and applies GCPs; `{"clear": true}` removes them |

## 7. Accuracy: how it is measured

| Script | Measures |
|---|---|
| `demo/gamus_benchmark.py [tiles_per_city]` | GAMUS test tiles (Washington DC, New York, Philadelphia) vs LiDAR nDSM: MAE / RMSE with the repo's official metric, plus pixel-pooled MAE / RMSE / bias / **r** by landscape and height band |
| `demo/landscape_benchmark.py` | Indian scenes of each landscape type (urban, sparse, hilly, forested), each centred on ICESat-2 laser tracks and processed by the running app |
| `demo/benchmark.py` | DFC2019 (Jacksonville, Omaha) vs LiDAR; needs the DFC2019 data in `data/DFC19` |
| `demo/icesat2_check.py` | all georeferenced demo scenes vs ICESat-2 |

Results go to `SynRS3D/demo/benchmark/*.md`. The current numbers are in the [README](../README.md#accuracy).

## Manual installation

Linux, macOS, or Windows without the installer, using Python 3.10+:
```
cd SynRS3D
python -m venv .venv && . .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128   # or .../whl/cpu
pip install -r requirements.txt
python -c "from huggingface_hub import hf_hub_download; hf_hub_download('JTRNEO/RS3DAda', 'RS3DAda_vitl_DPT_height.pth', local_dir='pretrain')"
python demo/fetch_scene.py chandigarh_sector17 30.7398 76.7827     # a sample scene
python app.py                                                      # then open http://127.0.0.1:8000
```

## Known limitations

- **Tall structures and trees are under-estimated.**
  - GAMUS: −9.8 m bias for 10–20 m objects and −8.5 m for trees. Many GAMUS trees are leafless in the imagery.
  - Indian scenes vs ICESat-2: the surface is mostly too low in towns and forests.
- **Terrain is 30 m.** It is about ±2–4 m before ICESat-2 levelling, and much better where laser data exists.
  ICESat-2 tracks are kilometres apart.
- **Imagery and reference dates differ.** Buildings change and trees grow, which adds apparent error.
- **Disaster tools give scenarios.** They have no flow dynamics or drainage network, and the 30 m terrain limits
  depth accuracy.
