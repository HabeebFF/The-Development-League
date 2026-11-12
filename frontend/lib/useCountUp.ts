"use client";

import { useEffect, useRef, useState, type RefObject } from "react";

import { countUpValue } from "./countup";

/**
 * Counts a number up from zero the first time it scrolls into view. The final number is shown straight
 * away (server render, no JS, reduced motion), so nothing ever sits at zero waiting.
 */
export function useCountUp(end: number, decimals = 0, duration = 750): [RefObject<HTMLSpanElement | null>, string] {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(() => end.toFixed(decimals));
  useEffect(() => {
    const el = ref.current;
    const final = end.toFixed(decimals);
    if (!el || typeof IntersectionObserver === "undefined" || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(final);
      return;
    }
    let frame = 0;
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        io.disconnect();
        const t0 = performance.now();
        const step = (t: number) => {
          const p = (t - t0) / duration;
          setShown(countUpValue(end, p, decimals));
          if (p < 1) frame = requestAnimationFrame(step);
        };
        frame = requestAnimationFrame(step);
      },
      { threshold: 0.6 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [end, decimals, duration]);
  return [ref, shown];
}
