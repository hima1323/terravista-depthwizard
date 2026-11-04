// Cards for the newer tools (engine/tools.ts). Each card has an on/off switch in its title, like the route finder:
// off, it says in one line what the tool does; on, it shows its inputs, its result and draws its layer on the map.
import { useState, type ReactNode } from 'react';
import {
  Eye, Package, Navigation2, Sun, Map as MapIcon, LayoutGrid, Sunset, TreePine, Gauge, Mountain, LocateFixed, MountainSnow,
  Droplets, SatelliteDish, Footprints, Construction, Users, FileText, Plus, Eraser, Play, Square, PenLine, Ruler, Download, Smartphone, type LucideIcon,
} from 'lucide-react';
import { engine, useEngine, useTools, tools } from '../engine/useEngine';
import { SLIDE_CLS, CAMP_COLORS, VKEYS, fmtN, fmtM3, fmtLen, fmtHa, fmtDur, type ToolId } from '../engine/tools';
import { ARR_KEYS, inferno, nice } from '../engine/algos';
import { Card, Kpi, Num, Row, Seg, Slider, Toggle } from './ui';

const Msg = ({ m }: { m: string }) => m ? <p className={`msg${m.startsWith('⚠') ? ' warn' : ''}`}>{m.replace(/^⚠ /, '')}</p> : null;

function ToolCard({ id, icon, title, blurb, children }: { id: ToolId; icon: LucideIcon; title: string; blurb: ReactNode; children: ReactNode }) {
  const on = useTools(s => !!s.open[id]);
  return (
    <Card id={`tool-${id}`} icon={icon} title={title}
      right={<input type="checkbox" className="switch" aria-label={title} checked={on} onChange={e => tools.toggle(id, e.target.checked)} />}>
      {on ? children : <p className="msg">{blurb}</p>}
    </Card>
  );
}

// ======================================== EXPLORE ========================================
export function LineOfSightCard() {
  const s = useTools(x => x), L = s.los, pick = useEngine(x => x.pick);
  return (
    <ToolCard id="los" icon={Eye} title="Line of sight" blurb="What can be seen from a point: a watch post, a siren, a radio mast or a camera.">
      <div className="fields">
        <Num label="Observer height" unit="m" value={s.losH} min={0} onChange={v => tools.setLosParam({ losH: v })} title="Above the roof or ground it stands on" />
        <Num label="Target height" unit="m" value={s.losT} min={0} step={0.1} onChange={v => tools.setLosParam({ losT: v })} title="1.7 m = a person standing" />
        <Num label="Range" unit="m" value={s.losR} min={10} step={50} onChange={v => tools.setLosParam({ losR: v })} wide />
      </div>
      <div className="btns">
        <button className={`btn sm${pick === 'los' ? ' on' : ''}`} onClick={() => tools.setPick(pick === 'los' ? null : 'los')}>{pick === 'los' ? 'Done' : <><Plus size={13} />Place observers</>}</button>
        <button className="btn sm" disabled={!L || !L.n} onClick={() => tools.clearLOS()}><Eraser size={13} />Clear</button>
      </div>
      {L && L.n ? (<>
        <div className="kpis">
          <Kpi v={`${Math.round(100 * L.seen / Math.max(1, L.inR))}%`} l="of the range visible" tone="good" />
          <Kpi v={fmtHa(L.seen * L.cell)} l="visible area" />
          <Kpi v={`${L.seenB} / ${L.inB}`} l="buildings seen" title="Building blocks with any visible roof cell, out of those in range" />
        </div>
        <div className="rows"><Row k="Farthest visible point (observer 1)" v={fmtLen(L.far)} /></div>
        <p className="fine">Green = visible, dark = hidden by terrain, buildings or trees. Uses the model's heights and the 30 m terrain; earth curvature ignored (under 0.1 m within 1 km).</p>
      </>) : <p className="msg">Click the map (2D or 3D) to place observers.</p>}
    </ToolCard>
  );
}

