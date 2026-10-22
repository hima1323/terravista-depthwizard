// Pure helpers ported unchanged from the classic viewer (web/index.html): colour ramps, slope classes,
// grid sampling, a binary heap, the exact distance transform, and the land-cover tables the tools use.

export type RGB = [number, number, number];

// Turbo colormap (Google, polynomial approximation)
export function turbo(x: number): RGB {
  x = Math.min(1, Math.max(0, x));
  const r = 0.13572138 + x*(4.61539260 + x*(-42.66032258 + x*(132.13108234 + x*(-152.94239396 + x*59.28637943))));
  const g = 0.09140261 + x*(2.19418839 + x*(4.84296658 + x*(-14.18503333 + x*(4.27729857 + x*2.82956604))));
  const b = 0.10667330 + x*(12.64194608 + x*(-60.58204836 + x*(110.36276771 + x*(-89.90310912 + x*27.34824973))));
  return [r, g, b].map(v => Math.round(Math.min(1, Math.max(0, v)) * 255)) as RGB;
}
// consistency-score ramp (inferno-like), distinct from the height ramp
export function inferno(x: number): RGB {
  const S = [[0,0,4],[87,16,110],[188,55,84],[249,142,9],[252,255,164]];
  x = Math.min(1, Math.max(0, x)) * (S.length - 1);
  const i = Math.min(S.length - 2, Math.floor(x)), f = x - i;
  return S[i].map((v, k) => Math.round(v + (S[i + 1][k] - v) * f)) as RGB;
}
// terrain slope classes (degrees) as in BIS IS 14496 (Part 2) landslide hazard zonation
export const SLOPE_CLASSES: [number, string, RGB][] = [[15, 'very gentle', [46, 160, 67]], [25, 'gentle', [166, 206, 57]],
  [35, 'moderately steep', [255, 214, 10]], [45, 'steep', [247, 127, 0]], [Infinity, 'escarpment / cliff', [214, 40, 40]]];
export const slopeClass = (d: number) => SLOPE_CLASSES.find(([t]) => d <= t)!;
export const slopeRamp = (x: number) => slopeClass(x * 50)[2];   // x = slope / 50°
// ours lower (blue) – equal (white) – ours higher (red)
export function divRamp(x: number): RGB {
  const a = [49, 104, 212], w = [240, 240, 240], b = [214, 57, 57];
  x = Math.min(1, Math.max(0, x));
  const [p, q, f] = x < 0.5 ? [a, w, x * 2] as const : [w, b, (x - 0.5) * 2] as const;
  return p.map((v, k) => Math.round(v + (q[k] - v) * f)) as RGB;
}

export function slopeGrid(z: ArrayLike<number>, W: number, H: number, dx: number, dy: number) {   // degrees, central differences
  const s = new Float32Array(W * H);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const xl = Math.max(0, x - 1), xr = Math.min(W - 1, x + 1), yu = Math.max(0, y - 1), yd = Math.min(H - 1, y + 1);
    const gx = (z[y * W + xr] - z[y * W + xl]) / ((xr - xl) * dx), gy = (z[yd * W + x] - z[yu * W + x]) / ((yd - yu) * dy);
    s[y * W + x] = Math.atan(Math.hypot(gx, gy)) * 180 / Math.PI;
  }
  return s;
}
export function colourCanvas(values: ArrayLike<number>, w: number, h: number, ramp: (x: number) => RGB, vmax: number) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
  const ctx = cv.getContext('2d')!, img = ctx.createImageData(w, h);
  for (let i = 0; i < values.length; i++) { const [r, g, b] = ramp(values[i] / vmax); img.data.set([r, g, b, 255], i * 4); }
  ctx.putImageData(img, 0, 0);
  return cv;
}
export function sampleAt(g: ArrayLike<number>, W: number, H: number, u: number, v: number) {   // bilinear, u,v in 0..1
  const x = Math.min(W - 1, Math.max(0, u * (W - 1))), y = Math.min(H - 1, Math.max(0, v * (H - 1)));
  const x0 = Math.floor(x), y0 = Math.floor(y), x1 = Math.min(W - 1, x0 + 1), y1 = Math.min(H - 1, y0 + 1), fx = x - x0, fy = y - y0;
  return (g[y0*W+x0]*(1-fx) + g[y0*W+x1]*fx) * (1-fy) + (g[y1*W+x0]*(1-fx) + g[y1*W+x1]*fx) * fy;
}

