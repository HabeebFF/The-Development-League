"use client";

import type Konva from "konva";
import { useEffect, useMemo, useRef, useState } from "react";
import { Image as KImage, Layer, Line, Rect, Stage } from "react-konva";
import useImage from "use-image";

import { followStep, settled, viewFor, type Box } from "@/lib/livepath";

type Props = {
  /** Size of the drawing in content pixels (the map image, or a virtual square). */
  width: number;
  height: number;
  image?: string | null;
  /** Content-pixel click (not fired after a pan drag). */
  onClick?: (px: number, py: number) => void;
  /** Draws in content pixels; ``px(n)`` converts n screen pixels to content pixels. */
  children?: (px: (n: number) => number) => React.ReactNode;
  className?: string;
  /** Content pixels to keep centred and in frame (camera follow); null leaves the view alone. */
  focus?: Box | null;
  /** Called when the person drags or zooms the map themselves. */
  onManualMove?: () => void;
  /** Extra buttons next to the zoom buttons. */
  buttons?: React.ReactNode;
  /** When this changes, the map fits itself again (e.g. a different set of teams). */
  resetKey?: string;
};

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 12;

/** Zoomable, pannable map. Children are Konva nodes in content pixels. */
export default function MapCanvas({
  width,
  height,
  image,
  onClick,
  children,
  className,
  focus = null,
  onManualMove,
  buttons,
  resetKey,
}: Props) {
  const box = useRef<HTMLDivElement>(null);
  const stage = useRef<Konva.Stage>(null);
  const [size, setSize] = useState({ w: 600, h: 600 });
  // null = fitted to the box; set once the user zooms or pans.
  const [moved, setMoved] = useState<{ scale: number; x: number; y: number } | null>(null);
  const [img] = useImage(image ?? "", "anonymous");

  const fitted = useMemo(() => {
    const scale = Math.min(size.w / width, size.h / height);
    return { scale, x: (size.w - width * scale) / 2, y: (size.h - height * scale) / 2 };
  }, [size, width, height]);
  const view = moved ?? fitted;
  const manual = () => onManualMove?.();
  const fit = () => {
    manual();
    setMoved(null);
  };
  const setView = (update: (v: typeof view) => typeof view) => setMoved(update(view));

  const lastKey = useRef(resetKey);
  useEffect(() => {
    if (lastKey.current === resetKey) return;
    lastKey.current = resetKey;
    if (!focus) setMoved(null);
  }, [resetKey, focus]);

  // Camera follow: glide towards the focus box every frame (see followStep).
  const live = useRef({ view, focus, size });
  live.current = { view, focus, size };
  const following = focus != null;
  useEffect(() => {
    if (!following) return;
    let last: number | null = null;
    let frame = requestAnimationFrame(function loop(now) {
      const dt = last == null ? 1 / 60 : Math.min(0.1, (now - last) / 1000);
      last = now;
      const { view: current, focus: box, size: s } = live.current;
      if (box) {
        const target = viewFor(box, s, 0.35, MAX_ZOOM);
        if (!settled(current, target)) setMoved(followStep(current, target, box, s, dt));
      }
      frame = requestAnimationFrame(loop);
    });
    return () => cancelAnimationFrame(frame);
  }, [following]);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width: w, height: h } = entry.contentRect;
      setSize({ w: Math.max(200, w), h: Math.max(200, h) });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  function zoomAt(factor: number, pointer: { x: number; y: number }) {
    setView((v) => {
      const scale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.scale * factor));
      const k = scale / v.scale;
      return { scale, x: pointer.x - (pointer.x - v.x) * k, y: pointer.y - (pointer.y - v.y) * k };
    });
  }

  function onWheel(e: Konva.KonvaEventObject<WheelEvent>) {
    e.evt.preventDefault();
    manual();
    const pointer = stage.current?.getPointerPosition();
    if (pointer) zoomAt(e.evt.deltaY < 0 ? 1.15 : 1 / 1.15, pointer);
  }

  function onStageClick(e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) {
    if (!onClick || e.target.draggable()) return;
    if (e.target !== e.target.getStage() && e.target.name() !== "backdrop") return;
    const pointer = stage.current?.getPointerPosition();
    if (!pointer) return;
    onClick((pointer.x - view.x) / view.scale, (pointer.y - view.y) / view.scale);
  }

  const gridLines = [];
  if (!image) {
    for (let i = 0; i <= 10; i++) {
      const t = (i / 10) * width;
      const u = (i / 10) * height;
      gridLines.push(<Line key={`v${i}`} points={[t, 0, t, height]} stroke="#2a2a37" strokeWidth={1} listening={false} />);
      gridLines.push(<Line key={`h${i}`} points={[0, u, width, u]} stroke="#2a2a37" strokeWidth={1} listening={false} />);
    }
  }

  return (
    <div ref={box} className={`relative overflow-hidden bg-[#08080b] ${className ?? ""}`}>
      <Stage
        ref={stage}
        width={size.w}
        height={size.h}
        draggable
        x={view.x}
        y={view.y}
        scaleX={view.scale}
        scaleY={view.scale}
        onWheel={onWheel}
        onDragStart={(e) => {
          if (e.target === stage.current) manual();
        }}
        onDragEnd={(e) => {
          if (e.target === stage.current) setView((v) => ({ ...v, x: e.target.x(), y: e.target.y() }));
        }}
        onClick={onStageClick}
        onTap={onStageClick}
      >
        <Layer>
          <Rect name="backdrop" width={width} height={height} fill="#101016" />
          {img && <KImage name="backdrop" image={img} width={width} height={height} />}
          {gridLines}
        </Layer>
        <Layer>{children?.((n) => n / view.scale)}</Layer>
      </Stage>
      <div className="absolute right-2 bottom-2 flex gap-1">
        {buttons}
        <button
          className="btn px-2 py-1"
          onClick={() => {
            manual();
            zoomAt(1.3, { x: size.w / 2, y: size.h / 2 });
          }}
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          className="btn px-2 py-1"
          onClick={() => {
            manual();
            zoomAt(1 / 1.3, { x: size.w / 2, y: size.h / 2 });
          }}
          aria-label="Zoom out"
        >
          -
        </button>
        <button className="btn px-2 py-1" onClick={fit}>
          Fit
        </button>
      </div>
    </div>
  );
}
