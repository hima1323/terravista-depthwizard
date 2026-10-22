import { Waves, Clock, CloudRain, Plus, Eraser } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { Card, Kpi, Num, Panel, Row, Seg, Slider, Toggle, ha, m2 } from '../components/ui';
import { RouteCard, FloodSwitch } from '../components/Shared';
import { TimelineChart } from '../components/Charts';
import { ARR_KEYS } from '../engine/algos';

function FloodCard() {
  const s = useEngine(x => x), f = s.floodSum;
  return (
    <Card icon={Waves} title="Flood scenario">
      <FloodSwitch />
      {s.flood && (<>
        <Slider label="Water level" value={s.depth} min={0} max={s.depthMax} step="any" onChange={v => engine.setDepth(v)}
          display={f && f.abs ? `+${s.depth.toFixed(1)} m · ${f.level.toFixed(1)} m a.s.l.` : `${s.depth.toFixed(1)} m`} />
        <label className="field"><span>Water comes from</span>
          <Seg full value={s.fsrc} onChange={v => engine.setFsrc(v)} options={[['all', 'All low ground'], ['edges', 'Scene edges'], ['pick', 'Points I click']]} /></label>
        {s.fsrc === 'pick' && (<>
          <div className="btns">
            <button className={`btn sm${s.pick === 'src' ? ' on' : ''}`} onClick={() => engine.setPick(s.pick === 'src' ? null : 'src')}><Plus size={13} />{s.pick === 'src' ? 'Done placing' : 'Place water sources'}</button>
            <button className="btn sm" disabled={!s.nSources} onClick={() => engine.clearSources()}><Eraser size={13} />Clear ({s.nSources})</button>
          </div>
          {!s.nSources && <p className="msg warn">Click where water comes in: a river, a canal, a breached embankment.</p>}
        </>)}
        {f && (<>
          <div className="kpis">
            <Kpi v={`${f.wetPct.toFixed(0)}%`} l={`ground wet · ${ha(f.wetHa)}`} tone="blue" />
            <Kpi v={f.sub} l="blocks submerged" tone="hot" />
            <Kpi v={f.part} l="partly flooded" tone="amber" />
            <Kpi v={`${f.maxDepth.toFixed(1)} m`} l="deepest water" />
            <Kpi v={f.dry} l="blocks dry" tone="good" />
            <Kpi v={m2(f.floorArea)} l="floor area under water" />
          </div>
          <p className="fine">{f.total} building blocks from the model's land cover (attached buildings count as one), ~3 m per floor. {f.model} {f.terrain} Heights carry model error. Hover or click a point to see when it floods.</p>
        </>)}
      </>)}
    </Card>
  );
}

function TimelineCard() {
  const s = useEngine(x => x), t = s.tlSum;
  return (
    <Card icon={Clock} title="Rain & river timeline" right={<input type="checkbox" className="switch" aria-label="Timeline" disabled={!s.flood} checked={s.timeOpen} onChange={e => engine.setTimeOpen(e.target.checked)} />}>
      {!s.timeOpen ? <p className="msg">{s.flood ? 'Step the flood hour by hour as rain falls and the river rises.' : 'Turn the flood scenario on first.'}</p> : (<>
        <div className="fields">
          <Num label="Rain" unit="mm/h" value={s.train} min={0} max={300} onChange={v => engine.setTimeParam({ train: v })} />
          <Num label="For" unit="h" value={s.thours} min={0} max={384} onChange={v => engine.setTimeParam({ thours: v })} />
          <Num label="River / sea rise" unit="m/day" value={s.trise} step={0.1} onChange={v => engine.setTimeParam({ trise: v })} title="Water from outside the image (gauge trend or CWC forecast). Negative = falling." />
          <Num label="Drains carry" unit="mm/h" value={s.tdrain} min={0} step={5} onChange={v => engine.setTimeParam({ tdrain: v })} title="Indian city drains are typically designed for about 25–50 mm/h" />
          <Num label="Area draining here" unit="× scene" value={s.tup} min={1} step={0.5} onChange={v => engine.setTimeParam({ tup: v })} />
          <Num label="Simulate" unit="days" value={s.tdays} min={1} max={16} onChange={v => engine.setTimeParam({ tdays: v })} />
        </div>
        <div className="btns" style={{ alignItems: 'center' }}>
          <button className={`btn sm${s.forecastOn ? ' on' : ''}`} onClick={() => engine.toggleForecast()}><CloudRain size={13} />{s.forecastOn ? 'Use constant rain' : 'Use rain forecast'}</button>
          <span className="fine">{s.forecastInfo}</span>
        </div>
        <Slider label="Time" value={s.tt} min={0} max={s.ttMax} step={1} onChange={v => engine.applyTime(v)} display={s.ttLabel} />
        <Toggle label="Show “time until flooded” map" checked={s.tarr} onChange={v => engine.setTarr(v)} />
        {s.tarr && <div className="keys">{ARR_KEYS.map(([, l, c]) => <span key={l}><i className="sw" style={{ background: `rgb(${c})` }} />{l}</span>)}</div>}
        {t && (<>
          {t.noSources && <p className="msg warn">Place water sources first: the water has nowhere to go.</p>}
          <TimelineChart P={t.chart.P} rises={t.chart.rises} days={t.chart.days} h={s.tt} />
          <div className="rows">
            <Row k={`Rain in ${t.chart.days} days`} v={`${t.totalRain.toFixed(0)} mm`} />
            <Row k="Max 24 h" v={`${t.max24.toFixed(0)} mm · IMD ${t.imd}`} />
            <Row k="Peak water" v={`+${t.peakRise.toFixed(2)} m${t.peakH ? ` at +${t.peakH} h` : ' (now)'}`} />
          </div>
          {t.deadline && <p className="msg"><b>{t.deadline}</b></p>}
          <table className="t"><thead><tr><th>When</th><th>Water</th><th>Flooded</th><th>Blocks wet</th></tr></thead>
            <tbody>{t.rows.map(r => <tr key={r.when}><td>{r.when}</td><td>+{r.rise.toFixed(2)} m</td><td>{ha(r.ha)}</td><td>{r.blocks}</td></tr>)}</tbody></table>
          <p className="fine">{t.note}</p>
        </>)}
      </>)}
    </Card>
  );
}

export default function Respond() {
  return (
    <Panel page="respond">
      <FloodCard />
      <TimelineCard />
      <RouteCard />
    </Panel>
  );
}
