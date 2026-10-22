import { Link } from 'react-router-dom';
import { Target, ScanLine, Mountain, Box } from 'lucide-react';
import { useEngine } from '../engine/useEngine';
import { PAGES } from '../nav';

// Landing page from the Claude Design canvas (split focus, photo-filled type, fanned phase cards). Presentation only:
// choosing and uploading scenes happens on /scenes.

// Accuracy figures from README.md (docs/CLAIMS.md): measured on this code, released RS3DAda weights, zero-shot
const ACC: [string, string, string][] = [
  ['3.90', 'm', 'MAE vs airborne LiDAR, height above ground · GAMUS, 150 tiles in 3 US cities (flat ground: 5.65 m)'],
  ['5.99 / 1.94', 'm', 'MAE on satellite tiles, Atlanta / Buenos Aires · matches the published RS3DAda result'],
  ['4.85', 'm', 'MAE vs NASA ICESat-2 laser on 8 Indian scenes · urban, sparse, hilly, forested (flat ground: 8.25 m)'],
];
const STEPS: [typeof ScanLine, string, string][] = [
  [ScanLine, 'Height of every pixel', 'RS3DAda (DINOv2 ViT-L/14 + DPT, NeurIPS 2024) estimates height above ground and land cover from one optical image.'],
  [Mountain, 'Absolute surface model', 'GeoTIFFs sit on a 30 m terrain model with roofs and trees removed, levelled to NASA ICESat-2 ground points and, if you have them, your control points.'],
  [Box, 'Fly through and check', 'The photo is draped on the surface in 3D. Validate it against LiDAR, survey points or ICESat-2: MAE, RMSE, correlation.'],
];

export default function Home() {
  const done = useEngine(s => s.scenes).filter(s => s.state === 'done').map(s => s.name);
  // the hero wants a hill town, as in the design; any processed scene will do
  const hero = done.find(n => n.includes('shimla')) ?? done[0], rest = done.filter(n => n !== hero);
  const headline = <><span>One image.</span><span>Every height.</span></>;
  return (
    <div className="home" style={hero ? { '--hero-img': `url(/results/${hero}.jpg)` } as React.CSSProperties : undefined}>
      <section className="hero" aria-label="DepthWizard">
        <div className="split" />
        <div className="hero-top">
          <span className="phase"><i />ISRO · SIH26175 · TerraVista, IIT Ropar</span>
          <Link to="/scenes" className="btn mist">Choose or upload a scene</Link>
        </div>
        <div className="display ko" aria-hidden="true">{headline}</div>
        <h1 className="display">{headline}</h1>
        <div className="hero-copy">
          <p className="tracked">Heights you can fly through and check.</p>
          <p>From one satellite image, DepthWizard estimates the height of every pixel, builds an absolute surface model with terrain and
            laser data, and turns it into tools for each phase of a disaster.</p>
          <div className="hero-cta">
            <Link to="/scenes" className="btn primary lg">Get started</Link>
            <a href="#accuracy" className="ring-link" onClick={e => { e.preventDefault(); document.getElementById('accuracy')?.scrollIntoView({ behavior: 'smooth' }); }}>
              <i><Target size={20} /></i>See the accuracy</a>
          </div>
        </div>
        <div className="fan" role="list" aria-label="Disaster cycle">
          {PAGES.filter(p => p.group === 'cycle').map((p, k) => (
            <Link key={p.page} to={p.path} role="listitem" title={p.blurb} style={{ '--c': p.c } as React.CSSProperties}>
              {rest.length > 0 && <img src={`/results/${rest[k % rest.length]}.jpg`} alt="" />}
              <span className="cap"><small>{p.phase}</small><b>{p.label}</b></span>
            </Link>
          ))}
        </div>
        <div className="dpager" aria-hidden="true"><i className="on" /><i /><i /></div>
        <p className="hero-foot tracked">Runs on this machine · works offline</p>
      </section>

      <section className="lib landing">
        <div className="land-sec">
          <span className="phase"><i />How it works</span>
          <ol className="steps">
            {STEPS.map(([Icon, t, d], k) => (
              <li key={t}><span className="step-n">{String(k + 1).padStart(2, '0')}</span><Icon size={20} /><b>{t}</b><p>{d}</p></li>
            ))}
          </ol>
        </div>
        <div className="land-sec" id="accuracy">
          <span className="phase"><i />Measured accuracy</span>
          <div className="acc">
            {ACC.map(([v, u, l]) => (
              <div key={l} className="stat"><div className="bl">{l}</div><div className="big md">{v}<sup>{u}</sup></div></div>
            ))}
          </div>
          <p className="note">Zero-shot: nothing was trained or tuned on these test sets. Tall objects come out too low (about −16 m above 20 m), and flood results
            are scenarios, not forecasts.</p>
          <div><Link to="/scenes" className="btn primary lg">Choose or upload a scene</Link></div>
        </div>
      </section>
    </div>
  );
}
