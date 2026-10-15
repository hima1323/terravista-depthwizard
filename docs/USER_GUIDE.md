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

## 3. Explore mode: the heights and the 3D flythrough

Choose a scene, then switch between **2D compare** and **3D view**.

**2D compare**
- **Layer:** Height, Uncertainty (±) or Slope.
- **Overlay:** sets how transparent the layer is over the photo.
- **Hover:** shows the height at any point. With terrain, this is metres above sea level = ground + height above
  ground. It also shows the uncertainty and the slope.
- **Hover over a building:** shows its height ± uncertainty, footprint area and estimated floors.

**3D view:** the photo draped on the reconstructed surface.

| Control | What it does |
|---|---|
| Camera: **Orbit** | Drag to rotate, scroll to zoom |
| Camera: **Fly** | W A S D to move, R / F up and down, drag to look, Shift for faster |
| Camera: **Street level** | Walk at eye height; buildings block you |
| **Height ×** | Exaggerates relief, for flat towns |
| **Surface** | Photo, height colours, uncertainty or slope |
| **Click** | Measure any point or building |
| **✎ Draw path**, then **▶ Fly through** | Fly along your own route |
| **● Record video** | Save the flythrough as an MP4/WebM file |

**Download:**
- DSM (m above sea level), terrain DTM, height above ground and uncertainty, as GeoTIFFs for QGIS or ArcGIS;
- the 3D model as `.glb`, in true metres, for Blender or any glTF viewer;
- building blocks as JSON.

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

## 5. Disaster tools mode

| Tool | What it does |
|---|---|
| **Flood** + water level | Colours flooded ground, submerged and partly flooded buildings, and the floor area under water |
| **Water from** | *All low ground* (everything below the level floods), *scene edges* (water comes from a river or the sea outside the image and floods only ground it can reach), or *points I click* |
| **⏱ Timeline** | How the flood develops hour by hour. Inputs: rain (constant, or the Open-Meteo forecast), river rise, drain capacity and the area draining into the scene. Shows a "time until flooded" map and when each building gets water. |
| **⤳ Route** | Route from A to B, on foot or by car. Avoids buildings, steep ground and water deeper than the limit, and prefers roads. **▶ Fly** follows the route in 3D. |
| **🚁 Relief sites** | Helicopter landing circles and relief camp areas: flat, open and dry ground. Shows capacity (45 m² per person), road access and **Route here**. |

These tools give **scenarios, not forecasts**. The ground model has a 30 m resolution (about ±2–4 m in height), so
check routes and sites on the ground.

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
