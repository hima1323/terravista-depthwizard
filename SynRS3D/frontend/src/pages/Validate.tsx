import { useState } from 'react';
import { FileCheck2, Satellite, Crosshair, Plus, X } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { Card, Panel, Ring, Seg, Stat, Toggle, Row } from '../components/ui';
import { Scatter, Hist } from '../components/Charts';
import { sgn } from '../engine/algos';

const VKEYS: Record<string, string> = { raster: 'Reference raster', points: 'Surveyed points', icesat2: 'ICESat-2 laser' };
const n = (v: number) => v.toLocaleString('en-IN');

function Kpis({ m }: { m: any }) {
  if (!m) return <p className="msg warn">Too few overlapping values to compute statistics.</p>;
  const w2 = m.within_2m_pct;
  return (<>
    <div className="stat-row">
      <Stat l="MAE" v={m.mae.toFixed(2)} unit="m" bar="#fff" />
      <Stat l="RMSE" v={m.rmse.toFixed(2)} unit="m" bar="#fff" />
    </div>
    <div className="stat-row">
      {w2 != null && <Ring pct={w2} size={96} label={`${w2.toFixed(0)} percent of values within plus or minus 2 metres`}>
        <span className="big sm">{w2.toFixed(0)}<sup>%</sup></span></Ring>}
      <div className="kpis" style={{ flex: 1 }}>
        <div className="kpi" title="Pearson correlation"><b>{m.r == null ? '–' : m.r.toFixed(2)}</b><span>correlation r</span></div>
        <div className="kpi" title="Mean of ours − reference"><b style={{ color: m.bias < 0 ? '#93c5fd' : '#f4a493' }}>{sgn(m.bias)} m</b>
          <span>bias · ours {m.bias < 0 ? 'lower' : 'higher'}</span></div>
        <div className="kpi" title="1.4826 × median absolute deviation"><b>{(m.nmad ?? 0).toFixed(2)} m</b><span>NMAD</span></div>
      </div>
    </div>
    <p className="fine">{n(m.n)} values compared.{w2 != null && ' Ring: share within ±2 m.'}</p>
  </>);
}
function StatTable({ title, obj }: { title: string; obj: any }) {
  const keys = Object.keys(obj || {});
  if (!keys.length) return null;
  return (
    <table className="t"><thead><tr><th>{title}</th><th>n</th><th>MAE</th><th>RMSE</th><th>bias</th><th>r</th></tr></thead>
      <tbody>{keys.map(k => { const m = obj[k]; return (
        <tr key={k}><td>{k.split(' (')[0]}</td><td>{m.n >= 1e4 ? Math.round(m.n / 1e3) + 'k' : m.n}</td><td>{m.mae.toFixed(2)}</td><td>{m.rmse.toFixed(2)}</td><td>{sgn(m.bias)}</td><td>{m.r == null ? '–' : m.r.toFixed(2)}</td></tr>); })}</tbody></table>
  );
}
function HeldOut({ ho }: { ho: any }) {
  if (!ho) return null;
  if (ho.error) return <p className="msg warn">Held-out check failed: {ho.error}</p>;
  if (ho.note) return <p className="msg">Held-out check: {ho.note}</p>;
  const r = (m: any, l: string) => m && <tr><td>{l}</td><td>{m.mae.toFixed(2)} m</td><td>{sgn(m.bias)} m</td><td>{n(m.n)}</td></tr>;
  return (<div className="hl">
    <h4 className="label">Held-out passes (not used for levelling)<span className="tag">Independent check</span></h4>
    {ho.roof_note && <p className="msg">{ho.roof_note}</p>}
    <table className="t"><thead><tr><th></th><th>MAE</th><th>bias</th><th>n</th></tr></thead>
      <tbody>{r(ho.terrain_vs_ground_footprint, 'Terrain vs ground')}{r(ho.surface_vs_all_footprint, 'Surface vs all photons')}</tbody></table>
    <p className="fine">Terrain levelled on {ho.passes_levelling} pass{ho.passes_levelling === 1 ? '' : 'es'}{ho.laser_shift_m == null ? ' (no shift applied)' : ` (shift ${sgn(ho.laser_shift_m)} m)`},
      checked on {ho.passes_validation} other pass{ho.passes_validation === 1 ? '' : 'es'} ({ho.validation_photons} photons), median over each ~11 m footprint.
      This is the non-circular number. In dense towns ICESat-2 often classes roof photons as ground, so a large negative terrain bias there can mean roofs, not bad terrain.</p>
  </div>);
}

