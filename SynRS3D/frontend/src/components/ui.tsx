import type { CSSProperties, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { metaOf } from '../nav';
import type { Page } from '../engine/Engine';

export function Panel({ page, children, extra }: { page: Page; children: ReactNode; extra?: ReactNode }) {
  const m = metaOf(page);
  return (
    <aside className="panel glass" key={page} aria-label={m.title}>
      <header className="panel-head">
        <div className="eyebrow">{m.phase}</div>
        <h2>{m.title}</h2>
        <p>{m.blurb}</p>
        {extra}
      </header>
      <div className="panel-body">{children}</div>
    </aside>
  );
}

export function Card({ icon: Icon, title, right, children }: { icon?: LucideIcon; title?: ReactNode; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="card glass-in">
      {title && <h3>{Icon && <Icon size={15} />}{title}{right && <span className="grow">{right}</span>}</h3>}
      {children}
    </section>
  );
}

export function Seg<T extends string>({ value, options, onChange, full }: { value: T; options: [T, ReactNode][]; onChange: (v: T) => void; full?: boolean }) {
  return (
    <div className={`seg${full ? ' full' : ''}`} role="radiogroup">
      {options.map(([v, l]) => (
        <button key={v} role="radio" aria-checked={value === v} className={value === v ? 'on' : ''} onClick={() => onChange(v)}>{l}</button>
      ))}
    </div>
  );
}

export function Num({ label, value, onChange, min, max, step = 1, unit, wide, title }:
  { label: ReactNode; value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; unit?: string; wide?: boolean; title?: string }) {
  return (
    <label className={`field${wide ? ' wide' : ''}`} title={title}>
      <span>{label}{unit && <em style={{ fontStyle: 'normal', color: 'var(--faint)' }}>{unit}</em>}</span>
      <input type="number" value={Number.isFinite(value) ? value : ''} min={min} max={max} step={step}
        onChange={e => onChange(e.target.value === '' ? 0 : +e.target.value)} />
    </label>
  );
}

export function Slider({ label, value, display, onChange, min, max, step }:
  { label: ReactNode; value: number; display: ReactNode; onChange: (v: number) => void; min: number; max: number; step: number | 'any' }) {
  return (
    <label className="field">
      <span>{label}<b>{display}</b></span>
      <input type="range" value={value} min={min} max={max} step={step} onChange={e => onChange(+e.target.value)} />
    </label>
  );
}

export function Toggle({ label, checked, onChange, title }: { label: ReactNode; checked: boolean; onChange: (v: boolean) => void; title?: string }) {
  return (
    <label className="check" title={title} style={{ justifyContent: 'space-between' }}>
      <span>{label}</span>
      <input type="checkbox" className="switch" checked={checked} onChange={e => onChange(e.target.checked)} />
    </label>
  );
}

export const Kpi = ({ v, l, tone, title }: { v: ReactNode; l: ReactNode; tone?: 'hot' | 'amber' | 'blue' | 'good'; title?: string }) =>
  <div className={`kpi${tone ? ' ' + tone : ''}`} title={title}><b>{v}</b><span>{l}</span></div>;

export const Row = ({ k, v, sw }: { k: ReactNode; v: ReactNode; sw?: string }) =>
  <div className="row"><span>{sw && <i className="sw" style={{ background: sw }} />}{k}</span><b>{v}</b></div>;

export const ha = (v: number) => `${v.toFixed(1)} ha`;
export const m2 = (v: number) => `${Math.round(v).toLocaleString('en-IN')} m²`;
export const dist = (m: number) => m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(2)} km`;

// ring chart: the accent arc is pct, the rest is `rest` (or bare track); a photo or a number sits in the middle
export const Ring = ({ pct, label, img, rest, size = 132, children }:
  { pct: number; label: string; img?: string; rest?: string; size?: number; children?: ReactNode }) => (
  <div className="donut" role="img" aria-label={label}
    style={{ '--p': `${Math.min(100, Math.max(0, pct))}%`, '--ring-2': rest ?? 'transparent', width: size, height: size } as CSSProperties}>
    <div className="track" /><div className="ring" />
    {img && <img src={img} alt="" />}
    {children && <div className="mid">{children}</div>}
  </div>
);

// big number with a raised unit, under a short label marked by a coloured bar
export const Stat = ({ l, v, unit, bar, size }: { l: ReactNode; v: ReactNode; unit?: string; bar?: string; size?: 'md' | 'sm' }) => (
  <div className="stat">
    <div className="bl" style={bar ? { '--bc': bar } as CSSProperties : undefined}>{l}</div>
    <div className={`big${size ? ' ' + size : ''}`}>{v}{unit && <sup>{unit}</sup>}</div>
  </div>
);
