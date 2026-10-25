import { useCallback, useEffect, useRef } from 'react';
import { engine, useEngine } from '../engine/useEngine';
import { metaOf } from '../nav';

// The map behind every page: the 3D terrain or the 2D photo + height layer + tool overlay.
// `hero`: the landing's backdrop, the 3D scene only (the engine flies the camera), no pins, tips or input.
export default function Stage({ hero = false }: { hero?: boolean }) {
  const view = useEngine(s => s.view), status = useEngine(s => s.status), aspect = useEngine(s => s.aspect);
  const alpha = useEngine(s => s.alpha), pick = useEngine(s => s.pick), waitText = useEngine(s => s.waitText);
  const hover = useEngine(s => s.hover), pinLines = useEngine(s => s.pinLines), hasScenes = useEngine(s => s.scenes.length > 0);
  const v3d = useCallback((el: HTMLDivElement | null) => engine.attach3D(el), []);
  const pin = useCallback((el: HTMLDivElement | null) => engine.attachPin(el), []);
  const photo = useRef<HTMLImageElement>(null), heat = useRef<HTMLCanvasElement>(null), ovl = useRef<HTMLCanvasElement>(null);
  useEffect(() => { engine.attach2D(photo.current, heat.current, ovl.current); }, [view, status]);
  const page = useEngine(s => s.page);
  useEffect(() => engine.setTint(metaOf(page).rgb), [page]);

  const uv = (e: React.MouseEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height, e.clientX - r.left, e.clientY - r.top] as const;
  };
  if (hero) return <div className="stage hero" aria-hidden="true"><div className="v3d" ref={v3d} hidden={status !== 'ready'} /></div>;
  return (
    <div className={`stage v-${view}`}>
      <div className="v3d" ref={v3d} hidden={view !== '3d' || status !== 'ready'}>
        {pinLines && (
          <div className="pin glass" ref={pin} role="status">
            <b>{pinLines[0]}</b>
            {pinLines.slice(1).map((l, i) => <div key={i}>{l}</div>)}
          </div>
        )}
      </div>
      <div className="v2d" hidden={view !== '2d' || status !== 'ready'}>
        <div className={`imgwrap${pick ? ' picking' : ''}`} style={{ aspectRatio: aspect }}
          onMouseMove={e => { const [u, v, x, y] = uv(e); engine.hover2D(u, v, x, y); }}
          onMouseLeave={() => engine.set({ hover: null })}
          onClick={e => { const [u, v] = uv(e); engine.click2D(u, v); }}>
          <img ref={photo} alt="Satellite image of the scene" />
          <canvas ref={heat} style={{ opacity: alpha }} />
          <canvas ref={ovl} />
          {hover && <div className="tip glass" style={{ left: Math.min(hover.x + 14, 99999), top: hover.y + 14 }}>{hover.text}</div>}
        </div>
      </div>
      {status === 'wait' && <div className="empty"><div className="glass">{waitText}</div></div>}
      {status === 'empty' && hasScenes && <div className="empty"><div className="glass">Loading scene…</div></div>}
    </div>
  );
}
