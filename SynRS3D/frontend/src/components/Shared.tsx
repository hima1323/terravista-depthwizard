import { Download, Route, Play, Eraser, MapPin } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { Card, Num, Row, Seg, Toggle, dist } from './ui';

export function RouteCard() {
  const s = useEngine(x => x), sum = s.routeSum;
  return (
    <Card icon={Route} title="Route finder" right={<input type="checkbox" className="switch" aria-label="Route finder" checked={s.routeOpen} onChange={e => engine.setRouteOpen(e.target.checked)} />}>
      {!s.routeOpen ? <p className="msg">Find a way from A to B that avoids buildings, steep ground and water deeper than you can wade or drive through.</p> : (<>
        <div className="fields">
          <label className="field"><span>Travel</span><Seg full value={s.rmode} onChange={v => engine.setRmode(v)} options={[['foot', 'On foot'], ['car', 'Car']]} /></label>
          <Num label="Max water" unit="m" value={s.rdepth} step={0.05} min={0} max={3} onChange={v => engine.setRdepth(v)} title="Water deeper than this blocks the route" />
        </div>
        <div className="btns">
          <button className={`btn sm${s.pick === 'A' ? ' on' : ''}`} onClick={() => engine.setPick(s.pick === 'A' ? null : 'A')}><MapPin size={13} />Set A</button>
          <button className={`btn sm${s.pick === 'B' ? ' on' : ''}`} onClick={() => engine.setPick(s.pick === 'B' ? null : 'B')}><MapPin size={13} />Set B</button>
          <button className="btn sm" disabled={!sum} onClick={() => engine.flyRoute()}><Play size={13} />Fly it</button>
          <button className="btn sm" onClick={() => engine.clearRoute()}><Eraser size={13} />Clear</button>
        </div>
        {sum ? (<>
          <div className="big num">{dist(sum.len)}<small>≈ {sum.minutes < 1 ? '<1' : Math.round(sum.minutes)} min {sum.how}</small></div>
          <div className="rows">
            {sum.wetLen != null && <Row k="Through water" v={`${Math.round(sum.wetLen)} m · deepest ${sum.maxDepth.toFixed(2)} m`} sw="#3da5ff" />}
            {sum.roadPct != null && <Row k="On roads" v={`${Math.round(sum.roadPct)}%`} sw="#4fe08a" />}
          </div>
          {sum.snapped && <p className="msg">A point was on a building or in deep water; the route starts from the nearest spot you can stand on.</p>}
          {sum.deadline && <p className="msg"><b>{sum.deadline}</b></p>}
          <p className="fine">Green = dry, blue = through water. Water depths come from the 30 m terrain (about ±2–4 m) and roads from the model's land cover: check on the ground before relying on a route.</p>
        </>) : <p className={`msg${s.routeMsg.startsWith('No route') ? ' warn' : ''}`}>{s.routeMsg}</p>}
      </>)}
    </Card>
  );
}

const DL: [string, string, 'terrain' | 'gcp' | null][] = [['glb', '3D model (.glb)', null], ['_dsm.tif', 'DSM, m a.s.l. (.tif)', 'terrain'], ['_dtm.tif', 'Terrain DTM (.tif)', 'terrain'],
  ['_height.tif', 'Height above ground (.tif)', null], ['_uncertainty.tif', 'Consistency score (.tif)', null], ['_dsm_gcp.tif', 'DSM with control points (.tif)', 'gcp'],
  ['_buildings.json', 'Building blocks (.json)', null]];
export function Downloads() {
  const hasTerrain = useEngine(s => s.hasTerrain), hasGcp = useEngine(s => s.hasGcp);
  return (
    <Card icon={Download} title="Downloads">
      <div className="btns">
        {DL.filter(([, , need]) => need === null || (need === 'terrain' ? hasTerrain : hasGcp)).map(([k, l]) =>
          <button key={k} className="btn sm" onClick={() => engine.download(k)}>{l}</button>)}
      </div>
      <p className="fine">GeoTIFFs open in QGIS / ArcGIS; the 3D model (true metres) in Blender or any glTF viewer.</p>
    </Card>
  );
}

export function FloodSwitch() {
  const flood = useEngine(s => s.flood);
  return <Toggle label="Simulate flooding" checked={flood} onChange={v => engine.setFlood(v)} />;
}
