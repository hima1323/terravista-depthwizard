// Ctrl K / "/": search every tool on every page, then jump there with the tool switched on.
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { engine, tools, useTools } from '../engine/useEngine';
import { PAGES, metaOf } from '../nav';
import type { Page } from '../engine/Engine';
import type { ToolId } from '../engine/tools';

interface Item { label: string; desc: string; kw: string; page: Page; tool?: ToolId; card?: string; run?: () => void }
const ITEMS: Item[] = [
  { label: 'Line of sight', desc: 'What can be seen from a point: watch posts, sirens, masts, cameras', kw: 'viewshed visibility tower antenna', page: 'explore', tool: 'los' },
  { label: 'Volume & area', desc: 'Area and volume of an outline: debris, stockpiles, pond capacity', kw: 'cut fill measure pile', page: 'explore', tool: 'vol' },
  { label: 'Drone flight plan', desc: 'Waypoints clear of roofs and trees; QGroundControl, KML, CSV', kw: 'uav mission survey waypoints', page: 'explore', tool: 'drone' },
  { label: 'Rooftop solar', desc: 'Solar energy of every roof per year, with shading', kw: 'pv energy kwh panels sun', page: 'explore', tool: 'solar' },
  { label: 'Map overlay', desc: 'OpenStreetMap, ISRO Bhuvan or any WMS over the scene', kw: 'wms osm bhuvan basemap roads', page: 'explore', tool: 'wms' },
  { label: 'Mosaic', desc: 'Join neighbouring GeoTIFF scenes into one larger scene', kw: 'merge tiles large area', page: 'explore', tool: 'mosaic' },
  { label: 'Fly-through & video', desc: 'Draw a path, fly it, record a video', kw: 'tour flythrough mp4 3d', page: 'explore' },
  { label: 'Downloads', desc: 'DSM, DTM, heights, 3D model, building footprints (GeoJSON), CityJSON', kw: 'export geotiff glb cityjson geojson qgis', page: 'explore' },
  { label: 'Compare with reference', desc: 'LiDAR / DSM raster, surveyed points or NASA ICESat-2: MAE, RMSE, r', kw: 'validate accuracy lidar icesat', page: 'validate' },
  { label: 'Control points', desc: 'Calibrate with points of known height', kw: 'gcp survey benchmark calibrate', page: 'validate' },
  { label: 'Heights from shadows', desc: 'Measure building heights from their shadows', kw: 'shadow sun elevation azimuth', page: 'validate', tool: 'shadow' },
  { label: 'Fix tall objects', desc: 'Scale building and tree heights (shadows, ICESat-2 canopy)', kw: 'trees canopy under-estimate correction', page: 'validate', tool: 'fix' },
  { label: 'Calibrated error bars', desc: 'Turn the consistency score into 68 / 90 / 95% error bars', kw: 'uncertainty conformal confidence', page: 'validate', tool: 'err' },
  { label: 'Terrain source', desc: 'Use your own DEM: CartoDEM, SRTM', kw: 'dem cartodem srtm bhuvan elevation', page: 'validate', tool: 'dem' },
  { label: 'GNSS & field points', desc: 'Import CSV / GPX or phone field-app points as control points', kw: 'gps gpx field phone', page: 'validate', tool: 'gnss' },
  { label: 'Landslide-prone slopes', desc: 'Slope classes (BIS IS 14496)', kw: 'slope hazard', page: 'prepare' },
  { label: 'Landslide risk', desc: 'Slope, land cover, relief and rain', kw: 'landslide susceptibility rain bis', page: 'prepare', tool: 'slide' },
  { label: 'Flood exposure', desc: 'What each water rise would reach', kw: 'exposure rise', page: 'prepare' },
  { label: 'People at risk', desc: 'Residents in buildings hit by each hazard', kw: 'population exposure affected', page: 'assess', card: 'tool-people' },
  { label: 'Flood scenario', desc: 'Water level, flooded ground and buildings', kw: 'inundation water level', page: 'respond' },
  { label: 'Rain & river timeline', desc: 'Hour by hour flooding from rain and river rise', kw: 'forecast hours rain', page: 'respond' },
  { label: 'Flowing water (2D)', desc: 'Water spreading from a breach or river over time', kw: 'breach dam embankment simulation shallow', page: 'respond', tool: 'flow' },
  { label: 'Observed flood', desc: 'Sentinel-1 / water mask vs the scenario; fit the level', kw: 'sentinel radar sar csi real', page: 'respond', tool: 'obs' },
  { label: 'Route finder', desc: 'A route that avoids buildings, steep ground and deep water', kw: 'path navigation access', page: 'respond' },
  { label: 'Relief sites', desc: 'Helipads and relief camps: flat, open, dry', kw: 'helipad helicopter camp shelter', page: 'relief' },
  { label: 'Evacuation plan', desc: 'Each building to the nearest camp with space', kw: 'evacuation shelter assignment', page: 'relief', tool: 'evac' },
  { label: 'Damage: before / after', desc: 'Collapsed and damaged buildings, debris, lost canopy', kw: 'earthquake collapse change detection', page: 'assess', tool: 'dmg' },
  { label: 'Impact report', desc: 'What the scenario affects, block by block (JSON + CSV)', kw: 'export affected', page: 'assess' },
  { label: 'Situation report', desc: 'Printable page with the map and every tool result (PDF)', kw: 'pdf print report', page: 'assess', card: 'tool-report' },
  { label: 'Field app (phone)', desc: 'Record GPS points in the field for calibration', kw: 'gps mobile phone', page: 'validate', run: () => window.open('/field', '_blank') },
  { label: 'Upload an image', desc: 'PNG, JPG or GeoTIFF (Cartosat, Maxar, …)', kw: 'add new scene file', page: 'scenes' },
];

