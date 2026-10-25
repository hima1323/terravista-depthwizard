// Footer sketch, drawn in the hero's pencil style. Original line art (no borrowed characters), white strokes on the dark footer:
// a chibi mapper cheering with a tablet, Himanshu surveying with a theodolite, Shlok flying a mapping drone over a
// contour-lined mountain, and a hard-hat cat waving an SOS flag. Classes drive small CSS loops (styles.css, "footer sketch").
const star = (x: number, y: number, r: number) => `M${x} ${y - r} l${r * .3} ${r * .7} l${r * .7} ${r * .3} l${-r * .7} ${r * .3} l${-r * .3} ${r * .7} l${-r * .3} ${-r * .7} l${-r * .7} ${-r * .3} l${r * .7} ${-r * .3} z`;

export default function Doodles() {
  return (
    <svg className="doodles" viewBox="0 0 840 262" role="img"
      aria-label="Sketch: a cheering chibi mapper with a tablet, Himanshu surveying with a theodolite, Shlok flying a mapping drone over a mountain, and a cat in a hard hat waving an SOS flag">
      <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 232 C 200 226, 640 236, 832 228" />

        {/* chibi mapper: big head, twin ponytails, tablet with a contour map; hops */}
        <g className="d-hop">
          <circle cx="70" cy="122" r="27" />
          <path d="M43 116 Q 48 90 70 88 Q 93 90 97 116" />
          <path d="M47 108 l8 6 l4 -11 l6 10 l5 -12 l5 12 l6 -10 l4 11 l8 -6" />
          <path d="M44 110 q-20 6 -15 32 q4 -11 12 -15 M96 110 q20 6 15 32 q-4 -11 -12 -15" />
          <path d="M66 138 q4 4 8 0" />
          <path d="M70 149 v26 M70 158 L54 166 M70 158 L86 166 M64 175 l-6 52 M76 175 l6 52" />
          <path d="M48 160 h44 v28 h-44 z" />
          <path d="M54 180 q8 -10 14 -4 t16 -7 M56 172 q6 -6 12 -2" opacity=".6" />
          <path d="M30 84 l-6 -10 M38 80 l-2 -12 M102 80 l2 -12" opacity=".7" />
        </g>
        <path className="d-twinkle" d={star(110, 104, 12)} />

        <g transform="translate(150 10)">
          <path d="M150 221 L232 118 L262 146 L314 72 L404 221" />
          <path d="M188 182 Q 240 168 280 176 T 366 172 M212 152 Q 246 140 262 148 M282 128 Q 310 116 336 126 M298 100 Q 314 92 328 100" opacity=".6" />
          <path className="d-wave" d="M314 72 l-3 -16 l14 6 l-11 4" />
          {/* Himanshu: cap, grin, theodolite */}
          <circle cx="66" cy="122" r="17" />
          <path d="M49 118 Q 66 96 83 118 M81 116 L97 112 M59 130 Q 66 136 73 130" />
          <path d="M66 139 L66 184 M66 152 L92 162 M66 152 L50 170 M66 184 L54 216 M66 184 L78 216" />
          <path d="M106 166 L94 216 M106 166 L106 216 M106 166 L118 216 M96 152 h20 v14 h-20 z M116 156 L130 150" />
          <path className="d-march" d="M130 150 L176 128" strokeDasharray="2 6" opacity=".7" />
          {/* Shlok: spiky hair, controller, signal to the drone */}
          <circle cx="474" cy="130" r="17" />
          <path d="M458 124 L461 108 L468 118 L474 102 L480 118 L487 108 L490 124 M467 137 Q 474 143 481 137" />
          <path d="M474 147 L474 190 M474 160 L462 172 M474 160 L486 172 M474 190 L462 220 M474 190 L486 220 M458 170 h32 v10 h-32 z" />
          <path className="d-march" d="M474 112 Q 446 66 404 56" strokeDasharray="3 6" opacity=".7" />
          {/* the drone hovers, rotors spin, scan beams sweep */}
          <g className="d-hover">
            <path d="M382 52 h22 v9 h-22 z M376 46 L410 66 M410 46 L376 66" />
            <ellipse className="d-rotor" cx="376" cy="45" rx="10" ry="2.5" /><ellipse className="d-rotor" cx="410" cy="45" rx="10" ry="2.5" />
            <ellipse className="d-rotor" cx="376" cy="67" rx="10" ry="2.5" /><ellipse className="d-rotor" cx="410" cy="67" rx="10" ry="2.5" />
            <path className="d-march" d="M393 62 L360 118 M393 62 L426 118" strokeDasharray="1 5" opacity=".5" />
          </g>
          <path className="d-twinkle slow" d={star(40, 55, 10)} />
        </g>

        {/* hard-hat cat: happy ^ ^ eyes, waving SOS flag, curly tail */}
        <circle cx="772" cy="146" r="24" />
        <path d="M752 132 l3 -20 l14 12 M792 132 l-3 -20 l-14 12" />
        <path d="M748 132 q24 -32 48 0 z M742 132 h60" />
        <path d="M760 146 q4 -5 8 0 M776 146 q4 -5 8 0 M766 155 q3 3 6 0 q3 3 6 0 M748 152 h-12 M748 157 l-11 3 M796 152 h12 M796 157 l11 3" />
        <path d="M772 170 v28 M772 180 l18 -10 M772 180 l-14 8 M766 198 l-6 30 M778 198 l6 30" />
        <path className="d-tail" d="M780 196 q22 2 18 -22" />
        <path d="M790 170 v-62" />
        <path className="d-wave" d="M790 108 h30 l-7 9 l7 9 h-30" />
        <path className="d-twinkle" d={star(818, 80, 8)} />
      </g>
      <g fill="currentColor">
        <g className="d-hop"><ellipse cx="61" cy="124" rx="4" ry="5.5" /><ellipse cx="79" cy="124" rx="4" ry="5.5" /></g>
        <circle cx="210" cy="131" r="1.8" /><circle cx="222" cy="131" r="1.8" /><circle cx="618" cy="139" r="1.8" /><circle cx="630" cy="139" r="1.8" />
      </g>
      <g className="d-hop" fill="#1c1c1e"><circle cx="62.5" cy="122" r="1.5" /><circle cx="80.5" cy="122" r="1.5" /></g>
      <g className="d-hop blush" fill="none" strokeWidth="2" strokeLinecap="round"><path d="M52 132 l5 -2 M83 130 l5 2" /></g>
      <g className="hand" fill="currentColor" textAnchor="middle">
        <g className="d-hop"><text x="70" y="70" fontSize="24" transform="rotate(-8 70 70)">yatta!</text></g>
        <text className="d-pulse" x="652" y="98" fontSize="26" transform="rotate(10 652 98)">!!</text>
        <text className="d-wave" x="805" y="122" fontSize="13">SOS</text>
        <text x="220" y="256" fontSize="22">Himanshu</text><text x="624" y="256" fontSize="22">Shlok</text>
      </g>
    </svg>
  );
}

