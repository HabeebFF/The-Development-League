"use client";

import type Konva from "konva";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Circle, Group } from "react-konva";

import MapCanvas from "@/components/map/MapCanvas";
import { api, type GameMap } from "@/lib/api";
import { anchorsFor, fitBounds, then, toPixel, toWorld, type Transform } from "@/lib/coordinates";

type Reference = { x: number; z: number; kind: "KILL" | "DEATH" };
type CalPoint = {
  id: number;
  label: string;
  world_x: number;
  world_z: number;
  pixel_x: number;
  pixel_y: number;
  error_px: number | null;
};
type CalState = {
  transform: Transform | null;
  calibration_error: number | null;
  calibrated_at: string | null;
  points: CalPoint[];
};

// Moves applied on top of the saved transform while lining the dots up.
type Adjust = { dx: number; dy: number; scale: number; angle: number; flipX: boolean; flipY: boolean };
const NO_ADJUST: Adjust = { dx: 0, dy: 0, scale: 1, angle: 0, flipX: false, flipY: false };

function adjustment(a: Adjust, cx: number, cy: number): Transform {
  const rad = (a.angle * Math.PI) / 180;
  const fx = a.flipX ? -1 : 1;
  const fy = a.flipY ? -1 : 1;
  const m = {
    a: a.scale * fx * Math.cos(rad),
    b: -a.scale * fy * Math.sin(rad),
    d: a.scale * fx * Math.sin(rad),
    e: a.scale * fy * Math.cos(rad),
  };
  return { ...m, c: cx + a.dx - (m.a * cx + m.b * cy), f: cy + a.dy - (m.d * cx + m.e * cy) };
}

