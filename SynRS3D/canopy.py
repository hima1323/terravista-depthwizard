"""Tree (canopy) heights from Meta's global 1 m canopy height map, for the model's weakest class: trees.

Source: Tolan et al. (2024), "Very high resolution canopy height maps from RGB imagery using self-supervised vision
transformer and convolutional decoder trained on aerial lidar", Remote Sensing of Environment 300 (the
HighResCanopyHeight model, run by Meta over the globe and calibrated with GEDI). Public on AWS Open Data, licence
CC BY 4.0: s3://dataforgood-fb-data/forests/v1/alsgedi_global_v6_float/chm/<zoom-9 quadkey>.tif, uint8 metres of
canopy height (0 = no canopy), Web Mercator, ~1.2 m pixels. The imagery behind it is mostly 2018-2020 (Maxar Vivid),
so trees felled or grown since then differ from your image.

    canopy_on_grid(image_path)  -> (float32 canopy heights on the image's pixel grid, NaN where no tile, info)
"""
import math, os

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds

URL = 'https://dataforgood-fb-data.s3.amazonaws.com/forests/v1/alsgedi_global_v6_float/chm/{}.tif'
ZOOM = 9
SOURCE = 'Meta global canopy height map (Tolan et al. 2024, CC BY 4.0)'
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                GDAL_HTTP_MAX_RETRY='3', GDAL_HTTP_RETRY_DELAY='1')


def tile_xy(lon, lat, z=ZOOM):
    s = math.sin(math.radians(max(-85.05, min(85.05, lat))))
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n)


def quadkey(x, y, z=ZOOM):
    return ''.join(str(((x >> (z - i - 1)) & 1) + 2 * ((y >> (z - i - 1)) & 1)) for i in range(z))


def tiles_for(bounds):
    """Quadkeys of the zoom-9 tiles that cover lon/lat bounds (w, s, e, n)."""
    w, s, e, n = bounds
    x0, y0 = tile_xy(w, n)
    x1, y1 = tile_xy(e, s)
    return [quadkey(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def canopy_on_grid(image_path, url=URL):
    """Canopy heights (m) on the image's own pixel grid, bilinear from the map's ~1.2 m pixels. NaN = no tile there."""
    with rasterio.open(image_path) as img:
        if not img.crs:
            raise ValueError('the canopy map needs a georeferenced (GeoTIFF) scene')
        crs, tr, shape = img.crs, img.transform, (img.height, img.width)
        bounds = transform_bounds(crs, 'EPSG:4326', *img.bounds)
    out = np.full(shape, np.nan, np.float32)
    used = []
    with rasterio.Env(**GDAL_ENV):
        for qk in tiles_for(bounds):
            path = url.format(qk)
            try:
                with rasterio.open(path if os.path.exists(path) else '/vsicurl/' + path) as src:
                    part = np.full(shape, np.nan, np.float32)
                    reproject(rasterio.band(src, 1), part, src_transform=src.transform, src_crs=src.crs, src_nodata=None,
                              dst_transform=tr, dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.bilinear)
            except rasterio.errors.RasterioIOError:
                continue   # no tile: open sea or no data
            out = np.where(np.isnan(out), part, out)
            used.append(qk)
    if not used or np.isnan(out).all():
        raise ValueError('the canopy map has no data for this area (or it could not be downloaded)')
    return out, {'source': SOURCE, 'tiles': used, 'coverage_pct': round(100 * float(np.isfinite(out).mean()), 1)}


def tree_stats(canopy, h, lc, trees=4):
    """How the model's tree heights compare with the canopy map on the model's tree pixels (both > 2 m)."""
    sel = (lc == trees) & np.isfinite(canopy)
    both = sel & (canopy > 2) & (h > 2)
    if both.sum() < 100:
        return {'tree_pixels': int(sel.sum()), 'note': 'too few tree pixels with canopy over 2 m to compare'}
    c, m = canopy[both], h[both]
    return {'tree_pixels': int(sel.sum()), 'compared': int(both.sum()), 'canopy_median_m': round(float(np.median(c)), 2),
            'model_median_m': round(float(np.median(m)), 2), 'ratio_median': round(float(np.median(c / m)), 3),
            'mean_diff_m': round(float((c - m).mean()), 2), 'canopy_p90_m': round(float(np.percentile(c, 90)), 1)}


if __name__ == '__main__':
    assert tile_xy(88.61, 27.63) == (382, 215) and quadkey(382, 215) == '123131332'   # a real tile: Teesta valley, Sikkim
    assert len(tiles_for((88.58, 27.60, 88.62, 27.65))) == 2            # straddles a tile edge at 88.594 E
    h = np.full((40, 40), 10, np.float32); lc = np.full((40, 40), 4, np.uint8); c = np.full((40, 40), 15, np.float32)
    s = tree_stats(c, h, lc)
    assert s['ratio_median'] == 1.5 and s['mean_diff_m'] == 5.0, s
    print('canopy.py self-check ok')