export default function ToolFinder() {
  const open = useTools(s => s.palette), nav = useNavigate(), [q, setQ] = useState(''), [sel, setSel] = useState(0), input = useRef<HTMLInputElement>(null);
  const shown = useMemo(() => {
    const words = q.toLowerCase().trim().split(/\s+/).filter(Boolean);
    return ITEMS.filter(it => words.every(w => `${it.label} ${it.desc} ${it.kw} ${metaOf(it.page).label}`.toLowerCase().includes(w)));
  }, [q]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); tools.set({ palette: !tools.s.palette }); }
      else if (e.key === '/' && !tools.s.palette && !(e.target as Element).matches?.('input, select, textarea')) { e.preventDefault(); tools.set({ palette: true }); }
    };
    addEventListener('keydown', key);
    return () => removeEventListener('keydown', key);
  }, []);
  useEffect(() => { if (open) { setQ(''); setSel(0); setTimeout(() => input.current?.focus(), 0); } }, [open]);
  if (!open) return null;
  const close = () => tools.set({ palette: false });
  const go = (it: Item | undefined) => {
    if (!it) return;
    close();
    if (it.run) return it.run();
    nav(PAGES.find(p => p.page === it.page)!.path);
    setTimeout(() => {   // after the page has rendered: switch the tool on and bring its card into view
      if (it.tool && engine.data) tools.toggle(it.tool, true);
      setTimeout(() => document.getElementById(it.card || (it.tool ? `tool-${it.tool}` : ''))?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 60);
    }, 60);
  };
  return (
    <div className="finder" role="dialog" aria-label="Find a tool" onClick={e => { if (e.target === e.currentTarget) close(); }}>
      <div className="finder-box glass">
        <label className="finder-q"><Search size={18} />
          <input ref={input} autoFocus type="text" placeholder="Find a tool… flood, drone, shadow, solar, damage" value={q} aria-label="Search tools"
            onChange={e => { setQ(e.target.value); setSel(0); }}
            onKeyDown={e => {
              if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); setSel(k => Math.min(shown.length - 1, Math.max(0, k + (e.key === 'ArrowDown' ? 1 : -1)))); }
              else if (e.key === 'Enter') go(shown[sel]);
              else if (e.key === 'Escape') close();
            }} /></label>
        <ul className="finder-list">
          {shown.map((it, k) => { const m = metaOf(it.page); return (
            <li key={it.label} className={k === sel ? 'sel' : ''} onMouseEnter={() => setSel(k)} onClick={() => go(it)}>
              <m.icon size={16} style={{ color: m.c }} />
              <div><b>{it.label}</b><span>{it.desc}</span></div>
              <em style={{ '--c': m.c } as React.CSSProperties}>{m.label}</em>
            </li>); })}
          {!shown.length && <li className="none"><div><b>No tool matches</b><span>Try another word: flood, drone, shadow, solar, damage…</span></div></li>}
        </ul>
        <div className="finder-foot">↑ ↓ to choose · Enter to open · Esc to close · it opens the right page for you</div>
      </div>
    </div>
  );
}

export function FinderButton() {
  return <button className="btn sm finder-btn" onClick={() => tools.set({ palette: true })} title="Search every tool (Ctrl K)"><Search size={13} />Find a tool<kbd>Ctrl K</kbd></button>;
}