export const NEVER = 65535;   // "never floods" in the hour-of-arrival grids
export const NX = [1, -1, 0, 0, 1, 1, -1, -1], NY = [0, 0, 1, -1, 1, -1, 1, -1];   // 4 straight neighbours first, then diagonals
// runoff share per land-cover class (rational-method coefficients), order of infer_height.LANDCOVER:
// bareland, rangeland, developed, road, trees, water, agriculture, buildings
export const LC_RUNOFF = [0.5, 0.35, 0.8, 0.9, 0.2, 1.0, 0.3, 0.9];
export const LC_NAMES = ['bare land', 'rangeland', 'developed', 'road', 'trees', 'water', 'agriculture', 'buildings'];
// travel cost per land-cover class (1 = paved road), slope penalty (cost × 1 + slope / s), limits, speed (m/s)
export const TRAVEL = {
  foot: { lc: [1.2, 1.3, 1.15, 1, 1.3, Infinity, 1.5, 2], slope: 15, maxSlope: 30, speed: 1.2, depth: 0.5 },
  car:  { lc: [3, 4, 2.5, 1, 2.5, Infinity, 6, 6], slope: 8, maxSlope: 15, speed: 5.5, depth: 0.3 },
};
export type TravelMode = keyof typeof TRAVEL;
export const SITE_LC = [true, true, true, true, false, false, true, false];
export const MAX_SITES = 5;
export const ARR_KEYS: [number, string, RGB][] = [[0, 'under water at the start', [73, 0, 106]], [6, 'within 6 h', [215, 48, 31]],
  [12, '6–12 h', [252, 141, 89]], [24, '12–24 h', [253, 204, 138]], [48, 'day 2', [166, 189, 219]], [Infinity, 'later', [116, 169, 207]]];
export const arrivalRGBA = (a: number) => [...ARR_KEYS.find(([t]) => a <= t)![2], 215];
export const FLOOD_RGBA = { water: [47, 127, 224, 170], sub: [229, 72, 77, 235], part: [245, 165, 36, 215] };

export function imdClass(mm: number) {   // IMD categories for 24-hour rainfall
  return mm >= 204.5 ? 'extremely heavy' : mm >= 115.6 ? 'very heavy' : mm >= 64.5 ? 'heavy' : mm >= 15.6 ? 'moderate'
    : mm >= 2.5 ? 'light' : mm > 0 ? 'very light' : 'no rain';
}

export class MinHeap {   // binary min-heap of grid cells keyed by a float; callers skip stale entries
  k = new Float64Array(1 << 16); v = new Int32Array(1 << 16); n = 0; key = 0;
  push(key: number, val: number) {
    if (this.n === this.k.length) {
      const k = new Float64Array(this.n * 2), v = new Int32Array(this.n * 2);
      k.set(this.k); v.set(this.v); this.k = k; this.v = v;
    }
    let i = this.n++;
    while (i > 0) { const p = (i - 1) >> 1; if (this.k[p] <= key) break; this.k[i] = this.k[p]; this.v[i] = this.v[p]; i = p; }
    this.k[i] = key; this.v[i] = val;
  }
  pop() {         // → cell; this.key = its key
    const top = this.v[0]; this.key = this.k[0];
    const key = this.k[--this.n], val = this.v[this.n];
    let i = 0;
    for (;;) {
      let c = 2 * i + 1;
      if (c >= this.n) break;
      if (c + 1 < this.n && this.k[c + 1] < this.k[c]) c++;
      if (this.k[c] >= key) break;
      this.k[i] = this.k[c]; this.v[i] = this.v[c]; i = c;
    }
    this.k[i] = key; this.v[i] = val;
    return top;
  }
}

// metres from each cell centre to the nearest blocked cell centre (exact, Felzenszwalb–Huttenlocher)
export function edt(blocked: ArrayLike<number>, W: number, H: number, dx: number, dy: number) {
  const n = Math.max(W, H), f = new Float64Array(n), d = new Float64Array(n), v = new Int32Array(n), z = new Float64Array(n + 1);
  const D = new Float64Array(W * H);
  for (let i = 0; i < W * H; i++) D[i] = blocked[i] ? 0 : 1e20;
  const pass = (len: number, s2: number) => {
    let k = 0; v[0] = 0; z[0] = -Infinity; z[1] = Infinity;
    for (let q = 1; q < len; q++) {
      let sx: number;
      for (;;) { const p = v[k]; sx = ((f[q] + q * q * s2) - (f[p] + p * p * s2)) / (2 * s2 * (q - p)); if (sx <= z[k]) k--; else break; }
      k++; v[k] = q; z[k] = sx; z[k + 1] = Infinity;
    }
    k = 0;
    for (let q = 0; q < len; q++) { while (z[k + 1] < q) k++; d[q] = s2 * (q - v[k]) ** 2 + f[v[k]]; }
  };
  for (let x = 0; x < W; x++) { for (let y = 0; y < H; y++) f[y] = D[y * W + x]; pass(H, dy * dy); for (let y = 0; y < H; y++) D[y * W + x] = d[y]; }
  for (let y = 0; y < H; y++) { for (let x = 0; x < W; x++) f[x] = D[y * W + x]; pass(W, dx * dx); for (let x = 0; x < W; x++) D[y * W + x] = d[x]; }
  for (let i = 0; i < W * H; i++) D[i] = Math.sqrt(D[i]);
  return D;
}

export const sgn = (v: number) => (v >= 0 ? '+' : '') + v.toFixed(2);
export const nice = (s: string) => s.replaceAll('_', ' ');
