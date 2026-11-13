// Cards for the newer tools (engine/tools.ts). Each card has an on/off switch in its title, like the route finder:
// off, it says in one line what the tool does; on, it shows its inputs, its result and draws its layer on the map.
import { useState, type ReactNode } from 'react';
import {
  Eye, Package, Navigation2, Sun, Map as MapIcon, LayoutGrid, Sunset, TreePine, Gauge, Mountain, LocateFixed, MountainSnow,
  Droplets, SatelliteDish, Footprints, Construction, Users, FileText, Plus, Eraser, Play, Square, PenLine, Ruler, Download, Smartphone, type LucideIcon,
  BrickWall, Unlink, ArrowDownToLine, Timer, Building2, PlaneLanding, Activity, Flame, Wind, Hospital, Tent, IndianRupee, Megaphone, RadioTower,
} from 'lucide-react';
import { engine, useEngine, useTools, tools } from '../engine/useEngine';
import { SLIDE_CLS, CAMP_COLORS, VKEYS, WARN_KEYS, POI_KINDS, COMPASS, fmtN, fmtM3, fmtLen, fmtHa, fmtDur, fmtRs, type ToolId } from '../engine/tools';
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
      <h4 className="label"><RadioTower size={12} /> Siren / radio coverage</h4>
      <div className="fields">
        <label className="field"><span>Cover</span><Seg full value={s.cvWhat} onChange={v => tools.set({ cvWhat: v })} options={[['buildings', 'Buildings'], ['all', 'Whole scene']]} /></label>
        <Num label="At most" unit="masts" value={s.cvMax} min={1} max={10} onChange={v => tools.set({ cvMax: v })} />
        <Num label="Stop at" unit="% covered" value={s.cvGoal} min={10} max={100} step={5} onChange={v => tools.set({ cvGoal: v })} wide />
      </div>
      <button className="btn sm primary" disabled={s.cvBusy} onClick={() => tools.suggestMasts()}><RadioTower size={13} />{s.cvBusy ? 'Searching…' : 'Suggest mast positions'}</button>
      {s.cover && <p className={`msg${s.cover.met ? '' : ' warn'}`}>{s.cover.n} mast{s.cover.n === 1 ? '' : 's'} see <b>{s.cover.pct.toFixed(0)}%</b> of {s.cover.what}{s.cover.met ? '.' : `: short of ${s.cover.goal}%. Raise the mast height, the range or the number of masts.`}</p>}
      <p className="fine">Tries the highest point of each of 100 blocks of the scene with the height and range above, and keeps adding the spot that sees the most not yet covered. For sirens set the range to how far one is heard.</p>
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
        <Seg full value={s.drSrc} onChange={v => tools.setDroneParam({ drSrc: v })} options={[['path', 'My drawn path'], ['route', 'Route A → B'], ['area', 'Search an area']]} /></label>
      {s.drSrc === 'area' && <Num label="Search lines every" unit="m" value={s.drSwath} min={5} step={5} onChange={v => tools.setDroneParam({ drSwath: v })} title="The width the camera sees on the ground, less an overlap: about the flying height for a 50° camera" />}
      <div className="fields">
        <Num label="Clearance" unit="m" value={s.drClr} min={5} step={5} onChange={v => tools.setDroneParam({ drClr: v })} title="Kept above the tallest roof, tree or ground near the path" />
        <Num label="Look around" unit="m" value={s.drBuf} min={0} step={5} onChange={v => tools.setDroneParam({ drBuf: v })} title="How far to each side obstacles are looked for" />
        <Num label="Waypoint every" unit="m" value={s.drStep} min={5} step={5} onChange={v => tools.setDroneParam({ drStep: v })} />
        <Num label="Speed" unit="m/s" value={s.drSpeed} min={1} onChange={v => tools.setDroneParam({ drSpeed: v })} />
        <Num label="Height limit" unit="m above ground" value={s.drMax} min={10} step={10} onChange={v => tools.setDroneParam({ drMax: v })} wide title="India, Drone Rules 2021: 400 ft (about 120 m) in green zones; check the Digital Sky airspace map" />
      </div>
      <div className="btns">
        <button className={`btn sm${drawing ? ' on' : ''}`} onClick={() => { if (s.drSrc === 'route') tools.set({ drSrc: 'path' }); engine.togglePath(); }}><PenLine size={13} />{drawing ? `Done (${pathN})` : s.drSrc === 'area' ? 'Draw the area' : 'Draw path'}</button>
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
          {D.area != null && <Row k="Search area" v={`${fmtHa(D.area)} · ${D.legs} legs`} />}
        </div>
        {D.over ? <p className="msg warn">{D.over} waypoint{D.over > 1 ? 's are' : ' is'} above the {D.lim} m limit (red): lower the clearance or get airspace permission.</p>
          : <p className="msg">All waypoints are within the height limit.</p>}
        {!D.geo && <p className="msg warn">No georeferencing: only the CSV (local metres) can be exported.</p>}
        <p className="fine">Altitude = the tallest roof, tree or ground within {s.drBuf} m, plus {s.drClr} m. Heights come from one satellite image and miss wires, masts and new construction: keep the drone in sight.</p>
      </>) : <p className="msg">{s.drSrc === 'route' ? 'No route yet: find one in Respond or Relief, or switch to “My drawn path”.' : s.drSrc === 'area' ? 'Click Draw the area, click its corners on the map (at least 3), then Done: the drone sweeps it back and forth.' : 'Click Draw path and click points on the map (2D or 3D), then Done.'}</p>}
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
  const s = useTools(x => x), hasTerrain = useEngine(x => x.hasTerrain), cur = useEngine(x => x.current), c = cur && engine.data?.meta?.class_scale, canopyInfo = cur && engine.data?.meta?.canopy;
  return (
    <ToolCard id="fix" icon={TreePine} title="Fix tall objects" blurb="Correct building and tree heights, which the model tends to under-estimate: from shadows, NASA laser data (ICESat-2, GEDI), Meta's canopy map, or by hand.">
      <Num label="Buildings ×" value={s.fixB} min={0.5} max={3} step={0.05} onChange={v => tools.set({ fixB: v })} />
      <label className="field"><span>Tree heights from</span>
        <Seg full value={s.fixTrees} onChange={v => v === 'canopy' && !canopyInfo ? tools.loadCanopy() : tools.set({ fixTrees: v })}
          options={[['scale', 'Model × factor'], ['canopy', 'Meta canopy map']]} /></label>
      {s.fixTrees === 'scale' ? (<>
        <Num label="Trees ×" value={s.fixT} min={0.5} max={3} step={0.05} onChange={v => tools.set({ fixT: v })} />
        <div className="btns">
          <button className="btn sm" disabled={s.fixBusy || !hasTerrain} onClick={() => tools.fitTrees('icesat2')} title="Top-of-canopy laser photons over the model's tree pixels (needs internet and a GeoTIFF scene)"><TreePine size={13} />Fit from ICESat-2</button>
          <button className="btn sm" disabled={s.fixBusy || !hasTerrain} onClick={() => tools.fitTrees('gedi')} title="GEDI rh98 (canopy top) on footprints the model calls trees (needs internet and a GeoTIFF scene)"><TreePine size={13} />Fit from GEDI</button>
        </div>
      </>) : canopyInfo && (
        <div className="rows">
          <Row k="Canopy map vs model on tree pixels" v={canopyInfo.canopy_median_m != null ? `${canopyInfo.canopy_median_m} m vs ${canopyInfo.model_median_m} m` : 'too few to compare'} />
          <Row k="Covered by the map" v={`${canopyInfo.coverage_pct}%`} />
        </div>)}
      <div className="btns">
        <button className="btn sm primary" disabled={s.fixBusy} onClick={() => tools.applyFix()}>Apply</button>
        <button className="btn sm" disabled={s.fixBusy || !c} onClick={() => tools.applyFix(undefined, true)}>Reset</button>
      </div>
      {c && <Toggle label="Use the fixed heights everywhere" checked={s.fixOn} onChange={v => tools.setFixOn(v)} />}
      <div className="rows">
        <Row k="Active" v={c ? `buildings ×${(+c.buildings).toFixed(2)} · trees ${c.trees_source === 'canopy' ? 'from the canopy map' : `×${(+c.trees).toFixed(2)}`}` : 'none (model heights)'} />
        {s.fixFit && s.fixFit.label === 'ICESat-2' && <Row k={`ICESat-2: ${s.fixFit.n} canopy photons`} v={`${s.fixFit.canopy_median_m} m vs model ${s.fixFit.model_median_m} m`} />}
        {s.fixFit && s.fixFit.label === 'ICESat-2' && <Row k="Tree error at the photons" v={`${s.fixFit.mae_before} → ${s.fixFit.mae_after} m`} />}
        {s.fixFit && s.fixFit.label === 'GEDI' && <Row k={`GEDI: ${s.fixFit.n} tree footprints`} v={`model ${s.fixFit.trees_model ? `${s.fixFit.trees_model.bias >= 0 ? '+' : ''}${s.fixFit.trees_model.bias.toFixed(1)} m off` : '–'}`} />}
        {s.fixFit && s.fixFit.label === 'GEDI' && s.fixFit.trees_canopy_map && <Row k="Canopy map at the same footprints" v={`${s.fixFit.trees_canopy_map.bias >= 0 ? '+' : ''}${s.fixFit.trees_canopy_map.bias.toFixed(1)} m off`} />}
      </div>
      <Msg m={s.fixMsg} />
      <p className="fine">Applied to every view, the tools, validation and the “Height with tall-object fixes” download. Re-run a check above to see the effect.
        The canopy map (Meta, Tolan et al. 2024, CC BY 4.0) is built from 2018–2020 imagery: trees felled or grown since then differ.</p>
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
          <Row k="Buildings the observed flood reached" v={`${O.hitB} · ≈ ${fmtN(Math.round(O.hitPpl))} residents`} />
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

// ======================================== RESPONSE TOOLS ========================================
const hrs = (h: number) => h < 48 ? `${h < 10 ? h.toFixed(1) : h.toFixed(0)} h` : `${(h / 24).toFixed(1)} days`;
const ppl = (p: number) => `≈ ${fmtN(Math.round(p))}`;

export function EmbankmentCard() {
  const s = useTools(x => x), B = s.bund, pick = useEngine(x => x.pick), flood = useEngine(x => x.flood), fsrc = useEngine(x => x.fsrc);
  return (
    <ToolCard id="bund" icon={BrickWall} title="Embankment what-if" blurb="Draw a bund or a sandbag wall and see what it keeps dry at this water level, and how many sandbags it takes.">
      <Num label="Height above the ground" unit="m" value={s.bundH} min={0.2} max={10} step={0.1} onChange={v => tools.setBundH(v)} />
      <div className="btns">
        <button className={`btn sm${pick === 'bund' ? ' on' : ''}`} onClick={() => tools.setPick(pick === 'bund' ? null : 'bund')}><PenLine size={13} />{pick === 'bund' ? `Done (${s.bundN})` : 'Draw the line'}</button>
        <button className="btn sm" disabled={!s.bundN} onClick={() => tools.clearBund()}><Eraser size={13} />Clear</button>
      </div>
      {fsrc === 'all' && <p className="msg warn">“All low ground” ignores barriers: choose Scene edges or Points I click in the flood card.</p>}
      {B ? (<>
        {B.nb != null ? (<>
          <div className="kpis">
            <Kpi v={B.nb} l="buildings kept dry" tone="good" title={`${ppl(B.ppl)} residents`} />
            <Kpi v={fmtHa(B.kept)} l="ground kept dry" tone="blue" />
            <Kpi v={B.still} l="still flooded" tone={B.still ? 'hot' : undefined} />
          </div>
          <p className="msg">{B.nb ? <>It protects <b>{ppl(B.ppl)}</b> people at +{B.rise.toFixed(1)} m.</> : 'It protects no building at this water level: the water goes round it, over it, or was not coming this way.'}
            {B.hold != null && <> The protected ground starts to flood at <b>+{B.hold.toFixed(1)} m</b>{B.hold - B.rise < 0.5 ? ': less than half a metre to spare' : ''}.</>}</p>
        </>) : <p className="msg">{flood ? 'Draw the line to see what it protects.' : 'Turn the flood scenario on to see what it protects.'}</p>}
        <div className="rows">
          <Row k="Length" v={fmtLen(B.len)} />
          <Row k="Sandbags" v={B.bags == null ? 'too high for sandbags (over 2 m)' : `≈ ${fmtN(B.bags)}`} />
          <Row k={B.bags == null ? 'Earth for a bund' : 'Or earth for a bund'} v={fmtM3(B.earth)} />
        </div>
        <p className="fine">The line is raised {B.h} m above the ground along it; the flood scenario, the timeline and the flowing water all meet it. Sandbag count after the US Army Corps of Engineers
          pyramid wall; earth for a 1 m crest with 1 : 2 sides. No seepage, no failure, and the 30 m terrain cannot show small gaps: an engineer must check the line.</p>
      </>) : <p className="msg">Click Draw the line, then click along where the wall would stand (2D or 3D).</p>}
    </ToolCard>
  );
}

export function CutoffCard() {
  const s = useTools(x => x), C = s.cut;
  return (
    <ToolCard id="cut" icon={Unlink} title="Cut-off areas" blurb="Buildings that stay dry but that nobody can leave or reach at this water level: the islands a flood makes.">
      <label className="field"><span>Reached</span><Seg full value={s.cutMode} onChange={v => tools.setParam('cut', { cutMode: v }, 0)} options={[['foot', 'On foot (≤ 0.5 m water)'], ['car', 'By vehicle (≤ 0.3 m)']]} /></label>
      {C && C.error ? <p className="msg warn">Turn the flood scenario on first.</p> : C && (<>
        <div className="kpis">
          <Kpi v={C.nb} l="dry but cut off" tone="hot" /><Kpi v={ppl(C.ppl)} l="people on islands" /><Kpi v={C.n} l={C.n === 1 ? 'island' : 'islands'} />
        </div>
        <div className="rows">
          {C.isles.map((it: any, k: number) => <Row key={k} sw="#d63384" k={`Island ${k + 1}${it.area ? ` · ${fmtHa(it.area)}` : ' · water at the walls'}`} v={`${ppl(it.ppl)} people · ${it.nb} bldg`} />)}
          <Row k="Flooded buildings also out of reach" v={`${C.wetB} · ${ppl(C.wetP)} people`} />
        </div>
        {C.nb + C.wetB > 0 ? <p className="msg">These need boats or helicopters: use the route finder's Boat mode, and Relief for helipads.</p> : <p className="msg">Every building can still be reached from the edge of the scene.</p>}
        <p className="fine">A building counts as reachable when ground next to it connects to the edge of the scene without crossing buildings, steep ground or water deeper than the limit.
          Roads leaving the scene may be cut further on, and bridges are not in the terrain model.</p>
      </>)}
    </ToolCard>
  );
}

export function PondingCard() {
  const s = useTools(x => x), P = s.pond;
  return (
    <ToolCard id="pond" icon={ArrowDownToLine} title="Ponding & pump sites" blurb="The hollows that keep their water after the river drops, how much there is to pump, and the deepest point of each for the pump.">
      <div className="fields">
        <Num label="Count water deeper than" unit="m" value={s.pdMin} min={0.05} step={0.05} onChange={v => tools.setParam('pond', { pdMin: v })} />
        <Num label="Ponds larger than" unit="m²" value={s.pdArea} min={0} step={50} onChange={v => tools.setParam('pond', { pdArea: v })} />
        <Num label="Pump" unit="L/s" value={s.pdRate} min={1} step={5} onChange={v => tools.setParam('pond', { pdRate: v })} wide title="A 4-inch trailer pump moves about 25 L/s, a 6-inch one about 50–80 L/s" />
      </div>
      {P && (<>
        <div className="kpis"><Kpi v={P.n} l={P.n === 1 ? 'pond' : 'ponds'} tone="blue" /><Kpi v={fmtM3(P.vol)} l="to pump out" /><Kpi v={P.nb} l="buildings in them" tone={P.nb ? 'amber' : undefined} /></div>
        <div className="rows">{P.list.map((q: any, k: number) =>
          <Row key={k} sw="#b9a2ff" k={`P${k + 1} · ${fmtHa(q.area)} · ${q.maxd.toFixed(1)} m deep${q.nb ? ` · ${q.nb} bldg` : ''}`} v={`${fmtM3(q.vol)} · ${hrs(q.hours)}`} />)}</div>
        {!P.n && <p className="msg">No hollow of that size {P.on ? 'holds water at this level' : 'in the terrain'}.</p>}
        <p className="fine">{P.on ? 'Water the current flood leaves behind' : 'Flood is off: every hollow, filled to its brim (after heavy rain)'}. A hollow is ground that cannot drain to the edge of the scene over the surface;
          pump time is for one pump with no inflow. Drains, culverts and soakage are not in the 30 m terrain, which also smooths small hollows away.</p>
      </>)}
    </ToolCard>
  );
}

export function WarningCard() {
  const s = useTools(x => x), W = s.warn;
  return (
    <ToolCard id="warn" icon={Timer} title="Warning time" blurb="How long each building has before the water arrives, and who cannot walk to a camp in that time.">
      <div className="fields">
        <Num label="Time to get ready" unit="min" value={s.wnDelay} min={0} step={5} onChange={v => tools.setParam('warn', { wnDelay: v })} title="From the warning to leaving the door" />
        <label className="field"><span>Travel</span><Seg full value={s.evMode === 'boat' ? 'foot' : s.evMode} onChange={v => tools.setParam('warn', { evMode: v, evac: null }, 0)} options={[['foot', 'On foot'], ['car', 'Car']]} /></label>
      </div>
      {W && W.error ? <p className="msg warn">Run Flowing water in Respond, or open the Rain & river timeline there, first: they give the arrival times.</p> : W && (<>
        <div className="rows">{WARN_KEYS.map(([, l, c], k) => <Row key={l} sw={`rgb(${c})`} k={l} v={`${ppl(W.rows[k].p)} people · ${W.rows[k].n} bldg`} />)}</div>
        {W.camps ? (W.late.n ? <p className="msg warn"><b>{ppl(W.late.p)}</b> people in {W.late.n} building{W.late.n > 1 ? 's' : ''} cannot reach a camp before the water, even leaving {W.delay} min after the warning: move them first or send transport.</p>
          : <p className="msg">Everyone the water reaches can walk to a camp in time, leaving {W.delay} min after the warning.</p>) : <p className="msg warn">No relief camp found: only the arrival times are shown.</p>}
        {W.top.length > 0 && <table className="t"><thead><tr><th>Block</th><th>Water in</th><th>To camp</th><th>Spare</th></tr></thead>
          <tbody>{W.top.map((r: any) => <tr key={r.id}><td>#{r.id}</td><td>{fmtDur(r.arr * 60)}</td><td>{r.travel == null ? '–' : r.travel < Infinity ? `${Math.ceil(r.travel)} min` : 'no route'}</td>
            <td>{r.lead == null || !(r.lead > -Infinity) ? '–' : r.lead < 0 ? <span className="warn">late</span> : fmtDur(r.lead * 60)}</td></tr>)}</tbody></table>}
        <button className="btn sm" onClick={() => tools.warnCSV()}><Download size={13} />Priority list (CSV)</button>
        <p className="fine">Arrival times from {W.src === 'flow' ? 'the last Flowing water run' : 'the Rain & river timeline (whole hours)'}; walking times over dry-weather routes to the nearest camp, ignoring its capacity.
          Hover a building for its own numbers. A scenario: real floods can arrive faster.</p>
      </>)}
    </ToolCard>
  );
}

export function RoofRefugeCard() {
  const s = useTools(x => x), R = s.roof;
  return (
    <ToolCard id="roof" icon={Building2} title="Rooftop refuge" blurb="Flooded buildings whose roof stays above the water, how many people each can hold, and who has no roof within reach.">
      <div className="fields">
        <Num label="Roof above water by" unit="m" value={s.rfFree} min={0} step={0.5} onChange={v => tools.setParam('roof', { rfFree: v })} />
        <Num label="Space per person" unit="m²" value={s.rfPer} min={0.5} step={0.5} onChange={v => tools.setParam('roof', { rfPer: v })} title="1–2 m² for a few hours' wait" />
        <Num label="Usable roof" unit="%" value={s.rfUse} min={5} max={100} step={5} onChange={v => tools.setParam('roof', { rfUse: v })} />
        <Num label="Neighbours within" unit="m" value={s.rfDist} min={0} step={25} onChange={v => tools.setParam('roof', { rfDist: v })} title="How far people can wade or be ferried to another roof" />
      </div>
      {R && R.error ? <p className="msg warn">Turn the flood scenario on first.</p> : R && (<>
        <div className="kpis"><Kpi v={R.roofs} l="refuge roofs" tone="good" /><Kpi v={fmtN(R.cap)} l="people they hold" /><Kpi v={ppl(R.left)} l="with no roof" tone={R.left ? 'hot' : undefined} /></div>
        <div className="keys"><span><i className="sw" style={{ background: '#4fe08a' }} />roof refuge</span><span><i className="sw" style={{ background: '#f5a524' }} />residents moved to a neighbour's roof</span>
          <span><i className="sw" style={{ background: '#e5484d' }} />no roof within reach</span></div>
        <div className="rows">
          <Row k="People in flooded buildings" v={ppl(R.people)} />
          <Row k="Safe on their own roof" v={ppl(R.own)} />
          <Row k="Fit on a neighbour's roof" v={ppl(R.moved)} />
          {R.top.map((r: any) => <Row key={r.id} k={`Block ${r.id} · ${Math.round(r.area)} m² · ${r.free.toFixed(1)} m above water`} v={`${fmtN(r.cap)} people`} />)}
        </div>
        {R.left > 0 && <p className="msg warn">{ppl(R.left)} people in {R.leftB} building{R.leftB > 1 ? 's' : ''} (red) have no roof to wait on: first for boats and helicopters.</p>}
        <p className="fine">Roof level = ground + the model's building height, which tends to come out too low, so roofs are, if anything, higher than shown. Flat, reachable roofs are assumed: tin and tiled roofs do not hold people.</p>
      </>)}
    </ToolCard>
  );
}

export function PadApproachCard() {
  const s = useTools(x => x), A = s.pad;
  return (
    <ToolCard id="pad" icon={PlaneLanding} title="Helipad approach" blurb="From which directions a helicopter can come in to each landing site without roofs, trees or rising ground in the way.">
      <div className="fields">
        <Num label="Approach slope" unit="%" value={s.paSlope} min={3} max={50} step={0.5} onChange={v => tools.setParam('pad', { paSlope: v })} title="12.5% is 1 in 8: nothing may rise above that line from the edge of the landing circle (ICAO heliport approach surface, performance class 2 / 3)" />
        <Num label="Check out to" unit="m" value={s.paDist} min={50} max={1000} step={50} onChange={v => tools.setParam('pad', { paDist: v })} />
      </div>
      {A && A.none ? <p className="msg warn">No landing site found: relax the site rules above.</p> : A && A.pads && (<>
        {A.pads.map((p: any) => (
          <div className="site" key={p.label}>
            <b className="tag" style={{ background: '#ffd400' }}>{p.label}</b>
            <span>{p.nClear ? <>{p.nClear} of {COMPASS.length} directions clear · best from <b>{p.best}</b></> : <span className="warn">no clear approach</span>}</span><span />
            <small>{p.through.length ? `straight in and out: ${p.through.join(', ')}` : p.nClear ? 'no straight in-and-out line: the pilot must turn after take-off' : ''}{p.block ? `${p.nClear ? ' · ' : ''}worst: ${p.block}` : ''}</small>
          </div>))}
        <p className="fine">On the map: thick green = the best way in, thin green = clear, red = something over 1 m rises above the {A.slope}% line from the edge of the circle within {A.far} m (a 14° wide sector each).
          North is taken as up in the image. Wires, masts and poles are not in the height model, and tall objects come out too low: a pilot or ground party must confirm.</p>
      </>)}
    </ToolCard>
  );
}

export function CampNeedsCard() {
  const s = useTools(x => x);
  useEngine(x => x.sites);
  const N = tools.campNeeds();
  return (
    <Card id="tool-needs" icon={Tent} title="Camp needs">
      <div className="fields">
        <Num label="For" unit="days" value={s.ndDays} min={1} max={90} onChange={v => tools.set({ ndDays: v })} />
        <Num label="Water" unit="L / person / day" value={s.ndWater} min={5} onChange={v => tools.set({ ndWater: v })} title="Sphere: at least 15 L for drinking, cooking and washing" />
        <Num label="People per toilet" value={s.ndToilet} min={5} step={5} onChange={v => tools.set({ ndToilet: v })} title="Sphere: 1 per 20 people (1 per 50 in the first days)" />
        <Num label="People per tent" value={s.ndTent} min={1} onChange={v => tools.set({ ndTent: v })} title="A 16 m² family tent: 3.5 m² covered space per person" />
      </div>
      {N ? (<>
        <table className="t"><thead><tr><th>Camp</th><th>People</th><th>Water / day</th><th>Toilets</th><th>Tents</th><th>Food / day</th></tr></thead>
          <tbody>{N.rows.map((r: any) => <tr key={r.label}><td>{r.label}</td><td>{fmtN(Math.round(r.p))}</td><td>{fmtN(r.water / 1000, 1)} kL</td><td>{r.toilets}</td><td>{r.tents}</td><td>{fmtN(Math.round(r.food))} kg</td></tr>)}</tbody></table>
        <div className="rows">
          <Row k={`Water for ${N.days} days`} v={`${fmtN(N.water * N.days / 1000, 1)} kL · ${fmtN(Math.ceil(N.water * N.days / 10000))} tanker loads`} />
          <Row k={`Food for ${N.days} days`} v={`${fmtN(N.food * N.days / 1000, 1)} t`} />
          <Row k="Toilets · tents" v={`${fmtN(N.toilets)} · ${fmtN(N.tents)}`} />
        </div>
        <button className="btn sm" onClick={() => tools.needsCSV()}><Download size={13} />CSV per camp</button>
        <p className="fine">{N.planned ? 'People from the evacuation plan above.' : 'No evacuation plan yet: every camp is counted full.'} Sphere minimum standards; food as a 2 100 kcal dry ration (0.56 kg per person a day); tankers of 10 000 L.</p>
      </>) : <p className="msg">No relief camp found yet: the camp finder above lists them.</p>}
    </Card>
  );
}

export function RunoutCard() {
  const s = useTools(x => x), R = s.runout;
  return (
    <ToolCard id="runout" icon={Activity} title="Landslide runout" blurb="Where a slide from the high-risk slopes would travel, and the buildings, roads and river below it.">
      <label className="field"><span>Slides start on</span><Seg full value={s.roSrc} onChange={v => tools.setParam('runout', { roSrc: v }, 0)} options={[['vh', 'Very high risk'], ['h', 'High and very high']]} /></label>
      <Num label="Reach angle" unit="°" value={s.roAng} min={5} max={45} onChange={v => tools.setParam('runout', { roAng: v })} title="The slide stops where the line from its source down to it is flatter than this. Dry rock and debris: about 30°; wet debris flows: 10–20°" />
      {R && R.none ? <p className="msg warn">Needs terrain: a GeoTIFF scene.</p> : R && (<>
        <div className="kpis"><Kpi v={fmtHa(R.m2)} l="in a runout path" tone="amber" /><Kpi v={R.nb} l="buildings below" tone={R.nb ? 'hot' : undefined} title={`${ppl(R.ppl)} residents`} /><Kpi v={fmtLen(R.maxRun)} l="longest run" /></div>
        <div className="rows">
          <Row sw="#ffd60a" k="Source slopes" v={fmtHa(R.srcM2)} />
          <Row sw="#c85014" k="People in the paths" v={ppl(R.ppl)} />
          <Row k="Road buried" v={`${fmtN(Math.round(R.roadM2))} m²`} />
          <Row k="Reaches a river or lake" v={R.dam ? 'yes' : 'no'} />
        </div>
        {R.dam && <p className="msg warn">A slide into the river can dam it; the lake behind it and its sudden release threaten the valley downstream.</p>}
        {!R.nSrc && <p className="msg">No slope in that risk class at this rainfall: raise the rain in Landslide risk, or include “high”.</p>}
        <p className="fine">Energy-line model (Heim's reach angle): from each source cell the mass follows the steeper ways down and stops where a line dropping at the reach angle meets the ground.
          It shows where material could go, not how much or how fast; sources come from the Landslide risk screening above (same rain). Check with GSI / NDMA maps.</p>
      </>)}
    </ToolCard>
  );
}

export function QuakeCard() {
  const s = useTools(x => x), Q = s.quake;
  useTools(x => x.dmg);
  const hasDmg = !!tools.T.dmg;
  return (
    <ToolCard id="quake" icon={Construction} title="Earthquake: debris & access" blurb="A what-if: buildings collapse, their rubble spreads over the streets, and some neighbourhoods can no longer be reached.">
      <label className="field"><span>Which buildings collapse</span>
        <Seg full value={s.qkSrc} onChange={v => tools.setParam('quake', { qkSrc: v }, 0)} options={[['floors', 'A share of the tall ones'], ['dmg', 'From Damage: before / after']]} /></label>
      {s.qkSrc === 'dmg' && !hasDmg && <p className="msg warn">Run Damage: before / after in Assess first (this scene as the after image).</p>}
      <div className="fields">
        {s.qkSrc === 'floors' && <Num label="Floors at least" value={s.qkFloors} min={1} onChange={v => tools.setParam('quake', { qkFloors: v })} />}
        {s.qkSrc === 'floors' && <Num label="Share that collapses" unit="%" value={s.qkShare} min={0} max={100} step={5} onChange={v => tools.setParam('quake', { qkShare: v })} />}
        <Num label="Rubble reaches" unit="% of height" value={s.qkReach} min={0} max={200} step={10} onChange={v => tools.setParam('quake', { qkReach: v })} title="Rubble commonly spreads a third to two thirds of a building's height from its walls" />
        <label className="field"><span>Access</span><Seg full value={s.qkMode === 'boat' ? 'car' : s.qkMode} onChange={v => tools.setParam('quake', { qkMode: v }, 0)} options={[['car', 'Vehicles'], ['foot', 'On foot']]} /></label>
      </div>
      {Q && (<>
        <div className="kpis"><Kpi v={Q.nCol} l="collapsed" tone="hot" title={`${ppl(Q.pCol)} residents`} /><Kpi v={Q.cutB} l="cut off by debris" tone="amber" title={`${ppl(Q.cutP)} residents`} /><Kpi v={fmtHa(Q.debrisM2)} l="under debris" /></div>
        <div className="keys"><span><i className="sw" style={{ background: '#e5484d' }} />collapsed</span><span><i className="sw" style={{ background: '#965a28' }} />debris</span><span><i className="sw" style={{ background: '#d63384' }} />cut off</span></div>
        <div className="rows">
          <Row k="People in collapsed buildings" v={ppl(Q.pCol)} />
          <Row k="People cut off" v={ppl(Q.cutP)} />
          <Row k="Road under debris" v={`${fmtN(Math.round(Q.roadM2))} m²`} />
          <Row k="Debris to clear" v={`${fmtM3(Q.debris)} · ${fmtN(Math.ceil(Q.debris / 10))} trucks`} />
        </div>
        <p className="fine">{Q.src === 'dmg' ? 'The buildings the before / after comparison found collapsed.' : `Of ${Q.cand} blocks with ${s.qkFloors}+ floors, a fixed ${s.qkShare}% picked by block number: a scenario, not a prediction (the image says nothing about how a building is built).`} Rubble
          spreads {s.qkReach}% of each building's height and stops at standing buildings; a building is cut off when it could be reached from the edge of the scene before and cannot now. Debris volume uses the debris share set in Damage.</p>
      </>)}
    </ToolCard>
  );
}

export function FireCard() {
  const s = useTools(x => x), F = s.fire, pick = useEngine(x => x.pick);
  return (
    <ToolCard id="fire" icon={Flame} title="Fire spread" blurb="How a forest or settlement fire spreads with fuel, slope and wind, and whether a firebreak holds it.">
      <div className="fields">
        <Num label="Wind" unit="km/h" value={s.fiWind} min={0} max={100} step={5} onChange={v => tools.setParam('fire', { fiWind: v })} />
        <label className="field"><span>Wind from</span><select value={s.fiDir} onChange={e => tools.setParam('fire', { fiDir: +e.target.value }, 0)}>
          {COMPASS.filter((_, k) => k % 2 === 0).map((n, k) => <option key={n} value={k * 45}>{n}</option>)}</select></label>
        <Num label="Simulate" unit="hours" value={s.fiHours} min={0.5} max={48} step={0.5} onChange={v => tools.setParam('fire', { fiHours: v, fiT: v })} wide />
      </div>
      <div className="btns">
        <button className={`btn sm${pick === 'fire' ? ' on' : ''}`} onClick={() => tools.setPick(pick === 'fire' ? null : 'fire')}>{pick === 'fire' ? 'Done' : <><Flame size={13} />Start points ({s.fiIgn})</>}</button>
        <button className={`btn sm${pick === 'firebreak' ? ' on' : ''}`} onClick={() => tools.setPick(pick === 'firebreak' ? null : 'firebreak')}><PenLine size={13} />{pick === 'firebreak' ? 'Done' : `Draw a firebreak (${s.fiBrk})`}</button>
        <button className="btn sm" onClick={() => tools.clearFire()}><Eraser size={13} />Clear</button>
      </div>
      {F && F.none ? <p className="msg warn">Needs the land-cover map of a processed scene.</p> : F && F.m2 != null ? (<>
        <Slider label="After" value={s.fiT} min={0} max={s.fiHours} step={0.25} onChange={v => tools.setFireTime(v)} display={fmtDur(s.fiT * 3600)} />
        <div className="kpis"><Kpi v={fmtHa(F.m2)} l="burnt" tone="hot" /><Kpi v={F.nb} l="buildings reached" tone="amber" title={`${ppl(F.ppl)} residents`} />
          <Kpi v={F.first < Infinity ? fmtDur(F.first * 60) : '–'} l="to the first building" /></div>
        {F.base && <p className={`msg${F.base.m2 > F.m2 ? '' : ' warn'}`}>{F.base.m2 > F.m2 ? <>The firebreak saves <b>{fmtHa(F.base.m2 - F.m2)}</b> and {F.base.nb - F.nb} building{F.base.nb - F.nb === 1 ? '' : 's'} by then.</>
          : 'The firebreak makes no difference by then: the fire is not there yet, or goes round it.'}</p>}
        <p className="fine">Bright = burnt first. Spread on flat ground without wind: scrub and grass 6, fields 4, trees 3, built-up 0.6, buildings 0.4 m/min; bare ground, roads and water do not burn.
          It doubles for every 10° uphill and runs faster downwind, slower against it. No spotting embers, fuel moisture or fire-fighting: a screening scenario, not a fire-behaviour forecast.</p>
      </>) : <p className="msg">Click Start points, then click where the fire begins (2D or 3D).</p>}
    </ToolCard>
  );
}

export function SurgeCard() {
  const s = useTools(x => x), X = s.surge, f = useEngine(x => x.floodSum);
  useTools(x => x.people);
  const fp = tools.floodPeople();
  return (
    <ToolCard id="surge" icon={Wind} title="Cyclone: surge & wind" blurb="Sea water pushed in from the coast side of the scene by a storm surge, and the buildings with nothing to shelter them from the wind.">
      <div className="fields">
        <label className="field"><span>The sea is to the</span><Seg full value={s.sgSide} onChange={v => tools.setSurge({ sgSide: v })} options={[['N', 'N'], ['E', 'E'], ['S', 'S'], ['W', 'W']]} /></label>
        <Num label="Surge + tide" unit="m" value={s.sgH} min={0} max={15} step={0.5} onChange={v => tools.setSurge({ sgH: v })} title="Above the sea level in the terrain model. IMD bulletins give the expected surge; add the tide" />
        <label className="field wide"><span>Wind from</span><select value={s.sgDir} onChange={e => tools.setSurge({ sgDir: +e.target.value })}>
          {COMPASS.filter((_, k) => k % 2 === 0).map((n, k) => <option key={n} value={k * 45}>{n}</option>)}</select></label>
      </div>
      {X && X.none ? <p className="msg warn">Needs terrain: a GeoTIFF scene.</p> : X && (<>
        <div className="kpis">
          <Kpi v={f ? `${f.wetPct.toFixed(0)}%` : '–'} l="ground under the surge" tone="blue" />
          <Kpi v={f ? f.sub + f.part : '–'} l="buildings flooded" tone="hot" title={fp ? `${ppl(fp.wet)} residents` : undefined} />
          <Kpi v={X.exposed} l="exposed to the wind" tone="amber" title={`${ppl(X.ppl)} residents`} />
        </div>
        <div className="rows">
          <Row k="Sea level with the surge" v={`${X.level.toFixed(1)} m a.s.l. (sea at ${X.sea.toFixed(1)} m)`} />
          {fp && <Row k="People in flooded buildings" v={ppl(fp.wet)} />}
          <Row sw="#ff8c00" k="People in wind-exposed buildings" v={ppl(X.ppl)} />
          {X.top.map((b: any) => <Row key={b.id} k={`Block ${b.id}: tallest exposed`} v={`${b.h.toFixed(0)} m`} />)}
        </div>
        <p className="fine">This sets the flood scenario: water enters only from that side, up to the lowest ground on it plus the surge, and reaches only ground it can flow to (see Respond for routes, cut-off areas and roofs).
          No waves, no rain and no weakening inland. Wind-exposed = nothing taller within ten times its height upwind; north is taken as up in the image.</p>
      </>)}
    </ToolCard>
  );
}

export function FacilitiesCard() {
  const s = useTools(x => x), P = s.poi, geo = useEngine(x => x.hasTerrain), [file, setFile] = useState<File | null>(null);
  return (
    <Card id="tool-poi" icon={Hospital} title="Critical facilities" right={P && <input type="checkbox" className="switch" aria-label="Show facilities on the map" checked={s.poiOn} onChange={e => tools.setPoiOn(e.target.checked)} />}>
      {P ? (<>
        <div className="kpis two"><Kpi v={`${P.hit} / ${P.n}`} l="affected by the hazards shown" tone={P.hit ? 'hot' : 'good'} /><Kpi v={P.n - P.hit} l="not affected" /></div>
        <div className="rows">{P.rows.slice(0, 10).map((r: any, k: number) =>
          <Row key={k} sw={r.st.length ? '#e5484d' : '#cfcfd4'} k={<><b>{(POI_KINDS[r.kind] || POI_KINDS.other)[0]}</b> {r.name}</>} v={r.st.length ? <span className="warn">{r.st.join(' · ')}</span> : 'ok'} />)}</div>
        {P.n > 10 && <p className="fine">{P.n - 10} more in the CSV.</p>}
      </>) : <p className="msg">Hospitals, schools, fire and police stations, substations, water works and bridges, checked against every hazard you switch on.</p>}
      <div className="btns">
        <button className="btn sm primary" disabled={!geo || s.poiBusy} onClick={() => tools.loadPoi()}><Hospital size={13} />{s.poiBusy ? 'Loading…' : P ? 'Refresh from OpenStreetMap' : 'Load from OpenStreetMap'}</button>
        <button className="btn sm" disabled={!P} onClick={() => tools.poiCSV()}><Download size={13} />CSV</button>
      </div>
      <label className="field"><span>Or your own list: CSV with name, type, lat, lon</span>
        <div className="btns" style={{ flexWrap: 'nowrap' }}><input type="file" accept=".csv,.txt" onChange={e => setFile(e.target.files?.[0] ?? null)} />
          <button className="btn sm" disabled={!geo || !file} onClick={() => file && tools.loadPoi(false, file)}>Use</button></div></label>
      {!geo ? <p className="msg warn">Needs a georeferenced (GeoTIFF) scene.</p> : <Msg m={s.poiMsg} />}
      <p className="fine">Squares on the map; red = a hazard reaches it. Types: {Object.values(POI_KINDS).slice(0, 8).map(([c, l]) => `${c} ${l.toLowerCase()}`).join(', ')}.
        OpenStreetMap is incomplete in many districts: add the district's own list. Bridges only show the water under them, as their deck height is unknown.</p>
    </Card>
  );
}

export function LossCard() {
  const s = useTools(x => x), L = s.loss;
  return (
    <Card id="tool-loss" icon={IndianRupee} title="Flood loss estimate">
      <Num label="Rebuild cost" unit="₹ per m² of floor" value={s.lsCost} min={0} step={1000} onChange={v => tools.setLossCost(v)} title="Ordinary RCC construction in India: roughly ₹16 000–27 000 per m² (₹1 500–2 500 per sq ft)" />
      {L ? (<>
        <div className="big num">{fmtRs(L.total)}<small>structural loss in {L.n} building block{L.n === 1 ? '' : 's'} · {Math.round(100 * L.total / Math.max(1, L.value))}% of their value</small></div>
        <div className="kpis"><Kpi v={L.bands[0]} l="light (< 20%)" tone="good" /><Kpi v={L.bands[1]} l="moderate" tone="amber" /><Kpi v={L.bands[2]} l="heavy (≥ 50%)" tone="hot" /></div>
        <div className="rows">{L.top.map((r: any) => <Row key={r.id} k={`Block ${r.id} · ${r.dep.toFixed(1)} m of water · ${Math.round(r.area)} m² × ${r.floors}`} v={fmtRs(r.loss)} />)}</div>
        <button className="btn sm" onClick={() => tools.lossCSV()}><Download size={13} />CSV per block</button>
        <p className="fine">For each storey: footprint × cost × the damage share for the water depth above its floor (JRC global depth-damage curve for residential buildings in Asia, Huizinga et al. 2017: 0.5 m 33%, 1 m 49%, 2 m 72%, 3 m 87%).
          Structure only: no contents, vehicles, crops or lost business. Depths come from the 30 m terrain and one image: an order of magnitude for relief budgeting, not an assessment.</p>
      </>) : <p className="msg">Set a flood scenario (Respond) to estimate what it costs.</p>}
    </Card>
  );
}

export function AlertCard() {
  const s = useTools(x => x), [msg, setMsg] = useState('');
  useEngine(x => x.floodSum); useTools(x => x.people);
  const C = tools.capSummary();
  return (
    <Card id="tool-cap" icon={Megaphone} title="Alert file (CAP)">
      {!C.hz.length ? <p className="msg">Run a flood, flowing-water, landslide-runout or fire scenario, or load an observed flood: its outline becomes the alert area.</p> : (<>
        <div className="fields">
          <label className="field"><span>Hazard</span><select value={C.key} onChange={e => tools.set({ capHaz: e.target.value })}>{C.hz.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          <label className="field"><span>Status</span><Seg full value={s.capStatus} onChange={v => tools.set({ capStatus: v })} options={[['Exercise', 'Exercise'], ['Actual', 'Actual']]} /></label>
          <label className="field"><span>Severity</span><select value={s.capSev} onChange={e => tools.set({ capSev: e.target.value })}>{['Extreme', 'Severe', 'Moderate', 'Minor'].map(v => <option key={v}>{v}</option>)}</select></label>
          <label className="field"><span>Urgency</span><select value={s.capUrg} onChange={e => tools.set({ capUrg: e.target.value })}>{['Immediate', 'Expected', 'Future'].map(v => <option key={v}>{v}</option>)}</select></label>
          <label className="field wide"><span>Sender</span><input type="text" value={s.capSender} onChange={e => tools.set({ capSender: e.target.value })} /></label>
          <label className="field wide"><span>Instruction to the public</span><input type="text" value={s.capText} onChange={e => tools.set({ capText: e.target.value })} /></label>
        </div>
        <button className="btn sm primary" disabled={!C.geo} onClick={() => setMsg(tools.exportCap() ? '' : 'Nothing to outline: the hazard reaches no ground in this scene.')}><Download size={13} />Download CAP 1.2 file</button>
        {!C.geo && <p className="msg warn">Needs a georeferenced (GeoTIFF) scene.</p>}
        {msg && <p className="msg warn">{msg}</p>}
        <p className="fine">Common Alerting Protocol 1.2 (the format of NDMA's Sachet and most warning systems). The area is the convex outline of the hazard, so it is a little generous; the text counts the people and buildings inside the hazard itself.
          “Exercise” is the default because these are scenarios: only the authority that owns the alerting channel should issue an “Actual” alert.</p>
      </>)}
    </Card>
  );
}
