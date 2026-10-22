# Design brief: DepthWizard, full redesign in glassmorphism

Design the complete UI of **DepthWizard**, a desktop web app, in a refined **glassmorphism** style. Below you'll find what the product is, who uses it, every screen and what it contains, real sample data, and the visual direction, which is inspired by the **attached reference image** (section 4.0). Treat this as the single source of truth. Don't invent features or numbers.

---

## 1. What the product is

**DepthWizard** is team **TerraVista (IIT Ropar)**'s entry for **Smart India Hackathon 2026, problem SIH26175: "Single-View Height Estimation and 3D Flythrough"**, set by **ISRO** under the **Disaster Management** theme.

**One-line pitch:** *One satellite image. Heights you can fly through and check.*

From **one optical satellite image** (PNG, JPG or GeoTIFF), DepthWizard:
1. **Estimates the height of every pixel** with RS3DAda, a published remote-sensing AI model (DINOv2 ViT-L/14 encoder + DPT head, NeurIPS 2024). It also outputs land cover (buildings, trees, roads, water and so on).
2. **Builds a surface model (DSM).**
   - For PNG/JPG the heights are **relative**: height above local ground.
   - For GeoTIFF they are **absolute**, in metres above sea level. Our heights sit on a 30 m terrain model with roofs and trees removed. That terrain is levelled to **NASA ICESat-2** laser ground points and, if the user has them, to **ground control points (GCPs)**.
3. **Shows the result as a 3D terrain you can fly through.** The photo is draped on the reconstructed surface, built with Three.js. Camera modes are orbit, free-fly (WASD) and street level, plus a drawn-path flythrough with video recording.
4. **Lets the user validate the heights** against reference data (LiDAR / DSM rasters, surveyed points or ICESat-2), reporting MAE, RMSE, correlation r, bias and NMAD.
5. **Adds disaster tools, organised by phase of the disaster cycle:** landslide-prone slopes and flood exposure (Before), flood scenarios with a rain and river-rise timeline and dry evacuation routes (During), helipad and relief-camp siting (Shelter), and a block-by-block impact report (After).

It runs **locally and offline** on a laptop, served at `http://127.0.0.1:8000`. It isn't a SaaS product: there are no accounts, pricing or login.

### Who uses it
- **Disaster-management officers and GIS analysts** (NDMA, state SDMAs, ISRO/NRSC). They're technical but busy, and they need clear numbers and fast decisions.
- **Hackathon judges** (ISRO scientists). They'll look for scientific honesty and polish.

### Tone
Calm, precise, trustworthy: a **scientific instrument**, not a marketing site. The product states its limitations openly. Tall buildings come out too low, flood results are "scenarios, not forecasts", and the uncertainty band has known coverage gaps. The design should make these caveats **readable, not hidden**. Use small "info" notes and fine print styled with care, not red error banners.

---

## 2. Layout model (keep this structure)

The app is **one full-screen canvas with floating glass panels over it**:

- **Stage (full-bleed, behind everything):** the live **3D terrain** (Three.js) or a **2D map view** (satellite image with a coloured data overlay). This is the hero of every screen, so glass panels must let it show through.
- **Left rail** (~88 px wide, full height, rounded glass pill): the logo plus "DepthWizard" at the top. Then come the workspace items **Scenes, Explore, Validate**, a small group label **"Disaster cycle"**, and the items **Prepare (Before), Respond (During), Relief (Shelter), Assess (After)**. Each item has an icon, a label and a tiny phase caption.
- **Top bar** (floating glass, top centre): a breadcrumb such as "During · Respond", the **current scene name** as the title, a row of **stat chips** (e.g. `Tallest 62.4 m`, `99th pct 38.1 m`, `Built-up 41%`, `Blocks 1,284`, `Ground 312–347 m`, `GSD 0.50 m`, `Consistency 0.84 m`), and a **3D / 2D segmented toggle**.
- **Right panel** (~390 px, floating glass, scrollable): the page's controls and results, grouped in **cards**.
- **Bottom toolbar** (floating glass, bottom centre): a map legend, an overlay-opacity slider, camera mode (**Orbit / Fly (W A S D) / Street level**) and **Auto-orbit**.
- **Toast** for short hints and status.

**Accent per page.** Each page has its own accent colour, so the phase you're in is obvious at a glance. Keep this idea and refine the hues if you like:

