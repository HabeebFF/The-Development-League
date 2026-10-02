"use client";

import Link from "next/link";
import { useCallback, useEffect, useEffectEvent, useMemo, useState } from "react";
import { Circle, Group, Line, Text } from "react-konva";

import MapCanvas from "@/components/map/MapCanvas";
import {
  api,
  type AdminMatch,
  type GameMap,
  type TeamRotation,
  type Zone,
} from "@/lib/api";
import { teamColor } from "@/lib/colors";
import { fitBounds, toPixel, toWorld, type Transform } from "@/lib/coordinates";
import {
  CHECKPOINT_KEYS,
  CHECKPOINTS,
  copyLast,
  LABELS,
  movePoint,
  nextCheckpoint,
  placePoint,
  removePoint,
  SHORT,
  type Checkpoint,
  type RotationPoint,
} from "@/lib/rotation";

const CANVAS = 1024;

type Loaded = {
  match: AdminMatch;
  map: GameMap | null;
  zones: Zone[];
  rotations: TeamRotation[];
};

export default function PlottingTool({ matchId }: { matchId: number }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState(0);
  const [edits, setEdits] = useState<Record<string, RotationPoint[]>>({});
  const [history, setHistory] = useState<Record<string, RotationPoint[][]>>({});
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [checkpoint, setCheckpoint] = useState<Checkpoint>("DROP");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const match = await api<AdminMatch>(`/admin/matches/${matchId}`);
        const [map, zones, rotations] = await Promise.all([
          match.map ? api<GameMap>(`/maps/${match.map}`) : Promise.resolve(null),
          api<{ zones: Zone[] }>(`/matches/${matchId}/zones`),
          api<{ rotations: TeamRotation[] }>(`/matches/${matchId}/rotations`),
        ]);
        setData({ match, map, zones: zones.zones, rotations: rotations.rotations });
        setEdits(Object.fromEntries(rotations.rotations.map((r) => [r.team.slug, r.points])));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Couldn't load this match.");
      }
    })();
  }, [matchId]);

  const rotations = useMemo(() => data?.rotations ?? [], [data]);
  const current = rotations[selected];
  const slug = current?.team.slug;
  const points = (slug && edits[slug]) || [];
  const shrinks = useMemo(
    () => (data?.zones ?? []).filter((z) => z.state === "SHRINK"),
    [data],
  );

  // World -> content pixels: the calibrated image, or a plain grid fitted to the data.
  const view = useMemo(() => {
    const map = data?.map;
    if (map?.image && map.transform && map.image_width && map.image_height) {
      return { t: map.transform, w: map.image_width, h: map.image_height, image: map.image };
    }
    const world = [
      ...Object.values(edits).flat(),
      ...shrinks.flatMap((z) => [
        { x: z.inner_x - z.inner_radius, z: z.inner_z - z.inner_radius },
        { x: z.inner_x + z.inner_radius, z: z.inner_z + z.inner_radius },
      ]),
    ];
    return { t: fitBounds(world, CANVAS, CANVAS), w: CANVAS, h: CANVAS, image: null };
    // Fitted once per match so the view doesn't jump while plotting.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  const unit = Math.sqrt(Math.abs(view.t.a * view.t.e - view.t.b * view.t.d)); // px per world unit

  const update = useCallback(
    (next: RotationPoint[]) => {
      if (!slug) return;
      setHistory((h) => ({ ...h, [slug]: [...(h[slug] ?? []), edits[slug] ?? []].slice(-50) }));
      setEdits((e) => ({ ...e, [slug]: next }));
      setDirty((d) => new Set(d).add(slug));
    },
    [slug, edits],
  );

  const undo = useCallback(() => {
    if (!slug) return;
    const stack = history[slug] ?? [];
    if (!stack.length) return;
    setEdits((e) => ({ ...e, [slug]: stack[stack.length - 1] }));
    setHistory((h) => ({ ...h, [slug]: stack.slice(0, -1) }));
    setDirty((d) => new Set(d).add(slug));
  }, [slug, history]);

  const replaceRotation = useCallback((saved: TeamRotation) => {
    setData((d) =>
      d && {
        ...d,
        rotations: d.rotations.map((r) => (r.team.slug === saved.team.slug ? saved : r)),
      },
    );
    setEdits((e) => ({ ...e, [saved.team.slug]: saved.points }));
    setDirty((d) => {
      const n = new Set(d);
      n.delete(saved.team.slug);
      return n;
    });
  }, []);

  const run = useCallback(async (action: () => Promise<void>) => {
    setBusy(true);
    setNotice(null);
    try {
      await action();
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }, []);

  const save = useCallback(
    async (teamSlug = slug) => {
      if (!teamSlug || !dirty.has(teamSlug)) return;
      const body = {
        points: (edits[teamSlug] ?? []).map((p) => ({
          checkpoint: p.checkpoint,
          x: p.x,
          z: p.z,
          game_time_s: p.game_time_s,
          note: p.note,
        })),
      };
      const saved = await api<TeamRotation>(`/matches/${matchId}/rotations/${teamSlug}`, {
        method: "PUT",
        body,
      });
      replaceRotation(saved);
    },
    [slug, dirty, edits, matchId, replaceRotation],
  );

  const select = useCallback(
    (index: number) => {
      if (index < 0 || index >= rotations.length || index === selected) return;
      run(async () => {
        await save();
        setSelected(index);
        const next = rotations[index];
        setCheckpoint(nextCheckpoint(edits[next.team.slug] ?? [], shrinks.length) ?? "DROP");
      });
    },
    [rotations, selected, run, save, edits, shrinks.length],
  );

  const confirm = useCallback(
    (andNext: boolean) =>
      run(async () => {
        if (!slug) return;
        await save();
        const saved = await api<TeamRotation>(
          `/matches/${matchId}/rotations/${slug}/confirm`,
          { method: "POST" },
        );
        replaceRotation(saved);
        if (andNext && selected < rotations.length - 1) {
          const next = rotations[selected + 1];
          setSelected(selected + 1);
          setCheckpoint(nextCheckpoint(edits[next.team.slug] ?? [], shrinks.length) ?? "DROP");
        }
      }),
    [run, slug, save, matchId, replaceRotation, selected, rotations, edits, shrinks.length],
  );

  const reset = useCallback(() => {
    if (!slug || !window.confirm(`Throw away edits to ${current.team.name} and go back to the auto draft?`)) return;
    run(async () => {
      const saved = await api<TeamRotation>(`/matches/${matchId}/rotations/${slug}/reset`, {
        method: "POST",
      });
      replaceRotation(saved);
      setHistory((h) => ({ ...h, [slug]: [] }));
    });
  }, [slug, current, run, matchId, replaceRotation]);

  // Keyboard shortcuts (ignored while typing in a field).
  const onKey = useEffectEvent((e: KeyboardEvent) => {
    const target = e.target as HTMLElement;
    if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || busy) return;
    const key = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && key === "z") {
      e.preventDefault();
      undo();
    } else if (e.ctrlKey || e.metaKey || e.altKey) {
      return;
    } else if (/^[1-9]$/.test(key)) {
      select(Number(key) - 1);
    } else if (key === "tab") {
      e.preventDefault();
      select(selected + (e.shiftKey ? -1 : 1));
    } else if (key === "enter") {
      confirm(true);
    } else if (key === "s") {
      run(() => save());
    } else if (key === "c") {
      update(copyLast(points, checkpoint));
      setCheckpoint(nextCheckpoint(copyLast(points, checkpoint), shrinks.length) ?? checkpoint);
    } else if (key === "backspace" || key === "delete") {
      const index = points.findIndex((p) => p.checkpoint === checkpoint);
      if (index >= 0) update(removePoint(points, index));
    } else if (CHECKPOINT_KEYS[key]) {
      setCheckpoint(CHECKPOINT_KEYS[key]);
    }
  });
  useEffect(() => {
    const handler = (e: KeyboardEvent) => onKey(e);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty.size) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (error) return <p className="p-6 text-bad">{error}</p>;
  if (!data) return <p className="p-6 text-muted">Loading match...</p>;
  if (!rotations.length) {
    return <p className="p-6 text-muted">This match has no team results yet, so there is nothing to plot.</p>;
  }

  const place = (px: number, py: number) => {
    const { x, z } = toWorld(view.t, px, py);
    const next = placePoint(points, checkpoint, x, z);
    update(next);
    setCheckpoint(nextCheckpoint(next, shrinks.length) ?? checkpoint);
  };

  const zoneKeys = Array.from({ length: Math.max(shrinks.length, 4) }, (_, i) => `ZONE_${i + 1}` as Checkpoint)
    .filter((c) => CHECKPOINTS.includes(c));
  const choices: Checkpoint[] = ["DROP", ...zoneKeys, "EXTRA", "FINAL", "ELIMINATED"];
  const keyOf = Object.fromEntries(Object.entries(CHECKPOINT_KEYS).map(([k, c]) => [c, k.toUpperCase()]));

  return (
    <div className="flex h-[calc(100dvh-var(--header-h)-var(--bottom-nav-h))] flex-col lg:flex-row">
      {/* Teams */}
      <aside className="flex shrink-0 gap-1 overflow-x-auto border-b border-line p-2 lg:w-60 lg:flex-col lg:overflow-y-auto lg:border-r lg:border-b-0">
        <Link href="/staff/matches" className="hidden px-2 pb-2 text-xs text-muted hover:text-text lg:block">
          &larr; {data.match.label}
        </Link>
        {rotations.map((r, i) => (
          <button
            key={r.team.slug}
            onClick={() => select(i)}
            className={`flex shrink-0 items-center gap-2 px-2 py-1.5 text-left text-sm ${
              i === selected ? "bg-panel-2 ring-1 ring-accent" : "hover:bg-panel"
            }`}
          >
            <span className="h-3 w-3 rounded-full" style={{ background: teamColor(i, r.team.primary_color) }} />
            <span className="w-5 text-xs text-muted">{i < 9 ? i + 1 : ""}</span>
            <span className="flex-1 truncate">
              #{r.placement} {r.team.name}
            </span>
            <StatusDot status={r.status} dirty={dirty.has(r.team.slug)} />
          </button>
        ))}
      </aside>

      {/* Map */}
      <MapCanvas width={view.w} height={view.h} image={view.image} onClick={place} className="min-h-[50dvh] flex-1">
        {(px) => (
          <>
            {shrinks.map((z) => {
              const c = toPixel(view.t, z.inner_x, z.inner_z);
              return (
                <Group key={`z${z.stage_index}`} listening={false}>
                  <Circle x={c.px} y={c.py} radius={z.inner_radius * unit} stroke="#ffffff66" strokeWidth={px(1.5)} dash={[px(6), px(4)]} />
                  <Text x={c.px + px(4)} y={c.py - z.inner_radius * unit - px(14)} text={`Z${z.stage_index + 1}`} fill="#ffffffaa" fontSize={px(12)} />
                </Group>
              );
            })}
            {rotations.map((r, i) =>
              i === selected ? null : (
                <Path key={r.team.slug} points={edits[r.team.slug] ?? []} t={view.t} color={teamColor(i, r.team.primary_color)} px={px} faint />
              ),
            )}
            {current && (
              <Path
                points={points}
                t={view.t}
                color={teamColor(selected, current.team.primary_color)}
                px={px}
                onMove={(index, cx, cy) => {
                  const { x, z } = toWorld(view.t, cx, cy);
                  update(movePoint(points, index, x, z));
                }}
                onRemove={(index) => update(removePoint(points, index))}
              />
            )}
          </>
        )}
      </MapCanvas>

      {/* Checkpoints, points and actions */}
      <aside className="shrink-0 overflow-y-auto border-t border-line p-3 text-sm lg:w-72 lg:border-t-0 lg:border-l">
        <h2 className="font-display text-xl uppercase">{current.team.name}</h2>
        <p className="text-xs text-muted">
          #{current.placement} · {statusText(current.status)}
          {current.plotted_by ? ` · ${current.plotted_by}` : ""}
        </p>
        {!data.map?.is_calibrated && (
          <p className="mt-2 border border-accent-2/40 bg-accent-2/10 p-2 text-xs text-accent-2">
            This map has no calibrated image yet, so points are drawn on a grid. They are
            still saved in game coordinates.
          </p>
        )}
        <div className="mt-3 grid grid-cols-3 gap-1">
          {choices.map((c) => (
            <button
              key={c}
              onClick={() => setCheckpoint(c)}
              className={`border px-1.5 py-1 text-xs ${
                c === checkpoint ? "border-accent bg-accent/20" : "border-line hover:border-muted"
              } ${points.some((p) => p.checkpoint === c) ? "" : "text-muted"}`}
            >
              {LABELS[c]} {keyOf[c] && <span className="text-[10px] text-muted">{keyOf[c]}</span>}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted">Click the map to place {LABELS[checkpoint]}. Drag a point to move it, right-click to delete it.</p>

        <ul className="mt-3 space-y-1">
          {points.map((p, i) => (
            <li key={`${p.checkpoint}-${i}`} className="flex items-center gap-2 bg-panel px-2 py-1">
              <span className="w-20 font-medium">{LABELS[p.checkpoint]}</span>
              <span className="flex-1 truncate text-xs text-muted">
                {p.area ?? `${Math.round(p.x)}, ${Math.round(p.z)}`}
                {p.game_time_s != null && ` · ${clock(p.game_time_s)}`}
              </span>
              {p.source === "AUTO" && (
                <span title={evidence(p)} className="text-[10px] tracking-wide text-accent-2 uppercase">
                  auto
                </span>
              )}
              <button onClick={() => update(removePoint(points, i))} className="text-muted hover:text-bad" aria-label="Remove point">
                ×
              </button>
            </li>
          ))}
          {!points.length && <li className="text-xs text-muted">No points yet.</li>}
        </ul>

        {notice && <p className="mt-3 text-xs text-bad">{notice}</p>}
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button className="btn" disabled={busy || !dirty.has(slug!)} onClick={() => run(() => save())}>
            Save <span className="kbd">S</span>
          </button>
          <button className="btn btn-primary" disabled={busy || !points.length} onClick={() => confirm(true)}>
            Confirm <span className="kbd">↵</span>
          </button>
          <button className="btn" disabled={busy || !(history[slug!]?.length)} onClick={undo}>
            Undo <span className="kbd">Ctrl Z</span>
          </button>
          <button className="btn" disabled={busy} onClick={reset}>
            Reset to auto
          </button>
        </div>
        <details className="mt-4 text-xs text-muted">
          <summary className="cursor-pointer">Keyboard shortcuts</summary>
          <ul className="mt-2 space-y-1">
            <li><span className="kbd">1-9</span> <span className="kbd">Tab</span> pick team</li>
            <li><span className="kbd">Q</span> drop, <span className="kbd">W E R T U I</span> zones 1-6</li>
            <li><span className="kbd">Y</span> final, <span className="kbd">X</span> eliminated, <span className="kbd">A</span> extra</li>
            <li><span className="kbd">C</span> copy the previous position</li>
            <li><span className="kbd">Backspace</span> remove the current checkpoint</li>
            <li><span className="kbd">Enter</span> confirm and go to the next team</li>
          </ul>
        </details>
      </aside>
    </div>
  );
}

function Path({
  points,
  t,
  color,
  px,
  faint,
  onMove,
  onRemove,
}: {
  points: RotationPoint[];
  t: Transform;
  color: string;
  px: (n: number) => number;
  faint?: boolean;
  onMove?: (index: number, px: number, py: number) => void;
  onRemove?: (index: number) => void;
}) {
  const pixels = points.map((p) => toPixel(t, p.x, p.z));
  const route = pixels.filter((_, i) => points[i].checkpoint !== "EXTRA").flatMap((p) => [p.px, p.py]);
  const r = px(faint ? 4 : 10);
  return (
    <Group opacity={faint ? 0.35 : 1} listening={!faint}>
      <Line points={route} stroke={color} strokeWidth={px(faint ? 1.5 : 3)} lineCap="round" lineJoin="round" />
      {points.map((p, i) => (
        <Group
          key={`${p.checkpoint}-${i}`}
          x={pixels[i].px}
          y={pixels[i].py}
          draggable={!!onMove}
          onDragEnd={(e) => onMove?.(i, e.target.x(), e.target.y())}
          onContextMenu={(e) => {
            e.evt.preventDefault();
            onRemove?.(i);
          }}
        >
          <Circle
            radius={r}
            fill={faint ? color : "#0b0b0f"}
            stroke={color}
            strokeWidth={px(2.5)}
            dash={p.source === "AUTO" && !faint ? [px(4), px(3)] : undefined}
          />
          {!faint && (
            <Text
              text={SHORT[p.checkpoint]}
              fill="#fff"
              fontSize={px(11)}
              fontStyle="bold"
              width={r * 2}
              height={r * 2}
              offsetX={r}
              offsetY={r}
              align="center"
              verticalAlign="middle"
              listening={false}
            />
          )}
        </Group>
      ))}
    </Group>
  );
}

function StatusDot({ status, dirty }: { status: TeamRotation["status"]; dirty: boolean }) {
  if (dirty) return <span className="text-[10px] text-accent-2">unsaved</span>;
  const cls = status === "CONFIRMED" ? "bg-ok" : status === "DRAFT" ? "bg-accent-2" : "border border-muted";
  return <span title={statusText(status)} className={`h-2.5 w-2.5 rounded-full ${cls}`} />;
}

function statusText(status: TeamRotation["status"]): string {
  return { AUTO: "Auto draft", DRAFT: "Edited", CONFIRMED: "Confirmed" }[status];
}

function clock(seconds: number): string {
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function evidence(p: RotationPoint): string {
  const parts = Object.entries(p.evidence ?? {}).map(([k, n]) => `${n} ${k}`);
  return parts.length ? `From ${parts.join(", ")}` : "Auto";
}
