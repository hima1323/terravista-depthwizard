import { NavLink } from 'react-router-dom';
import { Mountain } from 'lucide-react';
import { PAGES } from '../nav';

export default function Rail() {
  const item = (p: (typeof PAGES)[number]) => (
    <NavLink key={p.page} to={p.path} end className={({ isActive }) => `rail-item${isActive ? ' active' : ''}`}
      data-c style={{ '--c': p.c, '--crgb': p.rgb } as React.CSSProperties} title={`${p.title}: ${p.blurb}`}>
      <p.icon size={20} strokeWidth={1.9} />
      <span>{p.label}</span>
      {p.group === 'cycle' && <small>{p.phase}</small>}
    </NavLink>
  );
  return (
    <nav className="rail glass" aria-label="Pages">
      <NavLink to="/" className="brand" aria-label="DepthWizard home">
        <span className="logo"><Mountain size={20} color="#071018" strokeWidth={2.2} /></span>
        <b>Depth<br />Wizard</b>
      </NavLink>
      {PAGES.filter(p => p.group === 'workspace').map(item)}
      <div className="rail-group">Disaster cycle</div>
      {PAGES.filter(p => p.group === 'cycle').map(item)}
    </nav>
  );
}
