import { useEffect, useRef } from 'react';
import { divRamp } from '../engine/algos';

// rain bars on top, water level line below, cursor at the shown hour (classic viewer's drawChart)
export function TimelineChart({ P, rises, days, h }: { P: number[]; rises: number[]; days: number; h: number }) {
  const T = P.length, w = 340, ht = 96, top = 22, bot = 14;
  const lo = Math.min(...rises), hi = Math.max(lo + 0.5, ...rises), pmax = Math.max(1, ...P);
  const x = (t: number) => 4 + t / T * (w - 8), y = (r: number) => top + (1 - (r - lo) / (hi - lo)) * (ht - top - bot);
  return (
    <svg viewBox={`0 0 ${w} ${ht}`} width="100%" role="img" aria-label="Rain and water level over time" style={{ display: 'block' }}>
      {Array.from({ length: days - 1 }, (_, d) => <line key={d} x1={x((d + 1) * 24)} x2={x((d + 1) * 24)} y1={0} y2={ht} stroke="rgba(255,255,255,.08)" />)}
      {P.map((p, t) => p > 0 && <rect key={t} x={x(t)} y={top - 2 - p / pmax * 16} width={Math.max(1, (w - 8) / T)} height={p / pmax * 16} fill="#7cc4ff" opacity={.8} />)}
      <polyline fill="none" stroke="var(--accent)" strokeWidth={1.8} points={rises.map((r, t) => `${x(t).toFixed(1)},${y(r).toFixed(1)}`).join(' ')} />
      <line x1={x(h)} x2={x(h)} y1={0} y2={ht} stroke="#ffc861" strokeWidth={1.5} />
      <text x={w - 4} y={10} fill="rgba(197,209,218,.5)" fontSize={9.5} textAnchor="end">rain, max {pmax.toFixed(0)} mm/h</text>
      <text x={w - 4} y={ht - 2} fill="rgba(197,209,218,.5)" fontSize={9.5} textAnchor="end">water +{lo.toFixed(1)} → +{hi.toFixed(1)} m</text>
    </svg>
  );
}

function ctx2d(cv: HTMLCanvasElement, w: number, h: number) {
  const dpr = devicePixelRatio || 1;
  cv.width = w * dpr; cv.height = h * dpr; cv.style.width = '100%'; cv.style.maxWidth = w + 'px';
  const c = cv.getContext('2d')!; c.scale(dpr, dpr);
  c.font = '10px "Montserrat Variable", sans-serif'; c.fillStyle = 'rgba(197,209,218,.55)'; c.strokeStyle = 'rgba(255,255,255,.08)';
  return c;
}

// ours vs reference, 1:1 line, points coloured by their error
export function Scatter({ xs, ys, lim }: { xs: number[]; ys: number[]; lim: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const w = 340, h = 240, L = 38, B = 26, T = 8, R = 8, c = ctx2d(ref.current, w, h);
    const vals = xs.concat(ys).filter(Number.isFinite).sort((a, b) => a - b);
    if (!vals.length) return;
    let lo = vals[Math.floor(vals.length * 0.005)], hi = vals[Math.ceil(vals.length * 0.995) - 1];
    const pad = Math.max(1, (hi - lo) * 0.05); lo -= pad; hi += pad;
    const X = (v: number) => L + (v - lo) / (hi - lo) * (w - L - R), Y = (v: number) => h - B - (v - lo) / (hi - lo) * (h - B - T);
    for (let k = 0; k <= 4; k++) {
      const v = lo + (hi - lo) * k / 4;
      c.beginPath(); c.moveTo(X(v), T); c.lineTo(X(v), h - B); c.moveTo(L, Y(v)); c.lineTo(w - R, Y(v)); c.stroke();
      c.textAlign = 'center'; c.fillText(v.toFixed(0), X(v), h - B + 12); c.textAlign = 'right'; c.fillText(v.toFixed(0), L - 4, Y(v) + 3);
    }
    c.setLineDash([4, 3]); c.strokeStyle = 'rgba(238,242,251,.8)'; c.beginPath(); c.moveTo(X(lo), Y(lo)); c.lineTo(X(hi), Y(hi)); c.stroke(); c.setLineDash([]);
    xs.forEach((x, i) => {
      const y = ys[i];
      if (!Number.isFinite(x) || !Number.isFinite(y) || x < lo || x > hi || y < lo || y > hi) return;
      c.fillStyle = `rgba(${divRamp((y - x) / (2 * lim) + 0.5)},0.6)`; c.fillRect(X(x) - 1.2, Y(y) - 1.2, 2.4, 2.4);
    });
    c.fillStyle = 'rgba(197,209,218,.55)'; c.textAlign = 'center'; c.fillText('reference (m)', L + (w - L - R) / 2, h - 2);
    c.save(); c.translate(10, T + (h - B - T) / 2); c.rotate(-Math.PI / 2); c.fillText('ours (m)', 0, 0); c.restore();
    c.textAlign = 'left'; c.fillText('dashed = perfect agreement', L + 4, T + 10);
  }, [xs, ys, lim]);
  return <canvas ref={ref} role="img" aria-label="Scatter plot of our heights against the reference" />;
}

// distribution of ours − reference
export function Hist({ hg }: { hg: { counts: number[]; lo: number; hi: number } }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const w = 340, h = 96, L = 8, B = 16, T = 6, c = ctx2d(ref.current, w, h), n = hg.counts.length, mx = Math.max(...hg.counts, 1);
    hg.counts.forEach((k, i) => {
      const x0 = L + i / n * (w - 2 * L), bw = (w - 2 * L) / n - 1, mid = hg.lo + (i + 0.5) / n * (hg.hi - hg.lo);
      c.fillStyle = `rgb(${divRamp(mid / (2 * hg.hi) + 0.5)})`; c.fillRect(x0, h - B - k / mx * (h - B - T), bw, k / mx * (h - B - T));
    });
    c.fillStyle = 'rgba(197,209,218,.55)'; c.textAlign = 'left'; c.fillText(`${hg.lo.toFixed(1)} m`, L, h - 3);
    c.textAlign = 'center'; c.fillText('0 · error (ours − reference)', w / 2, h - 3); c.textAlign = 'right'; c.fillText(`+${hg.hi.toFixed(1)} m`, w - L, h - 3);
  }, [hg]);
  return <canvas ref={ref} role="img" aria-label="Histogram of errors" />;
}
