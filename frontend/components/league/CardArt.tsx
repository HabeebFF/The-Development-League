// The 30 art designs in the Player shop (Liberty Noir to Champion Platinum). Like CardFx,
// everything is original CSS and inline SVG, drawn under the card's numbers, name and photo,
// and animated with transform and opacity only. Styles live in app/card-art.css, which turns
// the motion off for people who ask for reduced motion.
//
// The SVG layers use a 150 x 210 box: the card's own size in tenths of an em, so a point
// (x, y) here sits x/10 em from the left and y/10 em from the top of the card. The rating
// column is x 15-47, the photo x 64-140 and y 11-85, the name y 87-108, the stats y 110-150,
// and y 152-185 is free art space above the footer.

import type { CSSProperties, ReactNode } from "react";

import { CARD_SHAPE_POINTS } from "./cardShape";

export const ART_EFFECTS = [
  "noir",
  "vice",
  "wanted",
  "comic",
  "anime",
  "glitch",
  "vapor",
  "graffiti",
  "dossier",
  "prism",
  "blueprint",
  "arcade",
  "afro",
  "lagos",
  "lava",
  "frost",
  "chaser",
  "royal",
  "ink",
  "steam",
  "station",
  "toxic",
  "mirage",
  "ruins",
  "racer",
  "classic",
  "glass",
  "assassin",
  "dragon",
  "platinum",
  // Earned only, never sold: TDL Cup places and MVP.
  "cupwin",
  "cupsecond",
  "cupthird",
  "cupmvp",
] as const;

/** The ribbon text and metal for each earned Cup design. */
const CUP: Record<string, { label: string; metal: string; deep: string }> = {
  cupwin: { label: "Champions", metal: "#f5c542", deep: "#7a4a06" },
  cupsecond: { label: "Runners-up", metal: "#dfe5ee", deep: "#5d6573" },
  cupthird: { label: "Third place", metal: "#e09a5a", deep: "#6a3510" },
  cupmvp: { label: "Cup MVP", metal: "#f5c542", deep: "#7a0e24" },
};

/** An original two-handled cup on a stepped base, centred on (0, 0), about 24 tall. */
function Trophy({ metal, deep }: { metal: string; deep: string }) {
  return (
    <g>
      <path d="M-7 -10 Q-13 -10 -13 -5 Q-13 1 -6 2 M7 -10 Q13 -10 13 -5 Q13 1 6 2" fill="none" stroke={metal} strokeWidth="1.6" />
      <path d="M-8 -12 H8 V-6 Q8 4 0 6 Q-8 4 -8 -6Z" fill={metal} stroke={deep} strokeWidth="0.6" />
      <path d="M-5 -10 V-6 Q-5 1 -1 3" fill="none" stroke="#fff" strokeWidth="0.8" opacity="0.6" />
      <rect x="-1.4" y="6" width="2.8" height="4" fill={metal} />
      <path d="M-6 10 H6 L7 13 H-7Z" fill={metal} stroke={deep} strokeWidth="0.5" />
      <rect x="-8" y="13" width="16" height="2.6" fill={deep} />
      <path d={`M0 -9.5 L1 -7.3 L3.4 -7.1 L1.6 -5.6 L2.1 -3.3 L0 -4.5 L-2.1 -3.3 L-1.6 -5.6 L-3.4 -7.1 L-1 -7.3Z`} fill="#fff" opacity="0.9" />
    </g>
  );
}

// Fixed "random" spreads so the server and the browser draw the same thing.
const SPREAD = [8, 83, 34, 61, 18, 72, 46, 92, 27, 55, 3, 66, 40, 88];
const DELAY = [0, 1.7, 0.6, 2.9, 1.1, 2.2, 0.3, 3.4, 1.4, 2.6, 0.9, 3.1, 1.9, 0.4];

function Svg({ children, className = "", style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <svg aria-hidden viewBox="0 0 150 210" preserveAspectRatio="none" className={`art-svg ${className}`} style={style}>
      {children}
    </svg>
  );
}

function Layer({ className, style }: { className: string; style?: CSSProperties }) {
  return <span aria-hidden className={`art-layer ${className}`} style={style} />;
}

/** A soft dark plate behind the name and stats, so busy art never hurts reading. */
function Plate({ color = "rgb(0 0 0 / 0.38)" }: { color?: string }) {
  return <span aria-hidden className="art-plate" style={{ background: color }} />;
}

function Particles({ cls, n, speed = 1, top }: { cls: string; n: number; speed?: number; top?: boolean }) {
  return (
    <>
      {SPREAD.slice(0, n).map((x, i) => (
        <span
          key={i}
          aria-hidden
          className={`art-p ${cls}`}
          style={
            {
              left: `${x}%`,
              ...(top ? { top: `${(x * 7) % 90}%` } : {}),
              animationDelay: `-${DELAY[i] * speed}s`,
              animationDuration: `${(3.2 + (i % 4) * 0.7) * speed}s`,
              "--drift": `${(i % 2 ? 1 : -1) * (0.4 + (i % 3) * 0.35)}em`,
            } as CSSProperties
          }
        />
      ))}
    </>
  );
}

const n1 = (v: number) => Math.round(v * 10) / 10;

/** A gear outline with a hole, centred on (cx, cy). */
function gear(cx: number, cy: number, r: number, teeth: number): string {
  const depth = r * 0.2;
  const s = (Math.PI * 2) / teeth;
  const pts: string[] = [];
  for (let i = 0; i < teeth; i++) {
    const a = i * s;
    for (const [da, rr] of [
      [0, r - depth],
      [0.18, r],
      [0.48, r],
      [0.66, r - depth],
    ] as const) {
      const t = a + da * s;
      pts.push(`${n1(cx + Math.cos(t) * rr)} ${n1(cy + Math.sin(t) * rr)}`);
    }
  }
  const h = r * 0.32;
  return `M${pts.join(" L")} Z M${n1(cx + h)} ${cy} A${n1(h)} ${n1(h)} 0 1 0 ${n1(cx - h)} ${cy} A${n1(h)} ${n1(h)} 0 1 0 ${n1(cx + h)} ${cy} Z`;
}

/** A palm tree: trunk from (x, y) leaning by ``lean``, with drooping fronds. */
function Palm({ x, y, h, lean }: { x: number; y: number; h: number; lean: number }) {
  const tx = x + lean;
  const ty = y - h;
  const L = h * 0.5;
  const dirs: [number, number][] = [[-1, 0.45], [-0.9, 0.05], [-0.45, -0.35], [0.45, -0.35], [0.9, 0.05], [1, 0.45], [-0.55, 0.8], [0.55, 0.8]];
  return (
    <g className="vx-palm">
      <path d={`M${x} ${y} Q${x + lean * 0.15} ${y - h * 0.55} ${tx} ${ty}`} fill="none" stroke="currentColor" strokeWidth={h * 0.06} strokeLinecap="round" />
      {dirs.map(([dx, dy], i) => {
        const ex = n1(tx + dx * L);
        const ey = n1(ty + dy * L * 0.7);
        const mx = n1(tx + dx * L * 0.5);
        const my = n1(ty + dy * L * 0.35 - L * 0.28);
        const my2 = n1(ty + dy * L * 0.35 - L * 0.12);
        return <path key={i} d={`M${n1(tx)} ${n1(ty)} Q${mx} ${my} ${ex} ${ey} Q${mx} ${my2} ${n1(tx)} ${n1(ty)}Z`} fill="currentColor" />;
      })}
    </g>
  );
}