function Results() {
  const val = useEngine(s => s.val), vsel = useEngine(s => s.vsel), lim = useEngine(s => s.errLim);
  const r = vsel ? val[vsel] : null;
  if (!r) return <p className="msg">No validation for this scene yet.</p>;
  if (vsel === 'icesat2') {
    if (!r.photons) return <p className="msg warn">{r.note || 'No ICESat-2 photons in this scene.'}</p>;
    const t = r.terrain_vs_ground;
    return (<>
      <h4 className="label">Surface (our DSM) vs all {r.photons} laser photons</h4><Kpis m={r.surface_vs_all} />
      <h4 className="label">Terrain vs {r.ground_photons - (r.roof_photons_removed || 0)} ground photons</h4>
      {r.roof_photons_removed > 0 && <p className="fine">{r.roof_photons_removed} photons ICESat-2 classed as ground are on buildings and more than 3 m above
        the other ground photons: they are roofs, so they are left out of the terrain checks and of the levelling.</p>}
      {t ? <p className="msg">Before the app's laser levelling: MAE {t.mae.toFixed(2)} m, median {sgn(t.median)} m, NMAD {t.nmad.toFixed(2)} m, r {t.r == null ? '–' : t.r.toFixed(2)}.</p>
        : <p className="msg">Too few ground photons.</p>}
      {r.laser_note && <p className="msg warn">{r.laser_note}</p>}
      <HeldOut ho={r.held_out} />
      {r.scatter && <Scatter xs={r.scatter.ref} ys={r.scatter.ours} lim={lim} />}
      <StatTable title="Landscape" obj={r.landscape} /><StatTable title="Terrain" obj={r.slope} /><StatTable title="Height" obj={r.height} />
      <p className="fine">NASA ICESat-2 (ATL03 photons, ATL08 classes) via SlideRule, {r.passes} pass{r.passes > 1 ? 'es' : ''} {r.dates?.[0]} – {r.dates?.[1]};
        heights converted to m above sea level (EGM2008). Footprints are ~11 m wide, so photons on roof edges and in trees mix heights. Dots on the map: blue = ours lower, red = ours higher.</p>
    </>);
  }
  return (<>
    <Kpis m={r.overall} />
    {r.bias_removed && <p className="msg">With the mean offset removed (e.g. a different datum): MAE {r.bias_removed.mae.toFixed(2)} m, RMSE {r.bias_removed.rmse.toFixed(2)} m.</p>}
    {r.relative_fit && <p className="msg">Relative heights (no georeferencing): compared after the best-fit line reference = {r.relative_fit.offset.toFixed(2)} + {r.relative_fit.scale.toFixed(3)} × ours.</p>}
    {r.scatter && <Scatter xs={r.scatter.ref} ys={r.scatter.ours} lim={lim} />}
    {r.histogram && <Hist hg={r.histogram} />}
    <StatTable title="Landscape" obj={r.landscape} /><StatTable title="Terrain" obj={r.slope} /><StatTable title="Height" obj={r.height} />
    <p className="fine">{r.reference ? `Reference: ${r.reference} (${r.kind === 'ndsm' ? 'height above ground' : r.kind === 'dtm' ? 'bare ground' : 'surface DSM'}), ${r.matched}; covers ${r.coverage_pct.toFixed(0)}% of the scene. `
      : `${r.points ? r.points.length : ''} surveyed points. `}{r.datum_shift_m ? `Datum shift applied: ${sgn(r.datum_shift_m)} m. ` : ''}Landscape = the model's land cover at each pixel; terrain = slope of our ground model.</p>
  </>);
}