| Page | Accent |
|---|---|
| Scenes | sky `#7dd3fc` |
| Explore | indigo `#818cf8` |
| Validate | violet `#c084fc` |
| Prepare | amber `#fbbf24` |
| Respond | blue `#38bdf8` |
| Relief | green `#4ade80` |
| Assess | rose `#fb7185` |

---

## 3. Screens to design (all 7, plus states)

### 3.1 Scenes (home / library)
- **Hero:** "One satellite image. *Heights you can fly through and check.*" Below it, a short paragraph: DepthWizard estimates the height of every pixel, builds an absolute surface model with terrain and laser data, and turns it into tools for each phase of a disaster.
- **Four disaster-phase cards** (Before / During / Shelter / After), each with an icon, phase, name and a one-line blurb (see 3.4–3.7).
- **Scene grid:** thumbnail cards showing the satellite image, scene name and a meta line such as "max 62.4 m · built 41% · geo".
  - **States to show:** done, **processing** (a progress badge like "37%", a progress bar, "estimating heights…"), queued, and error.
- **Side column:**
  - a **drag-and-drop upload zone**: "Drop a satellite image · or click to choose · PNG · JPG · GeoTIFF. GeoTIFF adds true scale and heights above sea level";
  - for the selected scene, **6 KPI tiles**, a fine-print note, and a primary button **"Open in 3D →"**.
- **Sample scenes:** Chandigarh Sector 17, Delhi Central, Mumbai Highrise, Bengaluru Electronic City, Guwahati Riverside, Shimla Hill Town, IIT Ropar, Porto Alegre Centre (Brazil, flood test), Canoas, Sarandi.

### 3.2 Explore (height model)
The full-screen 3D flythrough is the hero here.
- **"Colour the scene by"** card: Photo / Height / Consistency score / Slope, plus an overlay slider.
- **"Fly-through"** card: **✎ Draw path**, **▶ Fly through** / **Stop**, **● Record video**, and a **Height ×** exaggeration slider.
- **Click-to-measure popover** on a building: height **with a 90% interval** (e.g. "18.6 m, 90%: 12.4–24.9 m"), footprint area, and estimated floors (marked "3 m/floor, not validated").
- **Hover readout** in 2D: height, ground elevation, consistency score and slope at the cursor.
- **"Bias correction"** card: a toggle "Apply height correction" with the caveat "Learned on US LiDAR (DFC2019); not verified on Indian cities."
- **"About these heights"** card: the honest-caveats text.
- **Downloads:** DSM, DTM, height above ground and consistency as GeoTIFFs; the 3D model as `.glb`; building blocks as JSON.

### 3.3 Validate & calibrate (accuracy)
- **"Compare with reference data"** card:
  - a file picker ("Reference: GeoTIFF raster or CSV of points");
  - **Measures:** Surface DSM / Height above ground / Bare ground DTM;
  - **Datum:** EGM2008 / EGM96 (SRTM, CartoDEM) / Ellipsoid (GNSS);
  - a **Compare** button;
  - a secondary button **"Check with ICESat-2"**.
- **Results card:**
  - a big metric row: **MAE, RMSE, correlation r, bias, NMAD, within ±2 m**, using tabular numerals with units;
  - the same metrics again "with the mean offset removed";
  - a **scatter plot** (ours vs reference, with a dashed 1:1 line) and an **error histogram**;
  - **breakdown tables** by Landscape (urban / forested / sparse-open / water), Terrain (flat / rolling / hilly) and Height band;
  - for ICESat-2: "Surface vs all N laser photons", "Terrain vs N ground photons", and a highlighted **"Held-out passes (not used for levelling)"** sub-block, the independent check;
  - a "Show on the map → Error vs reference" toggle. Blue means ours is lower and red means ours is higher, using a diverging colour scale.
- **"Calibrate with control points"** card:
  - **＋ Add points** / **✓ Done adding**;
  - a list of points with editable known heights;
  - **Fit & apply** and **Clear**;
  - before/after error and a **leave-one-out** error;
  - a toggle "Use calibrated heights everywhere".
  - Empty state: "No control points yet."
- **Sample numbers:** MAE 3.90 m, RMSE 5.58 m, r 0.61, bias −2.61 m, NMAD 2.52 m, within ±2 m 48%.

### 3.4 Prepare (Before): hazard & exposure
- **"Landslide-prone slopes"** card:
  - a slope-class bar or legend using the BIS IS 14496 classes;
  - a headline "23% of the scene is moderately steep or steeper (> 25°)";
  - a fine-print source note.
