// The viewer engine: scene data, 2D map, 3D scene and every analysis tool of the classic viewer (web/index.html),
// ported function for function. The maths is unchanged; inputs come from `s` (UI state) instead of DOM controls and
// results go back into `s` as plain data for React to render. React subscribes with useEngine().
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import {
  turbo, inferno, slopeClass, slopeRamp, divRamp, slopeGrid, colourCanvas, sampleAt, MinHeap, edt, NEVER, NX, NY,
  LC_RUNOFF, TRAVEL, SITE_LC, MAX_SITES, ARR_KEYS, arrivalRGBA, FLOOD_RGBA, imdClass, SLOPE_CLASSES, nice, sgn,
  type TravelMode, type RGB,
} from './algos';

export type Page = 'home' | 'scenes' | 'explore' | 'validate' | 'prepare' | 'respond' | 'relief' | 'assess';
export const DISASTER_PAGES: Page[] = ['prepare', 'respond', 'relief', 'assess'];
export type Pick = null | 'A' | 'B' | 'src' | 'gcp';
export type Legend = { kind: 'grad'; ramp: (x: number) => RGB; lo: string; hi: string } | { kind: 'flood' } | { kind: 'arrival' } | null;

export interface FloodSummary {
  level: number; rise: number; abs: boolean; wetPct: number; wetHa: number; maxDepth: number;
  sub: number; part: number; dry: number; total: number; floorArea: number; model: string; terrain: string;
}
export interface RouteSummary { len: number; minutes: number; how: string; wetLen: number | null; maxDepth: number; roadPct: number | null; snapped: boolean; deadline: string }
export interface TimelineSummary { totalRain: number; max24: number; imd: string; peakRise: number; peakH: number; deadline: string;
  rows: { when: string; rise: number; ha: number; blocks: number }[]; note: string; noSources: boolean;
  chart: { P: number[]; rises: number[]; days: number }; }
export interface Site { kind: 'pad' | 'camp'; label: string; cell: number; text: string; sub: string }
export interface Hover { text: string; x: number; y: number }
export interface Exposure { rise: number; level: number; wetPct: number; blocks: number; sub: number; floorArea: number }

export interface UI {
  scenes: any[]; current: string | null; status: 'empty' | 'wait' | 'ready'; waitText: string;
  page: Page; view: '2d' | '3d';
  layer: 'height' | 'unc' | 'slope'; tex3d: 'photo' | 'heat' | 'unc' | 'slope'; alpha: number; exag: number; spin: boolean;
  cam: 'orbit' | 'fly' | 'street'; corr: boolean; vlayer: 'err' | 'height' | 'none';
  flood: boolean; depth: number; depthMax: number; fsrc: 'all' | 'edges' | 'pick'; nSources: number;
  pick: Pick; hint: string; drawing: boolean; pathN: number; playing: boolean; recording: boolean;
  routeOpen: boolean; rmode: TravelMode; rdepth: number; routeSum: RouteSummary | null; routeMsg: string;
  timeOpen: boolean; train: number; thours: number; trise: number; tdrain: number; tup: number; tdays: number;
  tt: number; ttMax: number; ttLabel: string; tarr: boolean; tlSum: TimelineSummary | null; forecastOn: boolean; forecastInfo: string;
  sitesOpen: boolean; spad: number; scamp: number; sper: number; sslope: number; sdry: number; stl: boolean;
  sites: { pads: Site[]; camps: Site[]; note: string; L: number } | null;
  floodSum: FloodSummary | null; exposure: Exposure[] | null; slopeShare: { label: string; pct: number; rgb: RGB }[] | null;
  stats: [string, string][]; note: string; hasTerrain: boolean; hasCorr: boolean; hasLc: boolean; hasGcp: boolean; gcpOn: boolean;
  val: Record<string, any>; vsel: string | null; vmsg: string; vbusy: boolean; errLim: number;
  gcpPts: { u: number; v: number; z: number | null; model: number }[]; gcpFit: any; gcpMsg: string;
  legend: Legend; hover: Hover | null; pinLines: string[] | null; aspect: string; uploadMsg: string;
  rev: number;
}

const INITIAL: UI = {
  scenes: [], current: null, status: 'empty', waitText: '', page: 'home', view: '3d',
  layer: 'height', tex3d: 'photo', alpha: 0.65, exag: 2, spin: false, cam: 'orbit', corr: false, vlayer: 'err',
  flood: false, depth: 3, depthMax: 15, fsrc: 'all', nSources: 0,
  pick: null, hint: '', drawing: false, pathN: 0, playing: false, recording: false,
  routeOpen: false, rmode: 'foot', rdepth: 0.5, routeSum: null, routeMsg: '',
  timeOpen: false, train: 15, thours: 12, trise: 0, tdrain: 25, tup: 1, tdays: 3, tt: 0, ttMax: 72, ttLabel: 'now', tarr: false,
  tlSum: null, forecastOn: false, forecastInfo: '',
  sitesOpen: false, spad: 25, scamp: 1000, sper: 45, sslope: 5, sdry: 0.5, stl: true, sites: null,
  floodSum: null, exposure: null, slopeShare: null,
  stats: [], note: '', hasTerrain: false, hasCorr: false, hasLc: false, hasGcp: false, gcpOn: true,
  val: {}, vsel: null, vmsg: '', vbusy: false, errLim: 5, gcpPts: [], gcpFit: null, gcpMsg: '',
  legend: null, hover: null, pinLines: null, aspect: '1 / 1', uploadMsg: '', rev: 0,
};
const EYE = 1.7;   // eye height at street level, metres
const isDisaster = (p: Page) => DISASTER_PAGES.includes(p);

export class Engine {
  s: UI = { ...INITIAL };
  private ls = new Set<() => void>();
  data: any = null;
  private loading: string | null = null;
  el: { photo?: HTMLImageElement; heat?: HTMLCanvasElement; ovl?: HTMLCanvasElement; v3d?: HTMLElement; pin?: HTMLElement } = {};

  // ---------- store ----------
  subscribe = (f: () => void) => { this.ls.add(f); return () => this.ls.delete(f); };
  getState = () => this.s;
  set(p: Partial<UI>) { this.s = { ...this.s, ...p }; this.ls.forEach(f => f()); }
  bump() { this.set({ rev: this.s.rev + 1 }); }

