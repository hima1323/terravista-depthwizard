// The newer analysis tools (line of sight, volume, drone plan, rooftop solar, map overlay, mosaics, shadow heights,
// tall-object fixes, calibrated error bars, terrain source, GNSS import, people at risk, evacuation, before/after damage,
// landslide risk, observed flood, flowing water, printable report), ported from the classic viewer's toolbar.
// The Engine owns the scene; it calls in here at its extension points (picks, overlay, 3D marks, hover lines, water
// surface, heights, scene load, page change). Tool inputs and results live in `s`, which the cards read with useTools().
import * as THREE from 'three';
import type { Engine, Page } from './Engine';
import { inferno, MinHeap, NX, NY, TRAVEL, ARR_KEYS, imdClass, nice, type RGB, type TravelMode } from './algos';

export type ToolId = 'los' | 'vol' | 'drone' | 'solar' | 'wms' | 'mosaic' | 'shadow' | 'fix' | 'err' | 'dem' | 'gnss'
  | 'slide' | 'flow' | 'obs' | 'evac' | 'dmg';
export type ToolPick = 'los' | 'vol' | 'shadow' | 'flowsrc';
// which page each tool's card is on (a tool closes when you leave its page)
export const TOOL_PAGE: Record<ToolId, Page> = { los: 'explore', vol: 'explore', drone: 'explore', solar: 'explore', wms: 'explore', mosaic: 'explore',
  shadow: 'validate', fix: 'validate', err: 'validate', dem: 'validate', gnss: 'validate', slide: 'prepare', flow: 'respond', obs: 'respond',
  evac: 'relief', dmg: 'assess' };