- **"Flood exposure"** card:
  - a "Water comes from" selector;
  - a table of water **Rise** → **Ground wet / Blocks / Under / Floor area**, one row per rise (+0.5 m, +1 m, +2 m, +3 m, +5 m);
  - it could also be shown as a small stepped chart.

### 3.5 Respond (During): flood response
- **"Flood scenario"** card:
  - a **Water level** slider;
  - "Water comes from": *All low ground* / *Scene edges* / *Points I click*, with the hint "Click where water comes in: a river, a canal, a breached embankment."
- **"Rain & river timeline"** card:
  - inputs: Rain (constant, or the Open-Meteo forecast), For (hours), River / sea rise, Drains carry (hint: "Indian city drains are typically designed for about 25–50 mm/h") and Area draining here;
  - a **Simulate** button;
  - a **Time** scrubber;
  - a toggle "Show 'time until flooded' map";
  - a timeline table: **When / Water / Flooded / Blocks wet**.
- **Route tool:** pick A → B, on foot or by car, avoiding deep water and steep ground, with **▶ Fly** along the route in 3D.
- **Map legend:** Water / Submerged / Partly flooded.

### 3.6 Relief (Shelter): relief sites
- **"Site rules"** card:
  - Helipad clear circle (hint: "ICAO rule of thumb: 1.5 × helicopter length: ~24 m ALH Dhruv, 38 m Mi-17");
  - Camp area at least;
  - Space per person (hint: "Sphere standard: ≥ 45 m² per person");
  - Max slope;
  - Dry by at least;
  - "Must stay dry for the whole timeline".
- **Ranked lists: "Helicopter landing sites"** and **"Relief camp sites"**. Each item shows size, capacity (persons), slope, distance to road, and a **Route here** button.
- A notice when flood is off: "Flood is off, so water is ignored. Set a scenario →".

### 3.7 Assess (After): impact report
- **Empty state:** "No scenario yet. Set a flood scenario in Respond (or Prepare) and this page sums up what it affects."
- **"Scenario impact"**:
  - KPI tiles: blocks submerged, blocks partly flooded, floor area under water, routes blocked;
  - a sortable table: **Block / State / Height / Floors wet / Area**;
  - **Export impact report (JSON + CSV)**.

### 3.8 Global states
Design these as well:
- loading or processing a scene (model running, with a progress indicator);
- an empty library;
- no internet for ICESat-2;
- the scene isn't a GeoTIFF, so the ICESat-2 feature is disabled with an explanation;
- the toast;
- a `#clean` presentation mode with no panels, the 3D scene only, for demos.

---

## 4. Visual direction: glassmorphism, done properly

### 4.0 Visual reference (image attached)

Take the theme from the attached reference, a "bioma" nature-conservation landing page. Its key ideas:
- a **dark, moody, full-bleed photo** with vivid bokeh (magenta, orange, teal) and **vertical motion-blur light streaks**;
- **huge, tight, bold grotesk headline**: the first lines in white, the punchline in **bright teal/aqua**, led by a short teal dash;
- **one signature accent, teal** (around `#2ee6d0`), with **coral-red** (around `#ef5a4a`) as its only counterpart;
- a **ring/donut stat** with a circular photo inside: a teal arc for one share, a coral arc for the other;
- **big stat numbers** (`36 %`, `64 %`) with the unit as a small superscript, a muted two-line label above, and a **thin vertical colour bar** (teal or coral) beside the label;
- a **glass pill link** ("1 / 8 All statistics here ›") in dark translucent glass;
- an **outline pill** button (Contact us), a **solid white pill** CTA (Speak with us), **circular outline icon buttons**, a centred circular scroll-down button and a **vertical dot pager** on the left edge;
- the whole page sits inside **one large rounded frame** with generous margins.

Adapt it to DepthWizard rather than copying it. The satellite image and 3D terrain replace the hummingbird, and the stats are height metrics instead of habitat loss:
- **Scenes hero:** "One satellite image." in big white type, then "— Heights you can **fly through and check.**" in teal, over a darkened, motion-blurred render of a 3D city terrain. On the right, a **ring stat** with the selected scene's thumbnail inside: teal arc = built-up %, coral arc = open ground %, with two big numbers below (`41 %` built-up, `59 %` open) and a glass pill "1 / 10 All scenes ›" that steps through scenes.
- **Validate:** a ring for "within ±2 m" (teal) vs "outside" (coral), with MAE / RMSE / r as big superscript-unit numbers (`3.90 m`).
- **Assess:** a ring for blocks dry (teal) vs reached by water (coral).
- **Vertical dot pager** on the stage edge for steps of the flythrough or the timeline hours.
- Use **teal for "good / ours / primary action"** and **coral for "loss / risk / flooded"** across the app.

