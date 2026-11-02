"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

import { INTRO_KEY } from "./introScript";
import "./RoaringLionIntro.css";

/**
 * "THE ROARING LION" splash, played over the home page the first time someone opens the site
 * in a browser session. Tap anywhere (or Skip, or Esc) to close it early. Add ?intro=1 to the
 * address to play it again.
 *
 * It lives in the root layout (outside the sign-in gate) and only shows on "/". The overlay
 * is part of the server HTML so the home page never flashes before it. A tiny script in the
 * root layout's <head> marks <html class="intro-seen"> before the first paint when it has
 * already played this session, and CSS hides it.
 */

const PLAY_MS = 4300; // when the exit starts
const EXIT_MS = 650;
const QUICK_MS = 1600; // reduced motion: a still frame, then a fade

function shouldPlay(): boolean {
  try {
    if (/[?&]intro=1/.test(window.location.search)) return true;
    return !sessionStorage.getItem(INTRO_KEY);
  } catch {
    return false;
  }
}

const noop = () => () => {};

// Embers: fixed pseudo-random spots so the server and browser draw the same thing.
const EMBERS = Array.from({ length: 26 }, (_, i) => {
  const r = (n: number) => ((Math.sin(i * 12.9898 + n * 78.233) * 43758.5453) % 1 + 1) % 1;
  return {
    left: `${(r(1) * 100).toFixed(1)}%`,
    size: `${(2 + r(2) * 5).toFixed(1)}px`,
    delay: `${(r(3) * 2.4).toFixed(2)}s`,
    dur: `${(2.6 + r(4) * 2.2).toFixed(2)}s`,
    drift: `${((r(5) - 0.5) * 80).toFixed(0)}px`,
  };
});

export default function RoaringLionIntro() {
  // During hydration this is the server's answer (show), then the browser's own.
  const home = usePathname() === "/";
  const wanted = useSyncExternalStore(noop, shouldPlay, () => true) && home;
  const [phase, setPhase] = useState<"play" | "leave" | "done">("play");

  const close = useCallback(() => {
    setPhase((p) => (p === "play" ? "leave" : p));
  }, []);

  useEffect(() => {
    if (!wanted) return;
    try {
      sessionStorage.setItem(INTRO_KEY, "1");
    } catch {}
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t = window.setTimeout(close, reduced ? QUICK_MS : PLAY_MS);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === "Enter" || e.key === " ") close();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [wanted, close]);

  useEffect(() => {
    if (phase !== "leave") return;
    const t = window.setTimeout(() => setPhase("done"), EXIT_MS);
    return () => window.clearTimeout(t);
  }, [phase]);

  useEffect(() => {
    if (phase === "done") document.body.style.overflow = "";
  }, [phase]);

  if (!wanted || phase === "done") return null;

  return (
    <div
      className={`lion-intro ${phase === "leave" ? "lion-leave" : ""}`}
      role="dialog"
      aria-label="The Roaring Lion"
      onClick={close}
    >
      <div className="lion-shake">
        <div className="lion-glow" aria-hidden />
        <div className="lion-rays" aria-hidden />
        <div className="lion-ghost font-display" aria-hidden>
          ROAR
        </div>
        <div className="lion-embers" aria-hidden>
          {EMBERS.map((e, i) => (
            <span
              key={i}
              style={
                {
                  left: e.left,
                  width: e.size,
                  height: e.size,
                  animationDelay: e.delay,
                  animationDuration: e.dur,
                  "--drift": e.drift,
                } as React.CSSProperties
              }
            />
          ))}
        </div>

        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="lion-player" src="/intro/roaring-lion.webp" alt="" width={415} height={610} fetchPriority="high" />
        <div className="lion-floor" aria-hidden />
        <div className="lion-flash" aria-hidden />

        <div className="lion-words font-display">
          <span className="lion-the">The</span>
          <h1 className="lion-title">
            <span className="lion-roaring">Roaring</span>
            <span className="lion-lion">Lion</span>
          </h1>
          <span className="lion-bar" aria-hidden />
          <span className="lion-sub">
            The Development <b>League</b>
          </span>
        </div>
      </div>

      <button
        type="button"
        className="lion-skip"
        onClick={(e) => {
          e.stopPropagation();
          close();
        }}
      >
        Skip &rsaquo;
      </button>
    </div>
  );
}