// Faint sky behind the whole footer: stars, orbit paths, a ringed planet, a satellite, clouds, contour loops, a helicopter
export function FooterSky() {
  const stars: [number, number, number][] = [[60, 60, 9], [300, 40, 6], [520, 120, 7], [700, 30, 5], [980, 80, 8], [1180, 40, 6], [1340, 130, 9],
    [120, 420, 6], [460, 470, 5], [880, 440, 7], [1260, 470, 6], [640, 300, 5], [1020, 300, 6], [200, 250, 5]];
  return (
    <svg className="foot-sky" viewBox="0 0 1400 520" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <g fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        {stars.map(([x, y, r], i) => <path key={i} className={`d-twinkle${i % 3 ? ' slow' : ''}`} style={{ animationDelay: `${-i * .7}s` }} d={star(x, y, r)} />)}
        <path d="M-40 200 C 300 90, 900 90, 1440 210" strokeDasharray="2 10" />
        <path d="M-40 360 C 400 250, 1000 300, 1440 380" strokeDasharray="2 12" opacity=".7" />
        <g className="d-drift"><circle cx="1240" cy="250" r="26" /><path d="M1200 262 C 1220 240, 1270 236, 1282 240" /><ellipse cx="1240" cy="252" rx="46" ry="10" transform="rotate(-14 1240 252)" /></g>
        <g className="d-drift slow"><path d="M560 196 h18 v12 h-18 z M542 198 h14 v8 h-14 z M582 198 h14 v8 h-14 z M569 196 v-8" /><path className="d-march" d="M569 208 L548 250 M569 208 L590 250" strokeDasharray="1 6" /></g>
        <path d="M120 140 a14 14 0 0 1 10 -24 a20 20 0 0 1 38 -2 a14 14 0 0 1 8 26 z" />
        <path d="M860 230 a12 12 0 0 1 8 -20 a16 16 0 0 1 30 -2 a12 12 0 0 1 6 22 z" />
        <path d="M40 330 c 40 -30 90 -20 110 10 c 20 30 -30 50 -70 40 c -40 -10 -60 -30 -40 -50 z M66 336 c 24 -14 54 -8 64 8 c 10 16 -18 26 -40 20 c -22 -6 -34 -18 -24 -28 z" opacity=".8" />
        <path d="M1130 420 c 50 -24 110 -10 120 22 c 8 26 -50 40 -94 30 c -40 -8 -60 -38 -26 -52 z" opacity=".8" />
        <g className="d-drift"><path d="M380 330 h44 M402 330 v5 M388 335 h32 a9 9 0 0 1 0 18 h-26 a9 9 0 0 1 -6 -18 z M420 344 h18 l4 -5 M396 353 l-4 6 M412 353 l-4 6" /></g>
      </g>
    </svg>
  );
}
