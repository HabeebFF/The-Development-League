"use client";

import type { ReactNode } from "react";

import { CARD_SHAPE } from "./PlayerCard";

/** A card that starts face down and turns over when tapped. The back shows which slot it
 * is (``title``, ``period``) but not who; ``children`` is the face. */
export default function FlipCard({
  up,
  animate,
  onFlip,
  title,
  period,
  children,
}: {
  up: boolean;
  /** Off while the remembered flips load, so cards opened before don't spin on arrival. */
  animate: boolean;
  onFlip: () => void;
  title: string;
  period: string;
  children: ReactNode;
}) {
  return (
    <div className="relative [perspective:1400px]">
      <div
        className={`relative [transform-style:preserve-3d] ${animate ? "transition-transform duration-700 ease-[cubic-bezier(.2,.8,.2,1)] motion-reduce:transition-none" : ""}`}
        style={{ transform: up ? "rotateY(180deg)" : "none" }}
      >
        <div
          className={`[backface-visibility:hidden] ${up && animate ? "card-reveal" : ""}`}
          style={{ transform: "rotateY(180deg)" }}
          aria-hidden={!up}
          inert={!up}
        >
          {children}
        </div>
        <button
          type="button"
          onClick={onFlip}
          className={`group absolute inset-0 [backface-visibility:hidden] ${up ? "pointer-events-none" : "cursor-pointer"}`}
          aria-label={`Reveal the ${title}`}
          tabIndex={up ? -1 : 0}
          aria-hidden={up}
        >
          <CardBack title={title} period={period} />
        </button>
      </div>
    </div>
  );
}

/** The back of a face-down card: the league mark, the slot and the week or month. */
function CardBack({ title, period }: { title: string; period: string }) {
  return (
    <span className="absolute inset-0 flex transition duration-200 group-hover:-translate-y-1 group-focus-visible:-translate-y-1">
      <span
        className="relative flex h-full w-full flex-col items-center justify-center gap-1.5 pb-[12%] text-center sm:gap-2"
        style={{
          clipPath: CARD_SHAPE,
          background:
            "radial-gradient(circle at 50% 38%, rgb(255 90 31 / 0.35), transparent 55%), linear-gradient(160deg, #1d2130, #07080c)",
        }}
      >
        <span className="absolute inset-0 bg-[repeating-linear-gradient(60deg,rgb(255_255_255/0.04)_0_2px,transparent_2px_12px)]" />
        <span
          className="absolute inset-[6px]"
          style={{
            clipPath: CARD_SHAPE,
            boxShadow: "inset 0 0 0 1.5px #ff5a1f",
          }}
        />
        <span className="card-back-shine absolute inset-0" />
        <span className="relative font-display text-4xl leading-none text-accent sm:text-6xl">
          TDL
        </span>
        <span className="relative h-px w-16 bg-accent/60" />
        <span className="relative px-3 font-display text-base leading-tight text-text uppercase sm:text-xl">
          {title}
        </span>
        <span className="relative px-2 text-[0.6rem] text-muted uppercase tracking-widest sm:text-[0.7rem]">
          {period}
        </span>
        <span className="relative mt-1 border border-accent/60 px-2 py-1 text-[0.55rem] sm:mt-3 sm:px-2.5 sm:text-[0.65rem] font-bold text-accent uppercase tracking-[0.2em] group-hover:bg-accent group-hover:text-bg">
          Tap to reveal
        </span>
      </span>
    </span>
  );
}