/** Pixel art from rows of text: "#" is a pixel. */
function Pixels({ rows, x, y, size, fill, className }: { rows: string[]; x: number; y: number; size: number; fill: string; className?: string }) {
  return (
    <g fill={fill} className={className}>
      {rows.flatMap((row, j) =>
        [...row].map((c, i) => (c === "#" ? <rect key={`${i}-${j}`} x={x + i * size} y={y + j * size} width={size + 0.05} height={size + 0.05} /> : null)),
      )}
    </g>
  );
}

function Bolt({ d, delay, className = "", dur }: { d: string; delay: number; className?: string; dur?: number }) {
  return (
    <g className={`art-bolt ${className}`} style={{ animationDelay: `${delay}s`, ...(dur ? { animationDuration: `${dur}s` } : {}) }}>
      <path d={d} className="art-bolt-glow" />
      <path d={d} className="art-bolt-core" />
    </g>
  );
}

/** A four-point sparkle. */
const sparkle = (x: number, y: number, r: number) =>
  `M${x} ${y - r} Q${x + r * 0.15} ${y - r * 0.15} ${x + r} ${y} Q${x + r * 0.15} ${y + r * 0.15} ${x} ${y + r} Q${x - r * 0.15} ${y + r * 0.15} ${x - r} ${y} Q${x - r * 0.15} ${y - r * 0.15} ${x} ${y - r}Z`;

