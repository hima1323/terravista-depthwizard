#!/usr/bin/env bash
# Start the DepthWizard demo on Replit (or any Linux server): install the light requirements once, then serve
# on 0.0.0.0. PORT defaults to 8000, the port .replit maps to the public URL.
set -e
cd "$(dirname "$0")"
python -c "import cv2, rasterio, pyproj, PIL" 2>/dev/null || pip install -q -r requirements-demo.txt
cd SynRS3D
exec python app.py --host 0.0.0.0 --port "${PORT:-8000}"
