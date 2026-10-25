import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { FileDown, Building2, Activity } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { Card, Kpi, Panel, Row, Stat, dist, m2 } from '../components/ui';
import { Downloads } from '../components/Shared';

export default function Assess() {
  const s = useEngine(x => x), f = s.floodSum;
  const rep = useMemo(() => engine.report(), [f, s.current]);   // recomputed when the scenario changes
  return (
    <Panel page="assess">
      {!s.flood || !f ? (
        <Card icon={Activity} title="No scenario yet">
          <p className="msg">Set a flood scenario in <Link to="/respond" style={{ color: 'var(--accent)' }}>Respond</Link> (or open a level from
            <Link to="/prepare" style={{ color: 'var(--accent)' }}> Prepare</Link>) and this page sums up what it affects.</p>
        </Card>
      ) : (<>
        <Card icon={Activity} title="Scenario impact" right={<Link to="/respond" className="tag acc">{f.abs ? `${f.level.toFixed(1)} m a.s.l.` : `+${f.rise.toFixed(1)} m`}</Link>}>
          <div className="kgrid">
            <Stat l="Blocks submerged" v={f.sub} bar="#e5484d" size="md" />
            <Stat l="Blocks partly flooded" v={f.part} bar="#f5a524" size="md" />
            <Stat l="Floor area under water" v={Math.round(f.floorArea).toLocaleString('en-IN')} unit="m²" bar="#2f7fe0" size="md" />
            <Stat l="Ground wet" v={f.wetHa.toFixed(1)} unit={`ha · ${f.wetPct.toFixed(0)}%`} bar="var(--text)" size="md" />
          </div>
          <div className="kpis">
            <Kpi v={`${f.maxDepth.toFixed(1)} m`} l="deepest water" />
            <Kpi v={`${f.total ? Math.round(100 * (f.sub + f.part) / f.total) : 0}%`} l="of blocks affected" />
            <Kpi v={f.dry} l="blocks dry" tone="good" />
          </div>
          <div className="rows">
            {s.tlSum && <Row k="Timeline peak" v={`+${s.tlSum.peakRise.toFixed(2)} m${s.tlSum.peakH ? ` at +${s.tlSum.peakH} h` : ''}`} />}
            {s.routeSum && <Row k="Route A → B" v={`${dist(s.routeSum.len)} · ${Math.round(s.routeSum.minutes)} min ${s.routeSum.how}`} />}
            {s.routeOpen && !s.routeSum && s.routeMsg.startsWith('No route') && <Row k="Route A → B" v={<span className="warn">blocked</span>} />}
            {s.sites && <Row k="Relief sites" v={`${s.sites.pads.length} helipads · ${s.sites.camps.length} camps`} />}
          </div>
          <button className="btn primary lg" onClick={() => engine.exportReport()}><FileDown size={15} />Export impact report (JSON + CSV)</button>
          <p className="note">A scenario, not a forecast: inspect on the ground before acting. Floors use 3 m per floor, which is not validated.</p>
          <p className="fine">{f.model} {f.terrain}</p>
        </Card>
        {rep && (
          <Card icon={Building2} title={`Most affected blocks (${rep.affected.length})`}>
            {rep.affected.length ? (
              <table className="t"><thead><tr><th>Block</th><th>State</th><th>Height</th><th>Floors wet</th><th>Area</th></tr></thead>
                <tbody>{rep.affected.slice(0, 14).map((a: any) => (
                  <tr key={a.id}><td>#{a.id}</td><td><span className="pill"><i style={{ background: a.state === 'submerged' ? '#e5484d' : '#f5a524' }} />{a.state === 'submerged' ? 'Submerged' : 'Partly'}</span></td>
                    <td>{a.height_m} m</td><td>{a.floors_under} / {a.floors}</td><td>{m2(a.area_m2)}</td></tr>))}</tbody></table>
            ) : <p className="msg">No building blocks are reached at this water level.</p>}
            {rep.affected.length > 14 && <p className="fine">The export lists all {rep.affected.length} blocks with their position in the image.</p>}
          </Card>
        )}
      </>)}
      <Downloads />
    </Panel>
  );
}
