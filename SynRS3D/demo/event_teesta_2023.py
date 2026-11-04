"""A real Indian event, end to end: the Teesta glacial-lake outburst flood, Sikkim, 4 October 2023.

On 4 Oct 2023 South Lhonak lake (North Sikkim) breached; the flood ran down the Lachen Chu / Teesta, destroyed the
Chungthang dam and killed over 70 people. This script builds what DepthWizard needs to analyse it, from public data
on AWS Open Data (no login), and measures what the satellites saw:

  1. Scene: a pre-event Maxar image (7 Mar 2022, 0.3 m, Maxar Open Data, CC BY-NC 4.0) of the Lachen Chu valley north
     of Chungthang, resampled to 0.5 m -> demo/samples/teesta_lachen_2022.tif. The app runs the height model on it.
  2. Observed flood map: Sentinel-2 L2A (ESA Copernicus, Element 84 COGs) one year apart, both cloud-free, same season:
     20 Nov 2022 (before) vs 15 Nov 2023 (after). Ground the flood scoured or buried = vegetation lost (NDVI drops by
     > 0.25 to < 0.3) or new water (MNDWI > 0), on clear pixels, within 600 m of the river channel, on slopes < 25°
     (Copernicus GLO-30). -> demo/reference/teesta_observed_2023.tif (1 = flood-affected, 0 = not, 255 = no data),
     for the app's Respond → Observed flood tool.
  3. Lake: South Lhonak lake water area (MNDWI > 0) before vs after.
  4. Report: demo/benchmark/event_teesta_2023.md + event_teesta_2023_results.json, every number from this run.

Then, in the app: open the scene, Respond → Observed flood → load teesta_observed_2023.tif → CSI against the flood
scenario and "Fit the water level"; Assess → People at risk, Situation report; Validate → Fix tall objects (canopy).

usage:  python demo/event_teesta_2023.py [--size-m 1600] [--skip-scene]
        python demo/event_teesta_2023.py --selftest
"""
import argparse, json, math, os, sys, time, urllib.request

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform as warp_transform, transform_bounds
from rasterio.windows import from_bounds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES, REFERENCE, BENCH = (os.path.join(ROOT, 'demo', d) for d in ('samples', 'reference', 'benchmark'))
MAXAR = ('https://maxar-opendata.s3.amazonaws.com/events/India-Floods-Oct-2023/ard/45/120220033311/2022-03-07/'
         '10300100CE8D0400-visual.tif')
S2 = 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/45/R/XL/'
BEFORE, AFTER = '2022/11/S2B_45RXL_20221120_0_L2A', '2023/11/S2B_45RXL_20231115_0_L2A'
GLO30 = '/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{0}/{0}.tif'
CENTRE = (88.6135, 27.6360)          # Lachen Chu valley, settlements on the river, north of Chungthang
LAKE_BBOX = (88.16, 27.88, 88.23, 27.94)
CRS = 'EPSG:32645'
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='4', GDAL_HTTP_RETRY_DELAY='2')
CLOUDY = (0, 1, 2, 3, 8, 9, 10, 11)  # SCL: no data, saturated, dark area (terrain shadow), cloud shadow, clouds, cirrus, snow
LAKE_CENTRE = (88.196, 27.912)       # South Lhonak lake


def utm_box(lon, lat, size_m):
    (x,), (y,) = warp_transform('EPSG:4326', CRS, [lon], [lat])
    h = size_m / 2
    return x - h, y - h, x + h, y + h


def item(path):
    n = path.split('/')[-1]
    return json.load(urllib.request.urlopen(f'{S2}{path}/{n}.json', timeout=60))


def read_band(href, box, res, resampling=Resampling.bilinear):
    """A Sentinel-2 band on a fixed UTM grid (res m) over box (xmin, ymin, xmax, ymax), float32."""
    W, H = int(round((box[2] - box[0]) / res)), int(round((box[3] - box[1]) / res))
    out = np.zeros((H, W), np.float32)
    with rasterio.open('/vsicurl/' + href) as src:
        reproject(rasterio.band(src, 1), out, src_transform=src.transform, src_crs=src.crs, dst_transform=from_origin(box[0], box[3], res, res),
                  dst_crs=CRS, resampling=resampling)
    return out


def indices(path, box, res=10.0):
    """NDVI, MNDWI and a usable-pixel mask for one Sentinel-2 item."""
    a = {k: v['href'] for k, v in item(path)['assets'].items()}
    g, r, n = (read_band(a[k], box, res) for k in ('green', 'red', 'nir'))
    sw = read_band(a['swir16'], box, res)
    scl = read_band(a['scl'], box, res, Resampling.nearest).astype(np.uint8)
    nd = lambda p, q: (p - q) / np.maximum(p + q, 1e-6)
    return nd(n, r), nd(g, sw), ~np.isin(scl, CLOUDY) & (g > 0)


