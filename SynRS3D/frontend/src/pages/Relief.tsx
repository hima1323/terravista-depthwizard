import { Link } from 'react-router-dom';
import { Tent, Navigation } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { Card, Num, Panel, Toggle } from '../components/ui';
import { RouteCard } from '../components/Shared';

export default function Relief() {
  const s = useEngine(x => x), S = s.sites, f = s.floodSum;
  const list = (items: NonNullable<typeof S>['pads'], color: string, empty: string) => items.length ? items.map((p, k) => (
    <div className="site" key={p.label}>
      <b className="tag" style={{ background: color }}>{p.label}</b>
      <span>{p.text}</span>
      <button className="btn sm" onClick={() => engine.routeToSite(p.kind, k)}><Navigation size={12} />Route</button>
      <small>{p.sub}</small>
    </div>)) : <p className="msg warn">{empty}</p>;
  return (
    <Panel page="relief" extra={
      <p className="msg" style={{ marginTop: 10 }}>{s.flood && f ? <>Sites stay at least {s.sdry} m above the {s.stl && s.timeOpen ? 'highest timeline water' : `current water (+${s.depth.toFixed(1)} m)`}.</>
        : <>Flood is off, so water is ignored. <Link to="/respond" style={{ color: 'var(--accent)' }}>Set a scenario →</Link></>}</p>}>
      <Card icon={Tent} title="Site rules">
        <div className="fields">
          <Num label="Helipad clear circle" unit="m" value={s.spad} min={10} max={100} onChange={v => engine.setSiteParam({ spad: v })}
            title="ICAO rule of thumb: 1.5 × the helicopter's overall length: about 24 m for an ALH Dhruv, 38 m for a Mi-17" />
          <Num label="Camp area at least" unit="m²" value={s.scamp} min={100} step={100} onChange={v => engine.setSiteParam({ scamp: v })} />
          <Num label="Space per person" unit="m²" value={s.sper} min={5} step={5} onChange={v => engine.setSiteParam({ sper: v })} title="Sphere standard: at least 45 m² per person" />
          <Num label="Max slope" unit="°" value={s.sslope} min={0} max={20} step={0.5} onChange={v => engine.setSiteParam({ sslope: v })} />
          <Num label="Dry by at least" unit="m" value={s.sdry} min={0} max={5} step={0.1} onChange={v => engine.setSiteParam({ sdry: v })} />
        </div>
        {s.timeOpen && <Toggle label="Must stay dry for the whole timeline" checked={s.stl} onChange={v => engine.setSiteParam({ stl: v })} />}
      </Card>
      {S && (<>
        <Card title={<><i className="sw" style={{ background: '#ffd400' }} />Helicopter landing sites</>}>{list(S.pads, '#ffd400', 'No clear circle that size: try a smaller circle, a steeper slope limit or a lower water level.')}</Card>
        <Card title={<><i className="sw" style={{ background: '#4fe08a' }} />Relief camp sites</>}>{list(S.camps, '#4fe08a', 'No open area that large here.')}</Card>
        <p className="fine">{S.note}</p>
      </>)}
      <RouteCard />
    </Panel>
  );
}
