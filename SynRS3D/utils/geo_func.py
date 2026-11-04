import json
import os

import numpy as np
import rasterio


def band_order(src, path):
    """1-based band indices of red, green, blue. A sidecar <image>.bands.json {"order": "rgb"|"bgr"} (written by
    the upload form) wins; then the file's colour interpretation or band names; 4+ unlabelled bands are taken as
    blue, green, red, NIR (Cartosat-3 MX, PlanetScope, most multispectral products); a single band (PAN) is greyscale."""
    side = os.path.splitext(path)[0] + '.bands.json'
    order = json.load(open(side)).get('order') if os.path.exists(side) else None
    n = src.count
    if n < 3:
        return [1, 1, 1]
    if order == 'rgb':
        return [1, 2, 3]
    if order == 'bgr':
        return [3, 2, 1]
    ci = [c.name for c in src.colorinterp]
    if all(c in ci for c in ('red', 'green', 'blue')):
        return [ci.index('red') + 1, ci.index('green') + 1, ci.index('blue') + 1]
    desc = [(d or '').lower() for d in src.descriptions]
    if all(any(c in d for d in desc) for c in ('red', 'green', 'blue')):
        return [next(i + 1 for i, d in enumerate(desc) if c in d) for c in ('red', 'green', 'blue')]
    return [3, 2, 1] if n >= 4 else [1, 2, 3]


def to_uint8(a, nodata=None):
    """HxWx3 array of any type -> uint8. 8-bit data stays as it is; 10/11/12/16-bit or float radiance is stretched
    per band between its 2nd and 98th percentile (a plain cast would wrap 16-bit values around)."""
    if a.dtype == np.uint8:
        return a
    out = np.zeros(a.shape, np.uint8)
    for b in range(a.shape[2]):
        v = a[:, :, b].astype(np.float32)
        ok = np.isfinite(v) & (v != nodata if nodata is not None else True) & (v > 0)
        s = v[ok][:: max(1, ok.sum() // 200000)] if ok.any() else np.zeros(1, np.float32)
        lo, hi = np.percentile(s, [2, 98]) if s.size > 1 else (0.0, 1.0)
        out[:, :, b] = np.clip((v - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
    return out


def load_multiband(path):
    """The image as HxWx3 uint8 RGB, whatever the band count, order or bit depth."""
    with rasterio.open(path, "r") as src:
        a = np.moveaxis(src.read(band_order(src, path)), 0, -1)
        return to_uint8(a, src.nodata)


def load_grayscale(path):
    src = rasterio.open(path, "r")
    return (src.read(1)).astype(np.uint8)

def get_crs(path):
    src = rasterio.open(path, "r")
    return src.crs, src.transform

def save_img(path,img,crs,transform):
    with rasterio.open(
        path,
        'w',
        driver='GTiff',
        height=img.shape[1],
        width=img.shape[2],
        count=img.shape[0],
        dtype=img.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(img)
        dst.close()