function Gcp() {
  const pts = useEngine(s => s.gcpPts), fit = useEngine(s => s.gcpFit), pick = useEngine(s => s.pick), msg = useEngine(s => s.gcpMsg), gcpOn = useEngine(s => s.gcpOn);
  const terms: Record<string, string> = { a: 'level', bx: 'tilt', s: 'height scale' };
  return (
    <Card icon={Crosshair} title="Calibrate with control points">
      <p className="msg">Click points of known elevation (survey marks, benchmarks, GNSS) and enter their height in m above sea level.
        1 point fixes the level; 2+ fix the height scale; 4+ also correct a tilt. PNG/JPG then get absolute heights.</p>
      <div className="btns">
        <button className={`btn sm${pick === 'gcp' ? ' on' : ''}`} onClick={() => engine.setPick(pick === 'gcp' ? null : 'gcp')}><Plus size={13} />{pick === 'gcp' ? 'Done adding' : 'Add points'}</button>
        <button className="btn sm primary" disabled={!pts.some(p => Number.isFinite(p.z as number))} onClick={() => engine.fitGcp()}>Fit & apply</button>
        <button className="btn sm" onClick={() => engine.clearGcp()}>Clear</button>
      </div>
      {pts.length ? pts.map((p, k) => (
        <div className="site" key={k}>
          <b className="tag" style={{ background: '#ff7ad9' }}>{k + 1}</b>
          <span className="num" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>model {p.model.toFixed(1)} m · known
            <input type="number" step="0.01" style={{ width: 90 }} value={p.z ?? ''} onChange={e => engine.setGcpZ(k, e.target.value === '' ? null : +e.target.value)} /> m</span>
          <button className="btn sm" aria-label={`Remove point ${k + 1}`} onClick={() => engine.removeGcp(k)}><X size={13} /></button>
        </div>
      )) : <p className="fine">No control points yet.</p>}
      {msg && <p className={`msg${msg.startsWith('⚠') ? ' warn' : ''}`}>{msg}</p>}
      {fit && (<>
        <Toggle label="Use calibrated heights everywhere" checked={gcpOn} onChange={v => engine.setGcpOn(v)} />
        <div className="rows">
          <Row k={`Fitted with ${fit.n} point${fit.n > 1 ? 's' : ''}`} v={[...new Set(fit.terms.map((t: string) => terms[t] || t))].join(', ')} />
          <Row k="Level shift" v={`${sgn(fit.a)} m`} />
          {fit.terms.includes('s') && <Row k="Height scale" v={`×${fit.s.toFixed(3)}`} />}
          {fit.terms.includes('bx') && <Row k="Tilt across the scene" v={`${sgn(fit.bx)} / ${sgn(fit.by)} m`} />}
          <Row k={fit.rmse_before != null ? 'Error at points, before → after' : 'Error at points after'}
            v={fit.rmse_before != null ? `${fit.rmse_before.toFixed(2)} → ${fit.rmse_after.toFixed(2)} m` : `${fit.rmse_after.toFixed(2)} m`} />
          {fit.loo ? <Row k="Leave-one-out error" v={`${fit.loo.rmse.toFixed(2)} m`} /> : null}
        </div>
        {!fit.loo && <p className="fine">Add more points than fitted terms to get a leave-one-out error estimate.</p>}
        {fit.warning && <p className="msg warn">{fit.warning}</p>}
      </>)}
    </Card>
  );
}

export default function Validate() {
  const s = useEngine(x => x), [file, setFile] = useState<File | null>(null), [kind, setKind] = useState('dsm'), [datum, setDatum] = useState('egm2008');
  const keys = Object.keys(VKEYS).filter(k => s.val[k]);
  const geo = s.hasTerrain;
  return (
    <Panel page="validate">
      <Card icon={FileCheck2} title="Compare with reference data">
        <label className="field"><span>Reference: GeoTIFF raster or CSV of points</span>
          <input type="file" accept=".tif,.tiff,.csv,.txt" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
        <div className="fields">
          <label className="field"><span>Measures</span><select value={kind} onChange={e => setKind(e.target.value)}>
            <option value="dsm">Surface DSM</option><option value="ndsm">Height above ground</option><option value="dtm">Bare ground DTM</option></select></label>
          <label className="field"><span>Datum</span><select value={datum} onChange={e => setDatum(e.target.value)}>
            <option value="egm2008">EGM2008</option><option value="egm96">EGM96 (SRTM, CartoDEM)</option><option value="ellipsoid">Ellipsoid (GNSS)</option></select></label>
        </div>
        <div className="btns">
          <button className="btn primary" disabled={s.vbusy || !file} onClick={() => file && engine.compareFile(file, kind, datum)}>Compare</button>
          <button className="btn" disabled={s.vbusy || !geo} onClick={() => engine.checkIcesat()} title="NASA ICESat-2 photons inside this scene (needs internet and a GeoTIFF scene)">
            <Satellite size={14} />Check with ICESat-2</button>
        </div>
        <p className={`msg${s.vmsg.startsWith('⚠') ? ' warn' : ''}`}>{s.vmsg || (geo ? 'Load a reference, or check against NASA ICESat-2 laser photons.'
          : 'This scene has no georeferencing: a raster must cover exactly the same area; heights are compared after a best-fit scale.')}</p>
      </Card>
      <Card title="Results" right={keys.length > 1 && <Seg value={s.vsel as string} onChange={v => engine.setVsel(v)} options={keys.map(k => [k, VKEYS[k].split(' ')[0]] as [string, string])} />}>
        <label className="field"><span>Show on the map</span>
          <Seg full value={s.vlayer} onChange={v => engine.setVlayer(v)} options={[['err', 'Error'], ['height', 'Our height'], ['none', 'Photo']]} /></label>
        <Results />
      </Card>
      <Gcp />
    </Panel>
  );
}
