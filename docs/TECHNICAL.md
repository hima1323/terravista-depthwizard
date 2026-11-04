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
  tools.py          before/after change, observed flood masks, mosaics, GeoJSON / CityJSON export, calibrated error
                    bars (conformal), tall-object height fixes, WMS overlays, GNSS / field points
  models/           DPT_DINOv2 network (RS3DAda); DINOv2 code loaded from pretrain/dinov2 (offline) or GitHub
  web/index.html    the whole viewer (three.js, bundled in web/vendor so it runs offline)
  web/field.html    phone page that records GPS points for calibration (served at /field)
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

## 5b. Toolbar tools

Every tool is a card opened from the toolbar; the tool finder (Ctrl K) searches them all. Browser-side tools work on
the 512 × 512 grids; server-side ones on the saved full-resolution results.

| Tool | Where | Method |
|---|---|---|
| Line of sight | browser | Rays from each observer to every cell on the edge of its range; a running maximum of the surface's elevation angle; a cell is visible if the target on it rises above that maximum. |
| Volume | browser | Cells whose centres are inside the outline; Σ (surface − base) · cell area, base = median surface along the outline, bare ground (DTM) or a fixed level. |
| Drone plan | browser | Path resampled every *n* m; altitude = highest surface within the look-around radius + clearance. KML (absolute, or relative to ground without terrain), QGroundControl plan (take-off, waypoints, return; altitudes relative to take-off), CSV. |
| Rooftop solar | browser | Sun positions hourly on the 21st of each month; per roof, up to 6 sample cells ray-marched toward the sun over the surface model; shade = weighted (sin elevation) share blocked. kWh = roof × usable × GHI × efficiency × PR × (1 − 0.85 · shade). |
| Shadow heights | browser | Manual: length along the shadow direction × tan(elevation). Automatic: from each block's shadow-side edge, walk the photo (≤ 2048 px) in the shadow direction across pixels darker than min(Otsu, 0.6 × median); runs that hit another building or the image edge are dropped; per block the median of ≥ 3 runs. |
| Tall-object fixes | server (`tools.fit_tree_scale`, `apply_class_scale`) | Per land-cover class height scale (buildings, trees). Tree scale = median(canopy / model) over ICESat-2 ATL08 top-of-canopy photons on tree pixels, canopy = photon height − our laser-levelled terrain. Stored as `class_scale` in the scene metadata; `validate.Scene` applies it. |
| Calibrated error | server (`tools.conformal`) | Split conformal on every validation: score = \|error\| / (spread + 0.25 m); k = the ⌈(n+1)·level⌉/n quantile; coverage is checked by fitting k on one random half and testing on the other. |
| Terrain source | server | Upload saved to `demo/terrain/<scene>__<file>.tif` and preferred by `terrain.build_dtm(prefer=…)`; terrain, DSM and building ground levels are rebuilt. |
| People at risk | browser | Residents = area × floors × occupied share ÷ m² per person. |
| Evacuation | browser | Dijkstra from each camp over the route-finder costs (water deeper than the travel mode's limit is impassable); buildings in order of their best time take places at their nearest camp with space (split when a camp fills). |
| Damage | server (`tools.change`) | Before heights and building ids reprojected (or resized) onto the after grid, then shifted by the phase correlation of the two photos; per before-building median before / after height; the browser classes them. Also new blocks (after ≥ 3 m where before < 1.5 m), canopy lost (tree cells ≥ 3 m that lost 60 % or their tree class). |
| Landslide risk | browser | Slope rating (≤15° 0.5, ≤25° 0.8, ≤35° 1.2, ≤45° 1.7, >45° 2.0) + land cover (bare 2.0, scrub 1.2, built / trees 0.8, fields 0.65) + relief within ~150 m (<25 m 0.3, <75 m 0.6, else 1.0), × rain factor (IMD 24 h: heavy 1.15, very heavy 1.3, extremely heavy 1.5). Classes < 2.2 / 3.2 / 4.2. |
| Observed flood | server + browser | Mask (values > 0) or backscatter (dB; linear converted) thresholded at Otsu in −30…0 dB (−18 dB if outside −24…−12), averaged onto the grid. CSI = hits / (hits + misses + false alarms) over non-building cells; the fit scans the water level in 0.1 m steps. |
| Flowing water | browser | Local-inertial shallow-water equations (Bates et al. 2010) on ≤ 150 × 150 cells sized so a run takes seconds; Manning n from land cover; building cells are walls; free outfall at the edges; Froude ≤ 1 and an outflow limiter keep it stable and mass-conserving. Snapshots every 5–30 min. |
| Mosaic | server (`tools.mosaic_arrays`) | `rasterio.merge` of the photos and the saved height, uncertainty and land-cover rasters (other CRSs warped to the first); then the usual building, grid and terrain steps. Grid 512 or 1024. |
| WMS overlay | server (`tools.wms_overlay`) | WMS 1.1.1 GetMap in EPSG:4326 for the scene bounds, warped onto the photo grid, saved as `<scene>_wms.png`. |
| Exports | server (`tools.geojson`, `cityjson`) | Block outlines traced on the grid (OpenCV contours), with the fixes and GCP calibration applied. GeoJSON in WGS84; CityJSON 1.1 LOD1 solids in the scene's projected CRS (UTM for lon/lat scenes). |
| Report | browser | The map, the 3D view and every open card as static HTML (charts as images), printable to PDF. |

**Image loading** (`utils/geo_func.load_multiband`): bands chosen from the upload form's order, the file's colour
interpretation or band names, else B, G, R for 4+ bands; non-8-bit data stretched per band between the 2nd and 98th
percentile (a plain cast to 8 bit wrapped 16-bit values around).

**Tests:** `demo/tools_harness.py <dir>` serves synthetic scenes with known truth through the real `app.py` (model
stubbed, no PyTorch needed); `node demo/tools_test.js <dir>` drives every tool in a headless browser (36 checks).
`python tools.py` runs the module's self-checks.

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
| POST | `/api/upload?name=&bands=auto\|rgb\|bgr` | band order for multispectral images |
| POST | `/api/change?name=<after>&before=<scene>` | before / after height change per building |
| POST | `/api/obsflood?name=&kind=auto\|mask\|db\|linear&threshold=&file=` | observed flood map (body) onto the grid |
| POST | `/api/mosaic` | `{"names": [...], "name", "grid"}` builds a new scene |
| POST | `/api/heightfix?name=` | `{"fit": "trees"}`, `{"buildings": k, "trees": k}` or `{"clear": true}` |
| POST | `/api/conformal?name=` | `{"source": "raster\|points\|icesat2", "level": "0.90"}` or `{"clear": true}` |
| POST | `/api/wms?name=` | `{"url", "layers", "styles"}` fetches and saves a map overlay |
| POST | `/api/dem?name=&datum=egm96\|egm2008&file=` | a DEM (body) as this scene's terrain; `&clear=1` back to the default |
| POST | `/api/field?name=` / GET `/api/field?name=` | points from the field page |
| POST | `/api/gnss?name=&datum=ellipsoid\|egm96\|egm2008[&source=field]` | CSV / GPX (body) or field points → image position + height (EGM2008) |
| GET | `/api/export?name=&fmt=geojson\|cityjson` | building footprints / LOD1 solids |
| GET | `/field` | the phone field page |

`python app.py --lan` also listens on the local network (for the field page); `--port` changes the port.

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
- **Disaster tools give scenarios.** The level-fill flood has no flow dynamics; the flowing-water model has no drains
  or infiltration; the 30 m terrain limits depth accuracy everywhere.
- **Toolbar tools inherit the heights' errors.** Shadow heights assume a near-vertical view; the landslide map is a
  screening index without geology or groundwater; people counts are planning estimates; before/after damage needs
  similar view angles and no clouds.