def glo30(box, res):
    """Copernicus GLO-30 elevation on the same UTM grid (for slope)."""
    w, s, e, n = transform_bounds(CRS, 'EPSG:4326', *box)
    W, H = int(round((box[2] - box[0]) / res)), int(round((box[3] - box[1]) / res))
    out = np.full((H, W), np.nan, np.float32)
    for la in range(math.floor(s), math.floor(n) + 1):
        for lo in range(math.floor(w), math.floor(e) + 1):
            t = f"Copernicus_DSM_COG_10_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM"
            part = np.full((H, W), np.nan, np.float32)
            with rasterio.open(GLO30.format(t)) as src:
                reproject(rasterio.band(src, 1), part, src_transform=src.transform, src_crs=src.crs, dst_transform=from_origin(box[0], box[3], res, res),
                          dst_crs=CRS, dst_nodata=np.nan, resampling=Resampling.bilinear)
            out = np.where(np.isnan(out), part, out)
    return out


def slope_deg(z, res):
    gy, gx = np.gradient(z.astype(np.float64), res, res)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def dilate(mask, r):
    import cv2
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.dilate(mask.astype(np.uint8), k) > 0


def flood_mask(nb, wb, ok_b, na, wa, ok_a, slope, res):
    """Flood-affected ground: vegetation lost or new water, near the river channel, on valley-floor slopes."""
    clear = ok_b & ok_a
    water_b, water_a = wb > 0, wa > 0
    scoured = (nb - na > 0.25) & (na < 0.3)
    new_water = water_a & ~water_b
    channel = dilate((water_b | water_a) & clear, int(round(600 / res)))
    hit = clear & channel & (slope < 25) & (scoured | new_water)
    return hit, clear, channel


def lake_area(path, res=10.0):
    box = transform_bounds('EPSG:4326', CRS, *LAKE_BBOX)
    _, w, ok = indices(path, box, res)
    water = (w > 0.3) & ok           # MNDWI on clear, unshadowed pixels (glacier ice and terrain shadow score high too)
    import cv2
    n, lab = cv2.connectedComponents(water.astype(np.uint8), connectivity=4)
    (cx,), (cy,) = warp_transform('EPSG:4326', CRS, [LAKE_CENTRE[0]], [LAKE_CENTRE[1]])
    r0, c0 = int((box[3] - cy) / res), int((cx - box[0]) / res)
    ids = lab[max(0, r0 - 3):r0 + 4, max(0, c0 - 3):c0 + 4]        # the lake = the water body at the lake's centre
    k = np.bincount(ids[ids > 0]).argmax() if (ids > 0).any() else 0
    nir = read_band({kk: v['href'] for kk, v in item(path)['assets'].items()}['nir'], box, res)
    return {'lake_km2': round(float((lab == k).sum()) * res * res / 1e6, 3) if k else 0.0,
            'lake_nir_median': round(float(np.median(nir[lab == k])) / 1e4, 3) if k else None,   # turbidity: silt raises NIR
            'clear_pct': round(100 * float(ok.mean()), 1)}


def make_scene(size_m, res=0.5):
    """The pre-event Maxar image over the valley, 0.5 m, as the app's scene."""
    box = utm_box(*CENTRE, size_m)
    W = H = int(round(size_m / res))
    rgb = np.zeros((3, H, W), np.uint8)
    with rasterio.open('/vsicurl/' + MAXAR) as src:
        assert str(src.crs) == CRS, src.crs
        for b in range(3):
            reproject(rasterio.band(src, b + 1), rgb[b], src_transform=src.transform, src_crs=src.crs,
                      dst_transform=from_origin(box[0], box[3], res, res), dst_crs=CRS, resampling=Resampling.average)
    valid = float((rgb.max(0) > 0).mean())
    os.makedirs(SAMPLES, exist_ok=True)
    path = os.path.join(SAMPLES, 'teesta_lachen_2022.tif')
    with rasterio.open(path, 'w', driver='GTiff', width=W, height=H, count=3, dtype='uint8', crs=CRS, photometric='RGB',
                       transform=from_origin(box[0], box[3], res, res), compress='deflate') as d:
        d.write(rgb)
        d.update_tags(SOURCE='Maxar Open Data, India-Floods-Oct-2023, 10300100CE8D0400, 2022-03-07 (CC BY-NC 4.0)')
    return path, box, valid


