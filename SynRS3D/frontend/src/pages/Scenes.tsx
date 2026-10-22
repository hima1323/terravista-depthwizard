import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { UploadCloud, Info } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { PAGES } from '../nav';
import { nice } from '../engine/algos';

const BADGE: Record<string, string> = { done: '#6fd17b', queued: '#a9b3a5', error: '#ef7d64' };

// Choosing or uploading a scene opens the "picked" section: everything you can do with that scene
export default function Scenes() {
  const scenes = useEngine(s => s.scenes), current = useEngine(s => s.current), stats = useEngine(s => s.stats);
  const note = useEngine(s => s.note), uploadMsg = useEngine(s => s.uploadMsg), status = useEngine(s => s.status), waitText = useEngine(s => s.waitText);
  const [over, setOver] = useState(false), picked = useRef<HTMLElement>(null);
  const reveal = () => requestAnimationFrame(() => picked.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  const choose = (name: string) => { engine.select(name); reveal(); };
  const upload = (f?: File) => { if (f) { engine.upload(f); reveal(); } };
  const running = scenes.filter(s => s.state === 'running').length, queued = scenes.filter(s => s.state === 'queued').length;
  return (
    <div className="home" style={current ? { '--hero-img': `url(/results/${current}.jpg)` } as React.CSSProperties : undefined}>
      <section className="lib scenes-page">
        <div className="sec-title">
          <div><span className="phase"><i />Library</span><h1 className="page-h">Scenes <em>{scenes.length}</em></h1></div>
          <span className="msg">{running} processing · {queued} queued</span>
        </div>

        <section className="picked" ref={picked} aria-label="Selected scene">
          {current ? (<>
            <div className="picked-scene">
              <img src={`/results/${current}.jpg`} alt={`Satellite image of ${nice(current)}`} />
              <div>
                <span className="phase"><i />Selected scene</span>
                <h2>{nice(current)}</h2>
                {status === 'ready'
                  ? <div className="chips">{stats.map(([k, v]) => <span key={k} className="chip">{k}<b>{v}</b></span>)}</div>
                  : <p className="msg">{waitText || 'Loading the scene…'}</p>}
              </div>
            </div>
            {status === 'ready' && (<>
              <p className="note"><Info size={14} /><span>{note}</span></p>
              <div className="options">
                {PAGES.filter(p => p.page !== 'home' && p.page !== 'scenes').map(p => (
                  <Link key={p.page} to={p.path} style={{ '--c': p.c } as React.CSSProperties}>
                    <p.icon size={20} /><small>{p.phase}</small><b>{p.label}</b><span>{p.blurb}</span>
                  </Link>
                ))}
              </div>
            </>)}
          </>) : <p className="msg">Choose a scene below or upload an image to see everything you can do with it.</p>}
        </section>

        <div className="lib-body">
          <div className="scene-grid">
            {scenes.map(s => {
              const ok = s.state === 'done';
              return (
                <button key={s.name} className={`scene-card${s.name === current ? ' active' : ''}${ok ? '' : s.state === 'error' ? ' error' : ' busy'}`}
                  onClick={() => choose(s.name)} aria-pressed={s.name === current}>
                  <img src={`/results/${s.name}.jpg`} alt="" loading="lazy" />
                  <span className="badge" style={{ '--c': BADGE[s.state] } as React.CSSProperties}>
                    <i />{ok ? 'Ready' : s.state === 'running' ? `${Math.round(s.progress * 100)}%` : s.state}</span>
                  <div className="meta">
                    <b>{nice(s.name)}</b>
                    <span>{ok ? `max ${s.meta.max.toFixed(1)} m · built ${s.meta.built_pct.toFixed(0)}%${s.meta.terrain?.source ? ' · geo' : ''}`
                      : s.state === 'error' ? `error: ${s.error}` : s.state === 'running' ? 'estimating heights…' : 'waiting for the model'}</span>
                    {s.state === 'running' && <div className="bar"><i style={{ width: `${s.progress * 100}%` }} /></div>}
                  </div>
                </button>
              );
            })}
          </div>
          <aside className="home-side" aria-label="Upload an image">
            <label className={`drop${over ? ' over' : ''}`} onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
              onDrop={e => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files[0]); }}>
              <span className="di"><UploadCloud size={20} /></span>
              <b>{uploadMsg || 'Drop a satellite image'}</b>
              <span>or click to choose · PNG · JPG · GeoTIFF<br />GeoTIFF adds true scale and heights above sea level.</span>
              <input type="file" hidden accept=".png,.jpg,.jpeg,.tif,.tiff" onChange={e => upload(e.target.files?.[0])} />
            </label>
            <p className="fine">The image is processed on this machine: a few seconds with an NVIDIA GPU, several minutes on CPU. Other scenes stay usable meanwhile.</p>
          </aside>
        </div>
      </section>
    </div>
  );
}