/** Background and edge art for one of the 30 designs, drawn inside the card's clipped shape. */
export default function CardArt({ effect, rating }: { effect: string; rating: number }) {
  switch (effect) {
    // 1. Liberty Noir: a painted crime-city loading screen in panels with thick black lines.
    case "noir":
      return (
        <>
          <Svg>
            {/* Left panel: smog over a suspension bridge. */}
            <rect x="0" y="0" width="60" height="89" fill="#8b7154" />
            <rect x="0" y="45" width="60" height="44" fill="#5d4e3e" />
            <g stroke="#1d1712" fill="none" strokeWidth="1.4" opacity="0.8">
              <path d="M10 89 V40 M40 89 V40 M0 72 Q10 50 10 40 Q25 70 40 40 Q50 52 60 66" />
              <path d="M0 74 H60" strokeWidth="3" />
              <path d="M14 74 V58 M20 74 V64 M26 74 V69 M32 74 V64 M36 74 V56" strokeWidth="0.6" />
            </g>
            {/* Right panel: the painted sky behind the portrait, and towers. */}
            <rect x="60" y="0" width="90" height="89" fill="#b8793f" />
            <rect x="60" y="0" width="90" height="40" fill="#d6a067" opacity="0.7" />
            <circle cx="122" cy="34" r="14" fill="#f1cf93" opacity="0.65" />
            <path
              d="M60 89 V68 H66 V58 H70 V66 H76 V50 H80 V44 H84 V50 H87 V62 H93 V54 H97 V36 H100 V30 H103 V36 H106 V58 H112 V64 H116 V46 H122 V60 H128 V52 H132 V68 H138 V60 H150 V89 Z"
              fill="#2a211b"
            />
            <g fill="#f3c46e" opacity="0.6">
              <rect x="77" y="54" width="1.6" height="2" />
              <rect x="99" y="42" width="1.6" height="2" />
              <rect x="99" y="48" width="1.6" height="2" />
              <rect x="118" y="52" width="1.6" height="2" />
              <rect x="88" y="66" width="1.6" height="2" />
            </g>
            {/* Brush strokes, like paint. */}
            <g stroke="#fff3dc" strokeWidth="2.5" opacity="0.12" strokeLinecap="round">
              <path d="M66 10 L94 6 M70 18 L140 12 M8 12 L46 8 M6 30 L30 26" />
            </g>
            {/* Bottom panel: a smoggy street. */}
            <rect x="0" y="89" width="150" height="121" fill="#2a2724" />
            <path d="M0 210 L60 150 H90 L150 210Z" fill="#363029" />
            <path d="M75 152 V210" stroke="#a88b5b" strokeWidth="1" strokeDasharray="4 5" opacity="0.5" />
            {/* Thick black gutters between panels. */}
            <g stroke="#0b0a09" strokeWidth="3.4" fill="none">
              <path d="M0 89 H150 M60 0 V89" />
              <polygon points={CARD_SHAPE_POINTS.split(" ").map((p) => p.split(",").map((v, i) => n1(Number(v) * (i ? 1.5 : 1.5))).join(",")).join(" ")} strokeWidth="6" />
            </g>
          </Svg>
          <Layer className="nx-smog nx-smog-a" />
          <Layer className="nx-smog nx-smog-b" />
          <Layer className="nx-grain" />
        </>
      );

    // 2. Neon Vice: an 80s sunset, a striped sun, palms and a neon grid.
    case "vice":
      return (
        <>
          <Layer className="vx-sky" />
          <span aria-hidden className="vx-sun" />
          <span aria-hidden className="vx-floor" />
          <span aria-hidden className="vx-grid" />
          <Svg className="vx-palms">
            <Palm x={14} y={150} h={95} lean={10} />
            <Palm x={4} y={160} h={70} lean={-2} />
            <Palm x={142} y={155} h={88} lean={-12} />
          </Svg>
          <Layer className="vx-neon" />
        </>
      );

    // 3. Wanted Poster: worn paper, nails, and a bounty that is the rating.
    case "wanted":
      return (
        <>
          <Svg>
            <rect x="62" y="9" width="80" height="79" fill="none" stroke="#4a2e14" strokeWidth="1.6" />
            <g fill="#3a2a1c">
              <circle cx="31" cy="6" r="1.8" />
              <circle cx="119" cy="6" r="1.8" />
              <circle cx="16" cy="182" r="1.8" />
              <circle cx="134" cy="182" r="1.8" />
            </g>
            <g stroke="#7a5a34" strokeWidth="0.5" opacity="0.5" fill="none">
              <path d="M0 120 L150 116 M74 0 L77 210" />
            </g>
            <path d="M20 160 H130 M26 187 H124" stroke="#4a2e14" strokeWidth="0.8" />
          </Svg>
          <span aria-hidden className="wx-word">
            <span>WANTED</span>
          </span>
          <span aria-hidden className="wx-bounty">
            <span>Bounty {(rating * 1000).toLocaleString("en-GB")} DC</span>
          </span>
          <Layer className="wx-burn" />
        </>
      );

    // 4. Comic Splash: halftone, a POW burst behind the rating, stats in a speech bubble.
    case "comic":
      return (
        <>
          <Layer className="cx-rays" />
          <Svg>
            <g transform="translate(31 22) scale(0.66) translate(-31 -30)">
            <g className="cx-burst">
              <polygon
                points="31,4 36,15 47,9 44,21 56,22 46,30 55,39 43,39 45,51 35,44 30,56 25,44 14,50 17,38 5,38 14,30 4,22 17,20 14,9 25,15"
                fill="#fff"
                stroke="#111"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
            </g>
            </g>
            <path
              d="M13 109 Q13 106 17 106 H112 L128 88 L122 106 H133 Q137 106 137 109 V156 Q137 160 133 160 H17 Q13 160 13 156 Z"
              fill="#fffdf2"
              stroke="#111"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
            <g transform="translate(119 177) scale(0.8) translate(-115 -171)">
            <g className="cx-boom">
              <polygon
                points="112,156 117,163 126,158 124,167 134,170 125,174 129,183 119,179 114,187 110,178 100,181 104,172 96,166 106,165 104,156"
                fill="#ff3b30"
                stroke="#111"
                strokeWidth="1.4"
                strokeLinejoin="round"
              />
              <text x="115" y="174" textAnchor="middle" className="cx-boom-text">
                BOOM!
              </text>
            </g>
            </g>
          </Svg>
        </>
      );

    // 5. Anime Ultimate: speed lines, a power-up aura and brush lettering.
    case "anime":
      return (
        <>
          <Layer className="ax-lines ax-lines-a" />
          <Layer className="ax-lines ax-lines-b" />
          <Svg className="ax-aura">
            <path
              d="M102 92 C78 92 66 80 70 62 C66 70 60 66 62 56 C64 44 72 40 70 26 C78 34 80 22 86 12 C88 22 94 20 98 6 C102 18 108 18 112 8 C114 20 120 22 128 14 C126 28 132 32 138 30 C134 42 142 50 140 60 C138 70 132 68 132 62 C136 80 124 92 102 92Z"
              fill="rgb(125 249 255 / 0.55)"
            />
          </Svg>
          <span aria-hidden className="ax-kanji">
            <span>極</span>
          </span>
          <span aria-hidden className="ax-tag">
            <span>覚醒</span>
          </span>
          <Plate color="rgb(3 6 40 / 0.45)" />
        </>
      );

    // 6. Cyberpunk Glitch: RGB split, scanlines and flicker.
    case "glitch":
      return (
        <>
          <Layer className="gx-glow" />
          <span aria-hidden className="gx-slice gx-slice-a" />
          <span aria-hidden className="gx-slice gx-slice-b" />
          <span aria-hidden className="gx-slice gx-slice-c" />
          <Svg>
            <g fill="none" stroke="#ff2bd6" strokeWidth="1.2" opacity="0.9">
              <path d="M8 26 V16 L18 6 H30 M120 6 H132 L142 16 V26 M8 160 V176 M142 160 V176" />
            </g>
            <g fill="#00f0ff" opacity="0.8" className="gx-blocks">
              <rect x="20" y="160" width="14" height="2" />
              <rect x="38" y="164" width="6" height="2" />
              <rect x="104" y="158" width="22" height="2" />
              <rect x="110" y="166" width="10" height="2" />
            </g>
            <text x="75" y="172" textAnchor="middle" className="gx-code">
              SYS//OVERRIDE {rating}
            </text>
          </Svg>
          <Layer className="gx-flicker" />
        </>
      );

    // 7. Vaporwave: pastel sky, a marble bust, columns and a grid floor.
    case "vapor":
      return (
        <>
          <span aria-hidden className="vp-sun" />
          <span aria-hidden className="vp-grid" />
          <Svg>
            {/* Fluted columns on both sides. */}
            <g fill="#fbf7ff" opacity="0.85">
              <rect x="3" y="98" width="8" height="70" />
              <rect x="1" y="94" width="12" height="4" />
              <rect x="139" y="98" width="8" height="70" />
              <rect x="137" y="94" width="12" height="4" />
            </g>
            <g stroke="#c9b6e0" strokeWidth="0.6">
              <path d="M5.5 98 V168 M8.5 98 V168 M141.5 98 V168 M144.5 98 V168" />
            </g>
            {/* A marble bust (original): head, curls, shoulders and plinth. */}
            <g className="vp-bust" transform="translate(118 189) scale(0.6) translate(-117 -187)">
              <path d="M100 182 Q100 168 110 165 L112 160 Q106 156 106 148 Q106 137 117 136 Q128 137 128 148 Q128 156 122 160 L124 165 Q134 168 134 182 Z" fill="#f4f1f6" />
              <path d="M107 143 Q110 134 117 134 Q125 134 128 143 Q124 138 117 139 Q111 139 107 143Z" fill="#dcd4e4" />
              <path d="M108 150 Q114 147 118 152 M104 176 Q114 172 120 178 M124 168 Q128 172 130 180" stroke="#c4b6d4" strokeWidth="0.7" fill="none" />
              <rect x="98" y="182" width="38" height="5" fill="#e3dcea" />
            </g>
            <g fill="#ffffff" opacity="0.75" transform="translate(0 8)">
              <rect x="26" y="160" width="3" height="3" />
              <rect x="31" y="160" width="3" height="3" />
              <rect x="36" y="160" width="3" height="3" />
              <rect x="26" y="165" width="3" height="3" />
              <rect x="36" y="165" width="3" height="3" />
              <rect x="26" y="170" width="3" height="3" />
              <rect x="31" y="170" width="3" height="3" />
              <rect x="36" y="170" width="3" height="3" />
            </g>
          </Svg>
          <Plate color="rgb(255 255 255 / 0.28)" />
        </>
      );

    // 8. Graffiti Wall: bricks, spray tags and drips.
    case "graffiti":
      return (
        <>
          <Layer className="fx-mist" />
          <Svg>
            <g fill="none" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 60 C14 40 24 70 30 48 S44 30 50 52 S58 70 62 44" stroke="#ff4fbf" strokeWidth="5" opacity="0.85" />
              <path d="M8 76 C20 64 30 84 42 70 S56 66 60 80" stroke="#22e3ff" strokeWidth="3" opacity="0.8" />
              <path d="M70 172 C80 162 86 184 96 170 S112 162 116 178 C120 186 132 170 140 176" stroke="#ffe14d" strokeWidth="5" opacity="0.85" />
              <path d="M22 180 L30 166 L36 180 L46 168" stroke="#7dff5a" strokeWidth="4" opacity="0.8" />
              <path d="M100 4 C110 20 124 0 134 16 S146 24 148 12" stroke="#22e3ff" strokeWidth="4" opacity="0.7" />
            </g>
            <g className="gw-drips" fill="#ff4fbf" opacity="0.85">
              <rect x="13" y="52" width="1.6" height="20" rx="0.8" />
              <rect x="29" y="50" width="1.4" height="14" rx="0.7" />
              <rect x="49" y="52" width="1.6" height="26" rx="0.8" />
            </g>
            <g fill="#ffe14d" opacity="0.85">
              <rect x="80" y="170" width="1.6" height="14" rx="0.8" />
              <rect x="105" y="168" width="1.4" height="18" rx="0.7" />
            </g>
            <text x="16" y="194" className="gw-tag" transform="rotate(-8 16 194)">
              TDL
            </text>
          </Svg>
          <Plate color="rgb(15 8 6 / 0.5)" />
        </>
      );

    // 9. Military Dossier: a camo frame, a clipped photo, a stamp and redacted lines.
    case "dossier":
      return (
        <>
          <span aria-hidden className="dx-camo" />
          <Svg>
            <rect x="61" y="8" width="82" height="80" fill="#f4efe2" transform="rotate(-2.5 102 48)" />
            <path d="M70 2 V18 Q70 22 74 22 Q78 22 78 18 V6 Q78 4 76 4 Q74 4 74 6 V16" fill="none" stroke="#8a8f96" strokeWidth="1.4" />
            <g fill="#14130f" transform="translate(0 8)">
              <rect x="18" y="156" width="40" height="4" />
              <rect x="62" y="156" width="20" height="4" opacity="0.25" />
              <rect x="18" y="164" width="22" height="4" opacity="0.25" />
              <rect x="44" y="164" width="52" height="4" />
              <rect x="100" y="164" width="30" height="4" opacity="0.25" />
              <rect x="22" y="172" width="64" height="4" />
              <rect x="90" y="172" width="34" height="4" opacity="0.25" />
            </g>
            <text x="75" y="6.5" textAnchor="middle" className="dx-file">
              FILE NO. TDL-{String(rating).padStart(3, "0")} · EYES ONLY
            </text>
          </Svg>
          <span aria-hidden className="dx-stamp">Classified</span>
        </>
      );

    // 10. Holographic Prism: rainbow facets that shift as the card tilts.
    case "prism":
      return (
        <>
          <Svg className="px-facets">
            <g opacity="0.55">
              <polygon points="0,0 60,0 20,70" fill="#ff8fc8" />
              <polygon points="60,0 150,0 100,50" fill="#8fd8ff" />
              <polygon points="20,70 60,0 100,50" fill="#fff08f" />
              <polygon points="0,0 20,70 0,120" fill="#a7ff9a" />
              <polygon points="100,50 150,0 150,110" fill="#c9a2ff" />
              <polygon points="0,120 20,70 75,150 0,190" fill="#8fffe8" />
              <polygon points="20,70 100,50 75,150" fill="#ffc68f" />
              <polygon points="100,50 150,110 75,150" fill="#ff9ab0" />
              <polygon points="75,150 150,110 150,190 75,210" fill="#9ab8ff" />
              <polygon points="0,190 75,150 75,210" fill="#e6a2ff" />
            </g>
            <g fill="none" stroke="#fff" strokeWidth="0.6" opacity="0.8">
              <path d="M60 0 L20 70 L0 120 M60 0 L100 50 L150 0 M20 70 L100 50 L75 150 L20 70 M100 50 L150 110 L75 150 L0 190 M75 150 V210 M150 190 L75 150" />
            </g>
          </Svg>
          <Layer className="px-foil" />
          <Layer className="px-glint" />
          <Plate color="rgb(255 255 255 / 0.4)" />
        </>
      );

    // 11. Blueprint: white line drawings on engineering blue.
    case "blueprint":
      return (
        <Svg className="bp-lines">
          <g fill="none" stroke="#fff" strokeWidth="0.6">
            <circle cx="102" cy="46" r="38" strokeDasharray="3 2" />
            <circle cx="102" cy="46" r="26" />
            <path d="M58 46 H146 M102 4 V90" strokeDasharray="6 2 1 2" />
            <path d="M20 4 H130 M20 2 V6 M130 2 V6 M24 3 L20 4 L24 5 M126 3 L130 4 L126 5" />
            <path d="M5 30 V180 M3 30 H7 M3 180 H7 M4 34 L5 30 L6 34 M4 176 L5 180 L6 176" />
            <path d={gear(32, 176, 9, 10)} />
            <circle cx="32" cy="176" r="13" strokeDasharray="1.5 2" />
            <rect x="92" y="162" width="44" height="24" />
            <path d="M92 170 H136 M92 178 H136 M114 162 V186" />
          </g>
          <g className="bp-text">
            <text x="75" y="2.6" textAnchor="middle">15.0 EM</text>
            <text x="94" y="167.5">TDL</text>
            <text x="116" y="167.5">DWG {rating}</text>
            <text x="94" y="175.5">PLAYER</text>
            <text x="116" y="175.5">SCALE 1:1</text>
            <text x="94" y="183.5">REV A</text>
            <text x="116" y="183.5">SHEET 1/1</text>
          </g>
        </Svg>
      );

    // 12. Retro Arcade: pixel art, a high score and CRT glow.
    case "arcade":
      return (
        <>
          <Svg>
            <g fill="#39ff14" opacity="0.9">
              {Array.from({ length: 18 }, (_, i) => (
                <rect key={`t${i}`} x={12 + i * 7} y={1} width={4} height={2} />
              ))}
              {Array.from({ length: 22 }, (_, i) => (
                <rect key={`l${i}`} x={1.5} y={18 + i * 7.5} width={2} height={4} />
              ))}
              {Array.from({ length: 22 }, (_, i) => (
                <rect key={`r${i}`} x={146.5} y={18 + i * 7.5} width={2} height={4} />
              ))}
            </g>
            <Pixels rows={[".##.##.", "#######", "#######", ".#####.", "..###..", "...#..."]} x={104} y={166} size={1.6} fill="#ff3b6b" />
            <Pixels rows={[".##.##.", "#######", "#######", ".#####.", "..###..", "...#..."]} x={117} y={166} size={1.6} fill="#ff3b6b" />
            <Pixels rows={[".##.##.", "#######", "#######", ".#####.", "..###..", "...#..."]} x={130} y={166} size={1.6} fill="#3a1630" />
            <g className="ar-coin">
              <Pixels rows={["..###..", ".#####.", "##.#.##", "##.#.##", "##.#.##", ".#####.", "..###.."]} x={20} y={165} size={1.6} fill="#ffd43b" />
            </g>
            <Pixels rows={["...#...", "..###..", "#######", ".#####.", "..#.#..", ".#...#."]} x={50} y={6} size={1.3} fill="#22e3ff" className="ar-star" />
            <text x="35" y="176" className="ar-text">
              HI {String(rating * 1000).padStart(6, "0")}
            </text>
            <text x="75" y="187" textAnchor="middle" className="ar-text ar-blink">
              INSERT COIN
            </text>
          </Svg>
          <Layer className="ar-crt" />
        </>
      );

    // 13. Afrofuturism: cosmic purple, gold orbits and kente-inspired weave.
    case "afro":
      return (
        <>
          <Layer className="af-nebula" />
          <Layer className="af-stars" />
          <span aria-hidden className="af-rays" />
          <Svg>
            <g fill="none" stroke="#f5c542" strokeWidth="0.9" className="af-orbit">
              <ellipse cx="102" cy="48" rx="46" ry="16" strokeDasharray="5 3" />
            </g>
            <g fill="none" stroke="#f5c542" strokeWidth="0.6" opacity="0.7" className="af-orbit af-orbit-b">
              <ellipse cx="102" cy="48" rx="40" ry="24" transform="rotate(-25 102 48)" />
            </g>
            <circle cx="140" cy="30" r="5" fill="#ffd66b" className="af-planet" />
            <g fill="#f5c542" opacity="0.9" transform="translate(0 14)">
              <path d="M75 166 L81 172 L75 178 L69 172Z" />
              <path d="M75 169 L78 172 L75 175 L72 172Z" fill="#3f0f66" />
            </g>
          </Svg>
          <span aria-hidden className="af-kente af-kente-l" />
          <span aria-hidden className="af-kente af-kente-r" />
          <span aria-hidden className="af-kente af-kente-b" />
          <Plate color="rgb(12 2 28 / 0.45)" />
        </>
      );

    // 14. Lagos Nights: skyline, a lagoon, danfo yellow and neon.
    case "lagos":
      return (
        <>
          <Layer className="lg-sky" />
          <span aria-hidden className="lg-stripe" />
          <Svg>
            <circle cx="30" cy="18" r="6" fill="#fff3c4" opacity="0.85" />
            <path
              d="M0 170 V150 H8 V140 H14 V148 H20 V128 H26 V124 H30 V128 H34 V146 H40 V138 H46 V152 H54 V144 H60 V156 H90 V146 H96 V136 H100 V120 H104 V114 H106 V120 H110 V136 H116 V142 H122 V132 H128 V126 H132 V132 H136 V144 H142 V138 H150 V170 Z"
              fill="#0c0718"
            />
            <g fill="#ffd400" className="lg-windows">
              <rect x="22" y="132" width="1.5" height="2" />
              <rect x="27" y="140" width="1.5" height="2" />
              <rect x="10" y="150" width="1.5" height="2" />
              <rect x="101" y="126" width="1.5" height="2" />
              <rect x="105" y="134" width="1.5" height="2" />
              <rect x="125" y="140" width="1.5" height="2" />
              <rect x="44" y="146" width="1.5" height="2" />
              <rect x="138" y="148" width="1.5" height="2" />
            </g>
            <g className="lg-neon">
              <rect x="94" y="140" width="4" height="10" fill="#ff3d9a" />
              <rect x="56" y="148" width="10" height="2" fill="#22e3ff" />
              <rect x="128" y="130" width="2" height="8" fill="#22e3ff" />
            </g>
            <path d="M0 170 H150" stroke="#2b2048" strokeWidth="1.2" />
            <g stroke="#2b2048" strokeWidth="0.6">
              <path d="M10 170 V176 M30 170 V176 M50 170 V176 M70 170 V176 M90 170 V176 M110 170 V176 M130 170 V176" />
            </g>
            {/* A yellow-and-black bus on the bridge. */}
            <g className="lg-bus-y" transform="translate(0 8)">
            <g className="lg-bus">
              <rect x="0" y="156" width="16" height="6" rx="1" fill="#ffd400" />
              <rect x="0" y="158" width="16" height="1" fill="#111" />
              <rect x="0" y="160" width="16" height="0.8" fill="#111" />
              <circle cx="3" cy="162.5" r="1.2" fill="#111" />
              <circle cx="13" cy="162.5" r="1.2" fill="#111" />
            </g>
            </g>
          </Svg>
          <span aria-hidden className="lg-water" />
          <Plate color="rgb(10 5 25 / 0.42)" />
        </>
      );

    // 15. Lava Core: cracked obsidian with glowing magma veins.
    case "lava":
      return (
        <>
          <Layer className="lv-pool" />
          <Svg className="lv-cracks">
            <g className="lv-vein lv-vein-a">
              <path d="M0 40 L14 46 L10 60 L22 70 L18 88 M10 60 L2 70" />
              <path d="M150 30 L136 40 L142 54 L130 64 M142 54 L150 62" />
            </g>
            <g className="lv-vein lv-vein-b">
              <path d="M0 150 L16 156 L26 150 L40 162 L58 160 L70 176 L75 210 M40 162 L36 178 M58 160 L66 150" />
              <path d="M150 140 L136 150 L124 146 L112 160 L96 164 L84 180 M112 160 L118 174" />
            </g>
            <g className="lv-vein lv-vein-c">
              <path d="M54 0 L50 8 L58 12 M150 92 L140 100 L146 112 M0 106 L8 114 L4 124" />
            </g>
          </Svg>
          <Particles cls="lv-ember" n={10} />
          <Plate color="rgb(0 0 0 / 0.35)" />
        </>
      );

    // 16. Frostbite: an ice-crystal frame and drifting breath fog.
    case "frost":
      return (
        <>
          <Svg>
            <g fill="rgb(230 248 255 / 0.75)" stroke="#fff" strokeWidth="0.4">
              <polygon points="0,14 18,0 26,0 10,22 22,20 4,40 0,40" />
              <polygon points="150,14 132,0 124,0 140,22 128,20 146,40 150,40" />
              <polygon points="0,100 6,108 0,112" />
              <polygon points="150,96 144,104 150,110" />
              <polygon points="0,126 12,150 6,152 18,170 0,160" />
              <polygon points="150,126 138,150 144,152 132,170 150,160" />
              <polygon points="58,0 64,8 70,0" />
              <polygon points="86,0 92,10 98,0" />
            </g>
            <g fill="none" stroke="#fff" strokeWidth="0.6" opacity="0.8">
              <path d="M75 168 V188 M66 173 L84 183 M66 183 L84 173 M75 172 L72 169 M75 172 L78 169 M75 184 L72 187 M75 184 L78 187" />
            </g>
          </Svg>
          <span aria-hidden className="fr-fog fr-fog-a" />
          <span aria-hidden className="fr-fog fr-fog-b" />
          <span aria-hidden className="fr-fog fr-fog-c" />
          <Particles cls="fr-snow" n={12} speed={1.4} />
          <Plate color="rgb(4 20 36 / 0.4)" />
        </>
      );

    // 17. Storm Chaser: a supercell, a funnel and branching lightning across the card.
    case "chaser":
      return (
        <>
          <span aria-hidden className="ch-cell" />
          <Layer className="ch-wind" />
          <Svg>
            <path d="M14 152 Q30 150 34 156 Q24 158 28 164 Q22 166 24 172 Q20 176 22 186 Q18 176 16 170 Q18 164 12 160 Q16 156 14 152Z" fill="rgb(30 30 50 / 0.85)" className="ch-funnel" />
            <Bolt d="M40 0 L52 30 L42 34 L62 74 L50 78 L72 120 M62 74 L80 86 M52 30 L30 50" delay={0} dur={4.2} />
            <Bolt d="M150 40 L128 70 L138 74 L108 118 L120 122 L96 160 M128 70 L148 90" delay={1.4} dur={4.2} />
            <Bolt d="M96 0 L90 18 L100 22 L86 44 M90 18 L76 28" delay={2.6} dur={4.2} className="opacity-80" />
          </Svg>
          <Layer className="ch-flash" />
          <Plate color="rgb(5 6 18 / 0.42)" />
        </>
      );

    // 18. Royal Gold: velvet, gold filigree corners and a crown crest.
    case "royal":
      return (
        <>
          <Svg className="ry-gold">
            <g fill="none" stroke="#e6b84d" strokeWidth="1.1" strokeLinecap="round">
              <path d="M8 20 C8 10 16 6 24 8 C18 10 16 16 20 20 C24 24 30 18 26 14 M8 20 C12 30 6 36 4 40 M24 8 C34 6 38 12 44 10" />
              <path d="M142 20 C142 10 134 6 126 8 C132 10 134 16 130 20 C126 24 120 18 124 14 M142 20 C138 30 144 36 146 40 M126 8 C116 6 112 12 106 10" />
              <path d="M8 120 C4 130 10 138 6 146 C14 142 18 148 14 154 M142 120 C146 130 140 138 144 146 C136 142 132 148 136 154" />
            </g>
            {/* The crest: a shield under a crown, with laurel sprigs. */}
            <g transform="translate(75 176) scale(0.66)">
              <path d="M-10 -10 H10 V2 Q10 12 0 16 Q-10 12 -10 2Z" fill="#3a0716" stroke="#e6b84d" strokeWidth="1.2" />
              <path d="M-5 -2 L0 -7 L5 -2 L0 3Z M0 3 V10" fill="none" stroke="#e6b84d" strokeWidth="0.9" />
              <path d="M-11 -12 L-11 -20 L-6 -15 L0 -22 L6 -15 L11 -20 L11 -12Z" fill="#e6b84d" />
              <circle cx="0" cy="-22" r="1.2" fill="#fff0c8" />
              <circle cx="-11" cy="-20" r="1" fill="#fff0c8" />
              <circle cx="11" cy="-20" r="1" fill="#fff0c8" />
              <path d="M-14 -6 Q-22 2 -16 14 M14 -6 Q22 2 16 14" fill="none" stroke="#e6b84d" strokeWidth="0.9" />
              <g fill="#e6b84d">
                <ellipse cx="-18" cy="0" rx="1.4" ry="3" transform="rotate(-30 -18 0)" />
                <ellipse cx="-19" cy="7" rx="1.4" ry="3" transform="rotate(-10 -19 7)" />
                <ellipse cx="18" cy="0" rx="1.4" ry="3" transform="rotate(30 18 0)" />
                <ellipse cx="19" cy="7" rx="1.4" ry="3" transform="rotate(10 19 7)" />
              </g>
            </g>
            <path d="M68 6 L68 1 L71 3.5 L75 0 L79 3.5 L82 1 L82 6Z" fill="#e6b84d" />
          </Svg>
          <Layer className="ry-sheen" />
          <Particles cls="ry-twinkle" n={8} top speed={1.2} />
          <Plate color="rgb(30 2 12 / 0.4)" />
        </>
      );

    // 19. Samurai Ink: sumi-e brush strokes, an enso and a red seal.
    case "ink":
      return (
        <>
          <Svg>
            <g className="ik-enso">
              <path d="M128 70 C146 46 134 12 104 10 C74 8 60 34 66 56 C72 78 98 88 120 78" fill="none" stroke="#141210" strokeWidth="5" strokeLinecap="round" opacity="0.75" pathLength={100} />
            </g>
            <path d="M0 176 L18 158 L30 166 L46 148 L62 162 L76 154 L96 170 L118 152 L134 164 L150 156 V200 H0Z" fill="rgb(20 18 16 / 0.18)" className="ik-mist" />
            <path d="M0 186 L24 170 L44 180 L70 166 L92 182 L116 172 L150 184 V200 H0Z" fill="rgb(20 18 16 / 0.28)" />
            <g stroke="#141210" strokeLinecap="round" opacity="0.6">
              <path d="M6 100 V168" strokeWidth="3" />
              <path d="M6 120 H9 M6 140 H9 M6 158 H9" strokeWidth="1.2" />
              <path d="M7 118 Q16 112 22 114 M7 138 Q14 130 20 128" strokeWidth="1.4" fill="none" />
            </g>
            <g fill="#141210" opacity="0.7">
              <circle cx="56" cy="20" r="1.4" />
              <circle cx="60" cy="26" r="0.8" />
              <circle cx="140" cy="96" r="1.2" />
              <circle cx="20" cy="94" r="0.9" />
            </g>
            <rect x="119" y="164" width="14" height="14" fill="#c8102e" rx="1" />
          </Svg>
          <span aria-hidden className="ik-seal">勝</span>
        </>
      );

    // 20. Steampunk: brass gears turning, copper pipes and rivets.
    case "steam":
      return (
        <>
          <span aria-hidden className="st-rivets" />
          <Svg>
            <g className="st-gear st-gear-a">
              <path d={gear(18, 176, 22, 14)} fill="#b8863b" stroke="#5a3b16" strokeWidth="0.8" fillRule="evenodd" />
            </g>
            <g className="st-gear st-gear-b">
              <path d={gear(49, 186, 12, 10)} fill="#d79a4a" stroke="#5a3b16" strokeWidth="0.8" fillRule="evenodd" />
            </g>
            <g className="st-gear st-gear-c">
              <path d={gear(140, 170, 18, 12)} fill="#c58e3e" stroke="#5a3b16" strokeWidth="0.8" fillRule="evenodd" />
            </g>
            <g className="st-gear st-gear-d">
              <path d={gear(56, 6, 9, 8)} fill="#b8863b" stroke="#5a3b16" strokeWidth="0.6" fillRule="evenodd" />
            </g>
            <g fill="none" stroke="#a0582a" strokeWidth="3">
              <path d="M2 30 V140" />
              <path d="M148 40 V140" />
            </g>
            <g fill="#d79a4a">
              <rect x="0" y="60" width="6" height="3" />
              <rect x="0" y="110" width="6" height="3" />
              <rect x="144" y="80" width="6" height="3" />
            </g>
            <g transform="translate(75 178) scale(0.8)">
              <circle r="11" fill="#f3e2bf" stroke="#b8863b" strokeWidth="2" />
              <path d="M-7 0 A7 7 0 0 1 7 0" fill="none" stroke="#5a3b16" strokeWidth="0.6" strokeDasharray="1 1.4" />
              <path d="M3 0 A3 3 0 0 1 7 0" fill="none" stroke="#c8102e" strokeWidth="1" />
              <g className="st-needle">
                <path d="M0 0 L0 -8" stroke="#2a1608" strokeWidth="1" strokeLinecap="round" />
              </g>
              <circle r="1.4" fill="#2a1608" />
            </g>
          </Svg>
          <span aria-hidden className="st-steam st-steam-a" />
          <span aria-hidden className="st-steam st-steam-b" />
          <Plate color="rgb(20 10 2 / 0.42)" />
        </>
      );

    // 21. Space Station: starfield, a planet's glow and HUD readouts.
    case "station":
      return (
        <>
          <span aria-hidden className="ss-stars ss-stars-a" />
          <span aria-hidden className="ss-stars ss-stars-b" />
          <span aria-hidden className="ss-planet" />
          <Svg>
            <g fill="none" stroke="#5fd4ff" strokeWidth="1" opacity="0.9">
              <path d="M6 22 V14 L14 6 H22 M128 6 H136 L144 14 V22 M6 150 V160 M144 150 V160" />
            </g>
            <g className="ss-ring" fill="none" stroke="#5fd4ff" strokeWidth="0.6" opacity="0.6">
              <circle cx="102" cy="48" r="40" strokeDasharray="2 4 12 4" />
            </g>
            <g transform="translate(22 177) scale(0.85)">
              <circle r="11" fill="rgb(95 212 255 / 0.08)" stroke="#5fd4ff" strokeWidth="0.6" />
              <circle r="6" fill="none" stroke="#5fd4ff" strokeWidth="0.4" />
              <path d="M-11 0 H11 M0 -11 V11" stroke="#5fd4ff" strokeWidth="0.3" />
              <g className="ss-sweep">
                <path d="M0 0 L0 -11 A11 11 0 0 1 9.5 -5.5Z" fill="rgb(95 212 255 / 0.4)" />
              </g>
              <circle cx="5" cy="-4" r="0.9" fill="#ff5f7a" className="ss-blip" />
            </g>
            <g className="ss-hud">
              <text x="102" y="171">O2  98%</text>
              <text x="102" y="177">ALT 412 KM</text>
              <text x="102" y="183">PWR {rating}%</text>
            </g>
            <circle cx="140" cy="10" r="1.2" fill="#ff5f7a" className="ss-blink" />
          </Svg>
          <Plate color="rgb(1 6 18 / 0.4)" />
        </>
      );

    // 22. Toxic Zone: hazard stripes, radioactive green and a closing gas wall.
    case "toxic":
      return (
        <>
          <Layer className="tx-glow" />
          <span aria-hidden className="tx-wall" />
          <span aria-hidden className="tx-tape tx-tape-top" />
          <span aria-hidden className="tx-tape tx-tape-b" />
          <Svg>
            <g transform="translate(26 177) scale(0.8)" className="tx-trefoil">
              <circle r="10" fill="#111" stroke="#b6ff1a" strokeWidth="1" />
              <circle r="2" fill="#b6ff1a" />
              {[-90, 30, 150].map((a) => (
                <path key={a} d="M3.2 0 L8.5 0 A8.5 8.5 0 0 1 4.25 7.36 L1.6 2.77 A3.2 3.2 0 0 0 3.2 0Z" fill="#b6ff1a" transform={`rotate(${a - 30})`} />
              ))}
            </g>
          </Svg>
          <Particles cls="tx-bubble" n={10} speed={1.2} />
          <Plate color="rgb(3 10 2 / 0.45)" />
        </>
      );

    // 23. Desert Mirage: a low sun, dunes and heat shimmer.
    case "mirage":
      return (
        <>
          <span aria-hidden className="mr-sun" />
          <span aria-hidden className="mr-haze" />
          <Svg>
            <path d="M0 132 Q30 118 60 128 T120 122 T150 126 V210 H0Z" fill="#b65a1f" opacity="0.75" />
            <path d="M0 152 Q40 136 80 150 T150 144 V210 H0Z" fill="#8a3d12" opacity="0.85" />
            <path d="M0 172 Q50 160 100 172 T150 168 V210 H0Z" fill="#5c2508" />
            <path d="M0 152 Q40 136 80 150" fill="none" stroke="#ffd08a" strokeWidth="0.6" opacity="0.6" />
          </Svg>
          <span aria-hidden className="mr-shimmer" />
          <Particles cls="mr-sand" n={10} top speed={1.4} />
          <Plate color="rgb(40 12 2 / 0.4)" />
        </>
      );

    // 24. Jungle Ruins: carved stone, hanging vines and moss.
    case "ruins":
      return (
        <>
          <Layer className="rn-moss" />
          <Svg>
            <g fill="none" stroke="rgb(0 0 0 / 0.45)" strokeWidth="1.6" transform="translate(0 9)">
              <path d="M16 160 h8 v8 h-4 v-4 M34 168 a5 5 0 1 1 5 -5 a2.5 2.5 0 1 1 -2.5 2.5 M52 160 l6 8 l6 -8 M74 160 h8 v8 h-8z M78 164 h0.1 M96 168 l4 -8 l4 8 l4 -8 M118 160 h8 v8 h-4 v-4" />
            </g>
            <g fill="none" stroke="rgb(255 255 255 / 0.18)" strokeWidth="0.8" transform="translate(0 9)">
              <path d="M17 161 h7 M35 169 M53 161 l5 7 M75 161 h7 M97 169 l3 -7 M119 161 h7" />
            </g>
            <g fill="none" stroke="#2f5a22" strokeWidth="1.6" strokeLinecap="round">
              <path d="M12 0 C16 20 6 34 12 52 C16 66 8 80 10 96" />
              <path d="M24 0 C22 12 30 22 26 34" />
              <path d="M140 0 C134 18 146 30 140 48 C136 60 144 72 140 84" />
            </g>
            <g fill="#4f8a32">
              {[
                [12, 14, -30], [9, 30, 30], [13, 46, -30], [10, 64, 30], [12, 82, -20], [26, 18, 30], [27, 30, -30],
                [138, 12, 30], [142, 28, -30], [139, 42, 30], [141, 60, -30], [140, 76, 30],
              ].map(([x, y, r], i) => (
                <ellipse key={i} cx={x} cy={y} rx="2.2" ry="4" transform={`rotate(${r} ${x} ${y})`} />
              ))}
            </g>
          </Svg>
          <Plate color="rgb(8 16 6 / 0.4)" />
        </>
      );

    // 25. Street Racer: carbon fibre, a speedometer for the rating, and a checkered flag.
    case "racer": {
      // The needle sweeps 270 degrees from 0 to 99.
      const angle = -225 + (Math.min(Math.max(rating, 0), 99) / 99) * 270;
      return (
        <>
          <Layer className="rc-streaks" />
          <Svg>
            <g transform="translate(31 26)">
              <path d="M-15.6 15.6 A22 22 0 1 1 15.6 15.6" fill="none" stroke="rgb(255 255 255 / 0.25)" strokeWidth="2.4" />
              <path d="M11 -19 A22 22 0 0 1 15.6 15.6" fill="none" stroke="#ff2a2a" strokeWidth="2.4" />
              {Array.from({ length: 10 }, (_, i) => {
                const a = ((-225 + i * 30) * Math.PI) / 180;
                return <path key={i} d={`M${n1(Math.cos(a) * 19)} ${n1(Math.sin(a) * 19)} L${n1(Math.cos(a) * 24)} ${n1(Math.sin(a) * 24)}`} stroke="#fff" strokeWidth="0.8" />;
              })}
              <g className="rc-needle" style={{ ["--a" as string]: `${angle}deg` }}>
                <path d="M14 0 L26 0" stroke="#ff2a2a" strokeWidth="1.6" strokeLinecap="round" />
              </g>
            </g>
            <text x="31" y="9" textAnchor="middle" className="rc-unit">
              KM/H
            </text>
            <g fill="#ff2a2a">
              <rect x="138" y="20" width="3" height="150" />
              <rect x="143" y="20" width="1.4" height="150" />
            </g>
          </Svg>
          <span aria-hidden className="rc-flag" />
          <Layer className="rc-tail" />
        </>
      );
    }

    // 26. Trading Card Classic: 90s cardboard, a foil border, a sunburst and a name banner.
    case "classic":
      return (
        <>
          <span aria-hidden className="tc-burst" />
          <span aria-hidden className="tc-border" />
          <Svg>
            <polygon points="8,88 142,84 142,108 8,112" fill="#d7262e" stroke="#ffe066" strokeWidth="1.2" />
            <g transform="translate(123 177) scale(0.8)">
              <circle r="11" fill="#ffe066" stroke="#d7262e" strokeWidth="1.5" />
              <text y="-1.5" textAnchor="middle" className="tc-num">
                No.
              </text>
              <text y="5.5" textAnchor="middle" className="tc-num tc-num-big">
                {String(rating).padStart(3, "0")}
              </text>
            </g>
            <text x="22" y="182" className="tc-series">
              SERIES 1 · 2026
            </text>
          </Svg>
        </>
      );

    // 27. Stained Glass: jewel panes in lead lines, an arched window behind the photo.
    case "glass":
      return (
        <>
          <Svg>
            <g stroke="#0a0710" strokeWidth="1.6" strokeLinejoin="round" opacity="0.92">
              {/* Arched window behind the photo. */}
              <path d="M62 90 V40 Q62 4 102 4 Q142 4 142 40 V90Z" fill="#2347a8" />
              <path d="M102 4 L102 90 M62 40 H142 M62 64 H142 M102 40 L72 12 M102 40 L132 12" fill="none" />
              <path d="M102 4 Q86 6 76 14 L102 40Z" fill="#b3122e" />
              <path d="M102 4 Q118 6 128 14 L102 40Z" fill="#14935f" />
              <path d="M62 40 L76 14 L102 40Z" fill="#e3a21a" />
              <path d="M142 40 L128 14 L102 40Z" fill="#6b2bd9" />
              <rect x="62" y="40" width="40" height="24" fill="#1d6fb8" />
              <rect x="102" y="40" width="40" height="24" fill="#c33d6a" />
              <rect x="62" y="64" width="40" height="26" fill="#14935f" />
              <rect x="102" y="64" width="40" height="26" fill="#e3a21a" />
              {/* Side panes. */}
              <path d="M0 14 L12 0 H50 L56 14 V94 H0Z" fill="#3b1d6e" />
              <path d="M0 40 H56 M0 66 H56 M28 14 V94" fill="none" />
              {/* A rose window along the base. */}
              <path d="M10 161 H140 L140 186 L75 210 L10 186Z" fill="#1d2766" />
              <path d="M75 163 A24 24 0 0 1 99 187 H51 A24 24 0 0 1 75 163Z" fill="#b3122e" />
              <path d="M75 163 V187 M75 187 L58 170 M75 187 L92 170 M51 187 H99" fill="none" />
              <path d="M10 161 L51 187 M140 161 L99 187" fill="none" />
            </g>
          </Svg>
          <Layer className="sg-rays" />
          <Plate color="rgb(5 3 12 / 0.55)" />
        </>
      );

    // 28. Shadow Assassin: smoke wisps, a hooded silhouette and red eyes.
    case "assassin":
      return (
        <>
          <span aria-hidden className="sa-smoke sa-smoke-a" />
          <span aria-hidden className="sa-smoke sa-smoke-b" />
          <span aria-hidden className="sa-smoke sa-smoke-c" />
          <Svg>
            <path d="M56 18 C44 18 38 32 40 46 C34 58 14 66 0 96 V130 H150 V96 C130 70 76 60 72 46 C74 32 68 18 56 18Z" fill="#050306" opacity="0.85" />
            <path d="M56 22 C48 22 45 32 46 42 Q56 50 66 42 C67 32 64 22 56 22Z" fill="#000" />
            <g className="sa-eyes">
              <path d="M50.5 36 L54.5 37 L50.5 38Z" fill="#ff1f3d" />
              <path d="M61.5 36 L57.5 37 L61.5 38Z" fill="#ff1f3d" />
            </g>
          </Svg>
          <span aria-hidden className="sa-blade" />
          <Layer className="sa-red" />
          <Plate color="rgb(0 0 0 / 0.35)" />
        </>
      );

    // 29. Galaxy Dragon: nebula colours and a dragon coiled round the card, scales shimmering.
    case "dragon":
      return (
        <>
          <span aria-hidden className="gd-nebula gd-nebula-a" />
          <span aria-hidden className="gd-nebula gd-nebula-b" />
          <Particles cls="gd-star" n={14} top speed={1.3} />
          <Svg>
            <g fill="none" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 196 C2 170 12 150 6 124 C0 96 10 74 6 48 C4 28 18 8 40 6 C62 4 74 14 96 8 C118 2 140 10 144 30 C148 56 140 80 146 106 C150 132 138 150 142 168 C144 180 134 188 124 182" stroke="#6b2bd9" strokeWidth="9" opacity="0.9" />
              <path d="M10 196 C2 170 12 150 6 124 C0 96 10 74 6 48 C4 28 18 8 40 6 C62 4 74 14 96 8 C118 2 140 10 144 30 C148 56 140 80 146 106 C150 132 138 150 142 168 C144 180 134 188 124 182" stroke="#ff8bf0" strokeWidth="6" strokeDasharray="2 2.6" className="gd-scales" />
              <path d="M10 196 C2 170 12 150 6 124 C0 96 10 74 6 48 C4 28 18 8 40 6 C62 4 74 14 96 8 C118 2 140 10 144 30 C148 56 140 80 146 106 C150 132 138 150 142 168" stroke="#7df9ff" strokeWidth="1" strokeDasharray="1 7" transform="translate(-2 -2)" opacity="0.9" />
            </g>
            {/* The head, at the bottom right, facing in. */}
            <g transform="translate(118 178)">
              <path d="M8 4 C2 -4 -10 -4 -18 0 L-26 -2 L-20 4 L-26 8 L-16 8 C-10 12 2 12 8 4Z" fill="#6b2bd9" stroke="#ff8bf0" strokeWidth="0.8" />
              <path d="M0 -2 L8 -12 L4 -2 M-6 -2 L-2 -12 L-2 -2" fill="#ff8bf0" />
              <circle cx="-8" cy="1.5" r="1.4" fill="#7df9ff" className="gd-eye" />
              <path d="M-26 6 Q-34 10 -38 6" stroke="#7df9ff" strokeWidth="0.6" fill="none" />
            </g>
          </Svg>
          <span aria-hidden className="gd-sheen" />
          <Plate color="rgb(8 0 30 / 0.4)" />
        </>
      );

    // 30. Champion Platinum: brushed platinum, bevelled edges, an engraved laurel and plate.
    case "platinum":
      return (
        <>
          <Svg>
            <g fill="none">
              <polygon points="12,3 138,3 147,12 147,176 75,206 3,176 3,12" stroke="rgb(255 255 255 / 0.9)" strokeWidth="0.8" />
              <polygon points="13,5 137,5 145,13 145,175 75,204 5,175 5,13" stroke="rgb(40 46 56 / 0.5)" strokeWidth="0.8" />
            </g>
            <g transform="translate(75 174) scale(0.68)">
              <g fill="none" stroke="rgb(30 36 46 / 0.7)" strokeWidth="0.8">
                <path d="M-6 12 Q-30 6 -30 -14 M6 12 Q30 6 30 -14" />
              </g>
              <g fill="rgb(30 36 46 / 0.55)">
                {[-12, -6, 0, 6, 12, 18].map((t, i) => {
                  const a = ((200 + t * 4.4) * Math.PI) / 180;
                  const x = n1(Math.cos(a) * 26 + 0);
                  const y = n1(Math.sin(a) * -22 - 2);
                  return (
                    <g key={i}>
                      <ellipse cx={x} cy={y} rx="1.6" ry="3.6" transform={`rotate(${-40 + i * 12} ${x} ${y})`} />
                      <ellipse cx={-x} cy={y} rx="1.6" ry="3.6" transform={`rotate(${40 - i * 12} ${-x} ${y})`} />
                    </g>
                  );
                })}
              </g>
              <rect x="-20" y="-6" width="40" height="11" fill="rgb(255 255 255 / 0.35)" stroke="rgb(30 36 46 / 0.6)" strokeWidth="0.6" />
              <text y="1.6" textAnchor="middle" className="pt-plate">
                CHAMPION
              </text>
            </g>
            <g fill="#fff" className="pt-sparkles">
              <path d={sparkle(22, 96, 3)} />
              <path d={sparkle(132, 92, 2.4)} />
              <path d={sparkle(56, 8, 2)} />
              <path d={sparkle(140, 150, 2.6)} />
            </g>
          </Svg>
          <Layer className="pt-sweep" />
          <Layer className="pt-edge" />
        </>
      );

    // Earned only: the TDL Cup winners, 2nd, 3rd and MVP. Staff award them on Confirm & pay.
    case "cupwin":
    case "cupsecond":
    case "cupthird":
    case "cupmvp": {
      const c = CUP[effect];
      return (
        <>
          <span aria-hidden className="cw-rays" style={{ ["--cw" as string]: c.metal }} />
          <Particles cls={`cw-confetti ${effect === "cupwin" || effect === "cupmvp" ? "" : "cw-confetti-soft"}`} n={14} speed={1.2} />
          <Svg>
            <g transform="translate(75 9) scale(0.5)">
              <Trophy metal={c.metal} deep={c.deep} />
            </g>
            {/* The ribbon along the base, with laurel sprigs. */}
            <g transform="translate(75 172)">
              <path d="M-48 -7 H48 L42 0 L48 7 H-48 L-42 0Z" fill={c.deep} stroke={c.metal} strokeWidth="0.9" />
              <path d="M-38 -5.5 H38 V5.5 H-38Z" fill={c.metal} opacity="0.95" />
              <text y="2.2" textAnchor="middle" className="cw-label" style={{ fill: c.deep }}>
                {c.label}
              </text>
              <g fill={c.metal}>
                {[0, 1, 2].map((i) => (
                  <g key={i}>
                    <ellipse cx={-52 - i * 3} cy={-6 + i * 5} rx="1.3" ry="3" transform={`rotate(${-30 + i * 20} ${-52 - i * 3} ${-6 + i * 5})`} />
                    <ellipse cx={52 + i * 3} cy={-6 + i * 5} rx="1.3" ry="3" transform={`rotate(${30 - i * 20} ${52 + i * 3} ${-6 + i * 5})`} />
                  </g>
                ))}
              </g>
            </g>
            <text x="75" y="186" textAnchor="middle" className="cw-cup" style={{ fill: c.metal }}>
              TDL CUP 2026
            </text>
            <g fill={c.metal} className="pt-sparkles">
              <path d={sparkle(22, 100, 2.6)} />
              <path d={sparkle(130, 96, 2.2)} />
              <path d={sparkle(60, 6, 1.8)} />
              <path d={sparkle(92, 6, 1.8)} />
            </g>
          </Svg>
          <Layer className="ry-sheen" />
          <Plate color="rgb(0 0 0 / 0.38)" />
        </>
      );
    }

    default:
      return null;
  }
}
