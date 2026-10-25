import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';
import LiquidGlass from 'liquid-glass-react';
import { Mountain, Target, ArrowUpRight, ArrowDownRight, UploadCloud } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { PAGES } from '../nav';
import { nice } from '../engine/algos';
import Stage from '../components/Stage';

// Landing page: full screen, no app shell. A real reconstructed scene flies by in 3D inside the hero card (Engine.cinema);
// choosing or uploading a scene opens the workspace at /scenes.

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
// terrain reads best from the air, so the hero prefers a hill town until the user has opened a scene of their own
const SHOWCASE = ['shimla_hill_town', 'iit_ropar', 'guwahati_riverside'];

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

export default function Home() {
  const nav = useNavigate(), file = useRef<HTMLInputElement>(null), [open, setOpen] = useState(1);
  const scenes = useEngine(s => s.scenes), current = useEngine(s => s.current), ready = useEngine(s => s.status === 'ready');
  const done = scenes.filter(s => s.state === 'done').map(s => s.name);
  const img = (k: number) => done.length ? `/results/${done[k % done.length]}.jpg` : '';
  useEffect(() => { if (engine.getState().view !== '3d') engine.setView('3d'); }, []);
  useEffect(() => {
    if (engine.visited) return;
    const pick = SHOWCASE.find(n => done.includes(n)) ?? done[0];
    if (pick && engine.getState().current !== pick) engine.select(pick);
  }, [done.join()]);
  const upload = (f?: File) => { if (f) { engine.upload(f); go(nav, '/scenes'); } };
  const pic = (k: number) => done.length ? <img className="ln-inline" src={img(k)} alt="" /> : null;
  return (
    <div className="landing-page">
      <section className="ln-hero" aria-label="DepthWizard">
        <div className="ln-sky" aria-hidden="true"><i className="sun" /><i className="cl c1" /><i className="cl c2" /><i className="cl c3" /></div>
        <Stage hero />
        <div className="ln-scrim" aria-hidden="true" />

        <header className="ln-nav">
          <Link to="/" className="ln-logo" aria-label="DepthWizard home"><Mountain size={28} strokeWidth={2} /></Link>
          <nav className="ln-tabs" aria-label="Landing">
            <a href="#top" aria-current="page">Home</a><a href="#how">How it works</a><a href="#cycle">Disaster cycle</a><a href="#accuracy">Accuracy</a><a href="#team">Team</a>
          </nav>
          <button className="cta light" onClick={() => go(nav, '/scenes')}>Open workspace<i><ArrowUpRight size={15} /></i></button>
        </header>

        <h1 className="ln-word">Elevation</h1>
        <div className="ln-sub">
          <p>One satellite image.<br />Heights you can fly<br />through and check.</p>
          <div className="ln-cta">
            <Liquid cls="pill-up" radius={999}>
              <button className="lg-in pill-in" onClick={() => file.current?.click()}><UploadCloud size={16} />Upload an image</button>
            </Liquid>
            <button className="ln-white" onClick={() => go(nav, '/scenes')}>Explore the workspace</button>
            <input ref={file} type="file" hidden accept=".png,.jpg,.jpeg,.tif,.tiff" onChange={e => upload(e.target.files?.[0])} />
          </div>
        </div>

        <div className="ln-stats" aria-label="Measured accuracy">
          <Liquid cls="stat-a" radius={30}>
            <div className="lg-in stat-in"><div><b className="num">4.85 m</b><span>MAE vs NASA ICESat-2 laser, 8 Indian scenes</span></div><i><Target size={18} /></i></div>
          </Liquid>
          <Liquid cls="stat-b" radius={30}>
            <div className="lg-in stat-in"><div><b className="num">3.90 m</b><span>MAE vs airborne LiDAR, 150 tiles in 3 US cities</span></div><i><Mountain size={18} /></i></div>
          </Liquid>
        </div>
        {ready && current && <p className="ln-live"><i />Live 3D · {nice(current)}, reconstructed by DepthWizard</p>}
      </section>

      <section className="ln-about" aria-label="About">
        <h2>About <em>us</em></h2>
        <div>
          <p>TerraVista, IIT Ropar builds DepthWizard for ISRO's SIH26175. <span>From one optical image it estimates the height of every pixel,
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

      <footer id="team" className="ln-foot">
        <div className="cols">
          <span>Runs on this machine · works offline</span>
          <div><b>Team</b>TerraVista, IIT Ropar<br />Smart India Hackathon 2026 · SIH26175 · ISRO</div>
          <div><b>Workspace</b>Scenes · Explore · Validate<br />Prepare · Respond · Relief · Assess</div>
        </div>
        <span className="mark" aria-hidden="true">DepthWizard</span>
      </footer>
    </div>
  );
}