export default function CalibrationTool({ slug }: { slug: string }) {
  const [map, setMap] = useState<GameMap | null>(null);
  const [refs, setRefs] = useState<Reference[]>([]);
  const [cal, setCal] = useState<CalState | null>(null);
  const [adjust, setAdjust] = useState<Adjust>(NO_ADJUST);
  const [pending, setPending] = useState<{ x: string; z: string; label: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad?: boolean } | null>(null);

  const load = useCallback(async () => {
    const [m, r, c] = await Promise.all([
      api<GameMap>(`/admin/maps/${slug}`),
      api<{ points: Reference[] }>(`/admin/maps/${slug}/reference-points`),
      api<CalState>(`/admin/maps/${slug}/calibration-points`),
    ]);
    setMap(m);
    setRefs(r.points);
    setCal(c);
    setAdjust(NO_ADJUST);
  }, [slug]);

  useEffect(() => {
    (async () => {
      try {
        await load();
      } catch (e) {
        setNotice({ text: e instanceof Error ? e.message : "Couldn't load this map.", bad: true });
      }
    })();
  }, [load]);

  const w = map?.image_width ?? 1024;
  const h = map?.image_height ?? 1024;
  const base = useMemo(() => cal?.transform ?? fitBounds(refs, w, h), [cal, refs, w, h]);
  const current = useMemo(() => then(base, adjustment(adjust, w / 2, h / 2)), [base, adjust, w, h]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setNotice(null);
    try {
      await action();
    } catch (e) {
      setNotice({ text: e instanceof Error ? e.message : "Something went wrong.", bad: true });
    } finally {
      setBusy(false);
    }
  };

  const upload = (file: File) =>
    run(async () => {
      const form = new FormData();
      form.append("image", file);
      await api(`/admin/maps/${slug}`, { method: "PATCH", body: form });
      await load();
      setNotice({ text: "Image uploaded. Now line the dots up with the map." });
    });

  const restoreBuiltIn = () =>
    run(async () => {
      await api(`/admin/maps/${slug}/use-default-image`, { method: "POST" });
      await load();
      setNotice({ text: "Built-in image restored with its calibration." });
    });

  const saveOverlay = () =>
    run(async () => {
      // Three anchors spread over the image pin the lined-up transform down exactly.
      const world = [
        [0.15, 0.15],
        [0.85, 0.15],
        [0.15, 0.85],
      ].map(([u, v]) => toWorld(current, u * w, v * h));
      await api(`/admin/maps/${slug}/calibration-points`, {
        method: "PUT",
        body: { points: anchorsFor(current, world).map((p, i) => ({ ...p, label: `Overlay ${i + 1}` })) },
      });
      await load();
      setNotice({ text: "Saved. Rotations on this map now use this calibration." });
    });

  const addKnownPoint = (px: number, py: number) => {
    if (!pending) return;
    const x = Number(pending.x);
    const z = Number(pending.z);
    if (!Number.isFinite(x) || !Number.isFinite(z)) {
      setNotice({ text: "Enter the spot's world X and Z first.", bad: true });
      return;
    }
    run(async () => {
      await api(`/admin/maps/${slug}/calibration-points`, {
        method: "POST",
        body: { label: pending.label, world_x: x, world_z: z, pixel_x: px, pixel_y: py },
      });
      setPending(null);
      await load();
    });
  };

  const remove = (id: number) =>
    run(async () => {
      await api(`/admin/maps/${slug}/calibration-points/${id}`, { method: "DELETE" });
      await load();
    });

  const onDragEnd = (e: Konva.KonvaEventObject<DragEvent>) => {
    const node = e.target;
    setAdjust((a) => ({ ...a, dx: a.dx + node.x(), dy: a.dy + node.y() }));
    node.position({ x: 0, y: 0 });
  };

  if (!map || !cal) {
    return <p className="p-6 text-muted">{notice?.text ?? "Loading map..."}</p>;
  }

  const nudge = (patch: Partial<Adjust> | ((a: Adjust) => Partial<Adjust>)) =>
    setAdjust((a) => ({ ...a, ...(typeof patch === "function" ? patch(a) : patch) }));
  const changed = JSON.stringify(adjust) !== JSON.stringify(NO_ADJUST);

  return (
    <div className="flex h-[calc(100dvh-var(--header-h))] flex-col lg:flex-row">
      <MapCanvas
        width={w}
        height={h}
        image={map.image}
        onClick={pending ? addKnownPoint : undefined}
        className="min-h-[50dvh] flex-1"
      >
        {(px) => (
          <>
            <Group draggable={!pending} onDragEnd={onDragEnd}>
              {/* A transparent hit area so the whole cloud can be dragged. */}
              {refs.map((r, i) => {
                const p = toPixel(current, r.x, r.z);
                return (
                  <Circle
                    key={i}
                    x={p.px}
                    y={p.py}
                    radius={px(3)}
                    hitStrokeWidth={px(10)}
                    fill={r.kind === "KILL" ? "#ff2e63" : "#ffffff"}
                    opacity={0.8}
                  />
                );
              })}
            </Group>
            {cal.points.map((p) => (
              <Circle key={p.id} x={p.pixel_x} y={p.pixel_y} radius={px(7)} stroke="#ffb800" strokeWidth={px(2)} listening={false} />
            ))}
          </>
        )}
      </MapCanvas>

      <aside className="shrink-0 overflow-y-auto border-t border-line p-4 text-sm lg:w-80 lg:border-t-0 lg:border-l">
        <Link href="/staff/maps" className="text-xs text-muted hover:text-text">
          &larr; Maps
        </Link>
        <h1 className="mt-1 font-display text-2xl uppercase">{map.name}</h1>
        <p className="text-xs text-muted">
          {cal.transform
            ? `Calibrated · error ${cal.calibration_error ?? 0} px`
            : "Not calibrated yet"}{" "}
          · {refs.length} fight positions
        </p>

        <label className="btn mt-4 w-full cursor-pointer">
          {map.image ? "Replace image" : "Upload map image"}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            disabled={busy}
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
        </label>
        {map.has_default_image && (
          <button className="btn mt-2 w-full" disabled={busy} onClick={restoreBuiltIn}>
            Use built-in image
          </button>
        )}
        {map.image && (
          <p className="mt-1 text-xs text-muted">Replacing the image clears its calibration.</p>
        )}

        <h2 className="mt-6 font-semibold">Line up the dots</h2>
        <p className="mt-1 text-xs text-muted">
          Each dot is a real fight (pink: kills, white: deaths). Drag the dots, then scale,
          rotate or flip them until they sit on buildings and roads, not in water.
        </p>
        {!refs.length && (
          <p className="mt-2 text-xs text-accent-2">
            No matches on this map yet. Upload one, or add known points below.
          </p>
        )}
        <div className="mt-3 grid grid-cols-4 gap-1">
          <button className="btn px-1" onClick={() => nudge((a) => ({ scale: a.scale * 0.9 }))}>−10%</button>
          <button className="btn px-1" onClick={() => nudge((a) => ({ scale: a.scale * 0.99 }))}>−1%</button>
          <button className="btn px-1" onClick={() => nudge((a) => ({ scale: a.scale * 1.01 }))}>+1%</button>
          <button className="btn px-1" onClick={() => nudge((a) => ({ scale: a.scale * 1.1 }))}>+10%</button>
          <button className="btn px-1" onClick={() => nudge((a) => ({ angle: a.angle - 5 }))}>↺ 5°</button>
          <button className="btn px-1" onClick={() => nudge((a) => ({ angle: a.angle - 0.5 }))}>↺ ½°</button>
          <button className="btn px-1" onClick={() => nudge((a) => ({ angle: a.angle + 0.5 }))}>↻ ½°</button>
          <button className="btn px-1" onClick={() => nudge((a) => ({ angle: a.angle + 5 }))}>↻ 5°</button>
          <button className="btn col-span-2 px-1" onClick={() => nudge((a) => ({ flipX: !a.flipX }))}>Flip ↔</button>
          <button className="btn col-span-2 px-1" onClick={() => nudge((a) => ({ flipY: !a.flipY }))}>Flip ↕</button>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button className="btn" disabled={!changed || busy} onClick={() => setAdjust(NO_ADJUST)}>
            Undo moves
          </button>
          <button className="btn btn-primary" disabled={!map.image || busy || (!changed && !!cal.transform)} onClick={saveOverlay}>
            Save alignment
          </button>
        </div>

        <h2 className="mt-6 font-semibold">Known points (precise)</h2>
        <p className="mt-1 text-xs text-muted">
          If you know a spot&apos;s game coordinates, enter them, then click that spot on the image.
        </p>
        {pending ? (
          <div className="mt-2 space-y-2">
            <input className="input" placeholder="Label (e.g. Clock Tower roof)" value={pending.label} onChange={(e) => setPending({ ...pending, label: e.target.value })} />
            <div className="grid grid-cols-2 gap-2">
              <input className="input" placeholder="World X" inputMode="decimal" value={pending.x} onChange={(e) => setPending({ ...pending, x: e.target.value })} />
              <input className="input" placeholder="World Z" inputMode="decimal" value={pending.z} onChange={(e) => setPending({ ...pending, z: e.target.value })} />
            </div>
            <p className="text-xs text-accent-2">Now click the spot on the image.</p>
            <button className="btn w-full" onClick={() => setPending(null)}>Cancel</button>
          </div>
        ) : (
          <button className="btn mt-2 w-full" disabled={!map.image} onClick={() => setPending({ x: "", z: "", label: "" })}>
            Add a known point
          </button>
        )}
        <ul className="mt-3 space-y-1">
          {cal.points.map((p) => (
            <li key={p.id} className="flex items-center gap-2 rounded bg-panel px-2 py-1 text-xs">
              <span className="flex-1 truncate">{p.label || `${p.world_x}, ${p.world_z}`}</span>
              <span className={p.error_px != null && p.error_px > 15 ? "text-bad" : "text-muted"}>
                {p.error_px != null ? `${p.error_px} px` : ""}
              </span>
              <button className="text-muted hover:text-bad" onClick={() => remove(p.id)} aria-label="Remove point">
                ×
              </button>
            </li>
          ))}
        </ul>
        {notice && <p className={`mt-4 text-xs ${notice.bad ? "text-bad" : "text-ok"}`}>{notice.text}</p>}
      </aside>
    </div>
  );
}
