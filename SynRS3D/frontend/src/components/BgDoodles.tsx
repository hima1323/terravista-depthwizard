// Background sticker layer: hand-drawn disaster-management doodles (original line art), tilted and faint, gently bobbing.
// Used behind the landing's sections, the scene library, and the map stage (behind the transparent 3D canvas / around
// the 2D image). `place` overrides each sticker's spot as [left, top, rotation°, width px]. Purely decorative.
type Sticker = { x: string; y: string; r: number; s: number; d: string; note?: string };

const S: Sticker[] = [
  // rescue helicopter with a rope and a life ring
  { x: '89%', y: '1%', r: -8, s: 130, note: 'on the way!',
    d: 'M20 40 h70 M55 40 v8 M30 48 h50 a14 14 0 0 1 0 28 h-40 a14 14 0 0 1 -10 -28 z M80 62 h30 l6 -8 M94 76 l-6 10 M46 76 l-6 10 M34 86 h60 M60 76 v34 M60 118 m-8 0 a8 8 0 1 0 16 0 a8 8 0 1 0 -16 0' },
  // house in flood water
  { x: '0.5%', y: '9%', r: 6, s: 120, note: 'stay dry ✌',
    d: 'M30 70 l30 -26 l30 26 M38 64 v34 h44 v-34 M54 98 v-16 h12 v16 M10 100 q10 -8 20 0 t20 0 t20 0 t20 0 t20 0 M18 112 q10 -8 20 0 t20 0 t20 0 t20 0' },
  // storm cloud with rain and a bolt
  { x: '92%', y: '24%', r: 10, s: 110,
    d: 'M30 60 a16 16 0 0 1 8 -30 a22 22 0 0 1 42 -4 a16 16 0 0 1 12 34 z M40 72 l-4 12 M60 72 l-4 12 M80 72 l-4 12 M58 62 l-8 18 h10 l-6 16' },
  // relief tent with a flag
  { x: '0.5%', y: '35%', r: -6, s: 110, note: 'camp here →',
    d: 'M20 100 l40 -56 l40 56 z M60 44 v56 M48 100 l12 -22 l12 22 M60 44 v-24 l16 6 l-16 6 M8 100 h104' },
  // satellite beaming down
  { x: '92%', y: '46%', r: -12, s: 105,
    d: 'M48 40 h24 v24 h-24 z M10 44 h30 v16 h-30 z M80 44 h30 v16 h-30 z M40 52 h8 M72 52 h8 M60 64 v10 M48 92 l12 -18 l12 18' },
  // life ring
  { x: '0.8%', y: '60%', r: 14, s: 90, note: 'sos!!',
    d: 'M50 50 m-34 0 a34 34 0 1 0 68 0 a34 34 0 1 0 -68 0 M50 50 m-16 0 a16 16 0 1 0 32 0 a16 16 0 1 0 -32 0 M26 26 l12 12 M74 26 l-12 12 M26 74 l12 -12 M74 74 l-12 -12' },
  // first-aid kit
  { x: '92.5%', y: '64%', r: 8, s: 95,
    d: 'M20 40 h80 v52 h-80 z M44 40 v-10 h32 v10 M60 52 v28 M46 66 h28' },
  // sandbags
  { x: '0.5%', y: '82%', r: -4, s: 110,
    d: 'M14 96 q22 -16 44 0 q-22 10 -44 0 z M62 96 q22 -16 44 0 q-22 10 -44 0 z M38 80 q22 -16 44 0 q-22 10 -44 0 z' },
  // siren
  { x: '92.5%', y: '86%', r: -10, s: 90,
    d: 'M34 80 v-26 a16 16 0 0 1 32 0 v26 M26 80 h48 v10 h-48 z M50 22 v-10 M28 30 l-8 -8 M72 30 l8 -8 M14 50 h-8 M86 50 h8' },
];

export type Spot = [string, string, number, number];
export default function BgDoodles({ place, className = '' }: { place?: Spot[]; className?: string }) {
  const list = place ? place.map(([x, y, r, s], i) => ({ ...S[i % S.length], x, y, r, s })) : S;
  return (
    <div className={`bg-doodles ${className}`} aria-hidden="true">
      {list.map((k, i) => (
        <div key={i} className="sticker" style={{ left: k.x, top: k.y, width: k.s, '--r': `${k.r}deg`, animationDelay: `${-i * 1.7}s` } as React.CSSProperties}>
          <svg viewBox="0 0 120 120"><path d={k.d} /></svg>
          {k.note && <span>{k.note}</span>}
        </div>
      ))}
    </div>
  );
}
