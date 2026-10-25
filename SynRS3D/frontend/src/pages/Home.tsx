import { useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';
import LiquidGlass from 'liquid-glass-react';
import { Mountain, ArrowUpRight, ArrowDownRight, UploadCloud } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { PAGES } from '../nav';
import HeroScene, { type HeroTerrain } from '../components/HeroScene';
import Doodles from '../components/Doodles';
import BgDoodles from '../components/BgDoodles';

// Landing page: full screen, no app shell. A fixed, baked scene flies by in 3D inside the hero card (HeroScene), with a
// hand-drawn annotation layer; choosing or uploading a scene opens the workspace at /scenes.

// Accuracy figures from README.md (docs/CLAIMS.md): measured on this code, released RS3DAda weights, zero-shot
const ACC: [string, string, string][] = [
  ['3.90', 'm', 'MAE vs airborne LiDAR, height above ground · GAMUS, 150 tiles in 3 US cities (flat ground: 5.65 m)'],
  ['5.99 / 1.94', 'm', 'MAE on satellite tiles, Atlanta / Buenos Aires · matches the published RS3DAda result'],
  ['4.85', 'm', 'MAE vs NASA ICESat-2 laser on 8 Indian scenes · urban, sparse, hilly, forested (flat ground: 8.25 m)'],
];
const STEPS: [string, string][] = [
  ['Height of every pixel', 'RS3DAda (DINOv2 ViT-L/14 + DPT, NeurIPS 2024) estimates height above ground and land cover from one optical image.'],
  ['Absolute surface model', 'GeoTIFFs sit on a 30 m terrain model with roofs and trees removed, levelled to NASA ICESat-2 ground points and, if you have them, your control points.'],
  ['Fly through and check', 'The photo is draped on the surface in 3D. Validate it against LiDAR, survey points or ICESat-2: MAE, RMSE, correlation.'],
];

// The page morphs into the workspace where the browser supports view transitions
function go(nav: (to: string) => void, to: string) {
  const d = document as Document & { startViewTransition?: (f: () => void) => void };
  if (d.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) d.startViewTransition(() => flushSync(() => nav(to)));
  else nav(to);
}

// liquid-glass-react centres itself on a point, so each piece sits in a fixed-size slot (.lg-slot, --w × --h)
function Liquid({ children, cls, radius }: { children: React.ReactNode; cls: string; radius: number }) {
  return (
    <div className={`lg-slot ${cls}`}>
      <LiquidGlass cornerRadius={radius} padding="0" displacementScale={52} blurAmount={0.08} saturation={160} elasticity={0.06}
        style={{ position: 'absolute', top: '50%', left: '50%' }}>
        {children}
      </LiquidGlass>
    </div>
  );
}

const fmt = (m: number) => Math.round(m).toLocaleString('en-IN');
const TABS: [string, string][] = [['top', 'Home'], ['how', 'How it works'], ['cycle', 'Disaster cycle'], ['accuracy', 'Accuracy'], ['team', 'Team']];

// Hero sketch: two pencil satellites drifting in the sky, each snapping the terrain (dashed capture cone + viewfinder)
function Satellites() {
  const sat = 'M14 20 h22 v14 h-22 z M-6 22 h16 v10 h-16 z M40 22 h16 v10 h-16 z M10 27 h4 M36 27 h4 M25 20 v-8 M21 12 h8 M25 34 v5 M20 39 h10 l-2 5 h-6 z';
  const cone = 'M25 46 L120 150 M25 46 L52 168';
  const finder = 'M64 150 v-8 h8 M112 158 h8 v-8 M66 178 h-8 v-8 M120 168 v8 h-8';
  return (
    <div className="ln-sats" aria-hidden="true">
      <div className="sat s1">
        <svg viewBox="-10 0 140 190"><path d={sat} /><path d={cone} strokeDasharray="3 7" /><path d={finder} /></svg>
        <span>click!</span>
      </div>
      <div className="sat s2">
        <svg viewBox="-10 0 140 190"><path d={sat} /><path d={cone} strokeDasharray="3 7" /><path d={finder} /></svg>
        <span>say cheese! ✦</span>
      </div>
    </div>
  );
}

// Card: the summit and a pencil cross-section through the scene that is flying behind
function ProfileCard({ t }: { t: HeroTerrain }) {
  const lo = Math.min(...t.profile), hi = Math.max(...t.profile), n = t.profile.length;
  const pts = t.profile.map((v, i) => `${(i / (n - 1) * 156 + 2).toFixed(1)},${(52 - (v - lo) / (hi - lo) * 44).toFixed(1)}`).join(' L');
  return (
    <div className="lg-in stat-in">
      <small>Summit</small>
      <b className="num">{fmt(t.peak_m)} m</b>
      <span>above sea level</span>
      <svg viewBox="0 0 160 62" role="img" aria-label={`Elevation profile across the scene, ${fmt(lo)} to ${fmt(hi)} m`}>
        <defs><pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" stroke="currentColor" strokeWidth="1" opacity=".28" /></pattern></defs>
        <path d={`M${pts} L158,60 L2,60 Z`} fill="url(#hatch)" />
        <path d={`M${pts}`} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
      <span className="cap"><i>A</i>{t.profile_len_m} m section<i>B</i></span>
    </div>
  );
}
// Card: mean error on an architect's ruler, LiDAR and NASA laser marked on the same 0–10 m scale
function RulerCard() {
  const x = (m: number) => 4 + m / 10 * 152;
  return (
    <div className="lg-in stat-in">
      <small>Mean error</small>
      <b className="num">3.90 m</b>
      <span>vs airborne LiDAR</span>
      <svg viewBox="0 0 160 62" role="img" aria-label="Mean absolute error on a 0 to 10 metre scale: 3.90 m against airborne LiDAR, 4.85 m against the NASA ICESat-2 laser">
        <line x1="4" x2="156" y1="34" y2="34" stroke="currentColor" strokeWidth="1.2" />
        {Array.from({ length: 21 }, (_, k) => <line key={k} x1={x(k / 2)} x2={x(k / 2)} y1="34" y2={k % 10 === 0 ? 24 : k % 2 === 0 ? 28 : 31} stroke="currentColor" strokeWidth="1" />)}
        <text x={x(0)} y="48" fontSize="9" fill="currentColor" textAnchor="middle">0</text>
        <text x={x(10)} y="48" fontSize="9" fill="currentColor" textAnchor="middle">10 m</text>
        <path d={`M${x(3.9)},22 l-5,-8 h10 z`} fill="#a8876a" />
        <path d={`M${x(4.85)},36 l-5,8 h10 z`} fill="currentColor" opacity=".55" />
        <text x={x(3.9) - 9} y="10" fontSize="9" fill="currentColor" textAnchor="end">LiDAR</text>
        <text x={x(4.85) + 8} y="58" fontSize="9" fill="currentColor">NASA laser 4.85</text>
      </svg>
    </div>
  );
}

export default function Home() {
  const nav = useNavigate(), file = useRef<HTMLInputElement>(null), peak = useRef<HTMLDivElement>(null), [open, setOpen] = useState(1);
  const [hero, setHero] = useState<HeroTerrain | null>(null), [stuck, setStuck] = useState(false), [active, setActive] = useState('top');
  const page = useRef<HTMLDivElement>(null);
  // hash links would be read as routes by the HashRouter, so the tabs scroll the page themselves
  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  const onScroll = () => {
    const el = page.current!, line = innerHeight * 0.4;
    setStuck(el.scrollTop > innerHeight * 0.75);
    setActive(TABS.reduce((a, [id]) => (document.getElementById(id)?.getBoundingClientRect().top ?? 1e9) < line ? id : a, 'top'));
  };
  const done = useEngine(s => s.scenes).filter(s => s.state === 'done').map(s => s.name);
  const img = (k: number) => done.length ? `/results/${done[k % done.length]}.jpg` : '';
  const upload = (f?: File) => { if (f) { engine.upload(f); go(nav, '/scenes'); } };
  const pic = (k: number) => done.length ? <img className="ln-inline" src={img(k)} alt="" /> : null;
  return (
    <div className="landing-page" ref={page} onScroll={onScroll}>
      {/* sticky: stays at the top while scrolling, turns light once past the hero; the active tab follows the section in view */}
      <header className={`ln-nav${stuck ? ' stuck' : ''}`}>
        <Link to="/" className="ln-logo" aria-label="DepthWizard home" onClick={e => { e.preventDefault(); jump('top'); }}><Mountain size={28} strokeWidth={2} /></Link>
        <nav className="ln-tabs" aria-label="Landing">
          {TABS.map(([id, label]) => (
            <a key={id} href={`#${id}`} aria-current={active === id ? 'location' : undefined} onClick={e => { e.preventDefault(); jump(id); }}>{label}</a>
          ))}
        </nav>
        <button className="cta light" onClick={() => go(nav, '/scenes')}>Open workspace<i><ArrowUpRight size={15} /></i></button>
      </header>
      <section id="top" className="ln-hero" aria-label="DepthWizard">
        <div className="ln-sky" aria-hidden="true"><i className="sun" /><i className="cl c1" /><i className="cl c2" /><i className="cl c3" /></div>
        <HeroScene peak={peak} onReady={setHero} />
        <div className="ln-scrim" aria-hidden="true" />

        <Satellites />

        {/* one column: the subtitle and buttons end exactly where the word ends */}
        <div className="ln-title">
          <h1 className="ln-word">Elevation</h1>
          <p>One satellite image.<br />Heights you can fly<br />through and check.</p>
          <div className="ln-cta">
            <Liquid cls="pill-up" radius={999}>
              <button className="lg-in pill-in" onClick={() => file.current?.click()}><UploadCloud size={16} />Upload an image</button>
            </Liquid>
            <button className="ln-white" onClick={() => go(nav, '/scenes')}>Explore the workspace</button>
            <input ref={file} type="file" hidden accept=".png,.jpg,.jpeg,.tif,.tiff" onChange={e => upload(e.target.files?.[0])} />
          </div>
          <div className="ln-note" aria-hidden="true">
            <span>one photo in,<br />every height out</span>
            <svg viewBox="0 0 120 70"><path d="M4 14 C 38 2, 82 6, 108 48" /><path d="M95 44 L108 49 L109 35" /></svg>
          </div>
        </div>

        {hero && <div className="ln-peak" ref={peak} aria-hidden="true"><b>summit · {fmt(hero.peak_m)} m</b><span className="lead" /><i className="dot" /></div>}

        {hero && (
          <div className="ln-stats" role="group" aria-label="Facts about the scene and the model">
            <Liquid cls="stat" radius={30}><ProfileCard t={hero} /></Liquid>
            <Liquid cls="stat" radius={30}><RulerCard /></Liquid>
          </div>
        )}
      </section>

      <div className="ln-body">
      <BgDoodles />
      <section className="ln-about" aria-label="About">
        <h2>About <em>us</em></h2>
        <div>
          <p>Himanshu and Shlok built DepthWizard for disaster teams. <span>From one optical image it estimates the height of every pixel,
            levels it to NASA laser points, and turns it into tools for every phase of a disaster, offline on this machine.</span></p>
          <a href="#how" className="cta">See how it works<i><ArrowUpRight size={15} /></i></a>
        </div>
      </section>

      <section className="ln-statement" aria-label="What it does">
        <p>One <em>image</em> {pic(0)} every <em>height.</em></p>
        <p>Built for <em>every phase</em> {pic(1)} of a</p>
        <p>{pic(2)} <em>disaster,</em> checked in 3D.</p>
      </section>

      <section id="how" className="ln-rows" aria-label="How it works">
        {STEPS.map(([t, d], k) => (
          <div key={t} className={`ln-row${open === k ? ' open' : ''}`}>
            <button aria-expanded={open === k} onClick={() => setOpen(open === k ? -1 : k)}>
              <span className="n">0{k + 1}</span><b>{t}</b>
              <i>{open === k ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}</i>
            </button>
            {open === k && <div className="body"><p>{d}</p>{done.length > 0 && <img src={img(k + 3)} alt="" />}</div>}
          </div>
        ))}
      </section>

      <section id="cycle" className="ln-sec" aria-label="Disaster cycle">
        <h2 className="ln-h2">Every phase of a <em>disaster</em></h2>
        <div className="ln-phases">
          {PAGES.filter(p => p.group === 'cycle').map((p, k) => (
            <Link key={p.page} to={p.path} style={{ '--c': p.c } as React.CSSProperties} onClick={e => { e.preventDefault(); go(nav, p.path); }}>
              {done.length > 0 && <img src={img(k + 1)} alt="" />}
              <span className="cap"><small>{p.phase} · {p.label}</small>{p.blurb}</span>
            </Link>
          ))}
        </div>
      </section>

      <section id="accuracy" className="ln-sec" aria-label="Measured accuracy">
        <h2 className="ln-h2">Measured, <em>not promised</em></h2>
        <div className="acc">
          {ACC.map(([v, u, l]) => (
            <div key={l} className="stat"><div className="bl">{l}</div><div className="big md">{v}<sup>{u}</sup></div></div>
          ))}
        </div>
        <p className="note">Zero-shot: nothing was trained or tuned on these test sets. Tall objects come out too low (about −16 m above 20 m), and flood results
          are scenarios, not forecasts.</p>
      </section>

      </div>

      <footer id="team" className="ln-foot">
        <div className="foot-top">
          <div className="foot-team">
            <span className="sec-label">Built by</span>
            <h2>Himanshu <em>&amp;</em> Shlok</h2>
            <button className="cta" onClick={() => go(nav, '/scenes')}>Open the workspace<i><ArrowUpRight size={15} /></i></button>
          </div>
          <Doodles />
        </div>
        <div className="foot-links">
          <nav aria-label="Workspace">{PAGES.filter(p => p.page !== 'home').map(p => <Link key={p.page} to={p.path}>{p.label}</Link>)}</nav>
          <span>Runs on this machine · works offline</span>
        </div>
        {/* stretched to exactly the card's width at any size (its natural width at this size is ~1,000 units, so ≤2% stretch) */}
        <svg className="mark" viewBox="0 0 1000 214" aria-hidden="true">
          <text x="0" y="164" fontSize="194" textLength="1000" lengthAdjust="spacingAndGlyphs">DepthWizard</text>
        </svg>
      </footer>
    </div>
  );
}