  // ---------- three.js ----------
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });   // transparent: the aurora backdrop shows around the terrain
  scene3 = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(50, 1, 1, 20000);
  controls: OrbitControls;
  mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshLambertMaterial> | null = null;
  water: THREE.Mesh;
  // instrument floor under the terrain: grid + range rings in the page accent, fading into the CSS sky behind the canvas
  ground = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: { tint: { value: new THREE.Color(0x1e6fb8) }, cell: { value: 50 }, reach: { value: 2000 }, strength: { value: 0.6 }, foot: { value: new THREE.Vector2(1, 1) } },
    vertexShader: 'varying vec2 vXZ; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vXZ = w.xz; gl_Position = projectionMatrix * viewMatrix * w; }',
    fragmentShader: `uniform vec3 tint; uniform vec2 foot; uniform float cell, reach, strength; varying vec2 vXZ;
      float lines(vec2 p) { vec2 g = abs(fract(p - 0.5) - 0.5) / fwidth(p); return 1.0 - min(min(g.x, g.y), 1.0); }
      void main() {
        float r = length(vXZ), ring = abs(fract(r / (cell * 4.0) - 0.5) - 0.5) / fwidth(r / (cell * 4.0));
        float a = lines(vXZ / cell) * 0.22 + lines(vXZ / (cell * 5.0)) * 0.34 + (1.0 - min(ring, 1.0)) * 0.16;
        float la = strength * a * (1.0 - smoothstep(reach * 0.15, reach, r));
        vec2 q = abs(vXZ) - foot; float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);   // distance to the scene's footprint
        float sh = 0.32 * (1.0 - smoothstep(0.0, max(foot.x, foot.y) * 0.6, d));               // soft contact shadow under the block
        gl_FragColor = vec4(mix(tint, vec3(0.06, 0.13, 0.19), sh / max(sh + la, 1e-4)), max(la, sh));
      }`,
  }));
  // the scene as a solid block: soil-coloured sides from the surface edge down to a base, so it reads as a model, not a sheet
  // with thin contour strata every `strata` metres, like a layered topographic model
  skirt = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, emissive: 0x241c14 }));
  private strata = { value: 5 };
  private ring = new Uint32Array(0);   // grid indices around the scene's edge, in order
  marks = new THREE.Group();
  route3 = new THREE.Group();
  marker: THREE.Mesh | null = null; markerPos: THREE.Vector3 | null = null; pinUV: [number, number] | null = null;
  nav: any = { mode: 'orbit', yaw: 0, pitch: 0, keys: new Set<string>(), look: null, path: [] as THREE.Vector2[], drawing: false, play: null, rec: null };
  clock = new THREE.Clock();
  private down: [number, number] | null = null;
  private timers: Record<string, any> = {};

  constructor() {
    this.renderer.setPixelRatio(Math.min(2, devicePixelRatio));
    this.renderer.setClearColor(0x000000, 0);
    this.camera.rotation.order = 'YXZ';
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.scene3.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(-1, 2, 1); this.scene3.add(sun);
    this.water = new THREE.Mesh(new THREE.BufferGeometry(),
      new THREE.MeshStandardMaterial({ color: 0x2f7fe0, transparent: true, opacity: 0.55, roughness: 0.2, metalness: 0.1, depthWrite: false }));
    this.water.visible = false; this.water.renderOrder = 1; this.water.frustumCulled = false;
    this.ground.renderOrder = -1; this.ground.frustumCulled = false; this.ground.raycast = () => {}; this.skirt.raycast = () => {};
    this.skirt.material.onBeforeCompile = sh => {
      sh.uniforms.band = this.strata;
      sh.vertexShader = 'varying float vY;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvY = position.y;');
      sh.fragmentShader = 'uniform float band;\nvarying float vY;\n' + sh.fragmentShader.replace('#include <color_fragment>',
        '#include <color_fragment>\nfloat dl = abs(fract(vY / band + 0.5) - 0.5) * band / fwidth(vY);\ndiffuseColor.rgb *= mix(0.78, 1.0, smoothstep(0.5, 1.5, dl));');
    };
    this.scene3.add(this.ground, this.skirt, this.water, this.marks, this.route3);
    const dom = this.renderer.domElement;
    dom.addEventListener('pointerdown', e => {
      this.down = [e.clientX, e.clientY];
      (document.activeElement as HTMLElement | null)?.blur();
      if (!this.controls.enabled && !this.nav.play) this.nav.look = [e.clientX, e.clientY];
    });
    dom.addEventListener('pointerup', e => this.click3D(e));
    addEventListener('pointermove', e => {         // drag to look around (grab-the-world, like Street View)
      if (!this.nav.look) return;
      if (!(e.buttons & 1)) return void (this.nav.look = null);
      this.nav.yaw += (e.clientX - this.nav.look[0]) * 0.004;
      this.nav.pitch = THREE.MathUtils.clamp(this.nav.pitch + (e.clientY - this.nav.look[1]) * 0.004, -1.45, 1.45);
      this.nav.look = [e.clientX, e.clientY];
    });
    addEventListener('pointerup', () => this.nav.look = null);
    addEventListener('keydown', e => {
      if (this.controls.enabled || this.nav.play || this.s.view !== '3d' || (e.target as Element).matches?.('select, textarea, input')) return;
      this.nav.keys.add(e.code);
      if (/^(Arrow|Space)/.test(e.code)) e.preventDefault();
    });
    addEventListener('keyup', e => this.nav.keys.delete(e.code));
    addEventListener('blur', () => this.nav.keys.clear());
    const frame = () => { requestAnimationFrame(frame); this.frame(); };
    frame();
    this.poll(); setInterval(() => this.poll(), 1500);
  }
  attach3D(el: HTMLElement | null) { if (el && this.renderer.domElement.parentElement !== el) el.prepend(this.renderer.domElement); this.el.v3d = el ?? undefined; }
  attach2D(photo: HTMLImageElement | null, heat: HTMLCanvasElement | null, ovl: HTMLCanvasElement | null) {
    this.el.photo = photo ?? undefined; this.el.heat = heat ?? undefined; this.el.ovl = ovl ?? undefined;
    if (this.data) { if (photo) photo.src = this.data.photo.src; this.showLayer(); this.drawOverlay(); }
  }
  attachPin(el: HTMLElement | null) { this.el.pin = el ?? undefined; }
  setTint(rgb: string) { (this.ground.material as THREE.ShaderMaterial).uniforms.tint.value.setRGB(...rgb.split(',').map(v => +v / 255) as [number, number, number], THREE.SRGBColorSpace); }

  // ---------- scene list ----------
  async poll() {
    let scenes: any[];
    try { scenes = await (await fetch('/api/scenes')).json(); } catch { return; }
    this.set({ scenes });
    const cur = scenes.find(s => s.name === this.s.current);
    if (!this.s.current && scenes.length) {
      const want = new URLSearchParams(location.hash.split('?')[1] || '').get('scene');
      this.select(want && scenes.some(s => s.name === want) ? want : (scenes.find(s => s.state === 'done') || scenes[0]).name);
    } else if (cur && cur.state === 'done' && (!this.data || this.data.name !== this.s.current) && this.loading !== this.s.current) this.select(this.s.current!);
    else if (cur && cur.state !== 'done') this.showWait(cur);
  }
  showWait(s: any) {
    this.set({ status: 'wait', waitText: s.state === 'error' ? `Could not process this image: ${s.error}`
      : `Estimating heights for ${nice(s.name)}: ${Math.round(s.progress * 100)}% · about 4 min per 1024×1024 image on an 8 GB M3; other scenes stay browsable` });
  }
  async select(name: string) {
    this.set({ current: name });
    const s = this.s.scenes.find(x => x.name === name);
    if (!s || s.state !== 'done') { this.data = null; this.set({ stats: [] }); return this.showWait(s || { name, state: 'queued', progress: 0 }); }
    this.loading = name;
    try { await this.load(name, s.meta); } finally { if (this.loading === name) this.loading = null; }
  }
  async upload(file: File) {
    this.set({ uploadMsg: `Uploading ${file.name}…` });
    const r = await fetch(`/api/upload?name=${encodeURIComponent(file.name)}`, { method: 'POST', body: file });
    const j = await r.json();
    this.set({ uploadMsg: r.ok ? '' : `Upload failed: ${j.error}` });
    if (r.ok) { await this.poll(); this.select(j.name); }
  }
  private async load(name: string, m: any) {
    const f32 = async (u: string) => new Float32Array(await (await fetch(u)).arrayBuffer());
    const buf = await f32(`/results/${name}.f32`);
    if (this.s.current !== name) return;
    const unc = await f32(`/results/${name}_unc.f32`);
    if (this.s.current !== name) return;
    const gridCorr = m.corrected ? await f32(`/results/${name}_corr.f32`) : null;
    const vmax = Math.max(5, m.p99), umax = Math.max(0.5, m.unc_p95);
    const uncCv = colourCanvas(unc, m.grid_w, m.grid_h, inferno, umax);
    const hasTerrain = !!(m.terrain && m.terrain.source);
    const [bid, buildings, dtm, lc] = await Promise.all([
      f32(`/results/${name}_bid.f32`), fetch(`/results/${name}_buildings.json`).then(r => r.json()),
      hasTerrain ? f32(`/results/${name}_dtm.f32`) : null,
      fetch(`/results/${name}_lc.f32`).then(r => r.ok ? r.arrayBuffer() : null).then(b => b && Uint8Array.from(new Float32Array(b))).catch(() => null)]);
    const [val, valerr] = await Promise.all([
      fetch(`/results/${name}_validation.json`).then(r => r.ok ? r.json() : {}).catch(() => ({})),
      fetch(`/results/${name}_valerr.f32`).then(r => r.ok ? r.arrayBuffer() : null).then(b => b && new Float32Array(b)).catch(() => null)]);
    const photo = new Image(); photo.src = `/results/${name}.jpg`; await photo.decode();
    if (this.s.current !== name) return;
    for (const b of buildings) b.height_raw_m = b.height_m;
    this.data = { name, meta: m, gridRaw: buf, gridCorr, unc, uncCv, photo, vmax, umax, bid, buildings, dtmRaw: dtm, lc, valerr,
      gcpPts: (m.gcp ? m.gcp.points : []).map((p: any) => ({ u: p.u, v: p.v, z: p.z })),
      sources: [] as number[], route: { a: null, b: null, kind: null, res: null, why: '' }, tl: null, forecast: null, tlStart: this.s.depth };
    this.set({ val, vsel: null, status: 'ready', hasCorr: !!gridCorr, hasLc: !!lc, forecastOn: false, forecastInfo: '',
      aspect: `${m.width} / ${m.height}`, corr: this.s.corr && !!gridCorr });
    this.applyTerrain();
    if (this.data.gmax - this.data.gmin > 50) this.set({ exag: 1 });   // hills: exaggeration would look unreal
    this.renderStats();
    if (this.el.photo) this.el.photo.src = photo.src;
    if (this.s.flood) this.renderFlood();
    this.showLayer();
    this.build3D();
    this.updateFlood();
    this.toolsSceneLoaded();
    this.renderValidation(); this.renderGcp(); this.computePrepare();
    this.applyLinkParams();
  }
  // demo links, once per page load: #/respond?scene=x&view=2d&flood=4&src=edges&timeline=1&tarr=1&t=12&route=1&sites=1&cam=street
  private linkDone = false;
  visited = false;   // set once any workspace page opens: from then on the landing shows the user's scene, not the showcase
  private applyLinkParams() {
    if (this.linkDone) return;
    this.linkDone = true;
    const q = new URLSearchParams(location.hash.split('?')[1] || '');
    if (q.get('view') === '2d' || q.get('view') === '3d') this.setView(q.get('view') as UI['view']);
    if (q.get('src') === 'edges') this.setFsrc('edges');
    if (q.has('flood')) { this.setFlood(true); this.setDepth(+(q.get('flood') || 3)); }
    if (q.get('timeline') === '1' && this.s.flood) { this.setTimeOpen(true); if (q.get('tarr') === '1') this.setTarr(true); if (q.has('t')) this.applyTime(+q.get('t')!); }
    if (q.get('sites') === '1') this.setSitesOpen(true);
    if (q.get('route') === '1') {   // a demo route between two far corners of the scene
      const W = this.W, H = this.H, d = this.data, { f } = this.travelCost(-Infinity);
      d.route = { a: this.nearestOpen(Math.round(H * 0.1) * W + Math.round(W * 0.1), f), b: this.nearestOpen(Math.round(H * 0.9) * W + Math.round(W * 0.9), f), kind: 'ab', res: null, why: '' };
      this.set({ routeOpen: true }); this.setPick(null); this.updateRoute();
    }
    if (q.has('cam')) this.setCam(q.get('cam') as UI['cam']);
  }

  // ---------- terrain, calibration, heights ----------
  gcpActive() { return !!(this.data.meta.gcp && this.s.gcpOn); }
  applyTerrain() {
    const d = this.data, m = d.meta, W = m.grid_w, H = m.grid_h, c = this.gcpActive() ? m.gcp : null;
    d.calib = c;
    if (c) {
      const t = new Float32Array(W * H);
      for (let y = 0; y < H; y++) for (let x = 0; x < W; x++)
        t[y * W + x] = (d.dtmRaw ? d.dtmRaw[y * W + x] : 0) + c.a + c.bx * ((x + 0.5) / W - 0.5) + c.by * ((y + 0.5) / H - 0.5);
      d.dtm = t;
    } else d.dtm = d.dtmRaw;
    d.hscale = c ? c.s : 1;
    const dtm = d.dtm;
    d.gmin = dtm ? dtm.reduce((a: number, v: number) => Math.min(a, v), Infinity) : 0;
    d.gmax = dtm ? dtm.reduce((a: number, v: number) => Math.max(a, v), -Infinity) : 0;
    d.flat = null;
    d.slope = dtm && slopeGrid(dtm, W, H, m.width * m.gsd / W, m.height * m.gsd / H);
    d.slopeCv = dtm && colourCanvas(d.slope, W, H, slopeRamp, 50);
    d.slopeTex = null; d.slopeRiskCv = null;
    const patch: Partial<UI> = { hasTerrain: !!dtm, hasGcp: !!m.gcp, depthMax: Math.ceil(d.gmax - d.gmin + 15) };
    if (!dtm && this.s.layer === 'slope') patch.layer = 'height';
    if (!dtm && this.s.tex3d === 'slope') patch.tex3d = 'photo';
    this.set(patch);
    for (const b of d.buildings) b.ground_use = c ? (b.ground_m ?? 0) + c.a + c.bx * (b.cx - 0.5) + c.by * (b.cy - 0.5) : b.ground_m;
    this.setGrid();
    this.computeReach();
  }
  terrainLabel() {
    const d = this.data, c = d.calib, base = d.dtmRaw ? d.meta.terrain.source : null, n = c ? `${c.n} ground control point${c.n > 1 ? 's' : ''}` : '';
    return c ? (base ? `${base} + ${n}` : `${n} (flat ground)`) : base;
  }
  laserShift() { const la = this.data.meta.terrain && this.data.meta.terrain.laser; return la && la.offset_m != null ? -la.offset_m : null; }
  corrOn() { return this.s.corr && !!this.data?.gridCorr; }
  setGrid() {
    const d = this.data, on = this.corrOn(), m = d.meta, k = d.hscale ?? 1, src = on ? d.gridCorr : d.gridRaw;
    d.grid = k === 1 ? src : Float32Array.from(src, (v: number) => v * k);
    for (const b of d.buildings) {
      b.height_m = (on && b.height_corr_m != null ? b.height_corr_m : b.height_raw_m) * k;
      b.floors = Math.max(1, Math.round(b.height_m / m.floor_m));
    }
    d.heat = colourCanvas(d.grid, m.grid_w, m.grid_h, turbo, d.vmax);
  }
  renderStats() {
    const d = this.data, m = d.meta, c = this.corrOn() ? m.corrected : m, k = d.hscale ?? 1, cal = d.calib;
    const stats: [string, string][] = [['Tallest', `${(c.max * k).toFixed(1)} m`], ['99th pct', `${(c.p99 * k).toFixed(1)} m`],
      ['Built-up', `${m.built_pct.toFixed(0)}%`], ['Blocks', String(m.buildings)],
      ...(d.dtm ? [['Ground', `${d.gmin.toFixed(0)}–${d.gmax.toFixed(0)} m`] as [string, string]] : []),
      ['GSD', `${m.gsd.toFixed(2)} m${m.gsd_assumed ? ' (assumed)' : ''}`], ['Consistency', `${m.unc_mean.toFixed(2)} m`]];
    const la = m.terrain && m.terrain.laser, ls = this.laserShift();
    const note = (m.gsd_assumed ? 'No georeferencing: scale assumes 0.5 m pixels. ' : '')
      + (this.corrOn() ? 'Heights bias-corrected with a curve learned on US LiDAR (DFC2019); not yet verified on Indian cities. ' : 'Model estimate of height above ground. ')
      + (cal ? `Calibrated with ${cal.n} control point${cal.n > 1 ? 's' : ''}: level ${cal.a >= 0 ? '+' : ''}${cal.a.toFixed(2)} m`
           + (cal.s !== 1 ? `, heights ×${cal.s.toFixed(2)}` : '') + (cal.terms.includes('bx') ? ', tilt corrected' : '') + '. ' : '')
      + 'Consistency score = spread of 4 flipped predictions, not an error bar; building blocks show a 90% interval calibrated on GAMUS LiDAR (US cities): about ±6 m, and it misses about half of the blocks that are really 10–20 m tall and most above 20 m. '
      + (d.dtmRaw ? `Absolute heights in m above mean sea level (EGM2008); terrain: ${this.terrainLabel()}, cleaned with the model's land cover`
           + (ls != null ? `, levelled ${ls.toFixed(1)} m to match ${la.ground_photons} NASA ICESat-2 laser ground points.`
                         : (la && la.none ? `; not levelled: ${la.none}.` : '; no ICESat-2 laser points in this scene.'))
        : cal ? 'Absolute heights in m from the control points (the ground is taken as flat or tilted).'
        : m.terrain && m.terrain.error ? 'Terrain could not be loaded (offline?), so heights are relative to local ground.'
        : 'No georeferencing, so heights are relative to local ground (add control points to make them absolute).');
    this.set({ stats, note });
  }
  setCorr(on: boolean) {
    this.set({ corr: on });
    if (!this.data) return;
    this.setGrid(); this.renderStats();
    if (this.s.flood) this.renderFlood();
    this.showLayer(); this.applyExag(); this.refreshSurface();
  }

  // ---------- point queries ----------
  get W() { return this.data.meta.grid_w; } get H() { return this.data.meta.grid_h; }
  sample(g: ArrayLike<number>, u: number, v: number) { return sampleAt(g, this.W, this.H, u, v); }
  heightAt(u: number, v: number) { return this.sample(this.data.grid, u, v); }
  groundAt(u: number, v: number) { return this.data.dtm ? this.sample(this.data.dtm, u, v) : 0; }
  uncAt(u: number, v: number) { return this.sample(this.data.unc, u, v); }
  waterLevel() { return this.data.gmin + this.s.depth; }
  curLevel() { return this.s.flood ? this.waterLevel() : -Infinity; }
  blockGround(b: any) { return b.ground_use ?? this.data.gmin; }
  blockReached(b: any, L: number) { return this.s.fsrc === 'all' || L > this.data.blockReach[b.id]; }
  blockDepth(b: any, L: number) { return this.blockReached(b, L) ? Math.max(0, L - this.blockGround(b)) : 0; }
  blockState(b: any, L: number) { const g = this.blockGround(b); return !this.blockReached(b, L) ? 'dry' : L > g + b.height_m ? 'sub' : L > g ? 'part' : 'dry'; }
  cellAt(u: number, v: number) {
    const W = this.W, H = this.H;
    return Math.min(H - 1, Math.max(0, Math.round(v * (H - 1)))) * W + Math.min(W - 1, Math.max(0, Math.round(u * (W - 1))));
  }
  buildingAt(u: number, v: number) { const id = this.data.bid[this.cellAt(u, v)]; return id > 0 ? this.data.buildings[id - 1] : null; }
  pointLines(u: number, v: number): string[] {
    const d = this.data, h = Math.max(0, this.heightAt(u, v)), un = this.uncAt(u, v), out: string[] = [];
    if (!d.dtm) out.push(`${h.toFixed(1)} m above ground (consistency score ${un.toFixed(1)} m)`);
    else {
      const g = this.groundAt(u, v), sl = this.sample(d.slope, u, v);
      out.push(`${(g + h).toFixed(1)} m a.s.l.`, `ground ${g.toFixed(1)} m + height ${h.toFixed(1)} m (consistency ${un.toFixed(1)} m)`,
        `terrain slope ${sl.toFixed(0)}° (${slopeClass(sl)[1]})`);
    }
    const f = this.floodText(u, v); if (f) out.push(f);
    const e = this.valText(u, v); if (e) out.push(e);
    const b = this.buildingAt(u, v); if (b) out.push(...this.buildingLines(b));
    return out;
  }
  buildingLines(b: any) {
    const d = this.data, k = d.hscale ?? 1, ci = b.ci90 && !this.corrOn() ? b.ci90 : null, out: string[] = [];
    out.push(`Block ${b.height_m.toFixed(1)} m tall · ${Math.round(b.area_m2)} m² · ~${b.floors} floor${b.floors > 1 ? 's' : ''}`);
    out.push(ci ? `90% interval (calibrated on GAMUS, US cities) ${(ci[0] * k).toFixed(1)}–${(ci[1] * k).toFixed(1)} m (often too low for buildings over 10 m)`
      : `consistency score ${b.unc_m.toFixed(1)} m`);
    if (d.dtm) out.push(`roof ${(this.blockGround(b) + b.height_m).toFixed(1)} m a.s.l.`);
    if (this.s.flood) {
      const L = this.waterLevel(), st = this.blockState(b, L);
      out.push(st === 'sub' ? 'Fully submerged at this water level' : st === 'dry' ? 'Dry at this water level'
        : `≈ ${Math.min(b.floors, (L - this.blockGround(b)) / d.meta.floor_m).toFixed(1)} floor(s) under water`);
      if (d.tl) { const a = d.tl.bArr[b.id];
        out.push(a === 0 ? 'Timeline: water inside from the start' : a < NEVER ? `Timeline: water reaches the ground floor ${this.fmtWhen(a)}` : 'Timeline: stays dry'); }
    }
    return out;
  }
  hover2D(u: number, v: number, x: number, y: number) {
    if (!this.data || u < 0 || v < 0 || u > 1 || v > 1) return this.set({ hover: null });
    this.set({ hover: { text: this.pointLines(u, v).join(' · '), x, y } });
  }
  click2D(u: number, v: number) { if (this.data) this.onPick(u, v); }

  // ---------- 2D layers and legend ----------
  showLayer() {
    const d = this.data, hc = this.el.heat;
    if (!d) return;
    let legend: Legend;
    if (this.s.page === 'validate') {
      const v = this.s.vlayer, err = v === 'err' && this.errCanvas(), src = err || (v === 'none' ? null : d.heat), lim = this.errLimit();
      if (hc) { hc.width = this.W; hc.height = this.H; const c = hc.getContext('2d')!; c.clearRect(0, 0, hc.width, hc.height); if (src) c.drawImage(src, 0, 0); }
      legend = v === 'none' ? null : err ? { kind: 'grad', ramp: divRamp, lo: `−${lim.toFixed(0)} m ours lower`, hi: `+${lim.toFixed(0)} m ours higher` }
        : { kind: 'grad', ramp: turbo, lo: '0 m', hi: `${d.vmax.toFixed(0)} m above ground` };
      return this.set({ legend });
    }
    const l = this.s.page === 'prepare' && d.slopeCv ? 'slope' : this.s.layer;
    const src = this.s.flood ? d.floodCv : this.s.page === 'prepare' && d.slopeCv ? this.slopeRisk() : ({ unc: d.uncCv, slope: d.slopeCv } as any)[l] || d.heat;
    if (hc && src) { hc.width = src.width; hc.height = src.height; hc.getContext('2d')!.drawImage(src, 0, 0); }
    if (this.s.flood) legend = this.s.tarr && this.s.timeOpen ? { kind: 'arrival' } : { kind: 'flood' };
    else if (l === 'unc') legend = { kind: 'grad', ramp: inferno, lo: 'consistency 0 m', hi: `${d.umax.toFixed(1)} m` };
    else if (l === 'slope') legend = { kind: 'grad', ramp: slopeRamp, lo: '0°', hi: '45°+ slope' };
    else legend = { kind: 'grad', ramp: turbo, lo: '0 m', hi: `${d.vmax.toFixed(0)} m above ground` };
    this.set({ legend });
  }
  setLayer(layer: UI['layer']) { this.set({ layer }); this.showLayer(); }

  // ---------- 3D ----------
  surfaceImage(): any {
    const d = this.data, p = this.s.page;
    if (p === 'validate') return this.s.vlayer === 'err' && this.errTexture() || (this.s.vlayer === 'none' ? d.photo : d.heat);
    if (this.s.flood && d.floodTex) return d.floodTex;
    if (p === 'prepare' && d.slopeCv) return this.slopeTexture();
    return ({ photo: d.photo, heat: d.heat, unc: d.uncCv, slope: d.slopeCv } as any)[this.s.tex3d] || d.photo;
  }
  slopeRisk() {   // Prepare: only the risky slope classes, clear on gentle ground (<= 15°) so the photo stays readable
    const d = this.data;
    if (d.slopeRiskCv) return d.slopeRiskCv;
    const W = this.W, H = this.H, ov = Object.assign(document.createElement('canvas'), { width: W, height: H }), oc = ov.getContext('2d')!, img = oc.createImageData(W, H);
    for (let i = 0; i < W * H; i++) { const s = d.slope[i], c = slopeClass(s)[2]; img.data.set([...c, s <= 15 ? 0 : s <= 25 ? 90 : 200], i * 4); }
    oc.putImageData(img, 0, 0);
    return d.slopeRiskCv = ov;
  }
  slopeTexture() {
    const d = this.data;
    if (d.slopeTex) return d.slopeTex;
    const t = Object.assign(document.createElement('canvas'), { width: d.photo.naturalWidth, height: d.photo.naturalHeight }), c = t.getContext('2d')!;
    c.drawImage(d.photo, 0, 0); c.drawImage(this.slopeRisk(), 0, 0, t.width, t.height);
    return d.slopeTex = t;
  }
  refreshSurface() { if (this.mesh) { const t = this.mesh.material.map!; t.image = this.surfaceImage(); t.needsUpdate = true; } }
  setTex3d(tex3d: UI['tex3d']) { this.set({ tex3d }); this.refreshSurface(); }
  build3D() {
    const d = this.data, m = d.meta;
    if (this.mesh) { this.scene3.remove(this.mesh); this.mesh.geometry.dispose(); this.mesh.material.map?.dispose(); this.mesh.material.dispose(); }
    const W = m.width * m.gsd, H = m.height * m.gsd;
    const geo = new THREE.PlaneGeometry(W, H, m.grid_w - 1, m.grid_h - 1);
    geo.rotateX(-Math.PI / 2);
    const tex = new THREE.Texture(this.surfaceImage());
    tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8; tex.needsUpdate = true;
    this.mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ map: tex }));
    // building walls in plain grey: a top-down photo has no facade pixels, stretching roof pixels down looks wrong
    this.mesh.material.onBeforeCompile = sh => {
      sh.vertexShader = 'attribute float steep;\nvarying float vSteep;\n'
        + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvSteep = steep;');
      sh.fragmentShader = 'varying float vSteep;\n' + sh.fragmentShader.replace('#include <map_fragment>',
        '#include <map_fragment>\ndiffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.74, 0.72, 0.68), smoothstep(0.45, 0.8, vSteep));');
    };
    const gw = m.grid_w, gh = m.grid_h, near = d.nearBuilding = new Uint8Array(gw * gh);   // building cells + 1-cell rim
    for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) if (d.bid[y * gw + x] > 0)
      for (let yy = Math.max(0, y - 1); yy <= Math.min(gh - 1, y + 1); yy++)
        for (let xx = Math.max(0, x - 1); xx <= Math.min(gw - 1, x + 1); xx++) near[yy * gw + xx] = 1;
    this.scene3.add(this.mesh);
    this.water.geometry.dispose();
    this.water.geometry = new THREE.PlaneGeometry(W, H, m.grid_w - 1, m.grid_h - 1).rotateX(-Math.PI / 2);
    const span = Math.max(W, H), gu = (this.ground.material as THREE.ShaderMaterial).uniforms;
    this.ground.scale.set(span * 12, 1, span * 12);   // its height follows the block's base (applyExag)
    gu.cell.value = [10, 25, 50, 100, 250].find(c => c >= span / 12) ?? 500; gu.foot.value.set(W / 2, H / 2);
    const ring: number[] = [];   // PlaneGeometry vertex (x, y) is index y * gw + x
    for (let x = 0; x < gw; x++) ring.push(x);
    for (let y = 1; y < gh; y++) ring.push(y * gw + gw - 1);
    for (let x = gw - 2; x >= 0; x--) ring.push((gh - 1) * gw + x);
    for (let y = gh - 2; y > 0; y--) ring.push(y * gw);
    const n = ring.length, sk = new THREE.BufferGeometry(), col = new Float32Array(n * 6), idx: number[] = [];
    for (let k = 0; k < n; k++) { col.set([0.36, 0.27, 0.19, 0.8, 0.71, 0.57], k * 6); const j = (k + 1) % n; idx.push(2 * k, 2 * k + 1, 2 * j, 2 * j, 2 * k + 1, 2 * j + 1); }
    sk.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 6), 3));
    sk.setAttribute('color', new THREE.BufferAttribute(col, 3)); sk.setIndex(idx);
    this.skirt.geometry.dispose(); this.skirt.geometry = sk; this.ring = Uint32Array.from(ring);
    this.resetNav(); this.applyExag(); this.overview(); this.clearPin(); this.atmosphere();
  }
  setExag(exag: number) { this.set({ exag }); this.applyExag(); }
  applyExag() {
    if (!this.mesh) return;
    const d = this.data, k = this.s.exag, pos = this.mesh.geometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) pos.setY(i, ((d.dtm ? d.dtm[i] - d.gmin : 0) + Math.max(0, d.grid[i])) * k);
    pos.needsUpdate = true;
    const base = -Math.max(this.sceneS() * 0.03, (d.gmax - d.gmin) * k * 0.12), sp = this.skirt.geometry.attributes.position as THREE.BufferAttribute;
    for (let j = 0; j < this.ring.length; j++) {
      const i = this.ring[j];
      sp.setXYZ(2 * j, pos.getX(i), pos.getY(i), pos.getZ(i)); sp.setXYZ(2 * j + 1, pos.getX(i), base, pos.getZ(i));
    }
    sp.needsUpdate = true; this.skirt.geometry.computeVertexNormals(); this.skirt.geometry.computeBoundingSphere();
    this.ground.position.y = base - 0.05;   // the block stands on the floor
    this.strata.value = Math.max(2, (d.gmax - d.gmin) * k / 12);
    this.mesh.geometry.computeVertexNormals();
    const n = this.mesh.geometry.attributes.normal, steep = new Float32Array(n.count);
    for (let i = 0; i < n.count; i++) steep[i] = d.nearBuilding[i] ? 1 - Math.abs(n.getY(i)) : 0;
    this.mesh.geometry.setAttribute('steep', new THREE.BufferAttribute(steep, 1));
    this.updateWater(); this.clearPin(); this.drawRoute(); this.drawMarks3D();
  }
  groundGrid() { const d = this.data; return d.dtm || d.flat || (d.flat = new Float32Array(d.grid.length)); }
  waterHeights(pos: THREE.BufferAttribute, k: number) {
    const d = this.data, L = this.waterLevel(), g = this.groundGrid(), y0 = (L - d.gmin) * k;
    for (let i = 0; i < pos.count; i++) pos.setY(i, d.reach[i] < L ? y0 : (g[i] - d.gmin - 1) * k);
    pos.needsUpdate = true;
  }
  updateWater() { if (this.data && this.water.visible && this.water.geometry.attributes.position) this.waterHeights(this.water.geometry.attributes.position as THREE.BufferAttribute, this.s.exag); }
  setSpin(spin: boolean) { this.set({ spin }); this.controls.autoRotate = spin; }

  private click3D(e: PointerEvent) {
    const down = this.down;
    if (!this.mesh || !down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
    const r = this.renderer.domElement.getBoundingClientRect(), ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1), this.camera);
    const hit = ray.intersectObject(this.mesh)[0];
    if (!hit) return this.clearPin();
    const hu = hit.point.x / this.sceneW() + 0.5, hv = hit.point.z / this.sceneH() + 0.5;
    if (this.onPick(hu, hv)) return;
    if (this.nav.drawing) { this.nav.path.push(new THREE.Vector2(hit.point.x, hit.point.z)); this.drawRoute(); this.set({ pathN: this.nav.path.length }); return this.showHint(); }
    if (!this.marker) { this.marker = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({ color: 0x7dd3fc })); this.scene3.add(this.marker); }
    this.marker.scale.setScalar(this.sceneS() / 250);
    this.marker.position.copy(hit.point); this.marker.visible = true; this.markerPos = hit.point.clone();
    this.pinUV = [hu, hv];
    this.set({ pinLines: this.pointLines(hu, hv) });
  }
  clearPin() { this.markerPos = null; if (this.marker) this.marker.visible = false; if (this.s.pinLines) this.set({ pinLines: null }); }
  refreshPin() { if (this.markerPos && this.pinUV && this.data) this.set({ pinLines: this.pointLines(...this.pinUV) }); }

  // ---------- fly-through: free flight, street level, planned route, video ----------
  sceneW() { return this.data.meta.width * this.data.meta.gsd; }
  sceneH() { return this.data.meta.height * this.data.meta.gsd; }
  sceneS() { return Math.max(this.sceneW(), this.sceneH()); }
  uvOf(x: number, z: number): [number, number] { return [x / this.sceneW() + 0.5, z / this.sceneH() + 0.5]; }
  groundY(x: number, z: number) { const [u, v] = this.uvOf(x, z); return (this.data.dtm ? this.sample(this.data.dtm, u, v) - this.data.gmin : 0) * this.s.exag; }
  surfaceY(x: number, z: number) { const [u, v] = this.uvOf(x, z); return this.groundY(x, z) + Math.max(0, this.sample(this.data.grid, u, v)) * this.s.exag; }
  blocked(x: number, z: number) { const [u, v] = this.uvOf(x, z); return u < 0 || u > 1 || v < 0 || v > 1 || !!this.buildingAt(u, v); }
  streetY(x: number, z: number) {
    const k = this.s.exag, y = Math.max(this.groundY(x, z) + EYE * k, this.surfaceY(x, z) + 0.5 * EYE * k);
    if (!this.s.flood) return y;
    const [u, v] = this.uvOf(x, z), L = this.waterLevel();
    return this.data.reach[this.cellAt(u, v)] < L ? Math.max(y, (L - this.data.gmin + 0.8) * k) : y;
  }
  aimPoint() {
    this.camera.updateMatrixWorld();
    const ray = new THREE.Raycaster(); ray.setFromCamera(new THREE.Vector2(0, 0), this.camera);
    return this.mesh && ray.intersectObject(this.mesh)[0]?.point;
  }
  syncAngles() {
    this.camera.updateMatrixWorld();
    const d = this.camera.getWorldDirection(new THREE.Vector3());
    this.nav.yaw = Math.atan2(-d.x, -d.z); this.nav.pitch = Math.asin(THREE.MathUtils.clamp(d.y, -1, 1));
  }
  freeSpot(x: number, z: number): [number, number] {
    const open = (px: number, pz: number) => !this.blocked(px, pz) && [...Array(8)].every((_, a) => !this.blocked(px + 4 * Math.cos(a * Math.PI / 4), pz + 4 * Math.sin(a * Math.PI / 4)));
    for (const test of [open, (px: number, pz: number) => !this.blocked(px, pz)])
      for (let r = 0; r < this.sceneS() / 2; r += 2)
        for (let a = 0; a < 16; a++) {
          const px = x + r * Math.cos(a * Math.PI / 8), pz = z + r * Math.sin(a * Math.PI / 8);
          if (test(px, pz)) return [px, pz];
        }
    return [x, z];
  }
  overview() {
    const S = this.sceneS(), relief = (this.data.gmax - this.data.gmin) * this.s.exag;
    this.camera.position.set(0, S * 0.82 + relief, S * 0.82 + relief * 0.5);
    this.controls.target.set(0, relief / 2, 0);
  }
  setCam(mode: UI['cam']) {
    if (!this.data) return;
    const prev = this.nav.mode;
    this.nav.mode = mode; this.set({ cam: mode });
    this.syncAngles();
    if (mode === 'street') {
      const p = this.aimPoint() || new THREE.Vector3(), [x, z] = this.freeSpot(p.x, p.z);
      this.camera.position.set(x, this.streetY(x, z), z); this.nav.pitch = 0;
    }
    this.camera.near = mode === 'street' ? 0.1 : 1; this.camera.fov = mode === 'street' ? 65 : 50; this.camera.updateProjectionMatrix();
    this.controls.enabled = mode === 'orbit' && !this.nav.play;
    if (mode === 'orbit') {
      if (prev === 'street') this.overview();
      else this.controls.target.copy(this.aimPoint() || this.camera.position.clone().addScaledVector(this.camera.getWorldDirection(new THREE.Vector3()), this.sceneS() / 2));
    }
    this.showHint(); this.drawRoute();
  }
  private walk(dt: number) {
    const nav = this.nav, key = (...c: string[]) => c.some(x => nav.keys.has(x)) ? 1 : 0, street = nav.mode === 'street';
    const f = key('KeyW', 'ArrowUp') - key('KeyS', 'ArrowDown'), s = key('KeyD', 'ArrowRight') - key('KeyA', 'ArrowLeft');
    const step = this.sceneS() / (street ? 30 : 8) * (key('ShiftLeft', 'ShiftRight') ? 3 : 1) * dt;
    const fwd = street ? new THREE.Vector3(-Math.sin(nav.yaw), 0, -Math.cos(nav.yaw)) : this.camera.getWorldDirection(new THREE.Vector3());
    const c = this.camera.position, p = c.clone().addScaledVector(fwd, f * step)
      .addScaledVector(new THREE.Vector3(Math.cos(nav.yaw), 0, -Math.sin(nav.yaw)), s * step);
    if (street) {
      if (this.blocked(p.x, p.z) && !this.blocked(c.x, c.z)) {
        if (!this.blocked(p.x, c.z)) p.z = c.z; else if (!this.blocked(c.x, p.z)) p.x = c.x; else p.copy(c);
      }
      const ty = this.streetY(p.x, p.z), k = this.s.exag;
      p.y = Math.max(ty - 0.5 * EYE * k, c.y + (ty - c.y) * Math.min(1, dt * 6));
    } else p.y = Math.max(p.y + (key('KeyR', 'KeyE', 'Space') - key('KeyF', 'KeyQ')) * step, this.surfaceY(p.x, p.z) + 2 * this.s.exag);
    c.copy(p);
    this.camera.rotation.set(nav.pitch, nav.yaw, 0);
  }
  flightPoints() {
    const W = this.sceneW(), H = this.sceneH(), S = this.sceneS(), nav = this.nav;
    const way = nav.path.length > 1 ? nav.path
      : [[-0.55, 0.45], [-0.2, 0.28], [0.08, 0.05], [-0.05, -0.25], [0.28, -0.36], [0.55, -0.12]].map(([a, b]) => new THREE.Vector2(a * W, b * H));
    const curve = new THREE.CatmullRomCurve3(way.map((p: THREE.Vector2) => new THREE.Vector3(p.x, 0, p.y)), false, 'centripetal');
    const pts = curve.getSpacedPoints(Math.max(2, Math.round(curve.getLength() / (S / 400))));
    const street = nav.mode === 'street', win = street ? 8 : 25, around = (a: number[], i: number) => a.slice(Math.max(0, i - win), i + win + 1);
    const top = pts.map(p => street ? this.streetY(p.x, p.z) : this.surfaceY(p.x, p.z)), lift = top.map((_, i) => Math.max(...around(top, i)));
    pts.forEach((p, i) => { const s = around(lift, i); p.y = s.reduce((a, b) => a + b) / s.length + (street ? 0 : S * 0.12); });
    return pts;
  }
  drawRoute() {
    for (const o of this.route3.children as any[]) { o.geometry.dispose(); o.material.dispose(); }
    this.route3.clear();
    if (!this.data || !this.mesh || !this.nav.path.length) return;
    const r = this.sceneS() / 220, color = 0xffb020;
    for (const p of this.nav.path) {
      const s = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 8), new THREE.MeshBasicMaterial({ color }));
      s.position.set(p.x, this.surfaceY(p.x, p.y) + r, p.y); this.route3.add(s);
    }
    if (this.nav.path.length > 1)
      this.route3.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(this.flightPoints()), new THREE.LineBasicMaterial({ color })));
  }
  togglePath() {
    const nav = this.nav;
    nav.drawing = !nav.drawing;
    if (nav.drawing) { nav.path = []; this.clearPin(); }
    this.set({ drawing: nav.drawing, pathN: nav.path.length });
    this.drawRoute(); this.showHint();
  }
  playPath(record = false) {
    const nav = this.nav;
    if (nav.play) return this.stopPath();
    if (!this.data || !this.mesh) return;
    if (nav.mode === 'street' && nav.path.length < 2) return this.showHint('Street level: click Draw path and add points along the streets first.', 5000);
    if (nav.drawing) this.togglePath();
    const pts = this.flightPoints();
    let len = 0; for (let i = 1; i < pts.length; i++) len += pts[i].distanceTo(pts[i - 1]);
    nav.play = { pts, t: 0, dur: Math.max(6, len / (this.sceneS() / (nav.mode === 'street' ? 25 : 9))) };
    this.controls.enabled = false; this.route3.visible = false; this.clearPin();
    this.set({ playing: true });
    if (record) this.startRec();
    this.stepPath(0); this.showHint();
  }
  private stepPath(dt: number) {
    const P = this.nav.play, pts = P.pts, n = pts.length - 1;
    P.t += dt;
    const f = Math.min(1, P.t / P.dur);
    const at = (x: number) => { const i = x * n, a = Math.floor(i); return pts[a].clone().lerp(pts[Math.min(n, a + 1)], i - a); };
    const pos = at(f), ahead = at(Math.min(1, f + 30 / n));
    this.camera.position.copy(pos);
    if (ahead.distanceToSquared(pos) > 1e-6) {
      if (this.nav.mode !== 'street') ahead.y -= pos.distanceTo(ahead) * 0.45;
      this.camera.lookAt(ahead);
    }
    if (f >= 1) this.stopPath();
  }
  stopPath() {
    this.nav.play = null; this.route3.visible = true;
    if (this.nav.rec) this.nav.rec.rec.stop();
    this.syncAngles();
    if (this.nav.mode === 'orbit') { this.controls.enabled = true; this.controls.target.copy(this.aimPoint() || new THREE.Vector3()); }
    this.set({ playing: false }); this.showHint();
  }
  private startRec() {
    const type = ['video/mp4;codecs=avc1', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'].find(t => MediaRecorder.isTypeSupported(t));
    if (!type) return this.showHint('This browser cannot record video.', 5000);
    this.renderer.setPixelRatio(1);
    const dom = this.renderer.domElement;
    const cv = Object.assign(document.createElement('canvas'), { width: dom.width & ~1, height: dom.height & ~1 });
    const rec = new MediaRecorder(cv.captureStream(30), { mimeType: type, videoBitsPerSecond: 8e6 }), chunks: Blob[] = [];
    rec.ondataavailable = e => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      this.nav.rec = null; this.renderer.setPixelRatio(Math.min(2, devicePixelRatio)); this.set({ recording: false });
      download(URL.createObjectURL(new Blob(chunks, { type })), `${this.data.name}_flythrough.${type.startsWith('video/mp4') ? 'mp4' : 'webm'}`);
    };
    rec.start(1000);
    this.nav.rec = { rec, cv };
    this.set({ recording: true });
  }
  private captionFrame() {
    const cv = this.nav.rec.cv, c = cv.getContext('2d'), fs = Math.round(cv.height / 38), pad = Math.round(fs * 0.6), k = this.s.exag;
    c.drawImage(this.renderer.domElement, 0, 0, cv.width, cv.height);
    const txt = `DepthWizard · ${nice(this.data.name)}` + (this.s.flood ? ` · water level ${this.waterLevel().toFixed(1)} m${this.data.dtm ? ' a.s.l.' : ''}` : '') + (k !== 1 ? ` · heights ×${k}` : '');
    c.font = `600 ${fs}px 'Montserrat Variable', sans-serif`;
    c.fillStyle = 'rgba(7,11,20,.7)'; c.fillRect(pad, cv.height - fs - 3 * pad, c.measureText(txt).width + 2 * pad, fs + 2 * pad);
    c.fillStyle = '#fff'; c.textBaseline = 'middle'; c.fillText(txt, 2 * pad, cv.height - fs / 2 - 2 * pad);
  }
  showHint(msg?: string, ms?: number) {
    clearTimeout(this.timers.hint);
    const nav = this.nav;
    const h = msg || (nav.play ? `Flying${nav.rec ? ' · recording video' : ''} · Stop to end`
      : nav.drawing ? `Click the scene to add route points (${nav.path.length}) · Done when finished`
      : this.s.pick === 'src' ? 'Click where water comes in (river, canal, breached embankment) · Done when finished'
      : this.s.pick === 'gcp' ? 'Click points of known elevation, then type their heights in the panel'
      : this.s.pick ? `Click the scene to place ${this.s.pick}`
      : nav.mode === 'fly' ? 'Drag to look · W A S D move · R / F up / down · Shift faster · click = measure'
      : nav.mode === 'street' ? 'Drag to look around · W A S D move (buildings block you; on flooded streets you float) · Shift faster'
      : '');
    this.set({ hint: h });
    if (ms) this.timers.hint = setTimeout(() => this.showHint(), ms);
  }
  resetNav() {
    if (this.nav.play) this.stopPath();
    this.nav.path = []; this.nav.drawing = false; this.nav.keys.clear();
    this.nav.mode = 'orbit'; this.controls.enabled = true;
    this.camera.near = 1; this.camera.fov = 50; this.camera.updateProjectionMatrix();
    this.set({ drawing: false, pathN: 0, cam: 'orbit' });
    this.showHint();
  }
  private frame() {
    const dt = Math.min(0.1, this.clock.getDelta()), el = this.el.v3d;
    if (this.s.view !== '3d' || !el) return;
    const w = el.clientWidth, h = el.clientHeight;
    if (!w || !h) return;
    // keep the scene centred in the part of the window the glass panels leave free
    // (on the landing the scene sits right of the headline instead)
    const shift = w <= 860 || this.s.page === 'scenes' ? 0 : this.s.page === 'home' ? -Math.round(w * 0.15) : Math.round((Math.min(392, w * 0.3) - 88) / 2);
    if (this.renderer.domElement.width !== Math.floor(w * this.renderer.getPixelRatio()) || this.camera.view?.offsetX !== shift) {
      this.renderer.setSize(w, h); this.camera.aspect = w / h;
      this.camera.setViewOffset(w, h, shift, 0, w, h);
      this.camera.updateProjectionMatrix();
    }
    if (this.nav.play) this.stepPath(dt);
    else if (this.s.page === 'home') { if (this.data) this.cinema(); }
    else if (this.controls.enabled) this.controls.update(); else if (this.data) this.walk(dt);
    this.renderer.render(this.scene3, this.camera);
    if (this.nav.rec) this.captionFrame();
    if (this.markerPos && this.el.pin) {
      const p = this.markerPos.clone().project(this.camera);
      this.el.pin.style.left = `${(p.x + 1) / 2 * w}px`; this.el.pin.style.top = `${(1 - p.y) / 2 * h}px`;
    }
  }
  // landing hero: a slow, low drone orbit (sky and horizon in frame) with a gentle push-in and out; a fixed angle under reduced motion
  private still = matchMedia('(prefers-reduced-motion: reduce)');
  private cinema() {
    const S = this.sceneS(), relief = (this.data.gmax - this.data.gmin) * this.s.exag, t = this.still.matches ? 8 : performance.now() / 1000;
    const a = 0.6 + t * 0.045, r = S * (1.6 - 0.08 * Math.sin(t * 0.09));
    this.camera.position.set(Math.sin(a) * r, S * 0.26 + relief * 0.9, Math.cos(a) * r);
    this.camera.lookAt(0, relief * 0.4, 0);
  }
  // landing: haze that melts the far edge into the sky (CSS horizon colour) and a faint floor that fades out early;
  // workspace: a clear view and a stronger floor that reaches further
  private atmosphere() {
    const home = this.s.page === 'home', S = this.data ? this.sceneS() : 0, gu = (this.ground.material as THREE.ShaderMaterial).uniforms;
    this.scene3.fog = home && S ? new THREE.Fog(0xe2d6c6, S * 1.4, S * 3.6) : null;
    gu.strength.value = home ? 0.3 : 0.6; gu.reach.value = S * (home ? 2.6 : 5);
  }
  setView(view: UI['view']) { this.set({ view }); if (view === '2d') { this.showLayer(); this.drawOverlay(); } }

  // ---------- downloads ----------
  async exportGLB() {
    const d = this.data, geo = this.mesh!.geometry.clone(), pos = geo.attributes.position as THREE.BufferAttribute;
    geo.deleteAttribute('steep');
    for (let i = 0; i < pos.count; i++) pos.setY(i, (d.dtm ? d.dtm[i] - d.gmin : 0) + Math.max(0, d.grid[i]));
    geo.computeVertexNormals();
    const group = new THREE.Group();
    group.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: this.mesh!.material.map, roughness: 1, metalness: 0 })));
    let wg: THREE.BufferGeometry | null = null;
    if (this.s.flood) {
      wg = this.water.geometry.clone(); this.waterHeights(wg.attributes.position as THREE.BufferAttribute, 1);
      const w = new THREE.Mesh(wg, new THREE.MeshStandardMaterial({ color: 0x2f7fe0, transparent: true, opacity: 0.55 }));
      w.name = 'water'; group.add(w);
    }
    group.name = d.name;
    group.userData = { generator: 'DepthWizard (RS3DAda)', units: 'metre', y0_metres_above_sea_level: d.dtm ? d.gmin : null,
      axes: 'origin = image centre; x = image columns (east if north-up), z = image rows (south), y = up' };
    const glb = await new GLTFExporter().parseAsync(group, { binary: true }) as ArrayBuffer;
    geo.dispose(); wg?.dispose();
    return new Blob([glb], { type: 'model/gltf-binary' });
  }
  async download(what: string) {
    if (!this.data || !what) return;
    if (what !== 'glb') return download(`/results/${this.data.name}${what}`, `${this.data.name}${what}`);
    download(URL.createObjectURL(await this.exportGLB()), `${this.data.name}.glb`);
  }

  // ---------- flood scenario ----------
  renderFlood() {
    const d = this.data, r = this.s.depth, L = this.waterLevel(), m = d.meta, W = m.grid_w, H = m.grid_h;
    const cv = d.floodCv || (d.floodCv = Object.assign(document.createElement('canvas'), { width: W, height: H }));
    const ctx = cv.getContext('2d'), img = ctx.createImageData(W, H), px = img.data;
    const state = d.buildings.map((b: any) => this.blockState(b, L));
    const arr = this.s.tarr && d.tl && this.s.timeOpen ? d.tl : null;
    let wetGround = 0, maxDepth = 0;
    for (let i = 0; i < d.grid.length; i++) {
      const g = d.dtm ? d.dtm[i] : 0, id = d.bid[i], wet = d.reach[i] < L;
      if (wet) { wetGround++; maxDepth = Math.max(maxDepth, L - g); }
      let c: number[] | null = null;
      if (arr) { const a = id > 0 ? arr.bArr[id] : arr.arrival[i]; if (a < NEVER) c = arrivalRGBA(a); }
      else if (id > 0) { const st = state[id - 1]; if (st !== 'dry') c = st === 'sub' ? FLOOD_RGBA.sub : FLOOD_RGBA.part; }
      else if (wet && g + Math.max(0, d.grid[i]) < L) c = [...FLOOD_RGBA.water.slice(0, 3), Math.min(235, 110 + (L - g) * 25)];
      if (c) px.set(c, i * 4);
    }
    ctx.putImageData(img, 0, 0);
    const t = d.floodTex || (d.floodTex = Object.assign(document.createElement('canvas'), { width: d.photo.naturalWidth, height: d.photo.naturalHeight }));
    const tc = t.getContext('2d');
    tc.drawImage(d.photo, 0, 0); tc.globalAlpha = 0.8; tc.drawImage(cv, 0, 0, t.width, t.height); tc.globalAlpha = 1;
    const count = (st: string) => state.filter((x: string) => x === st).length;
    const floorArea = d.buildings.reduce((sum: number, b: any) => sum + b.area_m2 * Math.min(b.floors, this.blockDepth(b, L) / m.floor_m), 0);
    const mode = this.s.fsrc, nSrc = d.sources.length;
    const model = mode === 'all' ? 'Bathtub model: all ground below the water level floods (no drainage or barriers).'
      : mode === 'edges' ? 'Connected model: water enters at the scene edges and floods only ground it can flow to; low spots behind higher ground stay dry (no drainage).'
      : `Connected model: water spreads from the ${nSrc} point${nSrc === 1 ? '' : 's'} you placed and floods only ground it can flow to (no drainage).`;
    const total = d.grid.length;
    this.set({ floodSum: { level: L, rise: r, abs: !!d.dtm, wetPct: 100 * wetGround / total, wetHa: wetGround * this.cellArea() / 1e4, maxDepth,
      sub: count('sub'), part: count('part'), dry: count('dry'), total: d.buildings.length, floorArea, model,
      terrain: d.dtm ? `Terrain: ${this.terrainLabel()} (30 m, about ±2–4 m)${this.laserShift() != null ? ', levelled to ICESat-2 laser points' : ''}.`
                     : 'No terrain for this image: flat ground and one uniform water depth.' } });
    this.drawOverlay();
  }
  setFlood(on: boolean) { this.set({ flood: on }); this.updateFlood(); }
  setDepth(depth: number) {   // the user sets the water level by hand: the timeline's new starting point
    this.set({ depth, tt: 0, ttLabel: 'now' });
    if (this.data) this.data.tlStart = depth;
    this.updateFlood();
    if (this.s.timeOpen) this.schedule('tl', () => this.runTimeline(), 250);
  }
  updateFlood() {
    const on = this.s.flood;
    this.water.visible = on;
    if (!on) {
      if (this.s.pick === 'src') this.setPick(null);
      if (this.s.timeOpen && this.data) { this.data.tl = null; this.set({ depth: this.data.tlStart }); }
      if (this.s.timeOpen) this.set({ timeOpen: false, tlSum: null });
    }
    if (!this.data) return;
    if (on) this.renderFlood(); else { this.set({ floodSum: null }); this.drawOverlay(); }
    this.updateWater(); this.showLayer(); this.refreshSurface(); this.drawMarks3D(); this.refreshPin();
    this.schedule('route', () => this.updateRoute(), 150);
    if (this.s.sitesOpen) this.schedule('sites', () => this.findSites(), 200);
  }
  cellArea() { const m = this.data.meta; return (m.width * m.gsd / m.grid_w) * (m.height * m.gsd / m.grid_h); }
  // data.reach[i] = lowest water level at which cell i is under water (bathtub: own ground; connected: priority flood)
  computeReach() {
    const d = this.data, W = this.W, H = this.H, N = W * H, g = this.groundGrid(), mode = this.s.fsrc;
    const reach = d.reach = mode === 'all' ? Float32Array.from(g) : new Float32Array(N).fill(Infinity);
    if (mode !== 'all') {
      const heap = new MinHeap(), seed = (i: number) => { if (g[i] < reach[i]) { reach[i] = g[i]; heap.push(g[i], i); } };
      if (mode === 'edges') {
        for (let x = 0; x < W; x++) { seed(x); seed((H - 1) * W + x); }
        for (let y = 0; y < H; y++) { seed(y * W); seed(y * W + W - 1); }
      } else for (const i of d.sources) seed(i);
      while (heap.n) {
        const i = heap.pop(), k = heap.key;
        if (k > reach[i]) continue;
        const x = i % W, y = (i - x) / W;
        for (let dd = 0; dd < 4; dd++) {
          const nx = x + NX[dd], ny = y + NY[dd];
          if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
          const j = ny * W + nx, nk = Math.max(k, g[j]);
          if (nk < reach[j]) { reach[j] = nk; heap.push(nk, j); }
        }
      }
    }
    const br = d.blockReach = new Float32Array(d.buildings.length + 1).fill(Infinity);
    for (let i = 0; i < N; i++) { const id = d.bid[i]; if (id > 0 && reach[i] < br[id]) br[id] = reach[i]; }
    d.vol = null;
  }
  reachChanged() {
    this.computeReach();
    if (this.s.flood) this.updateFlood(); else this.drawOverlay();
    if (this.s.timeOpen) this.runTimeline();
    this.computePrepare();
  }
  setFsrc(fsrc: UI['fsrc']) {
    this.set({ fsrc });
    if (!this.data) return;
    if (fsrc === 'pick' && !this.data.sources.length) this.setPick('src'); else if (this.s.pick === 'src') this.setPick(null);
    this.reachChanged();
  }
  clearSources() { if (!this.data) return; this.data.sources = []; this.set({ nSources: 0 }); this.reachChanged(); }
  floodText(u: number, v: number) {
    const d = this.data;
    if (!this.s.flood || !d.reach) return '';
    const i = this.cellAt(u, v), r = d.reach[i], L = this.waterLevel();
    if (d.bid[i] > 0) return '';
    if (!(r < Infinity)) return 'water from the chosen source cannot reach here';
    let t = r < L ? `under ${(L - this.groundGrid()[i]).toFixed(1)} m of water` : `floods at +${(r - d.gmin).toFixed(1)} m (${(r - L).toFixed(1)} m above now)`;
    if (d.tl) { const a = d.tl.arrival[i]; t += a === 0 ? '' : a < NEVER ? ` · timeline: ${this.fmtWhen(a)}` : ' · timeline: stays dry'; }
    return t;
  }

  // ---------- Prepare: hazard and exposure before an event ----------
  computePrepare() {
    const d = this.data;
    if (!d) return;
    let slopeShare: UI["slopeShare"] = null;
    if (d.slope) {
      const n = d.slope.length, cnt = SLOPE_CLASSES.map(() => 0);
      for (let i = 0; i < n; i++) cnt[SLOPE_CLASSES.findIndex(([t]) => d.slope[i] <= t)]++;
      slopeShare = SLOPE_CLASSES.map(([, label, rgb], k) => ({ label, pct: 100 * cnt[k] / n, rgb }));
    }
    const rises = [0.5, 1, 2, 3, 5, 8, 12].filter(r => r <= this.s.depthMax), N = d.reach.length, m = d.meta;
    const exposure = rises.map(rise => {
      const L = d.gmin + rise;
      let wet = 0; for (let i = 0; i < N; i++) if (d.reach[i] < L) wet++;
      let blocks = 0, sub = 0, floorArea = 0;
      for (const b of d.buildings) {
        const st = this.blockState(b, L);
        if (st !== 'dry') blocks++;
        if (st === 'sub') sub++;
        floorArea += b.area_m2 * Math.min(b.floors, this.blockDepth(b, L) / m.floor_m);
      }
      return { rise, level: L, wetPct: 100 * wet / N, blocks, sub, floorArea };
    });
    this.set({ slopeShare, exposure });
  }

  // ---------- click tools: route ends, water sources, control points ----------
  setPick(pick: Pick) { this.set({ pick }); this.showHint(); this.routeMsg(); }
  onPick(u: number, v: number) {
    const d = this.data;
    if (!this.s.pick || !d || u < 0 || u > 1 || v < 0 || v > 1) return false;
    const i = this.cellAt(u, v), R = d.route;
    if (this.s.pick === 'src') { d.sources.push(i); this.set({ nSources: d.sources.length }); this.reachChanged(); return true; }
    if (this.s.pick === 'gcp') { d.gcpPts.push({ u, v, z: null }); this.renderGcp(); this.drawOverlay(); this.drawMarks3D(); return true; }
    if (this.s.pick === 'A') { R.a = i; R.kind = R.b != null ? 'ab' : null; this.setPick(R.b != null ? null : 'B'); }
    else { R.b = i; R.kind = 'ab'; this.setPick(null); }
    this.updateRoute();
    return true;
  }

  // ---------- route finder: A* on the grid (8-connected) ----------
  travelCost(L: number) {
    const d = this.data, N = d.grid.length, tr = TRAVEL[this.s.rmode], maxD = Math.max(0, this.s.rdepth || 0), g = this.groundGrid();
    const f = new Float32Array(N), depth = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const lc = d.lc ? d.lc[i] : 2;
      if (d.bid[i] > 0 || (lc === 7 && d.grid[i] > 2.5)) { f[i] = Infinity; continue; }
      let c = d.lc ? tr.lc[lc] : 1.2;
      if (d.slope) { const s = d.slope[i]; c = s > tr.maxSlope ? Infinity : c * (1 + s / tr.slope); }
      if (d.reach[i] < L) { const dep = depth[i] = L - g[i]; c = dep > maxD ? Infinity : c * (1 + 3 * dep / Math.max(0.05, maxD)); }
      f[i] = c;
    }
    return { f, depth };
  }
  nearestOpen(i: number, f: Float32Array) {
    if (f[i] < Infinity) return i;
    const W = this.W, H = this.H, x0 = i % W, y0 = (i - x0) / W;
    for (let r = 1; r < 60; r++)
      for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue;
        const x = x0 + dx, y = y0 + dy;
        if (x >= 0 && y >= 0 && x < W && y < H && f[y * W + x] < Infinity) return y * W + x;
      }
    return -1;
  }
  findRoute(a: number, b: number, L: number) {
    const d = this.data, m = d.meta, W = m.grid_w, H = m.grid_h, N = W * H, tr = TRAVEL[this.s.rmode], maxD = this.s.rdepth;
    const dx = m.width * m.gsd / W, dy = m.height * m.gsd / H, dd = Math.hypot(dx, dy);
    const { f, depth } = this.travelCost(L);
    const s = this.nearestOpen(a, f), e = this.nearestOpen(b, f);
    if (s < 0 || e < 0) return null;
    const ex = e % W, ey = (e - ex) / W;
    const hfn = (i: number) => { const x = i % W, y = (i - x) / W; return Math.hypot((x - ex) * dx, (y - ey) * dy); };
    const cost = new Float64Array(N).fill(Infinity), from = new Int32Array(N).fill(-1), heap = new MinHeap();
    cost[s] = 0; heap.push(hfn(s), s);
    let end = -1;
    while (heap.n) {
      const i = heap.pop();
      if (heap.key > cost[i] + hfn(i) + 1e-6) continue;
      if (i === e) { end = i; break; }
      const x = i % W, y = (i - x) / W;
      for (let k = 0; k < 8; k++) {
        const nx = x + NX[k], ny = y + NY[k];
        if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
        const j = ny * W + nx;
        if (!(f[j] < Infinity)) continue;
        if (k >= 4 && !(f[y * W + nx] < Infinity && f[ny * W + x] < Infinity)) continue;
        const c = cost[i] + (k < 4 ? (NX[k] ? dx : dy) : dd) * (f[i] + f[j]) / 2;
        if (c < cost[j]) { cost[j] = c; from[j] = i; heap.push(c + hfn(j), j); }
      }
    }
    if (end < 0) return null;
    const path: number[] = [];
    for (let i = end; i >= 0; i = from[i]) path.push(i);
    path.reverse();
    let len = 0, time = 0, wetLen = 0, roadLen = 0, maxDepth = depth[s];
    for (let k = 1; k < path.length; k++) {
      const i = path[k - 1], j = path[k], xi = i % W, xj = j % W;
      const seg = Math.hypot((xi - xj) * dx, ((i - xi) / W - (j - xj) / W) * dy), dep = Math.max(depth[i], depth[j]);
      len += seg; time += seg / tr.speed * (1 + 2 * dep / Math.max(0.05, maxD));
      if (dep > 0) wetLen += seg;
      if (d.lc && d.lc[j] === 3) roadLen += seg;
      maxDepth = Math.max(maxDepth, depth[j]);
    }
    return { path, len, time, wetLen, roadLen, maxDepth, depth, end, snapped: s !== a || e !== b };
  }
  updateRoute() {
    const d = this.data;
    if (!d) return;
    const R = d.route, L = this.curLevel();
    R.res = null; R.why = '';
    if (this.s.routeOpen && R.a != null && R.kind === 'ab' && R.b != null) {
      R.res = this.findRoute(R.a, R.b, L);
      if (!R.res) R.why = L > -Infinity && this.findRoute(R.a, R.b, -Infinity)
        ? `No route at this water level: water deeper than ${this.s.rdepth} m blocks every way (a dry-weather route exists).`
        : 'No route: buildings, water bodies or steep ground block every way between A and B inside this scene.';
    }
    this.routeMsg(); this.drawOverlay(); this.drawMarks3D();
    if (d.tl) this.renderTimelineOut();
  }
  routeMsg() {
    const d = this.data;
    if (!d) return;
    const R = d.route, res = R.res;
    let msg = '';
    if (this.s.pick === 'A') msg = 'Click the map (2D or 3D) to place A, the start.';
    else if (this.s.pick === 'B') msg = 'Click the map to place B, the destination.';
    else if (R.a == null || !R.kind) msg = 'Set A and B. Routes avoid buildings, water bodies, steep ground and water deeper than the limit, and prefer roads.';
    else if (!res) msg = R.why || 'No route found.';
    this.set({ routeMsg: msg, routeSum: res && !this.s.pick ? {
      len: res.len, minutes: res.time / 60, how: this.s.rmode === 'car' ? 'by car' : 'on foot', wetLen: this.s.flood ? res.wetLen : null,
      maxDepth: res.maxDepth, roadPct: d.lc ? 100 * res.roadLen / Math.max(1, res.len) : null, snapped: res.snapped, deadline: this.ensureDeadline() } : null });
  }
  setRouteOpen(on: boolean) {
    this.set({ routeOpen: on });
    if (!this.data) return;
    if (on && this.data.route.a == null) this.setPick('A'); else if (!on && this.s.pick !== 'src') this.setPick(null);
    this.updateRoute();
  }
  clearRoute() { if (!this.data) return; this.data.route = { a: null, b: null, kind: null, res: null, why: '' }; this.setPick('A'); this.updateRoute(); }
  setRmode(rmode: TravelMode) { this.set({ rmode, rdepth: TRAVEL[rmode].depth }); this.updateRoute(); }
  setRdepth(rdepth: number) { this.set({ rdepth }); this.schedule('route', () => this.updateRoute(), 150); }
  routeCells(path: number[], every: number) {
    const W = this.W, H = this.H;
    return path.filter((_, k) => k % every === 0 || k === path.length - 1).map(i => {
      const x = i % W, y = (i - x) / W;
      return [(x / (W - 1) - 0.5) * this.sceneW(), (y / (H - 1) - 0.5) * this.sceneH()] as [number, number];
    });
  }
  flyRoute() {
    const res = this.data && this.data.route.res;
    if (!res || res.path.length < 2) return;
    this.setView('3d');
    if (this.nav.drawing) this.togglePath();
    this.setCam('street');
    this.nav.path = this.routeCells(res.path, Math.max(1, Math.round(6 / Math.sqrt(this.cellArea())))).map(([x, z]) => new THREE.Vector2(x, z));
    this.drawRoute(); this.playPath(false);
  }
  routeToSite(kind: 'pad' | 'camp', k: number) {
    const d = this.data;
    if (!d || !d.sites) return;
    const s = (kind === 'pad' ? d.sites.pads : d.sites.camps)[k], R = d.route;
    R.b = s.cell; R.kind = R.a != null ? 'ab' : null;
    if (!this.s.routeOpen) this.setRouteOpen(true); else if (R.a == null) this.setPick('A');
    this.updateRoute();
  }

  // ---------- drawing: 2D overlay and 3D markers ----------
  drawOverlay() {
    const d = this.data, c = this.el.ovl;
    if (!d || !c) return;
    const W = this.W, H = this.H, s = 2;
    if (c.width !== W * s || c.height !== H * s) { c.width = W * s; c.height = H * s; }
    const ctx = c.getContext('2d')!;
    ctx.clearRect(0, 0, c.width, c.height);
    const xy = (i: number) => [(i % W + 0.5) * s, (Math.floor(i / W) + 0.5) * s];
    if (this.s.page === 'validate') return this.drawValOverlay(ctx, c);
    const R = d.route, routeOn = this.s.routeOpen, S = this.s.sitesOpen && d.sites, m = d.meta;
    const label = (x: number, y: number, txt: string, col: string) => {
      ctx.font = 'bold 17px "Montserrat Variable", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(0,0,0,.75)'; ctx.strokeText(txt, x, y); ctx.fillStyle = col; ctx.fillText(txt, x, y);
    };
    if (S) {
      ctx.imageSmoothingEnabled = false; ctx.drawImage(S.campCv, 0, 0, c.width, c.height);
      const rpx = S.R / (m.width * m.gsd / W) * s;
      S.pads.forEach((p: any, k: number) => {
        const [x, y] = xy(p.cell);
        ctx.beginPath(); ctx.arc(x, y, rpx, 0, 2 * Math.PI); ctx.fillStyle = 'rgba(255,212,0,.18)'; ctx.fill();
        ctx.setLineDash([8, 6]); ctx.lineWidth = 3; ctx.strokeStyle = '#ffd400'; ctx.stroke(); ctx.setLineDash([]);
        label(x, y, `H${k + 1}`, '#ffd400');
      });
      S.camps.forEach((cp: any, k: number) => {
        let [x, y] = xy(cp.cell);
        const pad = S.pads.find((p: any) => { const [px, py] = xy(p.cell); return Math.hypot(px - x, py - y) < rpx + 12; });
        if (pad) { const [px, py] = xy(pad.cell); x = px; y = py + rpx + 14; }
        label(x, y, `C${k + 1}`, '#4fe08a');
      });
    }
    if (routeOn && R.res) {
      const p = R.res.path, line = (from: number, to: number, w: number, col: string) => {
        ctx.beginPath();
        for (let k = from; k <= to; k++) { const [x, y] = xy(p[k]); if (k === from) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
        ctx.lineWidth = w; ctx.strokeStyle = col; ctx.stroke();
      };
      ctx.lineJoin = ctx.lineCap = 'round';
      line(0, p.length - 1, 8, 'rgba(0,0,0,.6)'); line(0, p.length - 1, 4, '#4fe08a');
      for (let k = 1; k < p.length; k++) if (R.res.depth[p[k]] > 0 || R.res.depth[p[k - 1]] > 0) line(k - 1, k, 4, '#3da5ff');
    }
    const dot = (i: number, col: string, txt: string) => {
      const [x, y] = xy(i);
      ctx.beginPath(); ctx.arc(x, y, 15, 0, 2 * Math.PI); ctx.fillStyle = col; ctx.fill();
      ctx.lineWidth = 3; ctx.strokeStyle = '#fff'; ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = 'bold 17px "Montserrat Variable", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(txt, x, y + 0.5);
    };
    if (this.s.flood && this.s.fsrc === 'pick') for (const i of d.sources) dot(i, '#2f7fe0', '≈');
    if (routeOn) { if (R.a != null) dot(R.a, '#2e9e5b', 'A'); if (R.kind === 'ab' && R.b != null) dot(R.b, '#d64545', 'B'); }
  }
  drawMarks3D() {
    for (const o of this.marks.children as any[]) { o.geometry.dispose(); o.material.dispose(); }
    this.marks.clear();
    const d = this.data;
    if (!d || !this.mesh) return;
    const k = this.s.exag, L = this.curLevel(), r = this.sceneS() / 160, R = d.route;
    const at = (x: number, z: number) => Math.max(this.surfaceY(x, z), d.reach[this.cellAt(x / this.sceneW() + 0.5, z / this.sceneH() + 0.5)] < L ? (L - d.gmin) * k : -Infinity);
    const ball = (i: number, color: number) => {
      const [[x, z]] = this.routeCells([i], 1), b = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), new THREE.MeshBasicMaterial({ color }));
      b.position.set(x, at(x, z) + r, z); this.marks.add(b);
    };
    if (this.s.page === 'validate') { for (const p of d.gcpPts) ball(this.cellAt(p.u, p.v), 0xff7ad9); return; }
    if (this.s.flood && this.s.fsrc === 'pick') for (const i of d.sources) ball(i, 0x2f7fe0);
    const S = this.s.sitesOpen && d.sites;
    if (S) {
      for (const p of S.pads) {
        const [[x, z]] = this.routeCells([p.cell], 1), ring = new THREE.Mesh(new THREE.RingGeometry(S.R * 0.88, S.R, 64).rotateX(-Math.PI / 2),
          new THREE.MeshBasicMaterial({ color: 0xffd400, side: THREE.DoubleSide }));
        ring.position.set(x, at(x, z) + 0.3 * k, z); this.marks.add(ring);
      }
      for (const cp of S.camps) {
        const [[x, z]] = this.routeCells([cp.cell], 1), cone = new THREE.Mesh(new THREE.ConeGeometry(r, r * 3, 16).rotateX(Math.PI), new THREE.MeshBasicMaterial({ color: 0x4fe08a }));
        cone.position.set(x, at(x, z) + r * 2, z); this.marks.add(cone);
      }
    }
    if (!this.s.routeOpen) return;
    if (R.res && R.res.path.length > 1) {
      const pts = this.routeCells(R.res.path, 3).map(([x, z]) => new THREE.Vector3(x, at(x, z) + r * 0.5, z));
      if (pts.length > 1) this.marks.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), pts.length * 3, r * 0.35, 6, false),
        new THREE.MeshBasicMaterial({ color: 0x4fe08a })));
    }
    if (R.a != null) ball(R.a, 0x2e9e5b);
    if (R.kind === 'ab' && R.b != null) ball(R.b, 0xd64545);
  }

  // ---------- rain & rise timeline (scenario tool, not a forecast) ----------
  volumeTable() {
    const d = this.data;
    if (d.vol) return d.vol;
    const r = d.reach, g = this.groundGrid(), N = r.length, idx = new Uint32Array(N);
    for (let i = 0; i < N; i++) idx[i] = i;
    idx.sort((a, b) => r[a] < r[b] ? -1 : r[a] > r[b] ? 1 : 0);
    let M = 0;
    while (M < N && r[idx[M]] < Infinity) M++;
    const rs = new Float64Array(M), G = new Float64Array(M + 1);
    for (let k = 0; k < M; k++) { rs[k] = r[idx[k]]; G[k + 1] = G[k] + g[idx[k]]; }
    return d.vol = { rs, G, M, cell: this.cellArea() };
  }
  wetCount(T: any, L: number) { let lo = 0, hi = T.M; while (lo < hi) { const mid = (lo + hi) >> 1; if (T.rs[mid] < L) lo = mid + 1; else hi = mid; } return lo; }
  volAt(T: any, L: number) { const n = this.wetCount(T, L); return T.cell * (n * L - T.G[n]); }
  levelFor(T: any, V: number, Lmin: number) {
    if (!T.M || V <= this.volAt(T, Lmin)) return Lmin;
    let lo = Lmin, step = 0.5, hi = Lmin + step;
    while (this.volAt(T, hi) < V) { lo = hi; step *= 2; hi += step; }
    for (let it = 0; it < 50; it++) { const mid = (lo + hi) / 2; if (this.volAt(T, mid) < V) lo = mid; else hi = mid; }
    return hi;
  }
  runoffCoef() {
    const d = this.data;
    if (d.runoffC != null) return d.runoffC;
    if (!d.lc) return d.runoffC = 0.7;
    let s = 0;
    for (const c of d.lc) s += LC_RUNOFF[c] ?? 0.7;
    return d.runoffC = s / d.lc.length;
  }
  rainSeries(T: number) {
    const P = new Float32Array(T), d = this.data;
    if (d.forecast) for (let h = 0; h < T; h++) P[h] = d.forecast.mm[h] ?? 0;
    else { const rate = Math.max(0, this.s.train || 0), hrs = Math.max(0, this.s.thours || 0); for (let h = 0; h < T; h++) P[h] = !hrs || h < hrs ? rate : 0; }
    return P;
  }
  clockAt(h: number) { return new Date(this.data.tl.base + h * 3600e3).toLocaleString('en-IN', { weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }); }
  fmtWhen(h: number) { return `in ≈ ${h < 48 ? h + ' h' : (h / 24).toFixed(1) + ' days'} (${this.clockAt(h)})`; }
  setTimeParam(p: Partial<UI>) { this.set(p); this.schedule('tl', () => this.runTimeline(), 250); }
  setTimeOpen(on: boolean) {
    this.set({ timeOpen: on });
    if (!this.data) return;
    if (on) { this.data.tlStart = this.s.depth; this.set({ tt: 0 }); this.runTimeline(); }
    else { this.data.tl = null; this.set({ depth: this.data.tlStart, tlSum: null }); this.updateFlood(); this.routeMsg(); }
  }
  runTimeline() {
    const d = this.data;
    if (!d || !this.s.timeOpen) return;
    const days = Math.min(16, Math.max(1, Math.round(this.s.tdays || 3))), T = days * 24;
    const Tb = this.volumeTable(), N = d.reach.length, A = N * Tb.cell, C = this.runoffCoef();
    const D = Math.max(0, this.s.tdrain || 0), up = Math.max(1, this.s.tup || 1), rise = (this.s.trise || 0) / 24;
    const P = this.rainSeries(T), L0 = d.gmin + d.tlStart;
    const L = new Float64Array(T + 1), Lmax = new Float64Array(T + 1);
    L[0] = Lmax[0] = L0;
    let Vr = 0;
    for (let h = 0; h < T; h++) {
      const e = P[h] * C - D;
      Vr = Math.max(0, Vr + (e > 0 ? up * e : e) * A / 1000);
      const Le = L0 + rise * (h + 1);
      L[h + 1] = this.levelFor(Tb, this.volAt(Tb, Le) + Vr, Le);
      Lmax[h + 1] = Math.max(Lmax[h], L[h + 1]);
    }
    const first = (lv: number) => {
      if (!(Lmax[T] > lv)) return NEVER;
      let lo = 0, hi = T;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (Lmax[mid] > lv) hi = mid; else lo = mid + 1; }
      return lo;
    };
    const arrival = new Uint16Array(N);
    for (let i = 0; i < N; i++) arrival[i] = first(d.reach[i]);
    const bArr = new Uint16Array(d.buildings.length + 1).fill(NEVER);
    for (const b of d.buildings) bArr[b.id] = first(this.s.fsrc === 'all' ? this.blockGround(b) : Math.max(this.blockGround(b), d.blockReach[b.id]));
    const base = d.forecast ? new Date(d.forecast.start).getTime() : (() => { const x = new Date(); x.setMinutes(0, 0, 0); return x.getTime(); })();
    d.tl = { L, Lmax, P, T, days, C, D, up, arrival, bArr, base };
    this.set({ ttMax: T, tt: Math.min(this.s.tt, T) });
    this.renderTimelineOut();
    this.applyTime(this.s.tt);
  }
  applyTime(h: number) {
    const d = this.data, tl = d.tl;
    if (!tl) return;
    h = Math.min(tl.T, Math.max(0, h));
    const rise = Math.max(0, tl.L[h] - d.gmin);
    this.set({ tt: h, depth: rise, depthMax: Math.max(this.s.depthMax, Math.ceil(rise + 1)), ttLabel: h ? `+${h} h · ${this.clockAt(h)}` : 'now' });
    this.updateFlood();
  }
  setTarr(tarr: boolean) { this.set({ tarr }); if (this.data && this.data.tl) { this.renderTimelineOut(); this.updateFlood(); } }
  routeDeadline() {
    const d = this.data, R = d.route, tl = d.tl, ok = (h: number) => !!this.findRoute(R.a, R.b, tl.Lmax[h]);
    const who = this.s.rmode === 'car' ? 'cars' : 'people on foot';
    if (!ok(0)) return `Route A → B is already blocked for ${who} at the starting water level.`;
    if (ok(tl.T)) return `Route A → B stays open for ${who} for the whole ${tl.days}-day period.`;
    let lo = 0, hi = tl.T;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (ok(mid)) lo = mid; else hi = mid; }
    return `Route A → B stays open until ≈ ${this.clockAt(hi)} (+${hi} h) for ${who}; after that water deeper than ${this.s.rdepth} m blocks every way.`;
  }
  ensureDeadline() {
    const d = this.data, R = d.route, tl = d.tl;
    if (!tl || !this.s.routeOpen || R.kind !== 'ab' || R.a == null || R.b == null) return '';
    const key = [R.a, R.b, this.s.rmode, this.s.rdepth].join();
    if (tl.dlKey !== key) { tl.dlKey = key; tl.deadline = this.routeDeadline(); }
    return tl.deadline;
  }
  renderTimelineOut() {
    const d = this.data, tl = d.tl, Tb = d.vol, ha = (n: number) => n * Tb.cell / 1e4;
    let total = 0, run = 0, max24 = 0;
    for (let h = 0; h < tl.T; h++) { total += tl.P[h]; run += tl.P[h] - (h >= 24 ? tl.P[h - 24] : 0); max24 = Math.max(max24, run); }
    let peakH = 0;
    for (let h = 1; h <= tl.T; h++) if (tl.L[h] > tl.L[peakH]) peakH = h;
    const rows: TimelineSummary["rows"] = [];
    for (let dd = 0; dd <= tl.days; dd++) {
      const h = dd * 24, L = tl.L[h];
      rows.push({ when: dd ? `+${dd} d · ${this.clockAt(h)}` : 'Now', rise: L - d.gmin, ha: ha(this.wetCount(Tb, L)),
        blocks: tl.bArr.reduce((n: number, a: number, id: number) => n + (id > 0 && a <= h ? 1 : 0), 0) });
    }
    const fc = d.forecast;
    this.set({ tlSum: { totalRain: total, max24, imd: imdClass(max24), peakRise: tl.L[peakH] - d.gmin, peakH, deadline: this.ensureDeadline(), rows,
      noSources: !Tb.M, chart: { P: Array.from(tl.P), rises: Array.from(tl.L, (l: number) => l - d.gmin), days: tl.days },
      note: `Runoff coefficient ${tl.C.toFixed(2)} (${d.lc ? "from the model's land cover" : 'default'}); drains take ${tl.D} mm/h; area draining here ×${tl.up}. `
        + (fc && fc.mm.length < tl.T ? `The forecast covers ${fc.mm.length} h; no rain is assumed after that. ` : '')
        + 'Scenario, not a forecast: one water level over the flooded area, no flow speed, blocked drains or soaked soil; water from outside the image comes only from the river rise you enter. Terrain is 30 m (about ±2–4 m).' } });
  }
  async toggleForecast() {
    const d = this.data;
    if (!d) return;
    if (d.forecast) { d.forecast = null; this.set({ forecastOn: false, forecastInfo: '' }); return this.runTimeline(); }
    const ll = d.meta.center_lonlat;
    if (!ll) return this.set({ forecastInfo: 'needs a GeoTIFF scene (location unknown)' });
    this.set({ forecastInfo: 'loading…' });
    try {
      const days = Math.min(16, Math.round(this.s.tdays || 3) + 1);
      const j = await (await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${ll[1]}&longitude=${ll[0]}&hourly=precipitation&forecast_days=${days}&timezone=auto`)).json();
      if (!j.hourly) throw new Error(j.reason || 'no data');
      const now = new Date(Date.now() + j.utc_offset_seconds * 1000).toISOString().slice(0, 13);
      let s = j.hourly.time.findIndex((t: string) => t.slice(0, 13) >= now);
      if (s < 0) s = 0;
      d.forecast = { start: j.hourly.time[s], mm: j.hourly.precipitation.slice(s).map((v: number | null) => v ?? 0) };
    } catch (err: any) { return this.set({ forecastInfo: `forecast unavailable (${err.message})` }); }
    this.set({ forecastOn: true, forecastInfo: `Open-Meteo: ${d.forecast.mm.reduce((a: number, b: number) => a + b, 0).toFixed(0)} mm in the next ${d.forecast.mm.length} h` });
    this.runTimeline();
  }
  toolsSceneLoaded() {
    this.setPick(this.s.routeOpen ? 'A' : this.s.flood && this.s.fsrc === 'pick' ? 'src' : null);
    this.set({ nSources: 0 });
    if (this.s.timeOpen) this.runTimeline();
    this.updateRoute();
    if (this.s.sitesOpen) this.findSites();
  }

  // ---------- helipad & relief camp finder ----------
  setSitesOpen(on: boolean) {
    this.set({ sitesOpen: on });
    if (!this.data) return;
    if (on) this.findSites(); else { this.data.sites = null; this.set({ sites: null }); this.drawOverlay(); this.drawMarks3D(); }
  }
  setSiteParam(p: Partial<UI>) { this.set(p); this.schedule('sites', () => this.findSites(), 200); }
  siteLevel() { const tl = this.data.tl; return tl && this.s.stl ? tl.Lmax[tl.T] : this.curLevel(); }
  findSites() {
    const d = this.data;
    if (!d || !this.s.sitesOpen) return;
    const m = d.meta, W = m.grid_w, H = m.grid_h, N = W * H, dx = m.width * m.gsd / W, dy = m.height * m.gsd / H, cell = dx * dy;
    const L = this.siteLevel(), dry = Math.max(0, this.s.sdry || 0), maxS = this.s.sslope || 0;
    const R = Math.max(5, this.s.spad || 25) / 2, minArea = Math.max(50, this.s.scamp || 1000), per = Math.max(1, this.s.sper || 45);
    const blocked = new Uint8Array(N);
    for (let i = 0; i < N; i++)
      blocked[i] = d.bid[i] > 0 || (d.lc && !SITE_LC[d.lc[i]]) || d.grid[i] >= 1 || (d.slope && d.slope[i] > maxS) || d.reach[i] < L + dry ? 1 : 0;
    const dist = edt(blocked, W, H, dx, dy), half = Math.min(dx, dy) / 2;
    for (let i = 0; i < N; i++) {
      const x = i % W, y = (i - x) / W;
      dist[i] = blocked[i] ? 0 : Math.min(dist[i] - half, (x + 0.5) * dx, (W - x - 0.5) * dx, (y + 0.5) * dy, (H - y - 0.5) * dy);
    }
    const flood = L > -Infinity, xyOf = (i: number) => [i % W, Math.floor(i / W)];
    const aboveWater = (cells: ArrayLike<number>) => { let lo = Infinity; for (let k = 0; k < cells.length; k++) lo = Math.min(lo, d.reach[cells[k]] - L); return lo; };
    const cand: number[] = [];
    for (let i = 0; i < N; i++) if (dist[i] >= R) cand.push(i);
    cand.sort((a, b) => dist[b] - dist[a]);
    const pads: any[] = [];
    for (const i of cand) {
      if (pads.length >= MAX_SITES) break;
      const [x, y] = xyOf(i);
      if (pads.some(p => Math.hypot((p.x - x) * dx, (p.y - y) * dy) < 2 * R)) continue;
      const disc: number[] = [], near = { h: 0, d: 0 }, rr = Math.ceil((R + 30) / Math.min(dx, dy));
      for (let yy = Math.max(0, y - rr); yy <= Math.min(H - 1, y + rr); yy++)
        for (let xx = Math.max(0, x - rr); xx <= Math.min(W - 1, x + rr); xx++) {
          const j = yy * W + xx, dd = Math.hypot((xx - x) * dx, (yy - y) * dy);
          if (dd <= R) disc.push(j);
          else if (dd <= R + 30 && d.grid[j] > near.h) { near.h = d.grid[j]; near.d = dd - R; }
        }
      pads.push({ cell: i, x, y, clear: 2 * dist[i], slope: d.slope ? d.slope[i] : null, above: flood ? aboveWater(disc) : null, near });
    }
    const lab = new Int32Array(N), queue = new Int32Array(N), comps: any[] = [];
    for (let s0 = 0; s0 < N; s0++) {
      if (lab[s0] || dist[s0] < 3) continue;
      const id = comps.length + 1; let qh = 0, qt = 0, best = s0;
      lab[s0] = id; queue[qt++] = s0;
      while (qh < qt) {
        const i = queue[qh++], x = i % W, y = (i - x) / W;
        if (dist[i] > dist[best]) best = i;
        for (let k = 0; k < 8; k++) {
          const nx = x + NX[k], ny = y + NY[k];
          if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
          const j = ny * W + nx;
          if (!lab[j] && dist[j] >= 3) { lab[j] = id; queue[qt++] = j; }
        }
      }
      comps.push({ id, n: qt, best, cells: queue.slice(0, qt) });
    }
    const big = comps.filter(c => c.n * cell >= minArea).sort((a, b) => b.n - a.n).slice(0, MAX_SITES);
    let roadDist: Float64Array | null = null;
    if (d.lc && big.length) {
      const road = new Uint8Array(N);
      for (let i = 0; i < N; i++) road[i] = d.lc[i] === 3 && !(d.reach[i] < L) ? 1 : 0;
      roadDist = edt(road, W, H, dx, dy);
    }
    const camps = big.map(c => {
      let road = Infinity;
      if (roadDist) for (const i of c.cells) road = Math.min(road, roadDist[i]);
      const [x, y] = xyOf(c.best);
      return { cell: c.best, x, y, id: c.id, area: c.n * cell, people: Math.floor(c.n * cell / per), road, slope: d.slope ? d.slope[c.best] : null, above: flood ? aboveWater(c.cells) : null };
    });
    const cv = Object.assign(document.createElement('canvas'), { width: W, height: H }), ctx = cv.getContext('2d')!, img = ctx.createImageData(W, H);
    const keep = new Map(camps.map((c, k) => [c.id, k]));
    for (let i = 0; i < N; i++) if (keep.has(lab[i])) img.data.set([79, 224, 138, 105], i * 4);
    ctx.putImageData(img, 0, 0);
    d.sites = { pads, camps, campCv: cv, R, blocked, L };
    const aboveTxt = (a: number | null) => a == null ? '' : a < Infinity ? ` · ${a.toFixed(1)} m above water` : ' · water cannot reach';
    const tl = d.tl && this.s.stl, water = L > -Infinity ? (tl ? 'the highest water of the timeline' : 'the current water') : null;
    this.set({ sites: {
      pads: pads.map((p, k) => ({ kind: 'pad', label: `H${k + 1}`, cell: p.cell,
        text: `${p.clear > 80 ? '80+' : Math.floor(p.clear)} m clear${p.slope != null ? ` · ${p.slope.toFixed(1)}°` : ''}${aboveTxt(p.above)}`,
        sub: p.near.h >= 3 ? `approach: ${p.near.h.toFixed(0)} m tall obstacle ${Math.round(p.near.d)} m from the edge` : 'no obstacle over 3 m within 30 m' })),
      camps: camps.map((c, k) => ({ kind: 'camp', label: `C${k + 1}`, cell: c.cell,
        text: `${Math.round(c.area).toLocaleString('en-IN')} m² · ~${c.people.toLocaleString('en-IN')} people`,
        sub: `${c.road < Infinity ? (c.road < 2 ? 'on a road' : `road ${Math.round(c.road)} m away`) : 'no dry road found'}${c.slope != null ? ` · ${c.slope.toFixed(1)}°` : ''}${aboveTxt(c.above)}` })),
      L, note: `Open = no building, trees or water in the model's land cover, nothing over 1 m tall, slope ≤ ${this.s.sslope}°`
        + (water ? `, and at least ${this.s.sdry} m above ${water}` : ' (flood is off, so water is not considered)')
        + `. Camp capacity at ${this.s.sper} m² per person (Sphere standard); camp areas count only ground ≥ 3 m from obstacles. Slope comes from the 30 m terrain and heights from the model: inspect a site (and its approach) before using it.` } as any });
    this.drawOverlay(); this.drawMarks3D();
  }

  // ---------- validate against reference data ----------
  errLimit() { const r = this.s.val.raster; return Math.max(1, Math.min(20, (r && r.error_range) || 5)); }
  errCanvas() {
    const d = this.data;
    if (d.errCv || !d.valerr) return d.errCv || null;
    const lim = this.errLimit(), cv = Object.assign(document.createElement('canvas'), { width: this.W, height: this.H });
    const ctx = cv.getContext('2d')!, img = ctx.createImageData(this.W, this.H);
    d.valerr.forEach((e: number, i: number) => { if (Number.isFinite(e)) img.data.set([...divRamp(e / (2 * lim) + 0.5), 255], i * 4); });
    ctx.putImageData(img, 0, 0);
    return d.errCv = cv;
  }
  errTexture() {
    const d = this.data, e = this.errCanvas();
    if (!e) return null;
    if (d.errTex) return d.errTex;
    const t = Object.assign(document.createElement('canvas'), { width: d.photo.naturalWidth, height: d.photo.naturalHeight }), c = t.getContext('2d')!;
    c.drawImage(d.photo, 0, 0); c.globalAlpha = 0.8; c.drawImage(e, 0, 0, t.width, t.height);
    return d.errTex = t;
  }
  valText(u: number, v: number) {
    const d = this.data;
    if (this.s.page !== 'validate' || !d.valerr || this.s.vlayer !== 'err') return '';
    const e = d.valerr[this.cellAt(u, v)];
    return Number.isFinite(e) ? `vs reference: ${e >= 0 ? '+' : ''}${e.toFixed(2)} m (ours ${e >= 0 ? 'higher' : 'lower'})` : 'no reference data here';
  }
  renderValidation() {
    if (!this.data) return;
    const keys = ['raster', 'points', 'icesat2'].filter(k => this.s.val[k]);
    let vsel = this.s.vsel;
    if (!vsel || !keys.includes(vsel)) vsel = keys.includes('raster') ? 'raster' : keys[0] || null;
    this.set({ vsel, errLim: this.errLimit() });
    if (this.s.page === 'validate') { this.showLayer(); this.refreshSurface(); this.drawOverlay(); }
  }
  setVsel(vsel: string) { this.set({ vsel }); this.renderValidation(); }
  setVlayer(vlayer: UI['vlayer']) { this.set({ vlayer }); this.showLayer(); this.refreshSurface(); }
  private drawValOverlay(ctx: CanvasRenderingContext2D, c: HTMLCanvasElement) {
    const d = this.data, r = this.s.val[this.s.vsel!], lim = this.errLimit(), P = (u: number, v: number) => [u * c.width, v * c.height];
    const dot = (x: number, y: number, rad: number, rgb: RGB) => { ctx.beginPath(); ctx.arc(x, y, rad, 0, 2 * Math.PI); ctx.fillStyle = `rgb(${rgb})`; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = 'rgba(0,0,0,.7)'; ctx.stroke(); };
    if (this.s.vsel === 'icesat2' && r && r.photons_xy) {
      const p = r.photons_xy;
      p.u.forEach((u: number, i: number) => { const [x, y] = P(u, p.v[i]); dot(x, y, 3.5, divRamp((p.ours[i] - p.h[i]) / (2 * lim) + 0.5)); });
    }
    if (this.s.vsel === 'points' && r && r.points) for (const q of r.points) { const [x, y] = P(q.u, q.v); dot(x, y, 9, divRamp((q.ours - q.ref) / (2 * lim) + 0.5)); }
    d.gcpPts.forEach((q: any, k: number) => {
      const [x, y] = P(q.u, q.v);
      ctx.beginPath(); ctx.arc(x, y, 14, 0, 2 * Math.PI); ctx.fillStyle = '#ff7ad9'; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = '#fff'; ctx.stroke();
      ctx.fillStyle = '#111'; ctx.font = 'bold 15px "Montserrat Variable", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(String(k + 1), x, y + 0.5);
    });
  }
  async runValidation(url: string, body: BodyInit, label: string) {
    const name = this.data.name;
    this.set({ vmsg: label, vbusy: true });
    try {
      const r = await fetch(url, { method: 'POST', body }), j = await r.json();
      if (!r.ok) throw new Error(j.error || r.statusText);
      if (!this.data || this.data.name !== name) return;
      this.set({ val: { ...this.s.val, [j.key]: j }, vsel: j.key });
      if (j.key === 'raster') {
        this.data.valerr = new Float32Array(await (await fetch(`/results/${name}_valerr.f32?t=${Date.now()}`)).arrayBuffer());
        this.data.errCv = this.data.errTex = null; this.set({ vlayer: 'err' });
      }
      this.set({ vmsg: `Done: ${({ raster: 'reference raster', points: 'surveyed points', icesat2: 'ICESat-2 laser' } as any)[j.key]}.` });
    } catch (e: any) { this.set({ vmsg: `⚠ ${e.message}` }); }
    finally { this.set({ vbusy: false }); this.renderValidation(); }
  }
  compareFile(f: File, kind: string, datum: string) {
    if (!this.data) return;
    const csv = /\.(csv|txt)$/i.test(f.name);
    this.runValidation(`/api/validate?name=${encodeURIComponent(this.data.name)}&kind=${csv ? 'points' : kind}&datum=${datum}&file=${encodeURIComponent(f.name)}`, f, `Comparing with ${f.name}…`);
  }
  checkIcesat() { if (this.data) this.runValidation(`/api/icesat2?name=${encodeURIComponent(this.data.name)}`, '', 'Fetching NASA ICESat-2 laser photons for this scene (first time can take ~30 s)…'); }

  // ---------- calibrate with ground control points ----------
  modelHeightAt(u: number, v: number) {
    const d = this.data, g = this.corrOn() ? d.gridCorr : d.gridRaw;
    return (d.dtmRaw ? this.sample(d.dtmRaw, u, v) : 0) + Math.max(0, this.sample(g, u, v));
  }
  renderGcp() {
    const d = this.data;
    if (!d) return;
    this.set({ gcpPts: d.gcpPts.map((p: any) => ({ ...p, model: this.modelHeightAt(p.u, p.v) })), gcpFit: d.meta.gcp || null, hasGcp: !!d.meta.gcp });
  }
  setGcpZ(k: number, z: number | null) { this.data.gcpPts[k].z = z; this.renderGcp(); }
  removeGcp(k: number) { this.data.gcpPts.splice(k, 1); this.renderGcp(); this.drawOverlay(); this.drawMarks3D(); }
  rebuildScene() { this.applyTerrain(); this.renderStats(); this.showLayer(); this.build3D(); this.updateFlood(); this.renderGcp(); this.drawOverlay(); this.computePrepare(); }
  async fitGcp() {
    const d = this.data;
    if (!d) return;
    const pts = d.gcpPts.filter((p: any) => Number.isFinite(p.z)), name = d.name;
    this.setPick(null); this.set({ gcpMsg: 'Fitting…' });
    const r = await fetch(`/api/gcp?name=${encodeURIComponent(name)}`, { method: 'POST', body: JSON.stringify({ points: pts }) }), j = await r.json();
    if (!this.data || this.data.name !== name) return;
    if (!r.ok) return this.set({ gcpMsg: `⚠ ${j.error}` });
    d.meta.gcp = j; d.gcpPts = j.points.map((p: any) => ({ u: p.u, v: p.v, z: p.z }));
    this.set({ gcpOn: true, gcpMsg: '' });
    this.rebuildScene();
  }
  async clearGcp() {
    const d = this.data;
    if (!d) return;
    this.setPick(null);
    if (d.meta.gcp) await fetch(`/api/gcp?name=${encodeURIComponent(d.name)}`, { method: 'POST', body: JSON.stringify({ clear: true }) });
    delete d.meta.gcp; d.gcpPts = [];
    this.rebuildScene();
  }
  setGcpOn(gcpOn: boolean) { this.set({ gcpOn }); if (this.data) this.rebuildScene(); }

  // ---------- pages ----------
  setPage(page: Page) {
    const prev = this.s.page;
    if (page === prev) return;
    this.set({ page });
    if (page !== 'home') this.visited = true;
    this.atmosphere();
    if (prev === 'home' && this.data) this.overview();   // hand the camera back from the landing's drone shot
    if (this.s.pick) this.setPick(null);
    if (isDisaster(prev) && !isDisaster(page)) {   // the disaster tools run only on their own pages
      this.set({ routeOpen: false, sitesOpen: false, sites: null });
      if (this.data) this.data.sites = null;
      if (this.s.flood) this.setFlood(false);
    }
    if (page === 'relief' && !this.s.sitesOpen) this.setSitesOpen(true);
    if (!this.data) return;
    if (page === 'validate') { this.renderValidation(); this.renderGcp(); }
    if (page === 'prepare') this.computePrepare();
    this.showLayer(); this.refreshSurface(); this.drawOverlay(); this.drawMarks3D();
  }
  // impact report for the Assess page
  report() {
    const d = this.data;
    if (!d) return null;
    const L = this.curLevel(), m = d.meta;
    const affected = this.s.flood ? d.buildings.map((b: any) => ({ id: b.id, st: this.blockState(b, L), depth: this.blockDepth(b, L), b }))
      .filter((x: any) => x.st !== 'dry')
      .map((x: any) => ({ id: x.id, state: x.st === 'sub' ? 'submerged' : 'partly flooded', height_m: +x.b.height_m.toFixed(1),
        floors: x.b.floors, floors_under: +Math.min(x.b.floors, x.depth / m.floor_m).toFixed(1), area_m2: Math.round(x.b.area_m2),
        water_depth_m: +x.depth.toFixed(2), cx: +x.b.cx.toFixed(4), cy: +x.b.cy.toFixed(4) }))
      .sort((a: any, b: any) => b.floors_under - a.floors_under || b.area_m2 - a.area_m2) : [];
    return { affected, L };
  }
  exportReport() {
    const d = this.data, rep = this.report();
    if (!d || !rep) return;
    const s = this.s, out = {
      generator: 'DepthWizard', scene: d.name, created: new Date().toISOString(),
      scenario: s.flood ? { water_rise_m: +s.depth.toFixed(2), water_level_m: d.dtm ? +rep.L.toFixed(2) : null, source: s.fsrc,
        timeline: d.tl ? { days: d.tl.days, rain_mm_per_h: d.forecast ? 'Open-Meteo forecast' : s.train, river_rise_m_per_day: s.trise, drains_mm_per_h: s.tdrain } : null } : null,
      summary: s.floodSum, route: s.routeSum, sites: s.sites && { helipads: s.sites.pads.map(p => `${p.label}: ${p.text}`), camps: s.sites.camps.map(c => `${c.label}: ${c.text}`) },
      affected_blocks: rep.affected, caveats: 'Scenario tool, not a forecast. Heights carry model error; terrain is 30 m (about ±2–4 m). Inspect on the ground before acting.',
    };
    download(URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' })), `${d.name}_impact.json`);
    const csv = ['block_id,state,height_m,floors,floors_under_water,area_m2,water_depth_m,x_frac,y_frac',
      ...rep.affected.map((a: any) => [a.id, a.state, a.height_m, a.floors, a.floors_under, a.area_m2, a.water_depth_m, a.cx, a.cy].join(','))].join('\n');
    download(URL.createObjectURL(new Blob([csv], { type: 'text/csv' })), `${d.name}_affected_blocks.csv`);
  }

  private schedule(k: string, f: () => void, ms: number) { clearTimeout(this.timers[k]); this.timers[k] = setTimeout(f, ms); }
}

function download(href: string, name: string) { Object.assign(document.createElement('a'), { href, download: name }).click(); }

export const engine = new Engine();
