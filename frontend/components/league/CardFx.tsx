// The moving parts of a Player shop card design: particles, lightning, smoke, foil, storms.
// Everything is CSS and inline SVG, animated with transform and opacity only so it stays
// smooth on cheap phones; styles live in app/card-fx.css, which turns the motion off for
// people who ask for reduced motion. These layers only paint the card's background and
// edges: they never move or cover the numbers, name or photo.

import type { CSSProperties } from "react";

import { CARD_SHAPE_POINTS } from "./cardShape";

/** Effects drawn here; any other key is left to PlayerCard's simple effects. */
export const FX_EFFECTS = [
  "metal",
  "neon",
  "scope",
  "embers",
  "lightning",
  "smoke",
  "foil",
  "zone",
  "storm",
  "goldrain",
  "phoenix",
  "void",
] as const;

// Fixed "random" spreads so the server and the browser draw the same thing.
const SPREAD = [8, 83, 34, 61, 18, 72, 46, 92, 27, 55, 3, 66, 40, 88];
const DELAY = [0, 1.7, 0.6, 2.9, 1.1, 2.2, 0.3, 3.4, 1.4, 2.6, 0.9, 3.1, 1.9, 0.4];

function Particles({ cls, n, speed = 1 }: { cls: string; n: number; speed?: number }) {
  return (
    <>
      {SPREAD.slice(0, n).map((x, i) => (
        <span
          key={i}
          aria-hidden
          className={`fx-p ${cls}`}
          style={
            {
              left: `${x}%`,
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

function Bolt({ d, delay, className = "" }: { d: string; delay: number; className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 100 140"
      preserveAspectRatio="none"
      className={`fx-bolt absolute inset-0 h-full w-full ${className}`}
      style={{ animationDelay: `${delay}s` }}
    >
      <path d={d} className="fx-bolt-glow" />
      <path d={d} className="fx-bolt-core" />
    </svg>
  );
}

/** Background and edge layers for one effect, drawn inside the card's clipped shape. */
export default function CardFx({ effect }: { effect: string }) {
  switch (effect) {
    case "metal":
      return <span aria-hidden className="fx-layer fx-metal" />;
    case "neon":
      return (
        <>
          <span aria-hidden className="fx-layer fx-neon" />
          <span aria-hidden className="fx-layer fx-neon-run" />
        </>
      );
    case "scope":
      return (
        <>
          <span aria-hidden className="fx-layer fx-scan" />
          <svg aria-hidden viewBox="0 0 100 100" className="fx-reticle absolute top-[0.6em] right-[0.4em] h-[8.4em] w-[8.4em]">
            <circle cx="50" cy="50" r="30" />
            <circle cx="50" cy="50" r="2" className="fx-reticle-dot" />
            <path d="M50 8v26M50 66v26M8 50h26M66 50h26" />
          </svg>
          <span aria-hidden className="design-shine absolute inset-0" />
        </>
      );
    case "embers":
      return (
        <>
          <span aria-hidden className="fx-layer fx-heat" />
          <Particles cls="fx-ember" n={12} />
        </>
      );
    case "lightning":
      return (
        <>
          <span aria-hidden className="fx-layer fx-rage-flash" />
          <Bolt d="M14 0 L24 22 L16 26 L30 52 L22 55 L34 82" delay={0} />
          <Bolt d="M92 18 L80 40 L88 44 L72 70 L80 73 L66 100" delay={1.3} />
          <Bolt d="M58 0 L52 14 L60 17 L50 34" delay={2.4} className="opacity-80" />
        </>
      );
    case "smoke":
      return (
        <>
          <span aria-hidden className="fx-layer fx-smoke fx-smoke-a" />
          <span aria-hidden className="fx-layer fx-smoke fx-smoke-b" />
          <span aria-hidden className="fx-blast" />
          <Particles cls="fx-spark" n={8} speed={0.8} />
        </>
      );
    case "foil":
      return (
        <>
          <span aria-hidden className="fx-layer fx-foil" />
          <span aria-hidden className="fx-layer fx-foil-glint" />
        </>
      );
    case "zone":
      return (
        <>
          <span aria-hidden className="fx-layer fx-zone-burn" />
          <span aria-hidden className="fx-zone-ring" />
          <Particles cls="fx-ember" n={8} />
        </>
      );
    case "storm":
      return (
        <>
          <span aria-hidden className="fx-layer fx-clouds" />
          <span aria-hidden className="fx-rain" />
          <span aria-hidden className="fx-layer fx-storm-flash" />
          <Bolt d="M70 0 L62 20 L70 23 L56 48" delay={0.05} className="fx-bolt-storm" />
        </>
      );
    case "goldrain":
      return (
        <>
          <span aria-hidden className="fx-layer fx-gold-glow" />
          <Particles cls="fx-coin" n={14} speed={1.1} />
          <span aria-hidden className="design-shine absolute inset-0" />
        </>
      );
    case "phoenix":
      return (
        <>
          <span aria-hidden className="fx-layer fx-heat" />
          <svg aria-hidden viewBox="0 0 100 70" className="fx-wings absolute top-[0.8em] left-1/2 h-[9em] w-[15em] -translate-x-1/2">
            <defs>
              <linearGradient id="fx-wing" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0" stopColor="#ff4d00" stopOpacity="0.9" />
                <stop offset="0.6" stopColor="#ffb02e" stopOpacity="0.55" />
                <stop offset="1" stopColor="#fff2b0" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path className="fx-wing-l" d="M50 60 C38 52 22 50 4 30 C16 36 22 34 28 30 C18 28 12 18 8 6 C22 20 34 24 42 30 C38 20 38 12 40 2 C46 18 48 34 50 60Z" />
            <path className="fx-wing-r" d="M50 60 C62 52 78 50 96 30 C84 36 78 34 72 30 C82 28 88 18 92 6 C78 20 66 24 58 30 C62 20 62 12 60 2 C54 18 52 34 50 60Z" />
          </svg>
          <Particles cls="fx-ember" n={10} speed={0.9} />
        </>
      );
    case "void":
      return (
        <>
          <span aria-hidden className="fx-void-swirl" />
          <span aria-hidden className="fx-layer fx-void-core" />
          <Particles cls="fx-star" n={12} speed={1.3} />
        </>
      );
    default:
      return null;
  }
}

/** A glowing frame with a light running round it (Legendary and Mythic). Sits on top of
 *  the card, outside the clip, so the glow can spill over the edge. */
export function CardFrame({ color, glow }: { color: string; glow: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 100 140"
      preserveAspectRatio="none"
      className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
      style={{ filter: `drop-shadow(0 0 0.35em rgb(${glow} / 0.9))` }}
    >
      <polygon points={CARD_SHAPE_POINTS} fill="none" stroke={color} strokeWidth="1.1" vectorEffect="non-scaling-stroke" className="fx-frame-line" />
      <polygon
        points={CARD_SHAPE_POINTS}
        fill="none"
        stroke="#fff"
        strokeWidth="2.4"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        pathLength={100}
        className="fx-frame-run"
      />
    </svg>
  );
}
