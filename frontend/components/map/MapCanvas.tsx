"use client";

import type Konva from "konva";
import { useEffect, useMemo, useRef, useState } from "react";
import { Image as KImage, Layer, Line, Rect, Stage } from "react-konva";
import useImage from "use-image";

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
};

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 12;

/** Zoomable, pannable map. Children are Konva nodes in content pixels. */
export default function MapCanvas({ width, height, image, onClick, children, className }: Props) {
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
  const fit = () => setMoved(null);
  const setView = (update: (v: typeof view) => typeof view) => setMoved(update(view));

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
        <button className="btn px-2 py-1" onClick={() => zoomAt(1.3, { x: size.w / 2, y: size.h / 2 })} aria-label="Zoom in">
          +
        </button>
        <button className="btn px-2 py-1" onClick={() => zoomAt(1 / 1.3, { x: size.w / 2, y: size.h / 2 })} aria-label="Zoom out">
          -
        </button>
        <button className="btn px-2 py-1" onClick={fit}>
          Fit
        </button>
      </div>
    </div>
  );
}