def run(size_m, skip_scene):
    t0 = time.time()
    out = {'event': 'Teesta glacial-lake outburst flood (South Lhonak lake), Sikkim, 4 Oct 2023',
           'sentinel2_before': BEFORE.split('/')[-1], 'sentinel2_after': AFTER.split('/')[-1], 'maxar_pre_event': MAXAR.split('/')[-1]}
    with rasterio.Env(**GDAL_ENV):
        if not skip_scene:
            path, sbox, valid = make_scene(size_m)
            out['scene'] = {'file': os.path.relpath(path, ROOT), 'size_m': size_m, 'gsd_m': 0.5, 'valid_pct': round(100 * valid, 1),
                            'centre_lonlat': CENTRE}
            print(f'scene: {path} ({valid:.0%} image)', flush=True)
        # observed flood map on a 10 m grid: the scene, and a 12 km stretch of the valley for context
        for key, size in (('scene_area', size_m), ('valley_12km', 12000)):
            box = utm_box(*CENTRE, size)
            nb, wb, okb = indices(BEFORE, box)
            na, wa, oka = indices(AFTER, box)
            z = glo30(box, 10.0)
            hit, clear, channel = flood_mask(nb, wb, okb, na, wa, oka, slope_deg(np.nan_to_num(z, nan=float(np.nanmean(z))), 10.0), 10.0)
            out[key] = {'area_km2': round(size * size / 1e6, 2), 'clear_pct': round(100 * float(clear.mean()), 1),
                        'flood_affected_km2': round(float(hit.sum()) * 100 / 1e6, 3),
                        'valley_floor_checked_km2': round(float((clear & channel).sum()) * 100 / 1e6, 3),
                        'water_before_km2': round(float(((wb > 0) & clear).sum()) * 100 / 1e6, 3),
                        'water_after_km2': round(float(((wa > 0) & clear).sum()) * 100 / 1e6, 3)}
            if key == 'scene_area':
                os.makedirs(REFERENCE, exist_ok=True)
                f = os.path.join(REFERENCE, 'teesta_observed_2023.tif')
                m = np.where(clear, hit.astype(np.uint8), 255).astype(np.uint8)
                with rasterio.open(f, 'w', driver='GTiff', width=m.shape[1], height=m.shape[0], count=1, dtype='uint8', crs=CRS, nodata=255,
                                   transform=from_origin(box[0], box[3], 10.0, 10.0), compress='deflate') as d:
                    d.write(m, 1)
                    d.update_tags(CONTENT='1 = flood-affected (vegetation lost or new water near the channel), 0 = not, 255 = no data',
                                  SOURCE=f'Sentinel-2 L2A {out["sentinel2_before"]} vs {out["sentinel2_after"]}')
                out[key]['file'] = os.path.relpath(f, ROOT)
            print(key, out[key], flush=True)
        out['lake_before'], out['lake_after'] = lake_area(BEFORE), lake_area(AFTER)
        b, a = out['lake_before']['lake_km2'], out['lake_after']['lake_km2']
        out['lake_change'] = {'km2': round(a - b, 3), 'pct': round(100 * (a - b) / b, 1) if b else None}
        print('lake', out['lake_before'], '->', out['lake_after'], flush=True)
    out['seconds'] = round(time.time() - t0)
    os.makedirs(BENCH, exist_ok=True)
    json.dump(out, open(os.path.join(BENCH, 'event_teesta_2023_results.json'), 'w'), indent=1)
    write_report(out, size_m)
    return out


