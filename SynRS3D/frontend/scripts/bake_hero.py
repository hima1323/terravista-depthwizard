"""Bake the landing page's fixed 3D scene from a processed result, so the hero never depends on the scene library.

    python scripts/bake_hero.py [name]      (default shimla_hill_town; run from SynRS3D/frontend)

Writes public/hero/terrain.f32 (surface heights in m above the scene's lowest ground, N x N, row-major),
public/hero/terrain.jpg (the photo) and public/hero/terrain.json (size, peak, and an elevation profile for the card).
"""
import json, os, sys
import numpy as np
from PIL import Image

N = 192                                   # mesh resolution: plenty for a hero shot, ~150 KB
name = sys.argv[1] if len(sys.argv) > 1 else 'shimla_hill_town'
res = os.path.join(os.path.dirname(__file__), '..', '..', 'demo', 'results')
out = os.path.join(os.path.dirname(__file__), '..', 'public', 'hero')
meta = json.load(open(os.path.join(res, f'{name}.json')))
gw, gh = meta['grid_w'], meta['grid_h']
grid = np.fromfile(os.path.join(res, f'{name}.f32'), np.float32).reshape(gh, gw)
dtm_path = os.path.join(res, f'{name}_dtm.f32')
dtm = np.fromfile(dtm_path, np.float32).reshape(gh, gw) if os.path.exists(dtm_path) else np.zeros_like(grid)
surface = dtm + np.maximum(grid, 0)       # same surface the workspace shows: terrain + objects above ground

# block-average down to N x N (grid is square for the showcase scenes; resample otherwise)
small = np.asarray(Image.fromarray(surface).resize((N, N), Image.BOX), np.float32)
base = float(dtm.min())
os.makedirs(out, exist_ok=True)
(small - base).astype(np.float32).tofile(os.path.join(out, 'terrain.f32'))
Image.open(os.path.join(res, f'{name}.jpg')).convert('RGB').resize((1024, 1024), Image.LANCZOS).save(os.path.join(out, 'terrain.jpg'), quality=82)

# elevation profile along the diagonal from the north-west to the south-east corner
k = np.linspace(0, gw - 1, 72).astype(int)
profile = surface[k * (gh - 1) // (gw - 1), k]
py, px = np.unravel_index(np.argmax(small), small.shape)
json.dump({
    'name': name, 'n': N,
    'width_m': gw * meta['width'] / gw * meta['gsd'], 'height_m': meta['height'] * meta['gsd'],
    'base_m': round(base, 1), 'peak_m': round(float(surface.max()), 1),
    'peak_uv': [round(px / (N - 1), 3), round(py / (N - 1), 3)],
    'profile': [round(float(v), 1) for v in profile],
    'profile_len_m': round(float(np.hypot(meta['width'], meta['height']) * meta['gsd'])),
}, open(os.path.join(out, 'terrain.json'), 'w'))
print('baked', name, 'into', os.path.relpath(out))