export interface ToolsUI {
  open: Partial<Record<ToolId, boolean>>;
  losH: number; losT: number; losR: number; los: any;
  volBase: 'edge' | 'ground' | 'level'; volLevel: number; volN: number; vol: any;
  drSrc: 'path' | 'route'; drClr: number; drBuf: number; drStep: number; drSpeed: number; drMax: number; drone: any;
  solGhi: number; solEff: number; solUse: number; solPr: number; solTar: number; solar: any; solBusy: boolean;
  wmsPreset: 'osm' | 'custom'; wmsUrl: string; wmsLayers: string; wmsOp: number; wmsOn: boolean; wmsMsg: string;
  mosSel: string[]; mosName: string; mosGrid: number; mosMsg: string;
  shEl: number; shAz: number; shTime: string; shadow: any; shMsg: string; shBusy: boolean;
  fixB: number; fixT: number; fixFit: any; fixMsg: string; fixOn: boolean; fixBusy: boolean;
  errSrc: string; errLev: string; errMsg: string;
  demMsg: string; demDatum: 'egm96' | 'egm2008';
  gnssDatum: 'ellipsoid' | 'egm96' | 'egm2008'; gnssMsg: string;
  ppM2: number; ppOcc: number; people: any;
  evWho: 'flood' | 'slide' | 'all'; evMode: TravelMode; evac: any;
  dmgBefore: string; dmgCol: number; dmgDam: number; dmgDeb: number; dmg: any; dmgMsg: string;
  slRain: number; slide: any;
  obsKind: 'auto' | 'mask' | 'db' | 'linear'; obsThr: string; obs: any; obsMsg: string;
  flQ: number; flRain: number; flHours: number; flow: any; flK: number; flMax: number; flArr: boolean; flBusy: boolean; flSrcN: number;
  palette: boolean; rev: number;
}
const INITIAL: ToolsUI = {
  open: {},
  losH: 10, losT: 1.7, losR: 1000, los: null,
  volBase: 'edge', volLevel: 0, volN: 0, vol: null,
  drSrc: 'path', drClr: 30, drBuf: 15, drStep: 25, drSpeed: 8, drMax: 120, drone: null,
  solGhi: 1900, solEff: 20, solUse: 70, solPr: 0.75, solTar: 7, solar: null, solBusy: false,
  wmsPreset: 'osm', wmsUrl: '', wmsLayers: 'OSM-WMS', wmsOp: 0.6, wmsOn: false, wmsMsg: '',
  mosSel: [], mosName: 'mosaic', mosGrid: 1024, mosMsg: '',
  shEl: 45, shAz: 135, shTime: '', shadow: null, shMsg: '', shBusy: false,
  fixB: 1, fixT: 1, fixFit: null, fixMsg: '', fixOn: true, fixBusy: false,
  errSrc: '', errLev: '0.90', errMsg: '',
  demMsg: '', demDatum: 'egm96',
  gnssDatum: 'ellipsoid', gnssMsg: '',
  ppM2: 10, ppOcc: 80, people: null,
  evWho: 'flood', evMode: 'foot', evac: null,
  dmgBefore: '', dmgCol: 50, dmgDam: 20, dmgDeb: 30, dmg: null, dmgMsg: '',
  slRain: 70, slide: null,
  obsKind: 'auto', obsThr: '', obs: null, obsMsg: '',
  flQ: 40, flRain: 0, flHours: 3, flow: null, flK: 0, flMax: 0, flArr: false, flBusy: false, flSrcN: 0,
  palette: false, rev: 0,
};
export const WMS_OSM = 'https://ows.terrestris.de/osm/service';
export const VKEYS: Record<string, string> = { raster: 'Reference raster', points: 'Surveyed points', icesat2: 'ICESat-2 laser' };
const clampI = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const median = (a: ArrayLike<number>) => { if (!a.length) return NaN; const s = Float64Array.from(a).sort(); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
export const fmtN = (v: number, d = 0) => (+v).toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: d });
export const fmtM3 = (v: number) => v >= 1e6 ? `${(v / 1e6).toFixed(2)} million m³` : `${fmtN(Math.round(v))} m³`;
export const fmtLen = (v: number) => v < 1000 ? `${Math.round(v)} m` : `${(v / 1000).toFixed(2)} km`;
export const fmtHa = (m2: number) => m2 < 1e4 ? `${fmtN(Math.round(m2))} m²` : `${(m2 / 1e4).toFixed(1)} ha`;
export const fmtDur = (s: number) => s < 3600 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1)} h`;
const canvas = (w: number, h: number) => Object.assign(document.createElement('canvas'), { width: w, height: h });
function download(href: string, name: string) { Object.assign(document.createElement('a'), { href, download: name }).click(); }
export function downloadText(text: string, name: string, type = 'text/plain') { download(URL.createObjectURL(new Blob([text], { type })), name); }

export const SLIDE_SLOPE: [number, number][] = [[15, 0.5], [25, 0.8], [35, 1.2], [45, 1.7], [Infinity, 2.0]];
export const SLIDE_LC: (number | null)[] = [2.0, 1.2, 0.8, 0.8, 0.8, null, 0.65, 0.8];   // bare, scrub, developed, road, trees, water, fields, buildings
export const SLIDE_CLS: [number, string, RGB][] = [[2.2, 'low', [46, 160, 67]], [3.2, 'moderate', [255, 214, 10]], [4.2, 'high', [247, 127, 0]], [Infinity, 'very high', [214, 40, 40]]];
const rainFactor = (mm: number) => mm >= 204.5 ? 1.5 : mm >= 115.6 ? 1.3 : mm >= 64.5 ? 1.15 : 1;
export const CAMP_COLORS: RGB[] = [[79, 224, 138], [61, 165, 255], [255, 212, 0], [255, 122, 217], [255, 159, 67]];
const MANNING = [0.03, 0.035, 0.02, 0.016, 0.1, 0.025, 0.035, 0.02];

export class Tools {
  s: ToolsUI = { ...INITIAL };
  private ls = new Set<() => void>();
  T: any = {};                // per-scene working data (grids, canvases)
  private timers: Record<string, any> = {};
  constructor(private e: Engine) {}
  subscribe = (f: () => void) => { this.ls.add(f); return () => this.ls.delete(f); };
  set(p: Partial<ToolsUI>) { this.s = { ...this.s, ...p }; this.ls.forEach(f => f()); }
  private schedule(k: string, f: () => void, ms: number) { clearTimeout(this.timers[k]); this.timers[k] = setTimeout(f, ms); }
  get d() { return this.e.data; }
  isOpen(id: ToolId) { return !!this.s.open[id]; }

  // ---------------- engine extension points ----------------
  sceneLoaded() {
    if (this.T.flow && this.T.flow.sim) this.T.flow.sim.stop = true;
    this.T = { los: { obs: [] }, vol: { pts: [] }, shadow: { meas: [], a: null, auto: null }, flow: { src: [], sim: null }, wms: null };
    const c = this.d.meta.class_scale;
    this.set({ los: null, vol: null, volN: 0, drone: null, solar: null, wmsOn: false, wmsMsg: '', shadow: null, shMsg: '', fixFit: null, fixMsg: '',
      fixB: c ? +c.buildings : 1, fixT: c ? +c.trees : 1, errMsg: '', demMsg: '', gnssMsg: '', evac: null, dmg: null, dmgMsg: '', slide: null,
      obs: null, obsMsg: '', flow: null, flK: 0, flMax: 0, flSrcN: 0, mosMsg: '', mosSel: [this.d.name] });
    for (const id of Object.keys(this.s.open) as ToolId[]) if (this.s.open[id]) this.onOpen(id);
    this.people();
  }
  pageChanged(page: Page) {
    const open = { ...this.s.open };
    let changed = false;
    for (const id of Object.keys(open) as ToolId[]) if (open[id] && TOOL_PAGE[id] !== page) { open[id] = false; changed = true; if (this.d && this.T.los) this.onClose(id); }
    if (changed) this.set({ open });
  }
  heightsChanged() {
    if (!this.d || !this.T.los) return;
    if (this.T.los.obs.length) this.computeLOS();
    if (this.isOpen('vol')) this.computeVolume();
    if (this.isOpen('drone')) this.computeDrone();
    if (this.s.solar) this.computeSolar();
    if (this.isOpen('slide')) this.computeSlide();
    this.people();
  }
  floodChanged() {
    if (!this.d || !this.T.los) return;
    if (this.e.s.flood && this.isOpen('flow')) this.toggle('flow', false);
    this.people();
    if (this.isOpen('obs') && this.T.obs) this.renderObs();
    if (this.s.evac) this.set({ evac: null });
  }
  pathChanged() { if (this.isOpen('drone')) this.computeDrone(); }
  classScale(): { buildings: number; trees: number } | null {
    const c = this.d && this.d.meta.class_scale;
    return c && this.d.lc && this.s.fixOn ? { buildings: +c.buildings || 1, trees: +c.trees || 1 } : null;
  }
  conformal() { return this.d && this.d.meta.conformal; }
  /** the ± part of a read-out: a calibrated error bar once one is chosen for this scene, else the consistency score */
  pm(u: number) {
    const c = this.conformal();
    return c ? `± ${(c.k * (u + c.u0)).toFixed(1)} m (${Math.round(+c.level * 100)}%, calibrated on this scene)` : `consistency ${u.toFixed(1)} m`;
  }
  hint(): string {
    const p = this.e.s.pick as any;
    return p === 'los' ? 'Click places for observers (tower, post, siren) · Done in the panel when finished'
      : p === 'vol' ? `Click the corners of the outline (${this.T.vol ? this.T.vol.pts.length : 0} so far) · Done closes it`
      : p === 'shadow' ? (this.T.shadow && this.T.shadow.a ? 'Now click the far end of the shadow' : 'Click where a building meets its shadow, then the far end of the shadow')
      : p === 'flowsrc' ? 'Click where water comes in (breach, river, drain outlet) · Done when finished' : '';
  }
  pick(u: number, v: number) {
    const p = this.e.s.pick as any;
    if (p === 'los') { this.T.los.obs.push(this.cellOfUV(u, v)); this.computeLOS(); return true; }
    if (p === 'vol') { this.T.vol.pts.push([u, v]); this.set({ volN: this.T.vol.pts.length }); this.computeVolume(); this.e.showHint(); this.redraw(); return true; }
    if (p === 'shadow') { this.shadowClick(u, v); return true; }
    if (p === 'flowsrc') { this.T.flow.src.push([u, v]); this.set({ flSrcN: this.T.flow.src.length }); this.redraw(); return true; }
    return false;
  }
  setPick(p: ToolPick | null) { this.e.setPick(p as any); }
  redraw() { if (!this.d) return; this.e.drawOverlay(); this.e.drawMarks3D(); this.e.refreshSurface(); }

  toggle(id: ToolId, on?: boolean) {
    on = on ?? !this.s.open[id];
    if (!!this.s.open[id] === on) return;
    this.set({ open: { ...this.s.open, [id]: on } });
    if (!this.d) return;
    if (on) this.onOpen(id); else this.onClose(id);
    this.redraw();
  }
  private onOpen(id: ToolId) {
    const s = this.s;
    if (id === 'los') { if (!this.T.los.obs.length) this.setPick('los'); this.computeLOS(); }
    if (id === 'vol') { if (!this.T.vol.pts.length) this.setPick('vol'); this.computeVolume(); }
    if (id === 'drone') this.computeDrone();
    if (id === 'slide') { this.computeSlide(); this.people(); }
    if (id === 'flow') { if (this.e.s.flood) this.e.setFlood(false); if (!this.T.flow.src.length) this.setPick('flowsrc'); }
    if (id === 'evac') { if (!this.e.s.sitesOpen) this.e.setSitesOpen(true); }
    if (id === 'dmg') { const others = this.e.s.scenes.filter((x: any) => x.state === 'done' && x.name !== this.d.name);
      if (!others.some((x: any) => x.name === s.dmgBefore)) this.set({ dmgBefore: (others.find((x: any) => /before|pre/i.test(x.name)) || others[0] || { name: '' }).name }); }
    if (id === 'fix') { const c = this.d.meta.class_scale; this.set({ fixB: c ? +c.buildings : 1, fixT: c ? +c.trees : 1 }); }
    if (id === 'err') this.renderErr();
  }
  private onClose(id: ToolId) {
    const pk = this.e.s.pick as any, owner: Record<string, ToolId> = { los: 'los', vol: 'vol', shadow: 'shadow', flowsrc: 'flow' };
    if (pk && owner[pk] === id) this.setPick(null);
    if (id === 'flow' && this.T.flow.sim) { this.T.flow.sim.stop = true; this.e.water.visible = this.e.s.flood; this.e.updateWater(); }
    if (id === 'slide') { this.set({ slide: null }); this.T.slide = null; this.people(); }
    if (id === 'wms') { /* the overlay stays until hidden */ }
  }

  // ---------------- helpers on the engine's grids ----------------
  get W() { return this.d.meta.grid_w; } get H() { return this.d.meta.grid_h; }
  gridInfo() { const m = this.d.meta, W = m.grid_w, H = m.grid_h; return { m, W, H, N: W * H, dx: m.width * m.gsd / W, dy: m.height * m.gsd / H }; }
  surfaceGrid() { const g = this.e.groundGrid(), s = new Float32Array(g.length); for (let i = 0; i < g.length; i++) s[i] = g[i] + Math.max(0, this.d.grid[i]); return s; }
  cellUV(i: number): [number, number] { const W = this.W, x = i % W; return [(x + 0.5) / W, (Math.floor(i / W) + 0.5) / this.H]; }
  cellOfUV(u: number, v: number) { return clampI(Math.floor(v * this.H), 0, this.H - 1) * this.W + clampI(Math.floor(u * this.W), 0, this.W - 1); }
  lonlatAt(u: number, v: number): [number, number] | null {
    const c = this.d.meta.corners_lonlat;
    if (!c) return null;
    const [tl, tr, br, bl] = c, top = [tl[0] + (tr[0] - tl[0]) * u, tl[1] + (tr[1] - tl[1]) * u], bot = [bl[0] + (br[0] - bl[0]) * u, bl[1] + (br[1] - bl[1]) * u];
    return [top[0] + (bot[0] - top[0]) * v, top[1] + (bot[1] - top[1]) * v];
  }
  blockCells(): number[][] {
    if (this.d._bc) return this.d._bc;
    const bc: number[][] = this.d._bc = Array.from({ length: this.d.buildings.length + 1 }, () => []);
    for (let i = 0; i < this.d.bid.length; i++) if (this.d.bid[i] > 0) bc[this.d.bid[i]].push(i);
    return bc;
  }
  blockRims(): number[][] {
    if (this.d._rim) return this.d._rim;
    const W = this.W, H = this.H, bc = this.blockCells(), bid = this.d.bid;
    return this.d._rim = bc.map((cells, id) => {
      const s = new Set<number>();
      for (const i of cells) { const x = i % W, y = (i - x) / W;
        for (let k = 0; k < 4; k++) { const nx = x + NX[k], ny = y + NY[k]; if (nx >= 0 && ny >= 0 && nx < W && ny < H && bid[ny * W + nx] !== id) s.add(ny * W + nx); } }
      return [...s];
    });
  }
  residents(b: any) { return b.area_m2 * (b.floors || 1) * clampI(this.s.ppOcc, 0, 100) / 100 / Math.max(1, this.s.ppM2); }

  // ---------------- 2D overlay, 3D texture and marks ----------------
  rasterLayers(): HTMLCanvasElement[] {
    if (!this.d || !this.T.los) return [];
    const L: any[] = [];
    for (const [id, k] of [['slide', 'slide'], ['dmg', 'dmg'], ['flow', 'flow'], ['obs', 'obs'], ['los', 'los'], ['solar', 'solar'], ['evac', 'evac']] as [ToolId, string][])
      if (this.isOpen(id) && this.T[k] && this.T[k].cv) L.push(this.T[k].cv);
    return L;
  }
  rasters(ctx: CanvasRenderingContext2D, c: HTMLCanvasElement) {
    if (this.T.wms && this.s.wmsOn) { ctx.globalAlpha = this.s.wmsOp; ctx.drawImage(this.T.wms, 0, 0, c.width, c.height); ctx.globalAlpha = 1; }
    for (const cv of this.rasterLayers() as any[]) { ctx.imageSmoothingEnabled = !!cv.smooth; ctx.drawImage(cv, 0, 0, c.width, c.height); }
    ctx.imageSmoothingEnabled = true;
  }
  compose(base: any) {
    if (!this.d || !this.T.los || !base) return base;
    const L = this.rasterLayers() as any[], wms = this.s.wmsOn && this.T.wms;
    if (!L.length && !wms) return base;
    const w = base.naturalWidth || base.width, h = base.naturalHeight || base.height;
    const cv = this.T.texCv && this.T.texCv.width === w && this.T.texCv.height === h ? this.T.texCv : (this.T.texCv = canvas(w, h));
    const c = cv.getContext('2d')!;
    c.globalAlpha = 1; c.drawImage(base, 0, 0, w, h);
    if (wms) { c.globalAlpha = this.s.wmsOp; c.drawImage(this.T.wms, 0, 0, w, h); }
    for (const l of L) { c.imageSmoothingEnabled = !!l.smooth; c.globalAlpha = 0.85; c.drawImage(l, 0, 0, w, h); }
    c.globalAlpha = 1; c.imageSmoothingEnabled = true;
    return cv;
  }
  overlay(ctx: CanvasRenderingContext2D, c: HTMLCanvasElement) {
    if (!this.d || !this.T.los) return;
    const P = (u: number, v: number): [number, number] => [u * c.width, v * c.height], e = this.e;
    const line = (pts: [number, number][], w: number, col: string, close = false, dash: number[] = []) => {
      if (pts.length < 2) return;
      ctx.beginPath(); pts.forEach(([x, y], k) => k ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); if (close) ctx.closePath();
      ctx.setLineDash(dash); ctx.lineJoin = ctx.lineCap = 'round';
      ctx.lineWidth = w + 3; ctx.strokeStyle = 'rgba(0,0,0,.55)'; ctx.stroke(); ctx.lineWidth = w; ctx.strokeStyle = col; ctx.stroke(); ctx.setLineDash([]);
    };
    const dot = (x: number, y: number, r: number, col: string, txt = '') => {
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fillStyle = col; ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = '#fff'; ctx.stroke();
      if (txt) { ctx.fillStyle = '#111'; ctx.font = `bold ${Math.round(r * 1.1)}px "Manrope Variable", sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(txt, x, y + 0.5); }
    };
    if (e.nav.path.length) line(e.nav.path.map((p: THREE.Vector2) => P(...e.uvOf(p.x, p.y))), 3, '#ffb020', false, [10, 6]);
    if (e.nav.drawing) e.nav.path.forEach((p: THREE.Vector2) => dot(...P(...e.uvOf(p.x, p.y)), 6, '#ffb020'));
    if (this.isOpen('drone') && this.T.drone) this.T.drone.wps.forEach((w: any, k: number) => dot(...P(w.u, w.v), 7, w.agl > this.T.drone.lim ? '#e5484d' : '#ffb020', k === 0 ? 'H' : ''));
    if (this.isOpen('los')) this.T.los.obs.forEach((i: number) => dot(...P(...this.cellUV(i)), 12, '#4fe08a', 'O'));
    if (this.isOpen('vol') && this.T.vol.pts.length) {
      const pts = this.T.vol.pts.map(([u, v]: number[]) => P(u, v)), closed = e.s.pick !== ('vol' as any);
      if (pts.length > 2 && closed) { ctx.beginPath(); pts.forEach(([x, y]: number[], k: number) => k ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath(); ctx.fillStyle = 'rgba(255,176,32,.2)'; ctx.fill(); }
      line(pts, 3, '#ffb020', closed); pts.forEach(([x, y]: number[]) => dot(x, y, 5, '#ffb020'));
    }
    if (this.isOpen('shadow')) {
      for (const m of this.T.shadow.meas) { const a = P(...m.a as [number, number]), b = P(...m.b as [number, number]); line([a, b], 3, '#ff7ad9'); dot(...a, 5, '#ff7ad9'); dot(...b, 5, '#fff'); }
      if (this.T.shadow.a) dot(...P(...this.T.shadow.a as [number, number]), 6, '#ff7ad9');
      for (const s of this.T.shadow.auto || []) { const b = this.d.buildings[s.id - 1]; if (!b) continue; const [x, y] = P(b.cx, b.cy);
        ctx.font = 'bold 15px "Manrope Variable", sans-serif'; ctx.textAlign = 'center'; ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(0,0,0,.75)';
        const t = `${s.H.toFixed(0)} m`; ctx.strokeText(t, x, y); ctx.fillStyle = '#ff7ad9'; ctx.fillText(t, x, y); }
    }
    if (this.isOpen('flow')) this.T.flow.src.forEach(([u, v]: number[]) => dot(...P(u, v), 11, '#2f7fe0', '≈'));
  }
  marks3D(at: (x: number, z: number) => number, r: number, k: number) {
    if (!this.d || !this.T.los) return;
    const e = this.e, add = (o: THREE.Object3D) => e.marks.add(o), xz = (u: number, v: number): [number, number] => [(u - 0.5) * e.sceneW(), (v - 0.5) * e.sceneH()];
    const ball = (x: number, z: number, y: number, color: number, s = 1) => { const b = new THREE.Mesh(new THREE.SphereGeometry(r * s, 16, 12), new THREE.MeshBasicMaterial({ color })); b.position.set(x, y, z); add(b); };
    if (this.isOpen('los')) for (const i of this.T.los.obs) { const [x, z] = xz(...this.cellUV(i)); ball(x, z, at(x, z) + this.s.losH * k, 0x4fe08a, 1.2); }
    if (this.isOpen('flow')) for (const [u, v] of this.T.flow.src) { const [x, z] = xz(u, v); ball(x, z, at(x, z) + r, 0x2f7fe0); }
    if (this.isOpen('drone') && this.T.drone && this.T.drone.wps.length > 1) {
      const pts = this.T.drone.wps.map((w: any) => { const [x, z] = xz(w.u, w.v); return new THREE.Vector3(x, (w.alt - this.d.gmin) * k, z); });
      add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xffb020 })));
      this.T.drone.wps.forEach((w: any, j: number) => ball(pts[j].x, pts[j].z, pts[j].y, w.agl > this.T.drone.lim ? 0xe5484d : 0xffb020, 0.6));
    }
    if (this.isOpen('vol') && this.T.vol.pts.length > 1) {
      const pts = this.T.vol.pts.map(([u, v]: number[]) => { const [x, z] = xz(u, v); return new THREE.Vector3(x, at(x, z) + r * 0.5, z); });
      if (e.s.pick !== ('vol' as any)) pts.push(pts[0].clone());
      add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xffb020 })));
    }
  }
  pointLines(u: number, v: number): string[] {
    if (!this.d || !this.T.los) return [];
    const i = this.cellOfUV(u, v), out: string[] = [];
    if (this.isOpen('los') && this.T.los.vis) out.push(['out of range', 'hidden from the observers', 'visible from an observer'][this.T.los.vis[i]]);
    if (this.isOpen('slide') && this.T.slide) { const c = this.T.slide.cls[i]; if (c >= 0) out.push(`landslide risk: ${SLIDE_CLS[c][1]} (score ${this.T.slide.score[i].toFixed(1)})`); }
    if (this.isOpen('dmg') && this.T.dmg) {
      const bb = this.T.dmg.bidb[i], rb = bb > 0 && this.T.dmg.byId.get(bb);
      if (rb) out.push(`before ${rb.before_m.toFixed(1)} m → after ${rb.after_m.toFixed(1)} m (${this.T.dmg.cls.get(bb)})`);
      else if (Number.isFinite(this.T.dmg.dh[i]) && Math.abs(this.T.dmg.dh[i]) >= 1) out.push(`height change ${this.T.dmg.dh[i] > 0 ? '+' : ''}${this.T.dmg.dh[i].toFixed(1)} m`);
    }
    if (this.isOpen('flow') && this.T.flow.sim) { const d = this.flowDepthAt(u, v), a = this.flowArrivalAt(u, v);
      out.push(`flowing water: ${d > 0.05 ? d.toFixed(2) + ' m deep' : 'dry'} at ${this.flowClock(this.s.flK)}${a < Infinity ? ` · wet after ${fmtDur(a)}` : ''}`); }
    if (this.isOpen('obs') && this.T.obs) { const o = this.T.obs.grid[i]; if (Number.isFinite(o)) out.push(`satellite: ${o > 0.5 ? 'water' : 'dry'}`); }
    return out;
  }
  buildingLines(b: any): string[] {
    if (!this.d || !this.T.los) return [];
    const out: string[] = [], p = this.e.s.page;
    if (p === 'prepare' || p === 'respond' || p === 'relief' || p === 'assess') out.push(`~${fmtN(Math.round(this.residents(b)))} residents (estimate)`);
    if (this.isOpen('evac') && this.T.evac) { const a = this.T.evac.who.get(b.id);
      if (a) out.push(a.camp != null ? `evacuate to C${a.camp + 1}, ≈ ${Math.round(a.min)} min` : a.full ? 'no camp space left' : 'no dry route: needs boat or air rescue'); }
    if (this.isOpen('solar') && this.T.solar) { const r = this.T.solar.byId.get(b.id); if (r) out.push(`solar ≈ ${fmtN(r.kWh / 1000, 1)} MWh/yr · ${r.kWp.toFixed(1)} kWp · ${Math.round(r.shade * 100)}% shaded`); }
    return out;
  }

  // ======================================== EXPLORE ========================================
  // ----- line of sight: rays from each observer to the edge of its range, running maximum of the surface's elevation angle
  computeLOS() {
    if (!this.d) return;
    const L = this.T.los;
    if (!L.obs.length) { L.vis = L.cv = null; this.set({ los: { n: 0 } }); return this.redraw(); }
    const { W, H, N, dx, dy } = this.gridInfo(), Z = this.surfaceGrid(), s = this.s;
    const hO = Math.max(0, s.losH), hT = Math.max(0, s.losT), R = Math.max(10, s.losR), vis = new Uint8Array(N);
    for (const o of L.obs) {
      const ox = o % W, oy = (o - ox) / W, zo = Z[o] + hO, rx = Math.ceil(R / dx), ry = Math.ceil(R / dy);
      const x0 = Math.max(0, ox - rx), x1 = Math.min(W - 1, ox + rx), y0 = Math.max(0, oy - ry), y1 = Math.min(H - 1, oy + ry);
      for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (!vis[y * W + x] && Math.hypot((x - ox) * dx, (y - oy) * dy) <= R) vis[y * W + x] = 1;
      vis[o] = 2;
      const ray = (tx: number, ty: number) => {
        const n = Math.max(Math.abs(tx - ox), Math.abs(ty - oy));
        let maxS = -Infinity;
        for (let k = 1; k <= n; k++) {
          const x = Math.round(ox + (tx - ox) * k / n), y = Math.round(oy + (ty - oy) * k / n), i = y * W + x, dd = Math.hypot((x - ox) * dx, (y - oy) * dy);
          if (dd > R) break;
          if ((Z[i] + hT - zo) / dd >= maxS) vis[i] = 2;
          const gs = (Z[i] - zo) / dd; if (gs > maxS) maxS = gs;
        }
      };
      for (let x = x0; x <= x1; x++) { ray(x, y0); ray(x, y1); }
      for (let y = y0; y <= y1; y++) { ray(x0, y); ray(x1, y); }
    }
    const cv = canvas(W, H), ctx = cv.getContext('2d')!, img = ctx.createImageData(W, H);
    let inR = 0, seen = 0, far = 0;
    const seenB = new Set<number>(), inB = new Set<number>(), o0 = L.obs[0], ox = o0 % W, oy = (o0 - ox) / W, bid = this.d.bid;
    for (let i = 0; i < N; i++) {
      if (!vis[i]) continue;
      inR++; if (bid[i] > 0) inB.add(bid[i]);
      if (vis[i] === 2) { seen++; if (bid[i] > 0) seenB.add(bid[i]); const x = i % W; far = Math.max(far, Math.hypot((x - ox) * dx, ((i - x) / W - oy) * dy)); img.data.set([79, 224, 138, 120], i * 4); }
      else img.data.set([10, 12, 20, 165], i * 4);
    }
    ctx.putImageData(img, 0, 0);
    Object.assign(L, { vis, cv });
    this.set({ los: { n: L.obs.length, inR, seen, far, seenB: seenB.size, inB: inB.size, cell: dx * dy } });
    this.redraw();
  }
  setLosParam(p: Partial<ToolsUI>) { this.set(p); this.schedule('los', () => this.computeLOS(), 200); }
  clearLOS() { this.T.los.obs = []; this.computeLOS(); this.setPick('los'); }

  // ----- volume & area inside a drawn outline
  computeVolume() {
    const P: number[][] = this.T.vol.pts, how = this.s.volBase;
    if (P.length < 3) return this.set({ vol: null });
    const { W, H, dx, dy } = this.gridInfo(), A = dx * dy, S = this.surfaceGrid(), g = this.e.groundGrid(), e = this.e;
    const xs = P.map(p => p[0] * W), ys = P.map(p => p[1] * H);
    const inside = (px: number, py: number) => { let c = false; for (let a = 0, b = P.length - 1; a < P.length; b = a++)
      if ((ys[a] > py) !== (ys[b] > py) && px < (xs[b] - xs[a]) * (py - ys[a]) / (ys[b] - ys[a]) + xs[a]) c = !c; return c; };
    const edge: number[] = [];
    let perim = 0;
    for (let a = 0; a < P.length; a++) {
      const b = (a + 1) % P.length, len = Math.hypot((P[b][0] - P[a][0]) * e.sceneW(), (P[b][1] - P[a][1]) * e.sceneH()), n = Math.max(2, Math.ceil(len / Math.min(dx, dy)));
      perim += len;
      for (let k = 0; k < n; k++) edge.push(S[this.cellOfUV(P[a][0] + (P[b][0] - P[a][0]) * k / n, P[a][1] + (P[b][1] - P[a][1]) * k / n)]);
    }
    const base = how === 'edge' ? median(edge) : how === 'level' ? this.s.volLevel : null;
    let n = 0, above = 0, below = 0, top = -Infinity;
    const x0 = Math.max(0, Math.floor(Math.min(...xs))), x1 = Math.min(W - 1, Math.ceil(Math.max(...xs))), y0 = Math.max(0, Math.floor(Math.min(...ys))), y1 = Math.min(H - 1, Math.ceil(Math.max(...ys)));
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
      if (!inside(x + 0.5, y + 0.5)) continue;
      const i = y * W + x, dd = S[i] - (base ?? g[i]);
      n++; if (dd > 0) above += dd * A; else below -= dd * A; top = Math.max(top, dd);
    }
    this.set({ vol: { n, area: n * A, perim, above, below, base, top, how, cell: Math.sqrt(A) } });
  }
  toggleVolDraw() {
    if ((this.e.s.pick as any) === 'vol') this.setPick(null);
    else { if (this.T.vol.pts.length > 2) this.T.vol.pts = []; this.set({ volN: this.T.vol.pts.length }); this.setPick('vol'); }
    this.computeVolume(); this.redraw();
  }
  clearVolume() { this.T.vol.pts = []; this.set({ volN: 0 }); this.setPick('vol'); this.computeVolume(); this.redraw(); }

  // ----- drone flight plan
  dronePolyline(): [number, number][] {
    if (this.s.drSrc === 'route') { const r = this.d.route.res; return r ? this.e.routeCells(r.path, 1) : []; }
    return this.e.nav.path.map((p: THREE.Vector2) => [p.x, p.y]);
  }
  computeDrone() {
    if (!this.d) return;
    const line = this.dronePolyline();
    if (line.length < 2) { this.T.drone = null; this.set({ drone: null }); return this.redraw(); }
    const { W, H, dx, dy } = this.gridInfo(), S = this.surfaceGrid(), g = this.e.groundGrid(), s = this.s;
    const clr = Math.max(0, s.drClr), buf = Math.max(0, s.drBuf), step = Math.max(5, s.drStep), speed = Math.max(1, s.drSpeed), lim = s.drMax || 120;
    const pts: [number, number][] = [line[0]];
    let len = 0, carry = 0;
    for (let k = 1; k < line.length; k++) {
      const [ax, az] = line[k - 1], [bx, bz] = line[k], seg = Math.hypot(bx - ax, bz - az);
      let t = step - carry;
      while (t < seg) { pts.push([ax + (bx - ax) * t / seg, az + (bz - az) * t / seg]); t += step; }
      carry = seg - (t - step); len += seg;
    }
    pts.push(line[line.length - 1]);
    const rx = Math.ceil(buf / dx), ry = Math.ceil(buf / dy);
    const wps = pts.map(([x, z]) => {
      const [u, v] = this.e.uvOf(x, z), cx = clampI(Math.floor(u * W), 0, W - 1), cy = clampI(Math.floor(v * H), 0, H - 1);
      let top = S[cy * W + cx];
      for (let yy = Math.max(0, cy - ry); yy <= Math.min(H - 1, cy + ry); yy++) for (let xx = Math.max(0, cx - rx); xx <= Math.min(W - 1, cx + rx); xx++)
        if (Math.hypot((xx - cx) * dx, (yy - cy) * dy) <= buf) top = Math.max(top, S[yy * W + xx]);
      const ground = g[cy * W + cx], alt = top + clr;
      return { x, z, u, v, top, ground, alt, agl: alt - ground, rel: 0, ll: this.lonlatAt(u, v) };
    });
    const home = wps[0].ground;
    for (const w of wps) w.rel = w.alt - home;
    const D = this.T.drone = { wps, len, time: len / speed, speed, lim, home, maxAgl: Math.max(...wps.map(w => w.agl)), maxRel: Math.max(...wps.map(w => w.rel)), over: wps.filter(w => w.agl > lim).length };
    this.set({ drone: { n: wps.length, len: D.len, time: D.time, speed, lim, home, maxAgl: D.maxAgl, maxRel: D.maxRel, over: D.over, geo: !!this.d.meta.corners_lonlat, abs: !!this.d.dtm } });
    this.redraw();
  }
  setDroneParam(p: Partial<ToolsUI>) { this.set(p); this.computeDrone(); }
  droneKML() {
    const D = this.T.drone, abs = !!this.d.dtm, mode = abs ? 'absolute' : 'relativeToGround', c = (w: any) => `${w.ll[0].toFixed(7)},${w.ll[1].toFixed(7)},${(abs ? w.alt : w.agl).toFixed(1)}`;
    return `<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${this.d.name} drone plan (DepthWizard)</name>
<Style id="p"><LineStyle><color>ff20b0ff</color><width>3</width></LineStyle></Style>
<Placemark><name>Flight path</name><styleUrl>#p</styleUrl><LineString><altitudeMode>${mode}</altitudeMode><coordinates>${D.wps.map(c).join(' ')}</coordinates></LineString></Placemark>
${D.wps.map((w: any, k: number) => `<Placemark><name>WP${k + 1}</name><description>${w.agl.toFixed(0)} m above ground</description><Point><altitudeMode>${mode}</altitudeMode><coordinates>${c(w)}</coordinates></Point></Placemark>`).join('\n')}
</Document></kml>`;
  }
  dronePlan() {   // QGroundControl: take-off, waypoints (altitude above the take-off point), return to launch
    const D = this.T.drone, it = (k: number, cmd: number, p: any[], alt: number) => ({ type: 'SimpleItem', autoContinue: true, command: cmd, doJumpId: k, frame: 3, params: p, Altitude: alt, AltitudeMode: 1, AMSLAltAboveTerrain: null });
    const w0 = D.wps[0], items = [it(1, 22, [0, 0, 0, null, w0.ll[1], w0.ll[0], +w0.rel.toFixed(1)], +w0.rel.toFixed(1))];
    D.wps.forEach((w: any, k: number) => items.push(it(k + 2, 16, [0, 0, 0, null, w.ll[1], w.ll[0], +w.rel.toFixed(1)], +w.rel.toFixed(1))));
    items.push(it(D.wps.length + 2, 20, [0, 0, 0, 0, 0, 0, 0], 0));
    return JSON.stringify({ fileType: 'Plan', version: 1, groundStation: 'QGroundControl', geoFence: { circles: [], polygons: [], version: 2 }, rallyPoints: { points: [], version: 2 },
      mission: { version: 2, firmwareType: 12, vehicleType: 2, cruiseSpeed: D.speed, hoverSpeed: D.speed, globalPlanAltitudeMode: 1, plannedHomePosition: [w0.ll[1], w0.ll[0], +D.home.toFixed(1)], items } }, null, 1);
  }
  droneCSV() {
    return 'wp,lat,lon,alt_m_above_sea_level,alt_m_above_takeoff,alt_m_above_ground,x_m,y_m\n' + this.T.drone.wps.map((w: any, k: number) =>
      [k + 1, w.ll ? w.ll[1].toFixed(7) : '', w.ll ? w.ll[0].toFixed(7) : '', this.d.dtm ? w.alt.toFixed(1) : '', w.rel.toFixed(1), w.agl.toFixed(1), w.x.toFixed(1), (-w.z).toFixed(1)].join(',')).join('\n');
  }
  exportDrone(fmt: 'kml' | 'plan' | 'csv') {
    if (!this.T.drone) return;
    if (fmt === 'kml') downloadText(this.droneKML(), `${this.d.name}_drone.kml`, 'application/vnd.google-earth.kml+xml');
    if (fmt === 'plan') downloadText(this.dronePlan(), `${this.d.name}_drone.plan`, 'application/json');
    if (fmt === 'csv') downloadText(this.droneCSV(), `${this.d.name}_drone.csv`, 'text/csv');
  }

  // ----- rooftop solar: yearly yield per roof, shading traced along the sun's path (21st of each month, hourly)
  static sunPath(lat: number) {
    const out: { el: number; az: number; w: number }[] = [], rad = Math.PI / 180, phi = lat * rad;
    for (let mth = 0; mth < 12; mth++) {
      const n = 21 + Math.round(30.42 * mth), dec = 23.44 * rad * Math.sin(2 * Math.PI * (284 + n) / 365);
      for (let hr = 5.5; hr <= 18.5; hr += 1) {
        const ha = 15 * (hr - 12) * rad, se = Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(ha), el = Math.asin(se);
        if (el < 5 * rad) continue;
        const az = Math.atan2(-Math.sin(ha), Math.tan(dec) * Math.cos(phi) - Math.sin(phi) * Math.cos(ha));
        out.push({ el, az: (az + 2 * Math.PI) % (2 * Math.PI), w: se });
      }
    }
    return out;
  }
  static sunPos(date: Date, lat: number, lon: number) {   // sun elevation / azimuth (degrees, azimuth clockwise from north) at a UTC time
    const rad = Math.PI / 180, d = date.getTime() / 864e5 - 10957.5;
    const g = (357.529 + 0.98560028 * d) * rad, q = 280.459 + 0.98564736 * d;
    const L = (q + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * rad, ee = (23.439 - 3.6e-7 * d) * rad;
    const ra = Math.atan2(Math.cos(ee) * Math.sin(L), Math.cos(L)), dec = Math.asin(Math.sin(ee) * Math.sin(L));
    const gmst = ((18.697374558 + 24.06570982441908 * d) % 24 + 24) % 24, ha = (gmst * 15 + lon) * rad - ra, la = lat * rad;
    const el = Math.asin(Math.sin(la) * Math.sin(dec) + Math.cos(la) * Math.cos(dec) * Math.cos(ha));
    const az = Math.atan2(-Math.sin(ha), Math.tan(dec) * Math.cos(la) - Math.sin(la) * Math.cos(ha));
    return { el: el / rad, az: ((az / rad) % 360 + 360) % 360 };
  }
  computeSolar() {
    const { W, H, dx, dy } = this.gridInfo(), S = this.surfaceGrid(), cells = this.blockCells(), ll = this.lonlatAt(0.5, 0.5), lat = ll ? ll[1] : 23, s = this.s, bid = this.d.bid;
    const sun = Tools.sunPath(lat), zmax = S.reduce((a, v) => Math.max(a, v), -Infinity), step = Math.min(dx, dy);
    const ghi = s.solGhi || 1900, eff = (s.solEff || 20) / 100, use = (s.solUse || 70) / 100, pr = s.solPr || 0.75;
    const ns = this.d.buildings.length > 300 ? 3 : 6, res: any[] = [];
    for (const b of this.d.buildings) {
      const c = cells[b.id];
      if (!c || !c.length) continue;
      let tw = 0, bw = 0;
      for (let j = 0; j < ns; j++) {
        const s0 = c[Math.floor((j + 0.5) * c.length / ns)], x0 = s0 % W, y0 = (s0 - x0) / W, z0 = S[s0] + 0.3;
        for (const p of sun) {
          const tanE = Math.tan(p.el), maxT = Math.min(300, (zmax - z0) / tanE), sx = Math.sin(p.az) / dx, sy = -Math.cos(p.az) / dy;
          let blk = false;
          for (let t = step; t <= maxT; t += step) {
            const xi = Math.round(x0 + sx * t), yi = Math.round(y0 + sy * t);
            if (xi < 0 || yi < 0 || xi >= W || yi >= H) break;
            const q = yi * W + xi;
            if (bid[q] === b.id) continue;
            if (S[q] > z0 + t * tanE) { blk = true; break; }
          }
          tw += p.w; if (blk) bw += p.w;
        }
      }
      const shade = tw ? bw / tw : 0, panel = b.area_m2 * use;
      res.push({ id: b.id, area: b.area_m2, shade, kWp: panel * eff, kWh: panel * ghi * eff * pr * (1 - 0.85 * shade) });   // ~15 % diffuse light under shade
    }
    const cv = canvas(W, H), ctx = cv.getContext('2d')!, img = ctx.createImageData(W, H);
    const spec = (r: any) => r.kWh / r.area, smax = Math.max(1e-6, ...res.map(spec));
    for (const r of res) { const col = inferno(0.25 + 0.75 * spec(r) / smax); for (const i of cells[r.id]) img.data.set([...col, 225], i * 4); }
    ctx.putImageData(img, 0, 0);
    this.T.solar = { res, byId: new Map(res.map(r => [r.id, r])), cv };
    const sum = (k: string) => res.reduce((a, r) => a + r[k], 0), mwh = sum('kWh') / 1000;
    this.set({ solBusy: false, solar: { n: res.length, kWp: sum('kWp'), mwh, rupees: mwh * 1000 * (s.solTar || 0), co2: mwh * 0.72, low: res.filter(r => r.shade < 0.2).length,
      top: [...res].sort((a, b) => b.kWh - a.kWh).slice(0, 5), lat, latKnown: !!ll, nSun: sun.length, smax } });
    this.redraw();
  }
  runSolar() { this.set({ solBusy: true }); setTimeout(() => this.computeSolar(), 30); }
  setSolarParam(p: Partial<ToolsUI>) { this.set(p); if (this.s.solar) this.schedule('sol', () => this.computeSolar(), 300); }
  solarCSV() { if (this.T.solar) downloadText('block,roof_m2,shaded_pct,kWp,kWh_per_year\n' + this.T.solar.res.map((r: any) => [r.id, Math.round(r.area), Math.round(r.shade * 100), r.kWp.toFixed(1), Math.round(r.kWh)].join(',')).join('\n'), `${this.d.name}_solar.csv`, 'text/csv'); }

  // ----- WMS map overlay (fetched and warped by the server, saved with the scene)
  async loadWms() {
    const name = this.d.name, url = this.s.wmsPreset === 'osm' ? WMS_OSM : this.s.wmsUrl.trim();
    this.set({ wmsMsg: 'Fetching the map…' });
    try {
      const r = await fetch(`/api/wms?name=${encodeURIComponent(name)}`, { method: 'POST', body: JSON.stringify({ url, layers: this.s.wmsLayers.trim() }) }), j = await r.json();
      if (!r.ok) throw new Error(j.error);
      if (this.d.name !== name) return;
      this.d.meta.wms = j; await this.showWms(j.url);
      this.set({ wmsMsg: `Showing ${j.layers} on the 2D map and the 3D surface.` });
    } catch (err: any) { this.set({ wmsMsg: `⚠ ${err.message}` }); }
  }
  async showWms(url?: string) {
    const img = new Image(); img.src = `${url || this.d.meta.wms.url}?t=${Date.now()}`;
    await img.decode();
    this.T.wms = img; this.set({ wmsOn: true }); this.redraw();
  }
  hideWms() { this.set({ wmsOn: false }); this.redraw(); }
  setWmsOpacity(wmsOp: number) { this.set({ wmsOp }); this.e.drawOverlay(); this.schedule('wms', () => this.e.refreshSurface(), 150); }

  // ----- mosaic
  async buildMosaic() {
    if (this.s.mosSel.length < 2) return this.set({ mosMsg: '⚠ Tick at least two neighbouring scenes.' });
    const r = await fetch('/api/mosaic', { method: 'POST', body: JSON.stringify({ names: this.s.mosSel, name: this.s.mosName, grid: this.s.mosGrid }) }), j = await r.json();
    this.set({ mosMsg: r.ok ? `Building ${j.name}… it appears in the scene list (top) when ready.` : `⚠ ${j.error}` });
  }

  // ======================================== VALIDATE ========================================
  // ----- building heights from shadows
  sunDir() { const az = this.s.shAz * Math.PI / 180; return { ex: -Math.sin(az), ny: -Math.cos(az) }; }   // where shadows fall (east, north)
  nearBuilding(u: number, v: number, r = 3) {
    const W = this.W, H = this.H, x0 = Math.floor(u * W), y0 = Math.floor(v * H);
    let best = 0, bd = Infinity;
    for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) {
      const x = x0 + dx, y = y0 + dy;
      if (x < 0 || y < 0 || x >= W || y >= H) continue;
      const id = this.d.bid[y * W + x];
      if (id > 0 && dx * dx + dy * dy < bd) { bd = dx * dx + dy * dy; best = id; }
    }
    return best ? this.d.buildings[best - 1] : null;
  }
  modelBlockHeight(b: any) { return b.height_m / (this.d.hscale || 1) / ((this.classScale() || { buildings: 1 }).buildings); }
  shadowClick(u: number, v: number) {
    const S = this.T.shadow;
    if (!S.a) { S.a = [u, v]; this.e.showHint(); return this.e.drawOverlay(); }
    const a = S.a, ex = (u - a[0]) * this.e.sceneW(), ny = -(v - a[1]) * this.e.sceneH(), d = this.sunDir();
    let L = ex * d.ex + ny * d.ny;
    if (L <= 0) L = Math.hypot(ex, ny);
    const b = this.nearBuilding(a[0], a[1]);
    S.meas.push({ a, b: [u, v], L, H: L * Math.tan(this.s.shEl * Math.PI / 180), id: b ? b.id : null });
    S.a = null;
    this.renderShadow(); this.e.drawOverlay(); this.e.showHint();
  }
  photoLum() {
    if (this.T.lum) return this.T.lum;
    const p = this.d.photo, k = Math.min(1, 2048 / Math.max(p.naturalWidth, p.naturalHeight)), w = Math.round(p.naturalWidth * k), h = Math.round(p.naturalHeight * k);
    const c = canvas(w, h).getContext('2d', { willReadFrequently: true })!;
    c.drawImage(p, 0, 0, w, h);
    const dd = c.getImageData(0, 0, w, h).data, lum = new Float32Array(w * h);
    for (let i = 0; i < w * h; i++) lum[i] = 0.299 * dd[4 * i] + 0.587 * dd[4 * i + 1] + 0.114 * dd[4 * i + 2];
    return this.T.lum = { lum, w, h, px: this.d.meta.width * this.d.meta.gsd / w };
  }
  static otsu(v: ArrayLike<number>) {
    const hist = new Float64Array(256);
    for (let i = 0; i < v.length; i += 3) hist[Math.min(255, Math.max(0, Math.round(v[i])))]++;
    let tot = 0, sum = 0; for (let k = 0; k < 256; k++) { tot += hist[k]; sum += k * hist[k]; }
    let w0 = 0, s0 = 0, best = 0, th = 128;
    for (let k = 0; k < 256; k++) { w0 += hist[k]; s0 += k * hist[k]; if (!w0 || w0 === tot) continue;
      const m0 = s0 / w0, m1 = (sum - s0) / (tot - w0), b = w0 * (tot - w0) * (m0 - m1) ** 2; if (b > best) { best = b; th = k; } }
    return th;
  }
  autoShadows() {   // for every block: walk from its shadow-side edge across the dark shadow pixels of the photo
    const { lum, w, h, px } = this.photoLum(), W = this.W, H = this.H, dd = this.sunDir(), sx = dd.ex, sy = -dd.ny, nrm = Math.hypot(sx, sy) || 1, bid = this.d.bid;
    const ux = sx / nrm, uy = sy / nrm, tanE = Math.tan(this.s.shEl * Math.PI / 180), sample: number[] = [];
    for (let i = 0; i < lum.length; i += 7) sample.push(lum[i]);
    const thr = Math.min(Tools.otsu(lum), 0.6 * median(sample));
    const bidAt = (X: number, Y: number) => bid[Math.min(H - 1, Math.floor(Y * H / h)) * W + Math.min(W - 1, Math.floor(X * W / w))];
    const out: any[] = [], cells = this.blockCells();
    for (const b of this.d.buildings) {
      const runs: number[] = [];
      for (const i of cells[b.id]) {
        const x = i % W, y = (i - x) / W, nx = Math.round(x + ux * 1.5), ny = Math.round(y + uy * 1.5);
        if (nx >= 0 && ny >= 0 && nx < W && ny < H && bid[ny * W + nx] === b.id) continue;
        const X = (x + 0.5) * w / W, Y = (y + 0.5) * h / H;
        let t = 0;
        while (t < 3 * w / W && bidAt(X + ux * t, Y + uy * t) === b.id) t++;
        let run = 0, gap = 0, lead = 0, trunc = false;
        for (; ; t++) {
          const X2 = X + ux * t, Y2 = Y + uy * t;
          if (X2 < 0 || Y2 < 0 || X2 >= w || Y2 >= h) { trunc = true; break; }
          const id = bidAt(X2, Y2);
          if (id > 0 && id !== b.id) { trunc = true; break; }
          if (lum[Math.floor(Y2) * w + Math.floor(X2)] < thr) { run += gap + 1; gap = 0; }
          else if (!run) { if (++lead > 3) break; }
          else if (++gap > 2) break;
        }
        if (!trunc && run >= 2) runs.push(run * px);
      }
      if (runs.length >= 3) { const L = median(runs); out.push({ id: b.id, L, H: L * tanE, n: runs.length }); }
    }
    return out;
  }
  shadowRatio() {
    const by = new Map<number, number>();
    for (const s of this.T.shadow.auto || []) by.set(s.id, s.H);
    for (const m of this.T.shadow.meas) if (m.id) by.set(m.id, m.H);
    const r: number[] = [];
    for (const [id, Hs] of by) { const mh = this.modelBlockHeight(this.d.buildings[id - 1]); if (Hs >= 5 && mh >= 2) r.push(Hs / mh); }
    return r.length ? { k: median(r), n: r.length } : null;
  }
  renderShadow() {
    const S = this.T.shadow, rows: any[] = [];
    for (const m of S.meas) { const b = m.id && this.d.buildings[m.id - 1]; rows.push({ label: b ? `Block ${b.id} (clicked)` : 'no block (clicked)', model: b ? this.modelBlockHeight(b) : null, H: m.H }); }
    for (const s of (S.auto || []).slice(0, 12)) rows.push({ label: `Block ${s.id}`, model: this.modelBlockHeight(this.d.buildings[s.id - 1]), H: s.H });
    this.set({ shBusy: false, shadow: { rows, ratio: this.shadowRatio(), autoN: S.auto ? S.auto.length : null, total: this.d.buildings.length } });
  }
  runAutoShadows() { this.set({ shBusy: true }); setTimeout(() => { this.T.shadow.auto = this.autoShadows(); this.renderShadow(); this.e.drawOverlay(); }, 30); }
  toggleShadowPick() { this.T.shadow.a = null; this.setPick((this.e.s.pick as any) === 'shadow' ? null : 'shadow'); this.e.drawOverlay(); }
  clearShadows() { Object.assign(this.T.shadow, { meas: [], auto: null, a: null }); this.renderShadow(); this.e.drawOverlay(); }
  setSunAngles(p: Partial<ToolsUI>) {
    this.set(p);
    const k = Math.tan(this.s.shEl * Math.PI / 180);
    for (const m of this.T.shadow.meas) m.H = m.L * k;
    this.T.shadow.auto = null; this.renderShadow(); this.e.drawOverlay();
  }
  sunFromTime() {
    const ll = this.lonlatAt(0.5, 0.5), t = this.s.shTime;
    if (!ll) return this.set({ shMsg: '⚠ Needs a georeferenced scene; enter the sun angles from the image metadata instead.' });
    if (!t) return this.set({ shMsg: '⚠ Enter the acquisition time (UTC) first.' });
    const p = Tools.sunPos(new Date(t + 'Z'), ll[1], ll[0]);
    if (p.el <= 0) return this.set({ shMsg: '⚠ The sun is below the horizon at that time: check it is in UTC.' });
    this.set({ shMsg: '' }); this.setSunAngles({ shEl: +p.el.toFixed(1), shAz: +p.az.toFixed(1) });
  }
  useShadowRatio() {
    const R = this.shadowRatio();
    if (!R) return;
    this.set({ fixB: +R.k.toFixed(2) }); this.toggle('fix', true);
    this.applyFix({ buildings_from: `shadows of ${R.n} buildings` });
  }

  // ----- tall-object fixes (per-class height scale, stored on the server)
  async applyFix(source?: any, reset = false) {
    const name = this.d.name, body = reset ? { clear: true } : { buildings: this.s.fixB || 1, trees: this.s.fixT || 1, source: { ...(this.T.fixSource || {}), ...(source || {}) } };
    this.set({ fixBusy: true, fixMsg: 'Applying…' });
    const r = await fetch(`/api/heightfix?name=${encodeURIComponent(name)}`, { method: 'POST', body: JSON.stringify(body) }), j = await r.json();
    if (this.d.name !== name) return;
    this.set({ fixBusy: false });
    if (!r.ok) return this.set({ fixMsg: `⚠ ${j.error}` });
    if (j.cleared) { delete this.d.meta.class_scale; this.set({ fixB: 1, fixT: 1, fixFit: null }); this.T.fixSource = {}; } else { this.d.meta.class_scale = j; this.T.fixSource = (body as any).source; }
    this.set({ fixOn: true, fixMsg: '' });
    this.e.rebuildScene();
  }
  async fitTrees() {
    const name = this.d.name;
    this.set({ fixBusy: true, fixMsg: 'Fetching ICESat-2 canopy photons (first time can take ~30 s)…' });
    const r = await fetch(`/api/heightfix?name=${encodeURIComponent(name)}`, { method: 'POST', body: JSON.stringify({ fit: 'trees' }) }), j = await r.json();
    if (this.d.name !== name) return;
    this.set({ fixBusy: false });
    if (!r.ok) return this.set({ fixMsg: `⚠ ${j.error}` });
    this.T.fixSource = { ...(this.T.fixSource || {}), trees_from: `ICESat-2, ${j.n} canopy photons` };
    this.set({ fixFit: j, fixT: j.k, fixMsg: `Press Apply to use trees ×${j.k}.` });
  }
  setFixOn(fixOn: boolean) { this.set({ fixOn }); this.e.rebuildScene(); }

  // ----- calibrated error bars
  renderErr() {
    const val = this.e.s.val, srcs = Object.keys(VKEYS).filter(k => val[k] && val[k].conformal);
    if (!srcs.includes(this.s.errSrc)) this.set({ errSrc: srcs[0] || '' });
  }
  async useErr(clear = false) {
    const name = this.d.name, r = await fetch(`/api/conformal?name=${encodeURIComponent(name)}`, { method: 'POST',
      body: JSON.stringify(clear ? { clear: true } : { source: this.s.errSrc, level: this.s.errLev }) }), j = await r.json();
    if (this.d.name !== name) return;
    if (!r.ok) return this.set({ errMsg: `⚠ ${j.error}` });
    if (clear) delete this.d.meta.conformal; else this.d.meta.conformal = j;
    this.set({ errMsg: '' }); this.e.renderStats(); this.e.refreshPin(); this.set({ rev: this.s.rev + 1 });
  }

  // ----- terrain source (user DEM)
  async demRequest(qs: string, body: BodyInit, label: string) {
    const name = this.d.name;
    this.set({ demMsg: label });
    try {
      const r = await fetch(`/api/dem?name=${encodeURIComponent(name)}${qs}`, { method: 'POST', body }), j = await r.json();
      if (!r.ok) throw new Error(j.error);
      this.set({ demMsg: j.error ? `⚠ ${j.error}` : `Terrain rebuilt from ${j.source}. Reloading…` });
      await this.e.poll();
      if (this.e.s.current === name) { this.e.data = null; await this.e.select(name); }
    } catch (err: any) { this.set({ demMsg: `⚠ ${err.message}` }); }
  }
  useDem(f: File) { this.demRequest(`&datum=${this.s.demDatum}&file=${encodeURIComponent(f.name)}`, f, `Rebuilding the terrain from ${f.name}…`); }
  resetDem() { this.demRequest('&clear=1', '', 'Rebuilding the default terrain…'); }

  // ----- GNSS / field points into the control-point list
  async importGnss(qs: string, body: BodyInit) {
    const name = this.d.name;
    this.set({ gnssMsg: 'Reading points…' });
    const r = await fetch(`/api/gnss?name=${encodeURIComponent(name)}${qs}`, { method: 'POST', body }), j = await r.json();
    if (this.d.name !== name) return;
    if (!r.ok) return this.set({ gnssMsg: `⚠ ${j.error}` });
    for (const p of j.points) this.d.gcpPts.push({ u: p.u, v: p.v, z: +p.z.toFixed(2) });
    this.e.renderGcp(); this.e.drawOverlay(); this.e.drawMarks3D();
    this.set({ gnssMsg: `${j.points.length} point${j.points.length === 1 ? '' : 's'} added${j.outside ? `, ${j.outside} outside the scene skipped` : ''}, heights in m above sea level (EGM2008). Phone GPS heights are only good to about ±10 m. Then Fit & apply.` });
  }
  gnssFile(f: File) { this.importGnss(`&datum=${this.s.gnssDatum}`, f); }
  gnssField() { this.importGnss('&source=field', ''); }

  // ======================================== DISASTER ========================================
  // ----- people at risk (summary for whichever hazards are on)
  people() {
    if (!this.d) return;
    const e = this.e, d = this.d, sum = (f: (b: any) => boolean) => { let n = 0, p = 0; for (const b of d.buildings) if (f(b)) { n++; p += this.residents(b); } return { n, p }; };
    const out: any = { total: d.buildings.reduce((a: number, b: any) => a + this.residents(b), 0), blocks: d.buildings.length, groups: [] };
    if (e.s.flood) { const L = e.waterLevel();
      out.groups.push({ title: 'Flood (now)', rows: [['Water inside', sum(b => e.blockState(b, L) !== 'dry')], ['Fully submerged', sum(b => e.blockState(b, L) === 'sub')]] });
      if (d.tl) out.groups[out.groups.length - 1].rows.push([`Wet within ${d.tl.days} days (timeline)`, sum(b => d.tl.bArr[b.id] < 65535)]); }
    if (this.isOpen('flow') && this.T.flow.sim) { const wet = this.flowWetBlocks(); out.groups.push({ title: 'Flowing water', rows: [[`Wet by ${this.flowClock(this.s.flK)}`, sum(b => wet.has(b.id))]] }); }
    if (this.T.slide) out.groups.push({ title: 'Landslide risk', rows: [['Very high', sum(b => this.T.slide.bcls[b.id] === 3)], ['High', sum(b => this.T.slide.bcls[b.id] === 2)]] });
    if (this.T.dmg) { const r = (c: string) => { let n = 0, p = 0; for (const b of this.T.dmg.res.buildings) if (this.T.dmg.cls.get(b.id) === c) { n++; p += this.residents(b); } return { n, p }; };
      out.groups.push({ title: 'Damage (before → after)', rows: [['In collapsed buildings', r('collapsed')], ['In damaged buildings', r('damaged')]] }); }
    this.set({ people: out });
  }
  setPeopleParam(p: Partial<ToolsUI>) { this.set(p); this.people(); if (this.s.dmg) this.renderDmg(); }
  floodPeople() {
    const e = this.e, d = this.d;
    if (!d || !e.s.flood) return null;
    const L = e.waterLevel();
    let wet = 0, sub = 0;
    for (const b of d.buildings) { const st = e.blockState(b, L); if (st === 'dry') continue; const p = this.residents(b); wet += p; if (st === 'sub') sub += p; }
    return { wet, sub };
  }

  // ----- evacuation plan: Dijkstra from every camp over the route costs, then a greedy capacity-aware assignment
  costField(src: number, f: Float32Array, W: number, H: number, dx: number, dy: number) {
    const N = W * H, dist = new Float64Array(N).fill(Infinity), heap = new MinHeap(), dd = Math.hypot(dx, dy);
    dist[src] = 0; heap.push(0, src);
    while (heap.n) {
      const i = heap.pop(), k = heap.key;
      if (k > dist[i]) continue;
      const x = i % W, y = (i - x) / W;
      for (let q = 0; q < 8; q++) {
        const nx = x + NX[q], ny = y + NY[q];
        if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
        const j = ny * W + nx;
        if (!(f[j] < Infinity)) continue;
        if (q >= 4 && !(f[y * W + nx] < Infinity && f[ny * W + x] < Infinity)) continue;
        const c = k + (q < 4 ? (NX[q] ? dx : dy) : dd) * (f[i] + f[j]) / 2;
        if (c < dist[j]) { dist[j] = c; heap.push(c, j); }
      }
    }
    return dist;
  }
  planEvac() {
    const S = this.d.sites, e = this.e, { W, H, dx, dy } = this.gridInfo(), how = this.s.evMode, who = this.s.evWho, L = e.curLevel();
    if (!S || !S.camps.length) return { error: 'camps' };
    if (who === 'flood' && !e.s.flood) return { error: 'flood' };
    if (who === 'slide' && !this.T.slide) return { error: 'slide' };
    const { f } = e.travelCost(L, how, TRAVEL[how].depth), speed = TRAVEL[how].speed, rims = this.blockRims();
    const fields = S.camps.map((c: any) => { const s0 = e.nearestOpen(c.cell, f); return s0 < 0 ? null : this.costField(s0, f, W, H, dx, dy); });
    const leave = this.d.buildings.filter((b: any) => who === 'all' || (who === 'flood' ? e.blockState(b, L) !== 'dry' : this.T.slide.bcls[b.id] >= 2));
    const items = leave.map((b: any) => {
      const t = fields.map((F: any) => { if (!F) return Infinity; let m = Infinity; for (const i of rims[b.id]) if (F[i] < m) m = F[i]; return m / speed / 60; });
      return { b, p: this.residents(b), t, best: Math.min(...t) };
    }).sort((a: any, b: any) => a.best - b.best);
    const left = S.camps.map((c: any) => c.people), load = S.camps.map(() => 0), far = S.camps.map(() => 0), whoMap = new Map<number, any>();
    let unreach = 0, unreachB = 0, full = 0;
    for (const it of items) {
      if (!(it.best < Infinity)) { unreach += it.p; unreachB++; whoMap.set(it.b.id, { camp: null }); continue; }
      const order = it.t.map((t: number, k: number) => [t, k]).filter(([t]: number[]) => t < Infinity).sort((a: number[], b: number[]) => a[0] - b[0]);
      let p = it.p, first: any = null;
      for (const [t, k] of order) {
        if (p <= 0) break;
        const take = Math.min(p, left[k]);
        if (take <= 0) continue;
        left[k] -= take; load[k] += take; p -= take; far[k] = Math.max(far[k], t);
        if (first == null) first = { camp: k, min: t };
      }
      if (p > 0) full += p;
      whoMap.set(it.b.id, first || { camp: null, full: true });
    }
    const cv = canvas(W, H), ctx = cv.getContext('2d')!, img = ctx.createImageData(W, H), cells = this.blockCells();
    for (const [id, a] of whoMap) for (const i of cells[id]) img.data.set(a.camp != null ? [...CAMP_COLORS[a.camp % 5], 225] : a.full ? [140, 140, 150, 235] : [229, 72, 77, 235], i * 4);
    ctx.putImageData(img, 0, 0);
    this.T.evac = { who: whoMap, cv };
    return { load, far, cap: S.camps.map((c: any) => c.people), unreach, unreachB, full, n: items.length, total: items.reduce((a: number, b: any) => a + b.p, 0), how, pads: S.pads.length };
  }
  runEvac() { this.set({ evac: { busy: true } }); setTimeout(() => { this.set({ evac: this.planEvac() }); this.redraw(); }, 30); }

  // ----- damage from before / after images
  classifyDamage() {
    const D = this.T.dmg, col = (this.s.dmgCol || 50) / 100, dam = (this.s.dmgDam || 20) / 100, { W, H, N } = this.gridInfo();
    D.cls = new Map();
    for (const b of D.res.buildings) {
      const lost = b.before_m - b.after_m, f = lost / Math.max(0.1, b.before_m);
      D.cls.set(b.id, f >= col && lost >= 2 ? 'collapsed' : f >= dam && lost >= 1 ? 'damaged' : 'intact');
    }
    const COL: Record<string, number[]> = { collapsed: [229, 72, 77, 235], damaged: [245, 165, 36, 225], intact: [79, 224, 138, 110] }, newIds = new Set(D.res.new.map((b: any) => b.id));
    const cv = canvas(W, H), ctx = cv.getContext('2d')!, img = ctx.createImageData(W, H), bid = this.d.bid;
    for (let i = 0; i < N; i++) {
      const bb = D.bidb[i];
      if (bb > 0 && D.cls.has(bb)) img.data.set(COL[D.cls.get(bb)], i * 4);
      else if (newIds.has(bid[i])) img.data.set([167, 112, 255, 225], i * 4);
      else if (bid[i] === 0 && D.dh[i] < -3) img.data.set([150, 90, 40, 190], i * 4);
    }
    ctx.putImageData(img, 0, 0);
    D.cv = cv;
  }
  renderDmg() {
    const D = this.T.dmg;
    if (!D) return;
    const R = D.res, by = (c: string) => R.buildings.filter((b: any) => D.cls.get(b.id) === c), col = by('collapsed'), dam = by('damaged');
    const lostVol = [...col, ...dam].reduce((a: number, b: any) => a + Math.max(0, b.before_m - b.after_m) * b.area_m2, 0);
    this.set({ dmg: { col: col.length, dam: dam.length, intact: by('intact').length, newN: R.new.length, people: [...col, ...dam].reduce((a: number, b: any) => a + this.residents(b), 0),
      lostVol, debris: lostVol * (this.s.dmgDeb || 30) / 100, canopy: R.canopy, groundLost: R.ground_lost_m3, before: R.before, matched: R.matched, shift: R.shift, notes: R.notes } });
  }
  async runDamage() {
    const name = this.d.name, before = this.s.dmgBefore;
    this.set({ dmgMsg: 'Comparing…' });
    try {
      const r = await fetch(`/api/change?name=${encodeURIComponent(name)}&before=${encodeURIComponent(before)}`, { method: 'POST' }), res = await r.json();
      if (!r.ok) throw new Error(res.error);
      const [dh, bidb] = await Promise.all(['_dh', '_bidb'].map(s => fetch(`/results/${name}${s}.f32?t=${Date.now()}`).then(x => x.arrayBuffer()).then(b => new Float32Array(b))));
      if (this.d.name !== name) return;
      this.T.dmg = { res, dh, bidb, byId: new Map(res.buildings.map((b: any) => [b.id, b])) };
      this.classifyDamage(); this.renderDmg(); this.set({ dmgMsg: '' });
    } catch (err: any) { this.set({ dmgMsg: `⚠ ${err.message}` }); }
    this.people(); this.redraw();
  }
  setDmgParam(p: Partial<ToolsUI>) { this.set(p); if (this.T.dmg) { this.classifyDamage(); this.renderDmg(); this.people(); this.redraw(); } }

  // ----- landslide risk (screening): BIS IS 14496 (Part 2) style ratings, raised for heavy rain (IMD 24-hour classes)
  computeSlide() {
    const d = this.d;
    if (!d.dtm) { this.T.slide = null; return this.set({ slide: { none: true } }); }
    const { W, H, N, dx } = this.gridInfo(), g = d.dtm, rain = Math.max(0, this.s.slRain), f = rainFactor(rain);
    const bs = Math.max(1, Math.round(50 / dx)), BW = Math.ceil(W / bs), BH = Math.ceil(H / bs);
    const lo = new Float32Array(BW * BH).fill(Infinity), hi = new Float32Array(BW * BH).fill(-Infinity);
    for (let i = 0; i < N; i++) { const x = i % W, k = Math.floor((i - x) / W / bs) * BW + Math.floor(x / bs); lo[k] = Math.min(lo[k], g[i]); hi[k] = Math.max(hi[k], g[i]); }
    const rel = new Float32Array(BW * BH);
    for (let by = 0; by < BH; by++) for (let bx = 0; bx < BW; bx++) {
      let a = Infinity, b = -Infinity;
      for (let yy = Math.max(0, by - 1); yy <= Math.min(BH - 1, by + 1); yy++) for (let xx = Math.max(0, bx - 1); xx <= Math.min(BW - 1, bx + 1); xx++) { a = Math.min(a, lo[yy * BW + xx]); b = Math.max(b, hi[yy * BW + xx]); }
      rel[by * BW + bx] = b - a;
    }
    const score = new Float32Array(N), cls = new Int8Array(N), count = [0, 0, 0, 0];
    const cv = canvas(W, H), ctx = cv.getContext('2d')!, img = ctx.createImageData(W, H);
    for (let i = 0; i < N; i++) {
      const lcr = SLIDE_LC[d.lc ? d.lc[i] : 2];
      if (lcr == null) { cls[i] = -1; continue; }
      const x = i % W, r = rel[Math.floor((i - x) / W / bs) * BW + Math.floor(x / bs)], sl = d.slope[i];
      const sc = score[i] = (SLIDE_SLOPE.find(([t]) => sl <= t)![1] + lcr + (r < 25 ? 0.3 : r < 75 ? 0.6 : 1.0)) * f;
      const c = cls[i] = SLIDE_CLS.findIndex(([t]) => sc < t);
      count[c]++;
      if (c >= 1) img.data.set([...SLIDE_CLS[c][2], c === 1 ? 90 : 150], i * 4);
    }
    ctx.putImageData(img, 0, 0);
    const bcls = new Int8Array(d.buildings.length + 1).fill(-1), cells = this.blockCells(), rims = this.blockRims();
    for (const b of d.buildings) { let m = -1; for (const i of rims[b.id]) m = Math.max(m, cls[i]); for (const i of cells[b.id]) m = Math.max(m, cls[i]); bcls[b.id] = m; }
    this.T.slide = { score, cls, cv, bcls };
    const nb = (c: number) => d.buildings.filter((b: any) => bcls[b.id] === c).length;
    this.set({ slide: { count, total: count.reduce((a, b) => a + b, 0) || 1, cell: this.gridInfo().dx * this.gridInfo().dy, nb: [0, 1, 2, 3].map(nb), f, rain, imd: imdClass(rain) } });
    this.redraw();
  }
  setSlideRain(slRain: number) { this.set({ slRain }); this.schedule('sl', () => { this.computeSlide(); this.people(); }, 200); }
  slideRainFromTimeline() {
    const d = this.d;
    let mm: number | null = null;
    if (d.tl) { let run = 0; mm = 0; for (let h = 0; h < d.tl.T; h++) { run += d.tl.P[h] - (h >= 24 ? d.tl.P[h - 24] : 0); mm = Math.max(mm, run); } }
    else if (d.forecast) mm = d.forecast.mm.slice(0, 24).reduce((a: number, b: number) => a + b, 0);
    if (mm == null) return false;
    this.setSlideRain(Math.round(mm));
    return true;
  }

  // ----- observed flood (Sentinel-1 / water mask) vs the scenario
  obsMetrics(L: number) {
    const o = this.T.obs.grid, r = this.d.reach, bid = this.d.bid;
    let hit = 0, miss = 0, fa = 0;
    for (let i = 0; i < o.length; i++) {
      if (!Number.isFinite(o[i]) || bid[i] > 0) continue;
      const s = r[i] < L, w = o[i] > 0.5;
      if (s && w) hit++; else if (w) miss++; else if (s) fa++;
    }
    return { hit, miss, fa, csi: hit / Math.max(1, hit + miss + fa), pod: hit / Math.max(1, hit + miss), far: fa / Math.max(1, hit + fa) };
  }
  renderObs() {
    const O = this.T.obs;
    if (!O) return;
    const { W, H, N } = this.gridInfo(), on = this.e.s.flood, L = this.e.waterLevel(), bid = this.d.bid, reach = this.d.reach;
    const cv = O.cv || (O.cv = canvas(W, H)), ctx = cv.getContext('2d')!, img = ctx.createImageData(W, H);
    for (let i = 0; i < N; i++) {
      const o = O.grid[i];
      if (!Number.isFinite(o) || bid[i] > 0) continue;
      const w = o > 0.5, s = on && reach[i] < L;
      const c = !on ? (w ? [0, 220, 255, 150] : null) : s && w ? [47, 127, 224, 170] : w ? [214, 51, 132, 200] : s ? [245, 197, 24, 190] : null;
      if (c) img.data.set(c, i * 4);
    }
    ctx.putImageData(img, 0, 0);
    this.set({ obs: { res: O.res, m: on ? this.obsMetrics(L) : null, cell: this.gridInfo().dx * this.gridInfo().dy, fit: O.fit || null } });
    this.redraw();
  }
  async loadObs(body: BodyInit, fname: string) {
    const name = this.d.name, thr = this.s.obsThr;
    this.set({ obsMsg: 'Reading the flood map…' });
    try {
      const r = await fetch(`/api/obsflood?name=${encodeURIComponent(name)}&kind=${this.s.obsKind}&file=${encodeURIComponent(fname)}${thr !== '' ? `&threshold=${thr}` : ''}`, { method: 'POST', body }), res = await r.json();
      if (!r.ok) throw new Error(res.error);
      const grid = new Float32Array(await (await fetch(`/results/${name}_obsflood.f32?t=${Date.now()}`)).arrayBuffer());
      if (this.d.name !== name) return;
      this.T.obs = { res, grid }; this.set({ obsMsg: '' }); this.renderObs();
    } catch (err: any) { this.set({ obsMsg: `⚠ ${err.message}` }); }
  }
  fitObsLevel() {
    const e = this.e;
    if (!e.s.flood) e.setFlood(true);
    let best = { csi: -1, rise: 0 };
    for (let rr = 0; rr <= e.s.depthMax; rr += 0.1) { const m = this.obsMetrics(this.d.gmin + rr); if (m.csi > best.csi) best = { csi: m.csi, rise: rr }; }
    this.T.obs.fit = best;
    e.setDepth(best.rise);
    this.renderObs();
    return best;
  }

  // ----- flowing water: local-inertial shallow-water model (Bates et al. 2010) on a coarser grid
  flowSetup(hours: number) {
    const { W, H, dx, dy } = this.gridInfo(), L = Math.max(W * dx, H * dy), d = this.d;
    const n = clampI(Math.round(Math.cbrt(5e7 * 0.7 * L / (hours * 3600 * Math.sqrt(9.81 * 2)))), 40, 150);   // a run takes seconds
    const f = Math.max(1, Math.ceil(Math.max(W, H) / n)), Wc = Math.ceil(W / f), Hc = Math.ceil(H / f), Nc = Wc * Hc, g = this.e.groundGrid();
    const z = new Float64Array(Nc), cnt = new Float64Array(Nc), bld = new Float64Array(Nc), nn = new Float64Array(Nc);
    for (let i = 0; i < W * H; i++) {
      const x = i % W, c = Math.floor((i - x) / W / f) * Wc + Math.floor(x / f);
      z[c] += g[i]; cnt[c]++; if (d.bid[i] > 0) bld[c]++; nn[c] += MANNING[d.lc ? d.lc[i] : 2];
    }
    const solid = new Uint8Array(Nc), man = new Float64Array(Nc);
    for (let c = 0; c < Nc; c++) { z[c] /= cnt[c]; man[c] = nn[c] / cnt[c]; solid[c] = bld[c] / cnt[c] > 0.5 ? 1 : 0; }
    const brim = new Map<number, number[]>(), rims = this.blockRims();
    for (const b of d.buildings) brim.set(b.id, [...new Set(rims[b.id].map(i => { const x = i % W; return Math.floor((i - x) / W / f) * Wc + Math.floor(x / f); }))].filter(c => !solid[c]));
    return { f, Wc, Hc, Nc, z, solid, man, dxc: dx * f, dyc: dy * f, brim };
  }
  flowStart() {
    const s = this.s, hours = clampI(s.flHours || 3, 0.25, 24), G = this.flowSetup(hours), { Wc, Hc, Nc, solid } = G;
    const src = this.T.flow.src.map(([u, v]: number[]) => {
      let c = clampI(Math.floor(v * Hc), 0, Hc - 1) * Wc + clampI(Math.floor(u * Wc), 0, Wc - 1);
      if (solid[c]) { let best = -1, bd = Infinity; for (let k = 0; k < Nc; k++) if (!solid[k]) { const dd = (k % Wc - c % Wc) ** 2 + (Math.floor(k / Wc) - Math.floor(c / Wc)) ** 2; if (dd < bd) { bd = dd; best = k; } } c = best; }
      return c;
    }).filter((c: number) => c >= 0);
    const Tend = hours * 3600, every = Tend <= 3 * 3600 ? 300 : Tend <= 12 * 3600 ? 900 : 1800;
    return this.T.flow.sim = { G, h: new Float64Array(Nc), qx: new Float64Array((Wc + 1) * Hc), qy: new Float64Array(Wc * (Hc + 1)), lim: new Float64Array(Nc), t: 0, Tend, every, next: every,
      src, Q: Math.max(0, s.flQ), rain: Math.max(0, s.flRain) / 1000 / 3600, arrival: new Float32Array(Nc).fill(Infinity),
      snaps: [new Float32Array(Nc)], times: [0], vin: 0, vout: 0, done: false, stop: false };
  }
  flowStep(F: any) {
    const { Wc, Hc, Nc, z, solid, man, dxc, dyc } = F.G, h = F.h, qx = F.qx, qy = F.qy, g = 9.81, lim = F.lim;
    let hm = 0.01;
    for (let c = 0; c < Nc; c++) if (h[c] > hm) hm = h[c];
    const dt = Math.min(5, 0.7 * Math.min(dxc, dyc) / Math.sqrt(g * hm), F.Tend - F.t);
    const face = (q0: number, a: number, b: number, dd: number) => {   // discharge per metre of face a → b
      if (solid[a] || solid[b]) return 0;
      const ea = z[a] + h[a], eb = z[b] + h[b], hf = Math.max(ea, eb) - Math.max(z[a], z[b]);
      if (hf < 1e-3) return 0;
      const n = (man[a] + man[b]) / 2, qmax = hf * Math.sqrt(g * hf);   // Froude ≤ 1 keeps steep slopes stable
      return clampI((q0 - g * hf * dt * (eb - ea) / dd) / (1 + g * dt * n * n * Math.abs(q0) / Math.pow(hf, 7 / 3)), -qmax, qmax);
    };
    const outfall = (c: number) => solid[c] || h[c] < 0.01 ? 0 : 0.5 * h[c] * Math.sqrt(g * h[c]);   // water leaves at the edges
    for (let y = 0; y < Hc; y++) for (let i = 0; i <= Wc; i++) {
      const f = y * (Wc + 1) + i;
      qx[f] = i === 0 ? -outfall(y * Wc) : i === Wc ? outfall(y * Wc + Wc - 1) : face(qx[f], y * Wc + i - 1, y * Wc + i, dxc);
    }
    for (let j = 0; j <= Hc; j++) for (let x = 0; x < Wc; x++) {
      const f = j * Wc + x;
      qy[f] = j === 0 ? -outfall(x) : j === Hc ? outfall((Hc - 1) * Wc + x) : face(qy[f], (j - 1) * Wc + x, j * Wc + x, dyc);
    }
    for (let c = 0; c < Nc; c++) {   // no cell may lose more water than it holds in one step (exact mass balance)
      if (solid[c]) { lim[c] = 1; continue; }
      const x = c % Wc, y = (c - x) / Wc, fl = y * (Wc + 1) + x, ft = y * Wc + x;
      const outV = (Math.max(0, -qx[fl]) + Math.max(0, qx[fl + 1])) * dyc * dt + (Math.max(0, -qy[ft]) + Math.max(0, qy[ft + Wc])) * dxc * dt, have = h[c] * dxc * dyc;
      lim[c] = outV > have ? have / outV : 1;
    }
    for (let y = 0; y < Hc; y++) for (let i = 0; i <= Wc; i++) { const f = y * (Wc + 1) + i, q = qx[f]; if (q > 0 && i > 0) qx[f] = q * lim[y * Wc + i - 1]; else if (q < 0 && i < Wc) qx[f] = q * lim[y * Wc + i]; }
    for (let j = 0; j <= Hc; j++) for (let x = 0; x < Wc; x++) { const f = j * Wc + x, q = qy[f]; if (q > 0 && j > 0) qy[f] = q * lim[(j - 1) * Wc + x]; else if (q < 0 && j < Hc) qy[f] = q * lim[j * Wc + x]; }
    let out = 0;
    for (let y = 0; y < Hc; y++) out += (-qx[y * (Wc + 1)] + qx[y * (Wc + 1) + Wc]) * dyc * dt;
    for (let x = 0; x < Wc; x++) out += (-qy[x] + qy[Hc * Wc + x]) * dxc * dt;
    for (let c = 0; c < Nc; c++) {
      if (solid[c]) continue;
      const x = c % Wc, y = (c - x) / Wc;
      const dq = (qx[y * (Wc + 1) + x] - qx[y * (Wc + 1) + x + 1]) / dxc + (qy[y * Wc + x] - qy[(y + 1) * Wc + x]) / dyc;
      h[c] = Math.max(0, h[c] + dt * dq + F.rain * dt);
      if (F.rain) F.vin += F.rain * dt * dxc * dyc;
    }
    for (const c of F.src) h[c] += F.Q * dt / (dxc * dyc);
    F.vin += F.Q * F.src.length * dt; F.vout += out; F.t += dt;
    for (let c = 0; c < Nc; c++) if (h[c] > 0.1 && F.arrival[c] === Infinity) F.arrival[c] = F.t;
    if (F.t >= F.next - 1e-6 || F.t >= F.Tend - 1e-6) { F.snaps.push(Float32Array.from(h)); F.times.push(F.t); F.next += F.every; }
    if (F.t >= F.Tend - 1e-6) F.done = true;
  }
  runFlow(sync = false) {
    if (this.T.flow.sim && !this.T.flow.sim.done) { this.T.flow.sim.stop = true; return; }
    const F = this.flowStart();
    if (!F.src.length && !F.rain) { this.T.flow.sim = null; return this.set({ flow: { error: 'Place at least one inflow point (or set some rain) first.' } }); }
    this.setPick(null);
    if (sync) { while (!F.done) this.flowStep(F); return this.flowFinished(); }
    this.set({ flBusy: true });
    const chunk = () => {
      if (this.T.flow.sim !== F) return;
      const t0 = performance.now();
      while (!F.done && performance.now() - t0 < 30) this.flowStep(F);
      this.set({ flK: F.snaps.length - 1, flMax: F.snaps.length - 1 });
      this.renderFlowFrame();
      if (F.done || F.stop) this.flowFinished(); else requestAnimationFrame(chunk);
    };
    requestAnimationFrame(chunk);
  }
  flowFinished() {
    const F = this.T.flow.sim; F.done = true;
    this.set({ flBusy: false, flK: F.snaps.length - 1, flMax: F.snaps.length - 1 });
    this.renderFlowFrame(); this.people();
  }
  clearFlow() {
    if (this.T.flow.sim) this.T.flow.sim.stop = true;
    this.T.flow = { src: [], sim: null };
    this.set({ flow: null, flK: 0, flMax: 0, flSrcN: 0, flBusy: false });
    this.e.water.visible = this.e.s.flood; this.e.updateWater(); this.setPick('flowsrc'); this.redraw(); this.people();
  }
  setFlowTime(flK: number) { this.set({ flK }); if (this.T.flow.sim) { this.renderFlowFrame(); this.people(); } }
  setFlowArr(flArr: boolean) { this.set({ flArr }); if (this.T.flow.sim) this.renderFlowFrame(); }
  flowShown() { return !!(this.T.flow && this.T.flow.sim && this.isOpen('flow')); }
  flowClock(k: number) { const F = this.T.flow && this.T.flow.sim; return F ? `+${fmtDur(F.times[Math.min(k, F.times.length - 1)])}` : '–'; }
  flowSampler(arr: ArrayLike<number>) {
    const { f, Wc, Hc } = this.T.flow.sim.G, W = this.W, H = this.H;
    return (u: number, v: number) => {
      const x = clampI(u * W / f - 0.5, 0, Wc - 1), y = clampI(v * H / f - 0.5, 0, Hc - 1), x0 = Math.floor(x), y0 = Math.floor(y), x1 = Math.min(Wc - 1, x0 + 1), y1 = Math.min(Hc - 1, y0 + 1), fx = x - x0, fy = y - y0;
      return (arr[y0 * Wc + x0] * (1 - fx) + arr[y0 * Wc + x1] * fx) * (1 - fy) + (arr[y1 * Wc + x0] * (1 - fx) + arr[y1 * Wc + x1] * fx) * fy;
    };
  }
  flowDepthAt(u: number, v: number) { return this.flowSampler(this.T.flow.sim.snaps[this.s.flK])(u, v); }
  flowArrivalAt(u: number, v: number) {
    const F = this.T.flow.sim, { f, Wc, Hc } = F.G, a = F.arrival[clampI(Math.floor(v * this.H / f), 0, Hc - 1) * Wc + clampI(Math.floor(u * this.W / f), 0, Wc - 1)];
    return a <= F.times[this.s.flK] ? a : Infinity;
  }
  flowHeights(pos: THREE.BufferAttribute, k: number) {
    const F = this.T.flow.sim, W = this.W, H = this.H, g = this.e.groundGrid(), sm = this.flowSampler(F.snaps[this.s.flK]), gmin = this.d.gmin, bid = this.d.bid;
    for (let i = 0; i < pos.count; i++) {
      const x = i % W, y = (i - x) / W, dd = sm((x + 0.5) / W, (y + 0.5) / H);
      pos.setY(i, dd > 0.05 && !(bid[i] > 0) ? (g[i] - gmin + dd) * k : (g[i] - gmin - 1) * k);
    }
    pos.needsUpdate = true;
  }
  flowWetBlocks() {
    const F = this.T.flow.sim, h = F.snaps[this.s.flK], s = new Set<number>();
    for (const [id, cs] of F.G.brim) if (cs.some((c: number) => h[c] > 0.1)) s.add(id);
    return s;
  }
  renderFlowFrame() {
    const F = this.T.flow.sim, { Wc, Hc, Nc } = F.G, h = F.snaps[this.s.flK], t = F.times[this.s.flK], arr = this.s.flArr;
    const cv = this.T.flow.cv && this.T.flow.cv.width === Wc ? this.T.flow.cv : (this.T.flow.cv = Object.assign(canvas(Wc, Hc), { smooth: true }));
    const ctx = cv.getContext('2d')!, img = ctx.createImageData(Wc, Hc), cell = F.G.dxc * F.G.dyc;
    let wet = 0, maxd = 0, vol = 0;
    for (let c = 0; c < Nc; c++) {
      const dd = h[c];
      vol += dd * cell;
      if (dd <= 0.05) continue;
      if (dd > 0.1) wet++;
      maxd = Math.max(maxd, dd);
      if (arr) { const a = F.arrival[c]; if (a <= t) img.data.set([...ARR_KEYS[a <= 0 ? 0 : clampI(Math.ceil(4 * a / F.Tend), 1, 4)][2], 215], c * 4); continue; }
      const x = Math.min(1, dd / 3);
      img.data.set([Math.round(140 - 120 * x), Math.round(200 - 140 * x), 255, Math.round(Math.min(230, 110 + 120 * x))], c * 4);
    }
    ctx.putImageData(img, 0, 0);
    this.e.water.visible = true; this.e.updateWater();
    const wetB = this.flowWetBlocks(), ppl = this.d.buildings.filter((b: any) => wetB.has(b.id)).reduce((a: number, b: any) => a + this.residents(b), 0);
    this.set({ flow: { wetM2: wet * cell, maxd, wetB: wetB.size, ppl, vin: F.vin * Math.min(1, t / Math.max(F.t, 1e-6)), vout: F.vout, vol, done: F.done,
      pct: Math.round(100 * F.t / F.Tend), Wc, Hc, cellM: F.G.dxc, Tend: F.Tend, clock: this.flowClock(this.s.flK) } });
    this.redraw();
  }

  // ======================================== REPORT ========================================
  reportHTML() {
    const e = this.e, d = this.d, m = d.meta, W = d.photo.naturalWidth, H = d.photo.naturalHeight, k = Math.min(1, 1400 / Math.max(W, H));
    const cv = canvas(Math.round(W * k), Math.round(H * k)), c = cv.getContext('2d')!;
    c.drawImage(d.photo, 0, 0, cv.width, cv.height);
    if (e.el.heat) { c.globalAlpha = e.s.alpha; c.drawImage(e.el.heat, 0, 0, cv.width, cv.height); c.globalAlpha = 1; }
    if (e.el.ovl) c.drawImage(e.el.ovl, 0, 0, cv.width, cv.height);
    let shot3d = '';
    if (e.mesh && e.s.view === '3d') { e.renderer.render(e.scene3, e.camera); shot3d = e.renderer.domElement.toDataURL('image/png'); }
    const esc = (x: any) => String(x).replace(/[&<>]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' } as any)[ch]);
    const rows = (pairs: [string, any][]) => `<table>${pairs.filter(p => p[1] != null && p[1] !== '').map(([a, b]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td></tr>`).join('')}</table>`;
    const sec: [string, string][] = [];
    const f = e.s.floodSum;
    if (e.s.flood && f) { const fp = this.floodPeople();
      sec.push(['Flood scenario', rows([['Water level', f.abs ? `${f.level.toFixed(1)} m a.s.l. (+${f.rise.toFixed(1)} m)` : `+${f.rise.toFixed(1)} m`], ['Ground under water', `${f.wetPct.toFixed(0)}% · ${f.wetHa.toFixed(1)} ha`],
        ['Deepest water', `${f.maxDepth.toFixed(1)} m`], ['Blocks submerged / partly flooded / dry', `${f.sub} / ${f.part} / ${f.dry}`], ['Floor area under water', `${fmtN(Math.round(f.floorArea))} m²`],
        ['People in buildings with water (estimate)', fp ? fmtN(Math.round(fp.wet)) : null]]) + `<p class="n">${esc(f.model)}</p>`]); }
    if (e.s.tlSum) sec.push(['Rain & river timeline', rows([['Max 24 h rain', `${e.s.tlSum.max24.toFixed(0)} mm (IMD ${e.s.tlSum.imd})`], ['Peak water', `+${e.s.tlSum.peakRise.toFixed(2)} m`], ['Route', e.s.tlSum.deadline]])]);
    if (e.s.routeSum) sec.push(['Route A → B', rows([['Length', fmtLen(e.s.routeSum.len)], ['Time', `≈ ${Math.round(e.s.routeSum.minutes)} min ${e.s.routeSum.how}`]])]);
    if (e.s.sites) sec.push(['Relief sites', rows([...e.s.sites.pads.map(p => [p.label, p.text] as [string, any]), ...e.s.sites.camps.map(p => [p.label, p.text] as [string, any])])]);
    const P = this.s.people;
    if (P && P.groups.length) sec.push(['People at risk (estimate)', rows([['Residents in the scene', fmtN(Math.round(P.total))], ...P.groups.flatMap((g: any) => g.rows.map(([l, v]: any) => [`${g.title}: ${l}`, `${fmtN(Math.round(v.p))} people · ${v.n} buildings`]))])]);
    const E = this.s.evac;
    if (E && E.load) sec.push(['Evacuation plan', rows([...E.load.map((p: number, j: number) => [`Camp C${j + 1}`, `${fmtN(Math.round(p))} / ${fmtN(E.cap[j])} people · up to ${Math.ceil(E.far[j])} min`]), ['No dry route (boat / air)', fmtN(Math.round(E.unreach))], ['No camp space left', fmtN(Math.round(E.full))]])]);
    const D = this.s.dmg;
    if (D) sec.push(['Damage: before / after', rows([['Collapsed / damaged / intact', `${D.col} / ${D.dam} / ${D.intact}`], ['New structures', D.newN], ['People in collapsed or damaged buildings', fmtN(Math.round(D.people))], ['Debris to clear', fmtM3(D.debris)], ['Tree canopy lost', D.canopy ? fmtHa(D.canopy.lost_m2) : null], ['Before image', nice(D.before)]])]);
    const S = this.s.slide;
    if (S && !S.none) sec.push(['Landslide risk (screening)', rows([...SLIDE_CLS.map(([, n], j) => [n, `${Math.round(100 * S.count[j] / S.total)}% of the land · ${S.nb[j]} buildings`] as [string, any]), ['Rain in 24 h', `${S.rain} mm (×${S.f})`]])]);
    const O = this.s.obs;
    if (O && O.m) sec.push(['Observed flood vs scenario', rows([['CSI', O.m.csi.toFixed(2)], ['Real water found', `${Math.round(100 * O.m.pod)}%`], ['False alarms', `${Math.round(100 * O.m.far)}%`], ['Best fitting level', O.fit ? `+${O.fit.rise.toFixed(1)} m` : null]])]);
    const Fl = this.s.flow;
    if (Fl && Fl.cellM) sec.push(['Flowing water', rows([['Time', Fl.clock], ['Under water', fmtHa(Fl.wetM2)], ['Deepest', `${Fl.maxd.toFixed(1)} m`], ['Buildings wet', `${Fl.wetB} (≈ ${fmtN(Math.round(Fl.ppl))} people)`]])]);
    const Lo = this.s.los;
    if (Lo && Lo.n) sec.push(['Line of sight', rows([['Visible share of the range', `${Math.round(100 * Lo.seen / Math.max(1, Lo.inR))}%`], ['Buildings seen', `${Lo.seenB} / ${Lo.inB}`], ['Observers', `${Lo.n} at ${this.s.losH} m`]])]);
    const V = this.s.vol;
    if (V) sec.push(['Volume', rows([['Area', fmtHa(V.area)], ['Volume above', fmtM3(V.above)], ['Volume below', fmtM3(V.below)]])]);
    const So = this.s.solar;
    if (So) sec.push(['Rooftop solar', rows([['Could be installed', `${fmtN(So.kWp)} kWp`], ['Energy a year', `${fmtN(So.mwh)} MWh`], ['CO₂ avoided', `${fmtN(So.co2)} t a year`]])]);
    const Dr = this.s.drone;
    if (Dr) sec.push(['Drone flight plan', rows([['Waypoints', Dr.n], ['Distance', fmtLen(Dr.len)], ['Highest above ground', `${Math.round(Dr.maxAgl)} m`], ['Above the limit', Dr.over || 'none']])]);
    const val = e.s.val;
    for (const key of Object.keys(VKEYS)) { const r = val[key], mm = r && (r.overall || r.surface_vs_all);
      if (mm) sec.push([`Validation: ${VKEYS[key]}`, rows([['MAE', `${mm.mae.toFixed(2)} m`], ['RMSE', `${mm.rmse.toFixed(2)} m`], ['Correlation r', mm.r == null ? '–' : mm.r.toFixed(2)], ['Bias', `${mm.bias.toFixed(2)} m`], ['Values', fmtN(mm.n)]])]); }
    return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(nice(d.name))} situation report</title><style>
body{font:13px/1.5 Manrope,-apple-system,"Segoe UI",sans-serif;color:#1c1c1e;margin:28px auto;max-width:1000px;padding:0 20px}h1{font-weight:300;font-size:30px;margin:0;letter-spacing:-.03em}
h2{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#8a6a4a;margin:0 0 8px}.meta{color:#6a6a70}.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.chip{border:1px solid #ddd;border-radius:999px;padding:2px 10px;font-size:12px}img{width:100%;border-radius:14px;margin:8px 0 18px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.card{border:1px solid #e3e3e3;border-radius:18px;padding:14px 16px;break-inside:avoid}table{width:100%;border-collapse:collapse}td{padding:5px 0;border-top:1px solid #eee}
td:last-child{text-align:right;font-weight:700}tr:first-child td{border-top:0}.n{font-size:11px;color:#6a6a70;margin:6px 0 0}
.foot{margin-top:22px;color:#6a6a70;font-size:11.5px;border-top:1px solid #ddd;padding-top:10px}button{float:right;border:0;border-radius:999px;background:#1c1c1e;color:#fff;padding:9px 18px;font:inherit;cursor:pointer}
@media print{button{display:none}body{margin:0}}</style></head><body>
<button onclick="print()">Print / save as PDF</button>
<h1>${esc(nice(d.name))} · situation report</h1>
<div class="meta">DepthWizard · ${new Date().toLocaleString('en-IN')} · ${m.width}×${m.height} px at ${m.gsd.toFixed(2)} m${m.center_lonlat ? ` · centre ${m.center_lonlat[1].toFixed(5)}°N, ${m.center_lonlat[0].toFixed(5)}°E` : ''}</div>
<div class="chips">${e.s.stats.map(([a, b]) => `<span class="chip">${esc(a)} <b>${esc(b)}</b></span>`).join('')}</div>
<img src="${cv.toDataURL('image/jpeg', 0.88)}">${shot3d ? `<img src="${shot3d}">` : ''}
<div class="grid">${sec.map(([t, h]) => `<div class="card"><h2>${esc(t)}</h2>${h}</div>`).join('') || '<p>No tool results yet: run a scenario or a tool, then make the report again.</p>'}</div>
<div class="foot">${esc(e.s.note)}<br>Heights are estimated from a single satellite image; the tools give scenarios and planning estimates, not forecasts. Check on the ground before acting.</div>
</body></html>`;
  }
  openReport() {
    if (!this.d) return;
    const url = URL.createObjectURL(new Blob([this.reportHTML()], { type: 'text/html' }));
    if (!window.open(url, '_blank')) download(url, `${this.d.name}_report.html`);
  }
}
