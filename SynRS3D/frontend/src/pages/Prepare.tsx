import { useNavigate } from 'react-router-dom';
import { Mountain, Waves, ArrowRight } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { Card, Panel, Ring, Seg, Stat } from '../components/ui';

const RANGES = ['≤ 15°', '16–25°', '26–35°', '36–45°', '> 45°'];   // SLOPE_CLASSES in algos.ts

// Before an event: where the ground is steep enough to slide, and what each water rise would reach.
export default function Prepare() {
  const share = useEngine(s => s.slopeShare), exposure = useEngine(s => s.exposure), fsrc = useEngine(s => s.fsrc), hasTerrain = useEngine(s => s.hasTerrain), current = useEngine(s => s.current);
  const nav = useNavigate();
  const simulate = (rise: number) => { engine.setFlood(true); engine.setDepth(rise); nav('/respond'); };
  const steep = share ? share.slice(2).reduce((a, x) => a + x.pct, 0) : 0;
  return (
    <Panel page="prepare">
      <Card icon={Mountain} title="Landslide-prone slopes">
        {share ? (<>
          <div className="stat-row">
            <Ring pct={steep} label={`${steep.toFixed(1)} percent of the scene is steeper than 25 degrees`} img={current ? `/results/${current}.jpg` : undefined} />
            <div><Stat l="Moderately steep or steeper (> 25°)" v={steep.toFixed(1)} unit="%" /><div className="k">of the scene</div></div>
          </div>
          <div className="slopebar" aria-hidden="true"><span style={{ flex: 100 - steep, background: 'linear-gradient(90deg, #2ea043, #a6ce39)' }} />
            <span style={{ flex: steep, background: 'linear-gradient(90deg, #ffd60a, #f77f00, #d62828)' }} /></div>
          <div className="ticks"><span>≤ 25° · {(100 - steep).toFixed(0)}%</span><span>&gt; 25° · {steep.toFixed(0)}%</span></div>
          <div>
            {share.map((c, k) => (
              <div key={c.label} className="cls">
                <i className="sw" style={{ background: `rgb(${c.rgb})` }} /><span>{c.label}</span><span className="fine">{RANGES[k]}</span>
                <b className="num">{c.pct.toFixed(1)}%</b>
              </div>
            ))}
          </div>
          <p className="fine">Slope classes as in BIS IS 14496 (Part 2) landslide hazard zonation, from the 30 m terrain model. Slope is one factor; it is not a hazard map.
            On the map only slopes above 15° are tinted.</p>
        </>) : <p className="msg">{hasTerrain === false ? 'Slope needs terrain: upload a GeoTIFF (or calibrate with control points).' : 'Loading…'}</p>}
      </Card>
      <Card icon={Waves} title="Flood exposure">
        <label className="field"><span>Water comes from</span>
          <Seg full value={fsrc === 'pick' ? 'all' : fsrc} onChange={v => engine.setFsrc(v)} options={[['all', 'All low ground'], ['edges', 'Scene edges']]} /></label>
        {exposure && (
          <table className="t">
            <thead><tr><th>Rise</th><th>Ground wet</th><th>Blocks</th><th>Under</th><th>Floor area</th><th></th></tr></thead>
            <tbody>{exposure.map(r => (
              <tr key={r.rise}>
                <td>+{r.rise} m</td><td>{r.wetPct.toFixed(0)}%</td><td>{r.blocks}</td><td>{r.sub}</td><td>{r.floorArea >= 1e4 ? `${(r.floorArea / 1e3).toFixed(0)}k` : Math.round(r.floorArea).toLocaleString('en-IN')} m²</td>
                <td><button className="btn sm" aria-label={`Simulate a ${r.rise} m rise`} onClick={() => simulate(r.rise)}><ArrowRight size={12} /></button></td>
              </tr>))}</tbody>
          </table>
        )}
        <p className="fine">Rise above the lowest ground in the scene. "Scene edges" floods only ground water can flow to from outside the image (a river or the sea).
          Floor area = footprint × storeys under water. Press → to open that level in Respond.</p>
        <p className="note">These are scenarios, not forecasts. Use them to compare what each rise would reach.</p>
        <button className="btn" onClick={() => nav('/respond')}>Run a scenario in Respond <ArrowRight size={14} /></button>
      </Card>
    </Panel>
  );
}
