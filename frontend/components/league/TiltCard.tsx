"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** A slow 3D tilt that follows the pointer (and, on phones, page scroll). It also feeds the
 *  holo foil designs where to put their rainbow (``--fx-x`` and ``--fx-y``). Off for people
 *  who ask for reduced motion. */
export default function TiltCard({ children, max = 9 }: { children: ReactNode; max?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    el.dataset.tilt = "on";
    let frame = 0;
    let touched = false;
    const set = (x: number, y: number) => {
      el.style.setProperty("--fx-x", x.toFixed(3));
      el.style.setProperty("--fx-y", y.toFixed(3));
      el.style.transform = `perspective(900px) rotateX(${((0.5 - y) * max).toFixed(2)}deg) rotateY(${((x - 0.5) * max).toFixed(2)}deg)`;
    };
    const move = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") touched = true;
      const r = el.getBoundingClientRect();
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() =>
        set(Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1), Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1)),
      );
    };
    const leave = () => set(0.5, 0.5);
    // Phones: no hover, so scrolling the card through the screen moves the foil instead.
    const scroll = () => {
      if (window.matchMedia("(hover: hover)").matches && !touched) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const t = Math.min(Math.max((r.top + r.height / 2) / window.innerHeight, 0), 1);
        set(0.5 + (t - 0.5) * 0.6, t);
      });
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    window.addEventListener("scroll", scroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
      window.removeEventListener("scroll", scroll);
    };
  }, [max]);

  return (
    <div ref={ref} data-tilt="off" className="fx-tilt inline-block">
      {children}
    </div>
  );
}