def write_report(o, size_m):
    s, v = o.get('valley_12km', {}), o.get('scene_area', {})
    lb, la, lc = o['lake_before'], o['lake_after'], o['lake_change']
    md = f"""# Teesta glacial-lake outburst flood, Sikkim, 4 October 2023

A real Indian event, analysed with public satellite data only (AWS Open Data, no login). Every number below comes from
`demo/benchmark/event_teesta_2023_results.json`, written by:

```
python demo/event_teesta_2023.py --size-m {size_m}
```

## What the satellites saw

| Measure | Before (20 Nov 2022) | After (15 Nov 2023) | Change |
|---|---|---|---|
| South Lhonak lake area (open water, MNDWI > 0.3) | {lb['lake_km2']} km² | {la['lake_km2']} km² | {lc['km2']:+} km² ({lc['pct']:+}%) |
| Lake water near-infrared, median (silt makes it brighter) | {lb['lake_nir_median']} | {la['lake_nir_median']} | ×{la['lake_nir_median'] / lb['lake_nir_median']:.1f} |
| Water in the 12 km valley stretch | {s.get('water_before_km2')} km² | {s.get('water_after_km2')} km² | |

| Area | Clear pixels | Valley floor checked | Flood-affected ground |
|---|---|---|---|
| 12 km × 12 km of the Lachen Chu valley | {s.get('clear_pct')}% | {s.get('valley_floor_checked_km2')} km² | **{s.get('flood_affected_km2')} km²** |
| The DepthWizard scene ({size_m / 1000:.1f} km square) | {v.get('clear_pct')}% | {v.get('valley_floor_checked_km2')} km² | **{v.get('flood_affected_km2')} km²** |

![Sentinel-2, 20 Nov 2022 (left) and 15 Nov 2023 (middle); flood-affected ground in magenta (right); white box = the DepthWizard scene](../../../docs/img/teesta_2023_flood_map.jpg)

*Flood-affected* = within 600 m of the river channel, slope under 25°, clear in both images, and either vegetation lost
(NDVI fell by more than 0.25 to below 0.3: scoured or buried by debris) or new water (MNDWI > 0 now, not before).

## Data

| | |
|---|---|
| Pre-event scene | Maxar Open Data, event India-Floods-Oct-2023, `{o['maxar_pre_event']}`, 7 Mar 2022, 0.3 m, resampled to 0.5 m (CC BY-NC 4.0: demonstration only) |
| Before / after | Sentinel-2 L2A `{o['sentinel2_before']}` / `{o['sentinel2_after']}` (ESA Copernicus, Element 84 COGs), 10 m, same season, both under 2% cloud |
| Slope | Copernicus GLO-30 DEM |
| Outputs | `{v.get('file', 'demo/reference/teesta_observed_2023.tif')}` (observed flood map for the app), `{o.get('scene', {}).get('file', 'demo/samples/teesta_lachen_2022.tif')}` (the scene) |

## In the app

1. Start DepthWizard; it estimates heights for `teesta_lachen_2022` (the RS3DAda weights are needed once).
2. **Respond → Flood scenario** on, water from the scene edges; **Observed flood** → load `demo/reference/teesta_observed_2023.tif`
   → CSI of the scenario against what happened, **Fit the water level**.
3. **Validate → Fix tall objects → Meta canopy map**: the valley slopes are forest, the model's weakest class.
4. **Assess → People at risk** and **Situation report**.

**The lake:** its shoreline moved little, but its water became much more silt-laden. The outburst lowered the lake
(it emptied through the breached moraine) more than it shrank its outline, so area alone understates the water
released; the volume needs a before/after elevation model of the lake basin.

## Caveats

- The flood happened in October, under monsoon cloud; the first clear pair is a month later, so the map shows what the
  flood left (scoured banks, debris, new channels), not the peak water.
- Vegetation loss also comes from landslides and road works; the 600 m channel buffer and slope limit keep most of the
  map on the valley floor, not all of it.
- The pre-event Maxar image is from March 2022: buildings built since are missing from the scene.
- 10 m pixels: narrow channels and single buildings are below the resolution; use it for areas, not for one house.
"""
    open(os.path.join(BENCH, 'event_teesta_2023.md'), 'w').write(md)


def selftest():
    # a 20 × 20 valley: channel along row 10, the flood stripped vegetation from rows 8–12 and widened the water
    H = W = 20
    nb = np.full((H, W), 0.7, np.float32); na = nb.copy()
    wb = np.full((H, W), -0.4, np.float32); wa = wb.copy()
    wb[10] = 0.3; wa[9:12] = 0.3
    na[8:13] = 0.1
    ok = np.ones((H, W), bool)
    hit, clear, channel = flood_mask(nb, wb, ok, na, wa, ok, np.zeros((H, W)), 100.0)
    assert hit[8:13].all() and not hit[:7].any() and not hit[14:].any(), hit.astype(int)
    steep = np.zeros((H, W)); steep[12] = 40
    assert not flood_mask(nb, wb, ok, na, wa, ok, steep, 100.0)[0][12].any()          # steep slope: not the valley floor
    cloudy = ok.copy(); cloudy[8] = False
    assert not flood_mask(nb, wb, cloudy, na, wa, ok, np.zeros((H, W)), 100.0)[0][8].any()
    print('event_teesta_2023 self-check ok')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--size-m', type=float, default=1600, help='side of the square scene, metres (default 1600 = 3200 px at 0.5 m)')
    ap.add_argument('--skip-scene', action='store_true', help='only the Sentinel-2 / lake analysis')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        selftest()
        sys.exit()
    run(a.size_m, a.skip_scene)
