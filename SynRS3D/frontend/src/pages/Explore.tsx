import { Palette, Plane, Video, PenLine, Square, Info, Wand2 } from 'lucide-react';
import { engine, useEngine } from '../engine/useEngine';
import { Card, Panel, Seg, Toggle } from '../components/ui';
import { Downloads } from '../components/Shared';

export default function Explore() {
  const s = useEngine(x => x);
  const layers: [any, string][] = [['height', 'Height'], ['unc', 'Consistency'], ...(s.hasTerrain ? [['slope', 'Slope']] as [any, string][] : [])];
  return (
    <Panel page="explore">
      <Card icon={Palette} title="Colour the scene by">
        {s.view === '3d'
          ? <Seg full value={s.tex3d} onChange={v => engine.setTex3d(v)} options={[['photo', 'Photo'], ...layers.map(([k, l]) => [k === 'height' ? 'heat' : k, l]) as any]} />
          : <Seg full value={s.layer} onChange={v => engine.setLayer(v)} options={layers} />}
        <p className="fine">Consistency = spread of 4 flipped predictions: it ranks likely errors on flat ground and edges, it is not an error bar.
          Slope uses the BIS IS 14496 (Part 2) landslide classes.</p>
      </Card>
      <Card icon={Plane} title="Fly-through">
        <div className="btns">
          <button className={`btn${s.drawing ? ' on' : ''}`} disabled={s.view !== '3d'} onClick={() => engine.togglePath()}>
            <PenLine size={14} />{s.drawing ? `Done (${s.pathN})` : 'Draw path'}</button>
          <button className={`btn primary`} disabled={s.view !== '3d'} onClick={() => engine.playPath(false)}>
            {s.playing ? <><Square size={13} />Stop</> : <><Plane size={14} />Fly through</>}</button>
          <button className={`btn danger${s.recording ? ' on' : ''}`} disabled={s.view !== '3d' || s.playing} onClick={() => engine.playPath(true)}>
            <Video size={14} />Record video</button>
        </div>
        <p className="fine">{s.view === '3d' ? 'Click points on the terrain to plan a route, or fly the automatic tour. Click anywhere to measure. Switch the camera in the bar below.'
          : 'Switch to 3D to fly through the scene.'}</p>
      </Card>
      {s.hasCorr && (
        <Card icon={Wand2} title="Bias correction">
          <Toggle label="Apply height correction" checked={s.corr} onChange={v => engine.setCorr(v)} title="Learned on US LiDAR (DFC2019); not yet verified on Indian cities" />
          <p className="fine">Learned on US LiDAR (DFC2019, which is inside the model's adaptation data); not verified on Indian cities.</p>
        </Card>
      )}
      <Downloads />
      <Card icon={Info} title="About these heights"><p className="fine">{s.note}</p></Card>
    </Panel>
  );
}