**Mood:** a dark observatory at night. The satellite terrain glows like the jungle in the reference, under frosted-glass instruments.

**Background:**
- deep near-black plum-navy (`#0b0714` to `#05070f`) as the base;
- slow, blurred **bokeh blobs** in teal, magenta and warm orange, plus faint **vertical light streaks**, echoing the reference;
- a very subtle film grain.

On the 3D pages the terrain itself is the background, so panels must stay legible over a busy satellite photo.

**Glass panels:**
- translucent fill (around `rgba(20,26,44,0.45)`), `backdrop-filter: blur(20–24px) saturate(160%)`;
- a 1 px hairline border (`rgba(255,255,255,0.14)`) with a **brighter top-edge inner highlight**;
- large soft shadows;
- radii of 24 / 18 / 12 / 9 px.

Use **two depth levels**: the panel, and slightly lighter inner "glass-in" cards inside it. Avoid stacking glass on glass on glass.

**Legibility over imagery is non-negotiable:**
- body text contrast must meet WCAG AA against the *worst case* (a bright rooftop under the panel). Increase panel opacity where needed;
- provide a **"reduce transparency"** variant (solid panels) for `prefers-reduced-transparency`.

**Typography:**
- **Manrope** (or a similar geometric grotesk, as in the reference) for headings, big numbers and the brand, set large and tight (letter-spacing about −0.03em);
- **Inter** for UI;
- **tabular numerals** for all metrics.

Numbers are first-class, as in the reference: a big value, a small superscript unit, and a muted label with a thin colour bar.

**Accent use:**
- **teal is the brand colour everywhere**: logo, primary actions, focus rings, slider fills, active states;
- the per-page accents from section 2 survive only as a small tint: the active rail item's glow, the breadcrumb dot and the background bokeh;
- coral marks risk, loss and flooding.

**Data colour scales (must stay meaningful):**
- height: a perceptual sequential scale (viridis/turbo-like);
- error: diverging, **blue = ours lower, red = ours higher**;
- flood: water blue, with distinct colours for submerged vs partly flooded;
- slope: BIS classes from green to red.

**Components to define:**
- rail item (default / hover / active);
- top-bar chip; segmented control; slider with value bubble; toggle; select;
- primary / secondary / ghost buttons; icon button;
- card with title and optional info tooltip;
- KPI tile; metric row; data table with sticky header;
- scatter plot and histogram styling; legend; popover (building measure);
- drag-drop zone (idle / hover / uploading);
- scene card (done / processing / error);
- toast; empty state; fine-print / caveat note style.

**Icons:** Lucide (Layers, Box, Target, ShieldAlert, Waves, Tent, ClipboardCheck, Mountain for the logo).

**Motion:**
- subtle and fast (180–300 ms, ease-out `cubic-bezier(.22,1,.36,1)`);
- the accent cross-fades when switching pages, and panels slide in slightly;
- respect `prefers-reduced-motion`.

**Avoid:**
- neon cyberpunk overload and rainbow gradients on text. Vivid colour belongs in the imagery and the background, and the UI itself stays teal, coral and white;
- generic SaaS hero sections, pricing or testimonials;
- fake charts with made-up numbers;
- low-contrast grey-on-glass text;
- heavy borders.

---

## 5. Technical constraints (so the design can be built)

- **Stack:** React 18 + TypeScript + Vite, plain CSS with custom properties (no Tailwind), Three.js for 3D, and Lucide icons. Fonts are self-hosted via @fontsource (Inter Variable, Space Grotesk Variable).
- **Target screens:** desktop/laptop first, 1366×768 to 2560×1440. It must also work on a 1366×768 projector at a hackathon demo, where the right panel scrolls and the stage stays visible. Tablet is nice to have and phone isn't needed.
- **Dark theme** is primary. A light theme is optional.
- **Deliverables:**
  - a **design-token sheet** (colours, glass levels, radii, shadows, type scale, spacing);
  - the **component library**;
  - **all 7 pages** with realistic content from this brief;
  - the global states in 3.8.
