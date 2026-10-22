import { useEffect, useRef } from 'react';
import { engine, useEngine } from '../engine/useEngine';
import { ARR_KEYS } from '../engine/algos';

function Legend() {
  const legend = useEngine(s => s.legend), cv = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!cv.current || !legend || legend.kind !== 'grad') return;
    const c = cv.current.getContext('2d')!;
    for (let i = 0; i < 120; i++) { c.fillStyle = `rgb(${legend.ramp(i / 119)})`; c.fillRect(i, 0, 1, 1); }
  }, [legend]);
  if (!legend) return null;
  if (legend.kind === 'flood') return (
    <span className="legend keys"><span><i className="sw" style={{ background: '#2f7fe0' }} />Water</span>
      <span><i className="sw" style={{ background: '#e5484d' }} />Submerged</span><span><i className="sw" style={{ background: '#f5a524' }} />Partly flooded</span></span>);
  if (legend.kind === 'arrival') return (
    <span className="legend keys">{ARR_KEYS.map(([, l, c]) => <span key={l}><i className="sw" style={{ background: `rgb(${c})` }} />{l}</span>)}</span>);
  return <span className="legend"><span>{legend.lo}</span><canvas ref={cv} width={120} height={1} /><span>{legend.hi}</span></span>;
}

// Map chrome shared by every page: legend, overlay strength (2D) or height exaggeration and camera (3D)
export default function Toolbar() {
  const s = useEngine(x => x);
  if (s.status !== 'ready') return null;
  return (
    <div className="toolbar glass" role="toolbar" aria-label="Map controls">
      <Legend />
      <span className="divider" />
      {s.view === '2d' ? (
        <label className="lbl">Overlay<input type="range" min={0} max={1} step={0.01} value={s.alpha} onChange={e => engine.set({ alpha: +e.target.value })} /></label>
      ) : (<>
        <label className="lbl">Height ×{s.exag}<input type="range" min={1} max={5} step={0.5} value={s.exag} onChange={e => engine.setExag(+e.target.value)} /></label>
        <label className="lbl">Camera
          <select value={s.cam} onChange={e => { engine.setCam(e.target.value as any); e.target.blur(); }}>
            <option value="orbit">Orbit</option><option value="fly">Fly (W A S D)</option><option value="street">Street level</option>
          </select></label>
        <label className="lbl"><input type="checkbox" className="switch" checked={s.spin} onChange={e => engine.setSpin(e.target.checked)} />Auto-orbit</label>
      </>)}
    </div>
  );
}
