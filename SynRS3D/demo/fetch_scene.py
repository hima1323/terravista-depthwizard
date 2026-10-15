"""Download a georeferenced 1024x1024 satellite image (Esri World Imagery, zoom 18 ~0.5 m/px).

usage: python demo/fetch_scene.py <name> <lat> <lon> [out_dir]   -> <out_dir or demo/samples>/<name>.tif
"""
import io, os, sys, urllib.request
from math import asinh, pi, radians, tan

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import Affine

URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


def fetch(name, lat, lon, out_dir=None, z=18, n=4):
    N = 2 ** z
    tx = int((lon + 180) / 360 * N) - n // 2
    ty = int((1 - asinh(tan(radians(lat))) / pi) / 2 * N) - n // 2
    im = Image.new('RGB', (256 * n, 256 * n))
    for i in range(n):
        for j in range(n):
            data = urllib.request.urlopen(URL.format(z=z, y=ty + j, x=tx + i), timeout=30).read()
            im.paste(Image.open(io.BytesIO(data)).convert('RGB'), (256 * i, 256 * j))
    R = 6378137
    res = 2 * pi * R / (256 * N)  # metres per pixel in EPSG:3857
    transform = Affine(res, 0, tx * 256 * res - pi * R, 0, -res, pi * R - ty * 256 * res)
    a = np.array(im).transpose(2, 0, 1)
    out = os.path.join(out_dir or os.path.join(os.path.dirname(__file__), 'samples'), f'{name}.tif')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with rasterio.open(out, 'w', driver='GTiff', height=a.shape[1], width=a.shape[2], count=3,
                       dtype='uint8', crs='EPSG:3857', transform=transform) as dst:
        dst.write(a)
    return out


if __name__ == '__main__':
    print(fetch(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), *sys.argv[4:5]))
