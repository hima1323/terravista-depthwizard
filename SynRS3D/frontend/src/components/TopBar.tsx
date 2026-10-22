import { Box, Map, ChevronDown } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { metaOf } from '../nav';
import { nice } from '../engine/algos';
import { Seg } from './ui';

export default function TopBar() {
  const page = useEngine(s => s.page), current = useEngine(s => s.current), stats = useEngine(s => s.stats), view = useEngine(s => s.view);
  const scenes = useEngine(s => s.scenes).filter(s => s.state === 'done');
  const m = metaOf(page);
  if (page === 'home' || page === 'scenes') return null; // full pages with their own headers
  return (
    <header className="topbar glass">
      <div className="crumb">
        <span className="phase"><i />{m.group === 'cycle' ? `${m.phase} · ${m.label}` : m.label}</span>
        {/* the name is drawn as text and an invisible select lies over it: a select sizes itself to its longest option */}
        <h1 className="scene-pick">
          <span>{current ? nice(current) : 'No scene yet'}</span>
          <ChevronDown size={20} aria-hidden="true" />
          <select aria-label="Scene" value={current ?? ''} onChange={e => { engine.select(e.target.value); e.target.blur(); }}>
            {!current && <option value="">No scene yet</option>}
            {scenes.map(s => <option key={s.name} value={s.name}>{nice(s.name)}</option>)}
          </select>
        </h1>
      </div>
      <div className="chips">
        {stats.map(([k, v]) => <span key={k} className="chip">{k}<b>{v}</b></span>)}
      </div>
      <Seg value={view} onChange={v => engine.setView(v)} options={[['3d', <><Box size={14} />3D</>], ['2d', <><Map size={14} />2D</>]]} />
    </header>
  );
}