export function VolumeCard() {
  const s = useTools(x => x), V = s.vol, pick = useEngine(x => x.pick), abs = useEngine(x => x.hasTerrain);
  return (
    <ToolCard id="vol" icon={Package} title="Volume & area" blurb="Draw an outline around a debris pile, a stockpile, a pond or a group of buildings to get its area and volume.">
      <label className="field"><span>Measure against</span>
        <Seg full value={s.volBase} onChange={v => { tools.set({ volBase: v }); tools.computeVolume(); }} options={[['edge', 'Ground at outline'], ['ground', 'Bare ground'], ['level', 'A level']]} /></label>
      {s.volBase === 'level' && <Num label="Level" unit="m" value={s.volLevel} step={0.5} onChange={v => { tools.set({ volLevel: v }); tools.computeVolume(); }} />}
      <div className="btns">
        <button className={`btn sm${pick === 'vol' ? ' on' : ''}`} onClick={() => tools.toggleVolDraw()}><PenLine size={13} />{pick === 'vol' ? `Done (${s.volN})` : 'Draw outline'}</button>
        <button className="btn sm" disabled={!s.volN} onClick={() => tools.clearVolume()}><Eraser size={13} />Clear</button>
      </div>
      {V ? (<>
        <div className="kpis">
          <Kpi v={fmtM3(V.above)} l="above" tone="amber" />
          {V.how !== 'ground' && <Kpi v={fmtM3(V.below)} l={V.how === 'level' ? 'capacity below' : 'below'} tone="blue" />}
          <Kpi v={fmtHa(V.area)} l="area" />
        </div>
        <div className="rows">
          <Row k="Measured against" v={V.how === 'edge' ? `ground along the outline, ${V.base.toFixed(1)} m${abs ? ' a.s.l.' : ''}` : V.how === 'level' ? `level ${V.base.toFixed(1)} m` : 'bare ground'} />
          <Row k="Highest point above it" v={`${Math.max(0, V.top).toFixed(1)} m`} />
          <Row k="Outline length" v={fmtLen(V.perim)} />
          {V.above > 20 && <Row k="Truck trips (10 m³ each)" v={`≈ ${fmtN(Math.ceil(V.above / 10))}`} />}
          {V.how === 'level' && V.below > 0 && <Row k="Water it can hold" v={`≈ ${fmtN(V.below / 1000, 1)} million litres`} />}
        </div>
        <p className="fine">From the surface model (terrain + the model's heights) on {V.cell.toFixed(1)} m cells. Heights carry model error, so treat volumes as ± 20–30%.</p>
      </>) : <p className="msg">{s.volN ? `${s.volN} corner${s.volN > 1 ? 's' : ''}: add at least 3.` : 'Click Draw outline, then click the corners on the map.'}</p>}
    </ToolCard>
  );
}

export function DroneCard() {
  const s = useTools(x => x), D = s.drone, drawing = useEngine(x => x.drawing), pathN = useEngine(x => x.pathN);
  return (
    <ToolCard id="drone" icon={Navigation2} title="Drone flight plan" blurb="Turn a drawn path or a route into drone waypoints that stay clear of roofs and trees; export for QGroundControl, Google Earth or a spreadsheet.">
      <label className="field"><span>Follow</span>
        <Seg full value={s.drSrc} onChange={v => tools.setDroneParam({ drSrc: v })} options={[['path', 'My drawn path'], ['route', 'Route A → B']]} /></label>
      <div className="fields">
        <Num label="Clearance" unit="m" value={s.drClr} min={5} step={5} onChange={v => tools.setDroneParam({ drClr: v })} title="Kept above the tallest roof, tree or ground near the path" />
        <Num label="Look around" unit="m" value={s.drBuf} min={0} step={5} onChange={v => tools.setDroneParam({ drBuf: v })} title="How far to each side obstacles are looked for" />
        <Num label="Waypoint every" unit="m" value={s.drStep} min={5} step={5} onChange={v => tools.setDroneParam({ drStep: v })} />
        <Num label="Speed" unit="m/s" value={s.drSpeed} min={1} onChange={v => tools.setDroneParam({ drSpeed: v })} />
        <Num label="Height limit" unit="m above ground" value={s.drMax} min={10} step={10} onChange={v => tools.setDroneParam({ drMax: v })} wide title="India, Drone Rules 2021: 400 ft (about 120 m) in green zones; check the Digital Sky airspace map" />
      </div>
      <div className="btns">
        <button className={`btn sm${drawing ? ' on' : ''}`} onClick={() => { if (s.drSrc !== 'path') tools.set({ drSrc: 'path' }); engine.togglePath(); }}><PenLine size={13} />{drawing ? `Done (${pathN})` : 'Draw path'}</button>
        <button className="btn sm" disabled={!D || !D.geo} onClick={() => tools.exportDrone('plan')}><Download size={13} />QGroundControl</button>
        <button className="btn sm" disabled={!D || !D.geo} onClick={() => tools.exportDrone('kml')}><Download size={13} />KML</button>
        <button className="btn sm" disabled={!D} onClick={() => tools.exportDrone('csv')}><Download size={13} />CSV</button>
      </div>
      {D ? (<>
        <div className="kpis">
          <Kpi v={D.n} l="waypoints" /><Kpi v={fmtLen(D.len)} l="distance" /><Kpi v={`${Math.ceil(D.time / 60)} min`} l="flight time" title={`at ${D.speed} m/s, without take-off and landing`} />
        </div>
        <div className="rows">
          <Row k="Highest above ground" v={`${Math.round(D.maxAgl)} m`} />
          <Row k="Highest above take-off" v={`${Math.round(D.maxRel)} m`} />
          {D.abs && <Row k="Take-off ground level" v={`${D.home.toFixed(0)} m a.s.l.`} />}
        </div>
        {D.over ? <p className="msg warn">{D.over} waypoint{D.over > 1 ? 's are' : ' is'} above the {D.lim} m limit (red): lower the clearance or get airspace permission.</p>
          : <p className="msg">All waypoints are within the height limit.</p>}
        {!D.geo && <p className="msg warn">No georeferencing: only the CSV (local metres) can be exported.</p>}
        <p className="fine">Altitude = the tallest roof, tree or ground within {s.drBuf} m, plus {s.drClr} m. Heights come from one satellite image and miss wires, masts and new construction: keep the drone in sight.</p>
      </>) : <p className="msg">{s.drSrc === 'route' ? 'No route yet: find one in Respond or Relief, or switch to “My drawn path”.' : 'Click Draw path and click points on the map (2D or 3D), then Done.'}</p>}
    </ToolCard>
  );
}

export function SolarCard() {
  const s = useTools(x => x), S = s.solar;
  return (
    <ToolCard id="solar" icon={Sun} title="Rooftop solar" blurb="Yearly solar energy of every roof, with shading from taller buildings and trees traced along the sun's path.">
      <div className="fields">
        <Num label="Sunshine" unit="kWh/m²/yr" value={s.solGhi} min={500} step={50} onChange={v => tools.setSolarParam({ solGhi: v })} title="Most of India gets 1600–2200 kWh/m² a year (NIWE / NREL solar atlases)" />
        <Num label="Panel efficiency" unit="%" value={s.solEff} min={5} max={30} onChange={v => tools.setSolarParam({ solEff: v })} />
        <Num label="Usable roof" unit="%" value={s.solUse} min={10} max={100} step={5} onChange={v => tools.setSolarParam({ solUse: v })} title="Tanks, stairs and edges excluded" />
        <Num label="Performance ratio" value={s.solPr} min={0.4} max={1} step={0.01} onChange={v => tools.setSolarParam({ solPr: v })} title="Inverter, wiring, heat and dust losses: 0.75–0.8 is typical" />
        <Num label="Tariff" unit="₹/kWh" value={s.solTar} min={0} step={0.5} onChange={v => tools.setSolarParam({ solTar: v })} wide />
      </div>
      <div className="btns">
        <button className="btn sm primary" disabled={s.solBusy} onClick={() => tools.runSolar()}><Sun size={13} />{s.solBusy ? 'Tracing shadows…' : 'Calculate'}</button>
        <button className="btn sm" disabled={!S} onClick={() => tools.solarCSV()}><Download size={13} />CSV per building</button>
      </div>
      {S && (<>
        <div className="kpis">
          <Kpi v={`${fmtN(S.kWp)} kWp`} l="could be installed" /><Kpi v={`${fmtN(S.mwh)} MWh`} l="a year" tone="amber" />
          <Kpi v={`₹${fmtN(S.rupees / 1e5, 1)} L`} l="a year" title="Value at the tariff, in lakh rupees" />
        </div>
        <div className="rows">
          <Row k="CO₂ avoided" v={`≈ ${fmtN(S.co2)} t a year`} />
          <Row k="Roofs under 20% shading" v={`${S.low} of ${S.n}`} />
          {S.top.map((r: any) => <Row key={r.id} k={`Block ${r.id} · ${Math.round(r.area)} m² · ${Math.round(r.shade * 100)}% shaded`} v={`${fmtN(r.kWh / 1000, 1)} MWh`} />)}
        </div>
        <div className="bar" style={{ height: 8, background: `linear-gradient(90deg, rgb(${inferno(0.25)}), rgb(${inferno(1)}))` }} />
        <div className="keys"><span>less per m²</span><span style={{ marginLeft: 'auto' }}>more per m² (up to {fmtN(S.smax)} kWh/m²)</span></div>
        <p className="fine">Flat roofs assumed; shading traced on {S.nSun} sun positions for latitude {S.lat.toFixed(1)}°{S.latKnown ? '' : ' (assumed: no georeferencing)'}. Survey a roof before installing.</p>
      </>)}
    </ToolCard>
  );
}

export function MapOverlayCard() {
  const s = useTools(x => x), geo = useEngine(x => x.hasTerrain), saved = useEngine(x => x.current) && engine.data?.meta?.wms;
  return (
    <ToolCard id="wms" icon={MapIcon} title="Map overlay" blurb="Lay roads, names or boundaries from a web map service (OpenStreetMap, ISRO Bhuvan or any WMS) over the scene.">
      <label className="field"><span>Service</span>
        <Seg full value={s.wmsPreset} onChange={v => tools.set({ wmsPreset: v, ...(v === 'osm' ? { wmsLayers: 'OSM-WMS' } : {}) })} options={[['osm', 'OpenStreetMap'], ['custom', 'Another WMS']]} /></label>
      {s.wmsPreset === 'custom' && <label className="field"><span>WMS address (e.g. a Bhuvan WMS service)</span>
        <input type="text" placeholder="https://…/wms" value={s.wmsUrl} onChange={e => tools.set({ wmsUrl: e.target.value })} /></label>}
      <label className="field"><span>Layers</span><input type="text" value={s.wmsLayers} onChange={e => tools.set({ wmsLayers: e.target.value })} /></label>
      <Slider label="Opacity" value={s.wmsOp} min={0} max={1} step={0.05} onChange={v => tools.setWmsOpacity(v)} display={`${Math.round(s.wmsOp * 100)}%`} />
      <div className="btns">
        <button className="btn sm primary" disabled={!geo} onClick={() => tools.loadWms()}><MapIcon size={13} />Load overlay</button>
        {saved && !s.wmsOn && <button className="btn sm" onClick={() => tools.showWms()}>Show the saved one</button>}
        <button className="btn sm" disabled={!s.wmsOn} onClick={() => tools.hideWms()}>Hide</button>
      </div>
      {!geo ? <p className="msg warn">Needs a georeferenced (GeoTIFF) scene.</p> : <Msg m={s.wmsMsg} />}
      <p className="fine">Needs internet once; the map is saved with the scene and shown on the 2D map and the 3D surface.</p>
    </ToolCard>
  );
}

export function MosaicCard() {
  const s = useTools(x => x), scenes = useEngine(x => x.scenes).filter((x: any) => x.state === 'done' && x.meta && x.meta.corners_lonlat);
  return (
    <ToolCard id="mosaic" icon={LayoutGrid} title="Mosaic: join scenes" blurb="Join neighbouring GeoTIFF scenes into one larger scene, from their saved heights (no new model run).">
      {scenes.length ? <div className="fields">{scenes.map((x: any) => (
        <label key={x.name} className="check"><input type="checkbox" checked={s.mosSel.includes(x.name)}
          onChange={e => tools.set({ mosSel: e.target.checked ? [...s.mosSel, x.name] : s.mosSel.filter(n => n !== x.name) })} />{nice(x.name)}</label>))}</div>
        : <p className="msg">No georeferenced scenes yet.</p>}
      <div className="fields">
        <label className="field"><span>Name</span><input type="text" value={s.mosName} onChange={e => tools.set({ mosName: e.target.value })} /></label>
        <label className="field"><span>Detail</span><select value={s.mosGrid} onChange={e => tools.set({ mosGrid: +e.target.value })}>
          <option value={512}>Standard (512)</option><option value={1024}>High (1024)</option></select></label>
      </div>
      <button className="btn sm primary" onClick={() => tools.buildMosaic()}><LayoutGrid size={13} />Build mosaic</button>
      <Msg m={s.mosMsg} />
    </ToolCard>
  );
}

// ======================================== VALIDATE ========================================
export function ShadowCard() {
  const s = useTools(x => x), S = s.shadow, pick = useEngine(x => x.pick);
  return (
    <ToolCard id="shadow" icon={Sunset} title="Heights from shadows" blurb="Height = shadow length × tan(sun elevation). Checks tall buildings, which the model tends to under-estimate.">
      <div className="fields">
        <Num label="Sun elevation" unit="°" value={s.shEl} min={1} max={90} step={0.1} onChange={v => tools.setSunAngles({ shEl: v })} />
        <Num label="Sun azimuth" unit="°" value={s.shAz} min={0} max={360} step={0.1} onChange={v => tools.setSunAngles({ shAz: v })} title="Clockwise from north: 90 = east, 180 = south" />
      </div>
      <label className="field"><span>Or the image time (UTC)</span>
        <div className="btns" style={{ flexWrap: 'nowrap' }}><input type="text" placeholder="2024-03-15T05:30" value={s.shTime} onChange={e => tools.set({ shTime: e.target.value })} />
          <button className="btn sm" onClick={() => tools.sunFromTime()}>Compute</button></div></label>
      <div className="btns">
        <button className={`btn sm${pick === 'shadow' ? ' on' : ''}`} onClick={() => tools.toggleShadowPick()}><Ruler size={13} />{pick === 'shadow' ? 'Done measuring' : 'Measure a shadow'}</button>
        <button className="btn sm primary" disabled={s.shBusy} onClick={() => tools.runAutoShadows()}>{s.shBusy ? 'Measuring…' : 'Measure all buildings'}</button>
        <button className="btn sm" onClick={() => tools.clearShadows()}><Eraser size={13} />Clear</button>
      </div>
      <Msg m={s.shMsg} />
      {S && (<>
        {S.autoN != null && <p className="msg">Automatic: {S.autoN} of {S.total} blocks had a clear shadow.</p>}
        {S.rows.length ? <table className="t"><thead><tr><th>Building</th><th>Model</th><th>Shadow</th><th>Ratio</th></tr></thead>
          <tbody>{S.rows.map((r: any, k: number) => <tr key={k}><td>{r.label}</td><td>{r.model == null ? '–' : `${r.model.toFixed(1)} m`}</td><td>{r.H.toFixed(1)} m</td>
            <td>{r.model ? (r.H / Math.max(0.1, r.model)).toFixed(2) : '–'}</td></tr>)}</tbody></table> : <p className="msg">No measurements yet.</p>}
        {S.ratio && (<>
          <div className="big num">×{S.ratio.k.toFixed(2)}<small>shadow ÷ model, median of {S.ratio.n} building{S.ratio.n > 1 ? 's' : ''} ≥ 5 m</small></div>
          <button className="btn sm primary" onClick={() => tools.useShadowRatio()}>Use ×{S.ratio.k.toFixed(2)} for all buildings</button>
        </>)}
      </>)}
      <p className="fine">Take the sun angles from the image metadata. Shadows that fall on another building or leave the image are skipped; an off-nadir view adds error.</p>
    </ToolCard>
  );
}

export function FixCard() {
  const s = useTools(x => x), hasTerrain = useEngine(x => x.hasTerrain), cur = useEngine(x => x.current), c = cur && engine.data?.meta?.class_scale;
  return (
    <ToolCard id="fix" icon={TreePine} title="Fix tall objects" blurb="Scale building and tree heights, which the model tends to under-estimate: from shadows, from NASA ICESat-2 canopy heights, or by hand.">
      <div className="fields">
        <Num label="Buildings ×" value={s.fixB} min={0.5} max={3} step={0.05} onChange={v => tools.set({ fixB: v })} />
        <Num label="Trees ×" value={s.fixT} min={0.5} max={3} step={0.05} onChange={v => tools.set({ fixT: v })} />
      </div>
      <div className="btns">
        <button className="btn sm primary" disabled={s.fixBusy} onClick={() => tools.applyFix()}>Apply</button>
        <button className="btn sm" disabled={s.fixBusy || !hasTerrain} onClick={() => tools.fitTrees()} title="Top-of-canopy laser photons over the model's tree pixels (needs internet and a GeoTIFF scene)"><TreePine size={13} />Fit trees from ICESat-2</button>
        <button className="btn sm" disabled={s.fixBusy || !c} onClick={() => tools.applyFix(undefined, true)}>Reset</button>
      </div>
      {c && <Toggle label="Use the fixed heights everywhere" checked={s.fixOn} onChange={v => tools.setFixOn(v)} />}
      <div className="rows">
        <Row k="Active" v={c ? `buildings ×${(+c.buildings).toFixed(2)} · trees ×${(+c.trees).toFixed(2)}` : 'none (model heights)'} />
        {s.fixFit && <Row k={`ICESat-2: ${s.fixFit.n} canopy photons`} v={`${s.fixFit.canopy_median_m} m vs model ${s.fixFit.model_median_m} m`} />}
        {s.fixFit && <Row k="Tree error at the photons" v={`${s.fixFit.mae_before} → ${s.fixFit.mae_after} m`} />}
      </div>
      <Msg m={s.fixMsg} />
      <p className="fine">Applied to every view, the tools, validation and the “Height with tall-object fixes” download. Re-run a check above to see the effect.</p>
    </ToolCard>
  );
}

export function ErrorBarsCard() {
  const s = useTools(x => x), val = useEngine(x => x.val), cur = useEngine(x => x.current), conf = cur && engine.data?.meta?.conformal;
  useTools(x => x.rev);
  const srcs = Object.keys(VKEYS).filter(k => val[k] && val[k].conformal), src = srcs.includes(s.errSrc) ? s.errSrc : srcs[0], c = src && val[src].conformal;
  return (
    <ToolCard id="err" icon={Gauge} title="Calibrated error bars" blurb="Turn the consistency score into an error bar you can trust, calibrated on a check you ran for this scene (split conformal).">
      {!srcs.length ? <p className="msg warn">Run a check above first: a reference raster, 30+ surveyed points or ICESat-2.</p> : (<>
        <div className="fields">
          <label className="field"><span>Calibrate with</span><select value={src} onChange={e => tools.set({ errSrc: e.target.value })}>{srcs.map(k => <option key={k} value={k}>{VKEYS[k]}</option>)}</select></label>
          <label className="field"><span>Confidence</span><select value={s.errLev} onChange={e => tools.set({ errLev: e.target.value })}>
            <option value="0.68">68%</option><option value="0.90">90%</option><option value="0.95">95%</option></select></label>
        </div>
        <table className="t"><thead><tr><th>Level</th><th>k</th><th>Typical</th><th>Check</th></tr></thead>
          <tbody>{Object.entries(c.levels).map(([lv, x]: [string, any]) => <tr key={lv}><td>{Math.round(+lv * 100)}%</td><td>{x.k.toFixed(2)}</td><td>± {x.median_band_m.toFixed(1)} m</td><td>{x.coverage_check_pct.toFixed(0)}%</td></tr>)}</tbody></table>
        <div className="btns">
          <button className="btn sm primary" onClick={() => { tools.set({ errSrc: src }); tools.useErr(); }}>Use these error bars</button>
          <button className="btn sm" disabled={!conf} onClick={() => tools.useErr(true)}>Back to the consistency score</button>
        </div>
      </>)}
      {conf && <p className="msg">In use: {Math.round(+conf.level * 100)}% error bars from {VKEYS[conf.source] || conf.source} (k = {conf.k.toFixed(2)}).</p>}
      <Msg m={s.errMsg} />
      <p className="fine">Error bar = k × (consistency score + {c ? c.u0 : 0.25} m). “Check” fits k on a random half of the values and counts how many of the other half fall inside: it should be close to the level.</p>
    </ToolCard>
  );
}

export function TerrainSourceCard() {
  const s = useTools(x => x), cur = useEngine(x => x.current), t = (cur && engine.data?.meta?.terrain) || {}, geo = !!(cur && engine.data?.meta?.corners_lonlat);
  const [file, setFile] = useState<File | null>(null);
  return (
    <ToolCard id="dem" icon={Mountain} title="Terrain source" blurb="Use your own elevation model, e.g. ISRO CartoDEM from Bhuvan or SRTM, instead of Copernicus GLO-30.">
      <p className="msg">Now: <b>{t.source || 'no terrain (no georeferencing)'}</b>{t.laser && t.laser.offset_m != null ? `, levelled to ICESat-2 (${(-t.laser.offset_m).toFixed(1)} m)` : ''}.</p>
      <label className="field"><span>DEM GeoTIFF (must cover the whole scene)</span><input type="file" accept=".tif,.tiff" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
      <label className="field"><span>Its heights are</span>
        <Seg full value={s.demDatum} onChange={v => tools.set({ demDatum: v })} options={[['egm96', 'EGM96 (CartoDEM, SRTM)'], ['egm2008', 'EGM2008']]} /></label>
      <div className="btns">
        <button className="btn sm primary" disabled={!geo || !file} onClick={() => file && tools.useDem(file)}>Use this DEM</button>
        <button className="btn sm" disabled={!geo} onClick={() => tools.resetDem()}>Back to the default</button>
      </div>
      <Msg m={s.demMsg} />
    </ToolCard>
  );
}

export function GnssCard() {
  const s = useTools(x => x), [file, setFile] = useState<File | null>(null);
  return (
    <ToolCard id="gnss" icon={LocateFixed} title="GNSS & field points" blurb="Add control points from a GNSS receiver (CSV / GPX) or from the phone field app, instead of clicking them.">
      <label className="field"><span>CSV (lat, lon, alt) or GPX file</span><input type="file" accept=".csv,.txt,.gpx" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
      <label className="field"><span>Heights are</span>
        <Seg full value={s.gnssDatum} onChange={v => tools.set({ gnssDatum: v })} options={[['ellipsoid', 'GNSS (ellipsoid)'], ['egm96', 'Sea level, EGM96'], ['egm2008', 'EGM2008']]} /></label>
      <div className="btns">
        <button className="btn sm primary" disabled={!file} onClick={() => file && tools.gnssFile(file)}><Plus size={13} />Import file</button>
        <button className="btn sm" onClick={() => tools.gnssField()}><Smartphone size={13} />Load field-app points</button>
        <a className="btn sm" href="/field" target="_blank" rel="noreferrer">Open the field app</a>
      </div>
      <Msg m={s.gnssMsg} />
      <p className="fine">Points join the control-point list above; then Fit & apply. Most handheld GPS units report sea-level (EGM96) heights; raw GNSS and phone browsers report ellipsoidal ones. For a phone, start the app with <b>python app.py --lan</b> and open /field on the same Wi-Fi.</p>
    </ToolCard>
  );
}

// ======================================== DISASTER ========================================
export function PeopleCard() {
  const s = useTools(x => x), P = s.people;
  return (
    <Card id="tool-people" icon={Users} title="People at risk">
      <div className="fields">
        <Num label="Floor space per person" unit="m²" value={s.ppM2} min={2} onChange={v => tools.setPeopleParam({ ppM2: v })} title="Indian cities: roughly 8–15 m² per person; use the ward's census figure if you have it" />
        <Num label="Occupied" unit="%" value={s.ppOcc} min={0} max={100} step={5} onChange={v => tools.setPeopleParam({ ppOcc: v })} title="Share of floor area lived in" />
      </div>
      {P && (<>
        <div className="rows"><Row k="Residents in the scene" v={`≈ ${fmtN(Math.round(P.total))}`} /></div>
        {P.groups.map((g: any) => (
          <div className="rows" key={g.title}><h4 className="label">{g.title}</h4>
            {g.rows.map(([l, v]: any) => <Row key={l} k={l} v={`${fmtN(Math.round(v.p))} people · ${v.n} bldg`} />)}</div>))}
        {!P.groups.length && <p className="msg">Turn on a flood, flowing water, landslide risk or damage tool to count the people each affects.</p>}
      </>)}
      <p className="fine">Residents ≈ floors × footprint × occupied share ÷ floor space per person. Attached buildings count as one block. A planning estimate, not a census.</p>
    </Card>
  );
}

export function EvacuationCard() {
  const s = useTools(x => x), E = s.evac, sites = useEngine(x => x.sites);
  return (
    <ToolCard id="evac" icon={Footprints} title="Evacuation plan" blurb="Send each building's residents to the nearest relief camp that still has space, along routes that avoid deep water.">
      <label className="field"><span>Who leaves</span>
        <Seg full value={s.evWho} onChange={v => tools.set({ evWho: v, evac: null })} options={[['flood', 'Flooded'], ['slide', 'Landslide risk'], ['all', 'Everyone']]} /></label>
      <label className="field"><span>Travel</span><Seg full value={s.evMode} onChange={v => tools.set({ evMode: v, evac: null })} options={[['foot', 'On foot'], ['car', 'Car']]} /></label>
      <button className="btn sm primary" disabled={E && E.busy} onClick={() => tools.runEvac()}><Footprints size={13} />{E && E.busy ? 'Planning…' : 'Make the plan'}</button>
      {E && E.error && <p className="msg warn">{({ camps: 'No relief camps: the camp finder above found none. Lower the minimum camp area.',
        flood: 'Turn the flood on in Respond and set the water level first, or choose “Everyone”.', slide: 'Open Landslide risk in Prepare first, or choose another group.' } as any)[E.error]}</p>}
      {E && E.load && (<>
        <div className="kpis">
          <Kpi v={fmtN(Math.round(E.total))} l="people leave" /><Kpi v={E.n} l="buildings" />
          <Kpi v={`${Math.ceil(Math.max(0, ...E.far))} min`} l="longest trip" />
        </div>
        <div className="rows">{E.load.map((p: number, k: number) =>
          <Row key={k} sw={`rgb(${CAMP_COLORS[k % 5]})`} k={`Camp C${k + 1}`} v={`${fmtN(Math.round(p))} / ${fmtN(E.cap[k])} · ≤ ${Math.ceil(E.far[k])} min`} />)}</div>
        {E.unreach > 0 && <p className="msg warn">{fmtN(Math.round(E.unreach))} people in {E.unreachB} building{E.unreachB > 1 ? 's' : ''} (red) have no route through shallow water: they need boats or helicopters{E.pads ? ` (helipads H1–H${E.pads})` : ''}.</p>}
        {E.full > 0 ? <p className="msg warn">{fmtN(Math.round(E.full))} people do not fit in the camps (grey): find more camp space.</p> : <p className="msg">Everyone who can reach a camp has a place.</p>}
        <p className="fine">Buildings are coloured by their camp; hover one to see where it goes. Times are effort-weighted (roads fastest, water and slopes slower). Check on the ground.</p>
      </>)}
      {!sites && <p className="fine">Uses the camps found by the site finder on this page.</p>}
    </ToolCard>
  );
}

export function DamageCard() {
  const s = useTools(x => x), D = s.dmg, scenes = useEngine(x => x.scenes), cur = useEngine(x => x.current);
  const others = scenes.filter((x: any) => x.state === 'done' && x.name !== cur);
  return (
    <ToolCard id="dmg" icon={Construction} title="Damage: before / after" blurb="Compare a before image with this after-event scene: collapsed and damaged buildings, debris, lost tree canopy.">
      <label className="field"><span>Before image (this scene is the after image)</span>
        <select value={s.dmgBefore} onChange={e => tools.set({ dmgBefore: e.target.value })}>{others.map((x: any) => <option key={x.name} value={x.name}>{nice(x.name)}</option>)}</select></label>
      <div className="fields">
        <Num label="Collapsed if it lost ≥" unit="%" value={s.dmgCol} min={5} max={100} step={5} onChange={v => tools.setDmgParam({ dmgCol: v })} />
        <Num label="Damaged if it lost ≥" unit="%" value={s.dmgDam} min={5} max={100} step={5} onChange={v => tools.setDmgParam({ dmgDam: v })} />
        <Num label="Debris share" unit="% of lost volume" value={s.dmgDeb} min={5} max={100} step={5} onChange={v => tools.setDmgParam({ dmgDeb: v })} wide title="Rubble is commonly a quarter to a half of a building's lost volume" />
      </div>
      <button className="btn sm primary" disabled={!others.length} onClick={() => tools.runDamage()}><Construction size={13} />Compare</button>
      <Msg m={s.dmgMsg} />
      {D && (<>
        <div className="kpis"><Kpi v={D.col} l="collapsed" tone="hot" /><Kpi v={D.dam} l="damaged" tone="amber" /><Kpi v={D.intact} l="intact" tone="good" /></div>
        <div className="keys"><span><i className="sw" style={{ background: '#e5484d' }} />collapsed</span><span><i className="sw" style={{ background: '#f5a524' }} />damaged</span>
          <span><i className="sw" style={{ background: '#4fe08a' }} />intact</span><span><i className="sw" style={{ background: '#a770ff' }} />new</span><span><i className="sw" style={{ background: '#965a28' }} />trees / objects gone</span></div>
        <div className="rows">
          <Row k="People in collapsed or damaged buildings" v={`≈ ${fmtN(Math.round(D.people))}`} />
          <Row k="Debris to clear" v={`${fmtM3(D.debris)} · ${fmtN(Math.ceil(D.debris / 10))} trucks`} />
          {D.newN > 0 && <Row k="New structures (tents, sheds, rebuilt)" v={D.newN} />}
          {D.canopy && <Row k="Tree canopy lost" v={`${fmtHa(D.canopy.lost_m2)} of ${fmtHa(D.canopy.before_m2)}`} />}
          <Row k="Height lost outside buildings" v={fmtM3(D.groundLost)} />
        </div>
        <p className="fine">Before: {nice(D.before)}, {D.matched}{D.shift ? `; aligned by moving it ${Math.abs(D.shift.dx_m).toFixed(1)} m ${D.shift.dx_m >= 0 ? 'east' : 'west'}, ${Math.abs(D.shift.dy_m).toFixed(1)} m ${D.shift.dy_m >= 0 ? 'south' : 'north'}` : ''}. {D.notes.join(' ')}
          Both images go through the same model, so its biases mostly cancel; shadows, clouds and different view angles add false changes. Confirm on the ground.</p>
      </>)}
    </ToolCard>
  );
}

export function LandslideCard() {
  const s = useTools(x => x), S = s.slide, [msg, setMsg] = useState('');
  return (
    <ToolCard id="slide" icon={MountainSnow} title="Landslide risk" blurb="A screening map from slope, land cover and local relief (BIS IS 14496 Part 2 ratings), raised for heavy rain.">
      <Num label="Rain in 24 h" unit="mm" value={s.slRain} min={0} step={5} onChange={v => tools.setSlideRain(v)} />
      <button className="btn sm" onClick={() => setMsg(tools.slideRainFromTimeline() ? '' : 'Open the timeline in Respond (or its rain forecast) first.')}>From the timeline / forecast</button>
      {msg && <p className="msg warn">{msg}</p>}
      {S && S.none && <p className="msg warn">Needs terrain: a GeoTIFF scene.</p>}
      {S && !S.none && (<>
        <div className="rows">{SLIDE_CLS.map(([, name, col], k) =>
          <Row key={name} sw={`rgb(${col})`} k={name} v={`${Math.round(100 * S.count[k] / S.total)}% · ${fmtHa(S.count[k] * S.cell)}${k >= 2 ? ` · ${S.nb[k]} bldg` : ''}`} />)}</div>
        <div className="rows"><Row k="Rain factor" v={`×${S.f} · IMD ${S.imd}`} /></div>
        <p className="fine">Slope (≤15° 0.5 … &gt;45° 2.0) + land cover (bare 2.0, scrub 1.2, built / trees 0.8, fields 0.65) + relief within ~150 m (0.3 / 0.6 / 1.0), times the rain factor.
          Rock type, faults and groundwater are not included: use it to decide where to look, with GSI / NDMA landslide maps.</p>
      </>)}
    </ToolCard>
  );
}

export function ObservedFloodCard() {
  const s = useTools(x => x), O = s.obs, flood = useEngine(x => x.flood), [file, setFile] = useState<File | null>(null);
  return (
    <ToolCard id="obs" icon={SatelliteDish} title="Observed flood" blurb="Check the flood scenario against a real satellite flood map (Sentinel-1 radar or any water mask), or fit its water level to it.">
      <label className="field"><span>GeoTIFF</span><input type="file" accept=".tif,.tiff" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
      <div className="fields">
        <label className="field"><span>It contains</span><select value={s.obsKind} onChange={e => tools.set({ obsKind: e.target.value as any })}>
          <option value="auto">Detect automatically</option><option value="mask">A water mask (1 = water)</option><option value="db">Radar backscatter, dB</option><option value="linear">Radar backscatter, linear</option></select></label>
        <label className="field" title="Calm water reflects little radar: Sentinel-1 VV below about −18 dB. Empty = found automatically"><span>Water below (dB)</span>
          <input type="text" placeholder="auto" value={s.obsThr} onChange={e => tools.set({ obsThr: e.target.value })} /></label>
      </div>
      <div className="btns">
        <button className="btn sm primary" disabled={!file} onClick={() => file && tools.loadObs(file, file.name)}><SatelliteDish size={13} />Load & compare</button>
        <button className="btn sm" disabled={!O} onClick={() => tools.fitObsLevel()}>Fit the water level</button>
      </div>
      <Msg m={s.obsMsg} />
      {O && (<>
        <div className="rows">
          <Row k="Observed water" v={`${O.res.water_pct.toFixed(0)}% of the covered area`} />
          <Row k="Read as" v={O.res.kind === 'db' ? `radar, water < ${O.res.threshold_db.toFixed(1)} dB` : 'a water mask'} />
          {O.fit && <Row k="Best fitting water level" v={`+${O.fit.rise.toFixed(1)} m · CSI ${O.fit.csi.toFixed(2)}`} />}
        </div>
        {flood && O.m ? (<>
          <div className="kpis">
            <Kpi v={O.m.csi.toFixed(2)} l="CSI" title="Critical success index: hits ÷ (hits + misses + false alarms); 1 = perfect" />
            <Kpi v={`${Math.round(100 * O.m.pod)}%`} l="real water found" tone="blue" /><Kpi v={`${Math.round(100 * O.m.far)}%`} l="false alarms" tone="amber" />
          </div>
          <div className="keys"><span><i className="sw" style={{ background: '#2f7fe0' }} />both ({fmtHa(O.m.hit * O.cell)})</span><span><i className="sw" style={{ background: '#d63384' }} />missed ({fmtHa(O.m.miss * O.cell)})</span>
            <span><i className="sw" style={{ background: '#f5c518' }} />false alarm ({fmtHa(O.m.fa * O.cell)})</span></div>
        </>) : <p className="msg">Turn on the flood scenario above to compare (cyan = observed water).</p>}
        <p className="fine">Building pixels are left out (radar sees walls, not water, there). Radar misses water under trees and between tall buildings.</p>
      </>)}
    </ToolCard>
  );
}

export function FlowCard() {
  const s = useTools(x => x), F = s.flow, pick = useEngine(x => x.pick);
  return (
    <ToolCard id="flow" icon={Droplets} title="Flowing water (2D)" blurb="Water spreading over time from a breach, a river or a drain outlet: a 2D shallow-water simulation on the terrain (turns the level flood off).">
      <div className="fields">
        <Num label="Inflow per point" unit="m³/s" value={s.flQ} min={0} step={5} onChange={v => tools.set({ flQ: v })} title="A small breach: 10–50 m³/s" />
        <Num label="Rain" unit="mm/h" value={s.flRain} min={0} step={5} onChange={v => tools.set({ flRain: v })} />
        <Num label="Simulate" unit="hours" value={s.flHours} min={0.25} max={24} step={0.25} onChange={v => tools.set({ flHours: v })} wide />
      </div>
      <div className="btns">
        <button className={`btn sm${pick === 'flowsrc' ? ' on' : ''}`} onClick={() => tools.setPick(pick === 'flowsrc' ? null : 'flowsrc')}>{pick === 'flowsrc' ? 'Done' : <><Plus size={13} />Place inflow points ({s.flSrcN})</>}</button>
        <button className="btn sm primary" onClick={() => tools.runFlow()}>{s.flBusy ? <><Square size={12} />Stop</> : <><Play size={13} />Run</>}</button>
        <button className="btn sm" onClick={() => tools.clearFlow()}><Eraser size={13} />Clear</button>
      </div>
      {F && F.error && <p className="msg warn">{F.error}</p>}
      {F && F.cellM && (<>
        <Slider label="Time" value={s.flK} min={0} max={s.flMax} step={1} onChange={v => tools.setFlowTime(v)} display={F.clock} />
        <Toggle label="Show “time until wet” map" checked={s.flArr} onChange={v => tools.setFlowArr(v)} />
        {s.flArr && <div className="keys">{ARR_KEYS.slice(0, 5).map(([, , c], k) => <span key={k}><i className="sw" style={{ background: `rgb(${c})` }} />{k ? `by ${fmtDur(F.Tend * k / 4)}` : 'at the start'}</span>)}</div>}
        <div className="kpis"><Kpi v={fmtHa(F.wetM2)} l="under water" tone="blue" /><Kpi v={`${F.maxd.toFixed(1)} m`} l="deepest" /><Kpi v={F.wetB} l="buildings wet" tone="hot" title={`≈ ${fmtN(Math.round(F.ppl))} residents`} /></div>
        <div className="rows">
          <Row k="Water in so far" v={`${fmtM3(F.vin)}${F.done ? ` · ${fmtM3(F.vout)} left the scene` : ''}`} />
          <Row k="Standing in the scene" v={fmtM3(F.vol)} />
        </div>
        {!F.done && <p className="msg">Simulating… {F.pct}%</p>}
        <p className="fine">Local-inertial shallow-water model (Manning friction from land cover) on {F.Wc}×{F.Hc} cells of {F.cellM.toFixed(0)} m; buildings block the flow; water leaves at the scene edges.
          No drains, culverts or infiltration, and the 30 m terrain limits depths. A scenario, not a forecast.</p>
      </>)}
      {!F && <p className="msg">Place inflow points on the map, then Run.</p>}
    </ToolCard>
  );
}

export function ReportCard() {
  return (
    <Card id="tool-report" icon={FileText} title="Situation report">
      <p className="msg">The map, the 3D view and the results of every tool you used, on one printable page (save it as PDF).</p>
      <button className="btn primary" onClick={() => tools.openReport()}><FileText size={14} />Open the report</button>
    </Card>
  );
}
