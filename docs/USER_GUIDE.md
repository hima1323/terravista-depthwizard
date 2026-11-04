# DepthWizard user guide

DepthWizard turns **one optical satellite image** into heights. It works out the height of every pixel, then gives you
a surface model you can download (DSM, as a GeoTIFF) and a 3D scene you can fly through.

- **PNG / JPG** images give **relative** heights: height above the local ground, with no real-world level.
- **GeoTIFF** images give **absolute** heights in metres above mean sea level.

## 1. Install and start (Windows)

| Step | What to do |
|---|---|
| Once | Double-click **`Install.bat`**. It needs Python 3.10+ from [python.org](https://www.python.org/downloads/), with "Add python.exe to PATH" ticked. It installs everything into `SynRS3D\`, about 5 GB including the 1.5 GB model. It needs internet once. |
| Every time | Double-click **`DepthWizard.bat`**. DepthWizard opens in its own window. To stop it, close the minimised "DepthWizard server" window. |

- **Graphics card:** with an NVIDIA graphics card, a 1024 × 1024 image takes a few seconds. Without one, the CPU
  version is installed and takes several minutes per image.
- **Working offline:** after installation the app works offline, except for three things. Terrain for new
  GeoTIFF scenes, ICESat-2 laser data and the rain forecast are downloaded when they are first used.
- **Linux / macOS:** see *Manual installation* in [TECHNICAL.md](TECHNICAL.md#manual-installation).

## 2. Add an image

Drag an image onto the box at the bottom left, or click it to choose a file. PNG, JPG, TIFF and GeoTIFF are
accepted, up to 50 MB. The image is processed in the background and appears in the scene list when it is done.
Other scenes stay usable while you wait.

- **GeoTIFF:** gets true scale (metres per pixel from its coordinate system) and absolute heights.
- **PNG/JPG:** assumed to be 0.5 m per pixel, with relative heights. Section 4.2 explains how to make them absolute
  with control points.
- **Band order** (under the drop box): *auto* reads the file's band labels. Use **B, G, R (+NIR)** for 4-band
  multispectral products without labels, such as Cartosat-3 MX or PlanetScope. 16-bit images are stretched to 8 bit
  automatically.

## Finding the tools

- **The toolbar** under the mode tabs shows every tool of the current mode. Click a tool to open its card on the
  right; click it again, or **×** on the card, to close it. Each card starts with one line saying what it does and
  the steps.
- **🔍 Find a tool** (or **Ctrl K**, or **/**) searches every tool in every mode and switches the mode for you.
  Example: type `drone` and press Enter.
- **📄 Report** turns the map and every open card into a printable page (save it as PDF from the print dialog).

## 3. Explore mode: the heights and the 3D flythrough

Choose a scene, then switch between **2D compare** and **3D view**.

**2D compare**
- **Layer:** Height, Consistency score (flip spread) or Slope. The consistency score is the spread of 4 flipped
  predictions. It points to likely errors on flat ground and edges, but not on tall buildings or trees, so it is not
  an error bar.
- **Overlay:** sets how transparent the layer is over the photo.
- **Hover:** shows the height at any point. With terrain, this is metres above sea level = ground + height above
  ground. It also shows the consistency score and the slope.
- **Hover over a building:** shows its height, a 90% interval, footprint area and estimated floors (3 m per floor,
  not validated). The interval was calibrated on LiDAR in three US cities.
  - **Width:** it is about ±6 m wide.
  - **Held-out cities:** it covered 83–97% of blocks there, but only about half of the blocks that are really
    10–20 m tall, and few above 20 m.
  - **Tall buildings:** treat it as too low for buildings over 10 m.

**3D view:** the photo draped on the reconstructed surface.

| Control | What it does |
|---|---|
| Camera: **Orbit** | Drag to rotate, scroll to zoom |
| Camera: **Fly** | W A S D to move, R / F up and down, drag to look, Shift for faster |
| Camera: **Street level** | Walk at eye height; buildings block you |
| **Height ×** | Exaggerates relief, for flat towns |
| **Surface** | Photo, height colours, consistency score or slope |
| **Click** | Measure any point or building |
| **✎ Draw path**, then **▶ Fly through** | Fly along your own route |
| **● Record video** | Save the flythrough as an MP4/WebM file |

**Download:**
- DSM (m above sea level), terrain DTM, height above ground and consistency score, as GeoTIFFs for QGIS or ArcGIS;
- the 3D model as `.glb`, in true metres, for Blender or any glTF viewer;
- **building footprints + heights** as GeoJSON (for QGIS), and **3D buildings** as CityJSON LOD1 (for city models);
- building blocks as JSON.

**Explore tools (toolbar):**

| Tool | What it does | Example |
|---|---|---|
| **👁 Line of sight** | Click observer points; green = visible, dark = hidden by terrain, buildings or trees. | Test scene: a 10 m mast sees 61 % of its 1 km range and 8 of 8 buildings. |
| **📦 Volume** | Draw an outline; get area and volume above the ground along it, above bare ground, or below a level. | Test scene: an 18 m block of 40 × 60 px gives 10 802 m³ (truth 10 800). Piles also show truck trips at 10 m³ each. |
| **✈ Drone plan** | Draw a path (2D or 3D) or use a route; waypoints fly a set clearance above the tallest thing nearby. Export **KML**, **QGroundControl .plan** or CSV. Red waypoints exceed the height limit (120 m by default, India's Drone Rules 2021). | Test scene: a 3-click path → 19 waypoints over 427 m, about 1 min at 8 m/s. |
| **☀ Rooftop solar** | Energy per roof per year, with shading from taller buildings and trees traced along the sun's path. CSV per building. | Test scene: 8 roofs, about 900 MWh a year; the card adds kWp, ₹ a year and CO₂ avoided. |
| **🗺 Map overlay** | Lays a WMS map (OpenStreetMap, ISRO Bhuvan or any WMS address) over the scene, in 2D and 3D. GeoTIFF only. | Roads and names over a flood scenario. |
| **🧩 Mosaic** | Joins neighbouring GeoTIFF scenes into one larger scene from their saved results (no new model run). | Two 400 m tiles → one 700 m scene. |

## 4. Validate & calibrate mode

### 4.1 Check the heights against reference data

**Load a reference:**
- a **raster**: a LiDAR or other reference **DSM** (surface, m above sea level), **nDSM** (height above ground) or
  **DTM** (bare ground), in any coordinate system; or
- a **CSV of surveyed points**, with `lon,lat,z` (WGS84) or `col,row,z` (image pixels).

Set the **Type** and the vertical **Datum**:
- EGM2008 sea level, what DepthWizard uses;
- EGM96, used by SRTM and CartoDEM;
- the ellipsoid, used by GPS / GNSS.

Then press **Compare**.

**Check with ICESat-2 laser** compares the scene with NASA ICESat-2 laser photons that cross it. This needs a
GeoTIFF scene and internet. Laser tracks are kilometres apart, so many small scenes have none.
- **The main numbers are not independent.** Where the terrain was levelled to these same photons, the surface figure
  partly checks the laser against itself.
- **Held-out passes (not used for levelling)** is the independent check. The terrain is levelled on some laser passes
  and checked on the others. It needs at least 2 passes on each side; with fewer, the table shows a note instead.
- **When the terrain was not levelled.** The terrain is only levelled when the photons come from 2 or more passes. One
  pass is a single line, and a local DEM error along it is not an offset for the whole scene. If the scene has only
  one pass, a note says so, and the figures describe the unlevelled terrain.
- **Roof photons in towns.** ICESat-2 sometimes labels roof photons as ground. In dense towns the held-out terrain
  figure can then measure roofs, not ground (in Chandigarh it reads about 15 m too low for this reason).

**Results:**
- **Summary figures:** MAE, RMSE, **correlation r**, bias, NMAD (a robust spread) and the share within ±2 m.
- **Mean offset removed:** the same figures again with the mean offset taken out. This shows what remains if the
  reference uses a different datum.
- **Scatter plot:** ours against the reference. The dashed line means perfect agreement.
- **Error histogram.**
- **Tables by landscape** (urban / forested / sparse-open / water), **by terrain** (flat / rolling / hilly) and by
  height band.
- **Map:** **Show → Error vs reference** colours the map. Blue means ours is lower, red means ours is higher.
  Hovering gives the error at that point. ICESat-2 photons and surveyed points are drawn as dots coloured by their
  error.

**Scenes without georeferencing:** a raster must cover exactly the same area. The heights are then compared after a
best-fit scale and offset, because relative heights have no absolute scale.

### 4.2 Calibrate with ground control points (GCPs)

1. Click **＋ Add points**, then click places whose elevation you know: survey marks, benchmarks, GNSS points. Click
   **✓ Done adding** when finished.
2. Type each point's known height in metres above sea level.
3. Click **Fit & apply**.

The fit always adjusts the **level**. With 2 or more points that differ in height by at least 3 m it also fits a
**height scale**. With 4 or more points (5 if a height scale is fitted) it also corrects a **tilt**.

**The card shows:**
- the error at the points before and after the fit;
- a **leave-one-out** error: each point is predicted by a fit that did not use it, so this is an honest estimate of
  accuracy at new places.

**What the calibration changes:** it applies to every view, the flood tools and the download **DSM calibrated with
control points**. Untick "Use the calibrated heights" to compare with and without it.

**PNG/JPG images:** control points turn their relative heights into absolute ones.

### 4.3 More checks and fixes (toolbar)

| Tool | What it does | Example |
|---|---|---|
| **🌗 Shadow heights** | Height = shadow length × tan(sun elevation). Enter the sun elevation and azimuth from the image metadata, or the acquisition time in UTC and press **Compute**. **📏 Measure a shadow**: click where a building meets its shadow, then the far end. **🤖 Measure all buildings** does it for every building with a clear shadow. The card shows shadow height ÷ model height. | Test scene (model at 0.75 × true): median ×1.33 over 8 buildings → **Use ×1.33 for all buildings**. |
| **🌲 Fix tall objects** | Scales building and tree heights (the model's main weakness). **Fit from ICESat-2** uses NASA laser top-of-canopy heights over the model's trees. Applies to every view, the tools and validation, and adds the download *Height with tall-object fixes*. **Reset** removes it. | Test scene: trees ×1.5, canopy error 6.0 → 0.01 m at 44 laser photons. |
| **± Calibrated error** | After a check in **Compare with reference**, turns the ± spread into a calibrated error bar (68 / 90 / 95 %). The *check* column tests it on half of the values it did not use. | Hover then reads like `12.4 m ± 3.1 m (90 %)`: 9 in 10 true heights lie within the band. |
| **⛰ Terrain source** | Upload your own DEM (ISRO CartoDEM from Bhuvan, SRTM…) to replace Copernicus GLO-30. Choose EGM96 for CartoDEM / SRTM. It must cover the whole scene. **Back to the default** undoes it. | `cartodem_shimla.tif`, EGM96. |

**GNSS and field points** (in **📍 Control points**): import a CSV (`lat, lon, alt`) or GPX file, or **Load
field-app points**. Pick the height type: raw GNSS / phone GPS heights are *ellipsoidal*, and DepthWizard converts
them to sea level. Then **Fit & apply** as in 4.2.

### 4.4 Field app (phone)

Start the app with `python app.py --lan` and open the printed `http://<computer>:8000/field` on a phone on the same
Wi-Fi. Choose the scene, **📍 Record my position**, type the known height of a survey mark (or keep the GPS height),
and **Send to DepthWizard**. Points stay on the phone until they are sent.

- Phone GPS heights are only good to about ±10 m. Use a survey mark's known height or a survey-grade GNSS receiver
  for calibration.
- Browsers give GPS only on https pages or on the computer itself. Over plain http on a phone, type the position.
- `--lan` lets anyone on that network reach the app. Use it only on a trusted network.

## 5. Disaster tools mode

| Tool | What it does |
|---|---|
| **Flood** + water level | Colours flooded ground, submerged and partly flooded buildings, and the floor area under water |
| **Water from** | *All low ground* (everything below the level floods), *scene edges* (water comes from a river or the sea outside the image and floods only ground it can reach), or *points I click* |
| **⏱ Timeline** | How the flood develops hour by hour. Inputs: rain (constant, or the Open-Meteo forecast), river rise, drain capacity and the area draining into the scene. Shows a "time until flooded" map and when each building gets water. |
| **⤳ Route** | Route from A to B, on foot or by car. Avoids buildings, steep ground and water deeper than the limit, and prefers roads. **▶ Fly** follows the route in 3D. |
| **🚁 Relief sites** | Helicopter landing circles and relief camp areas: flat, open and dry ground. Shows capacity (45 m² per person), road access and **Route here**. |

| **💧 Flowing water** | A 2D shallow-water simulation: water spreads over time from inflow points (a breach, a river, a drain outlet) and rain. Drag the time slider, or show the "time until wet" map. Turns the level flood off (one water model at a time). The card shows the area under water, the deepest water and the buildings wet at each time. |
| **🧭 Evacuation plan** | Sends each building's residents to the nearest relief camp that still has space, avoiding deep water. Choose who leaves: flooded buildings, high landslide risk, or everyone. Buildings are coloured by their camp; red = no dry route (boats / helicopters), grey = no camp space left. |
| **👥 People at risk** | Residents ≈ floors × footprint × occupied share ÷ floor space per person (10 m², 80 % by default), counted for each open hazard tool. Test scenes: 1 651 residents; 616 lived in the 2 collapsed buildings. |
| **🏚 Damage** | Open the after-event scene, choose the before image, **Compare**. Buildings that lost ≥ 50 % of their height are collapsed, ≥ 20 % damaged (both editable); also new structures, lost tree canopy and debris volume. The two images are aligned automatically. |
| **⛰ Landslide risk** | A screening map from slope, land cover and local relief (ratings after BIS IS 14496 Part 2), raised for heavy rain. **From timeline / forecast** takes the highest 24-hour rain. Needs a GeoTIFF scene. |
| **🛰 Observed flood** | Load a real flood map (Sentinel-1 radar in dB or linear, or any 0/1 water mask). Shows hits, misses and false alarms against the scenario, with CSI. **🎯 Fit the water level** finds the level that matches it best. |


These tools give **scenarios, not forecasts**. The ground model has a 30 m resolution, so check routes and sites on
the ground.
- **Terrain error:** in our Indian laser tests (2 scenes per landscape) it was about 2 m on sparse and urban land,
  about 8 m in hills, and about 20 m under dense forest.
- **Building and tree heights:** they carry the model error. Tall buildings and trees come out too low.

## 6. Shortcuts

Address-bar shortcuts, combinable with `-`:

| Shortcut | Effect |
|---|---|
| `#3d` | Open in 3D view |
| `#validate` | Open in Validate & calibrate mode |
| `#flood`, `#sites` | Open the Disaster tools with flooding or the relief-site finder on |
| `#scene=<name>` | Open a particular scene |
| `#clean` | Presentation view with no panels |
| `#tour` | Start the automatic flythrough |

Example: `http://127.0.0.1:8000/#3d-validate-scene=chandigarh_sector17`.
