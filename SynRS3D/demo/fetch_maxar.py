"""Cut a georeferenced RGB window around a point from a Maxar Open Data image (real disaster imagery, CC BY-NC 4.0).

usage: python demo/fetch_maxar.py <item.json url> <lat> <lon> <out.tif> [size_px=1024]
Item URLs come from the STAC catalog at https://maxar-opendata.s3.amazonaws.com/events/catalog.json.
Only the needed part of the cloud-optimised GeoTIFF is downloaded.
"""
import json, sys, urllib.request
from urllib.parse import urljoin

import numpy as np
import rasterio
from rasterio.warp import transform
from rasterio.windows import Window

GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
                GDAL_HTTP_MAX_RETRY='4', GDAL_HTTP_RETRY_DELAY='2')


def fetch(item_url, lat, lon, out, size=1024):
    item = json.load(urllib.request.urlopen(item_url, timeout=60))
    href = urljoin(item_url, item['assets']['visual']['href'])
    with rasterio.Env(**GDAL_ENV), rasterio.open('/vsicurl/' + href) as src:
        (x,), (y,) = transform('EPSG:4326', src.crs, [lon], [lat])
        row, col = src.index(x, y)
        win = Window(col - size // 2, row - size // 2, size, size)
        a = src.read([1, 2, 3], window=win, boundless=True, fill_value=0)
        empty = float((a.max(0) == 0).mean())  # share of pixels outside the image strip
        profile = dict(driver='GTiff', height=size, width=size, count=3, dtype='uint8', crs=src.crs,
                       transform=src.window_transform(win), compress='deflate')
    with rasterio.open(out, 'w', **profile) as dst:
        dst.write(a)
        dst.update_tags(SOURCE=f"Maxar Open Data, {item['id']}, {item['properties'].get('datetime', '')[:10]} "
                               '(CC BY-NC 4.0)')
    return empty, abs(profile['transform'].a)


if __name__ == '__main__':
    empty, gsd = fetch(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4],
                       *(int(v) for v in sys.argv[5:6]))
    print(f'{sys.argv[4]}: {gsd:.2f} m/px, {empty:.0%} empty')
