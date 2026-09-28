"use client";

import Link from "next/link";
import { useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { Circle, Group, Line, Text } from "react-konva";

import MapCanvas from "@/components/map/MapCanvas";
import { api, type GameMap } from "@/lib/api";
import { teamColor } from "@/lib/colors";
import { fitBounds, toPixel } from "@/lib/coordinates";
import {
  clock,
  positionAt,
  timeRange,
  trailAt,
  zoneAt,
  type Replay,
  type ReplayEvent,
} from "@/lib/replay";

const CANVAS = 1024;
const SPEEDS = [1, 2, 4, 8, 16];
const TRAIL_S = 20;
const MARK_S = 8; // how long a kill or knock stays on the map

type Loaded = { replay: Replay; map: GameMap | null };

/** Every player's movement over the match, played back on the map like a replay. */
export default function ReplayViewer({ matchId }: { matchId: number }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const [labels, setLabels] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const replay = await api<Replay>(`/matches/${matchId}/replay`);
        const map = replay.map ? await api<GameMap>(`/maps/${replay.map.slug}`) : null;
        setData({ replay, map });
        const first = replay.teams.find((team) => team.has_tracks);
        if (first) setChosen(new Set([first.slug]));
        if (replay.step_s) setT(timeRange(replay.players, replay.step_s)[0]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Couldn't load this match.");
      }
    })();
  }, [matchId]);

  const replay = data?.replay;
  const step = replay?.step_s ?? 0.5;
  const [start, end] = useMemo(() => (replay ? timeRange(replay.players, step) : [0, 0]), [replay, step]);
  const colors = useMemo(
    () => Object.fromEntries((replay?.teams ?? []).map((team, i) => [team.slug, teamColor(i, team.color)])),
    [replay],
  );
  const players = useMemo(() => (replay?.players ?? []).filter((p) => chosen.has(p.team)), [replay, chosen]);
  const byEntity = useMemo(
    () => Object.fromEntries((replay?.players ?? []).map((p) => [p.entity_id, p])),
    [replay],
  );

  // World -> content pixels: the calibrated image, or a grid fitted to every path.
  const view = useMemo(() => {
    const map = data?.map;
    if (map?.image && map.transform && map.image_width && map.image_height) {
      return { t: map.transform, w: map.image_width, h: map.image_height, image: map.image };
    }
    const world = (replay?.players ?? []).flatMap((p) =>
      p.points.filter((v, i) => v && i % 20 === 0).map((v) => ({ x: v![0] / 10, z: v![1] / 10 })),
    );
    return { t: fitBounds(world, CANVAS, CANVAS), w: CANVAS, h: CANVAS, image: null };
  }, [data, replay]);
  const unit = Math.sqrt(Math.abs(view.t.a * view.t.e - view.t.b * view.t.d));

  // Playback clock.
  const last = useRef<number | null>(null);
  const tick = useEffectEvent((now: number) => {
    const dt = last.current == null ? 0 : (now - last.current) / 1000;
    last.current = now;
    const next = t + dt * speed;
    if (next >= end) {
      setT(end);
      setPlaying(false);
    } else setT(next);
  });
  useEffect(() => {
    if (!playing) return;
    let frame = requestAnimationFrame(function loop(now) {
      tick(now);
      frame = requestAnimationFrame(loop);
    });
    return () => {
      cancelAnimationFrame(frame);
      last.current = null;
    };
  }, [playing]);

  const onKey = useEffectEvent((e: KeyboardEvent) => {
    if (e.target instanceof HTMLInputElement && e.target.type !== "range") return;
    if (e.key === " ") {
      e.preventDefault();
      togglePlay();
    } else if (e.key === "ArrowRight") setT((v) => Math.min(end, v + 5));
    else if (e.key === "ArrowLeft") setT((v) => Math.max(start, v - 5));
  });
  useEffect(() => {
    const listener = (e: KeyboardEvent) => onKey(e);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  function togglePlay() {
    if (!playing && t >= end) setT(start);
    setPlaying((p) => !p);
  }

  function toggleTeam(slug: string, only: boolean) {
    setChosen((current) => {
      if (only) return new Set([slug]);
      const next = new Set(current);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  if (error) return <p className="p-6 text-bad">{error}</p>;
  if (!data || !replay) return <p className="p-6 text-muted">Loading the replay...</p>;
  if (!replay.players.length) {
    return (
      <div className="p-6">
        <p className="text-muted">
          This match has no player movement yet. Upload its ReplayInfo .bin file with the other logs
          (or upload the match again with it) and the live replay appears here.
        </p>
        <Link href="/staff/matches" className="mt-4 inline-block text-accent">
          &larr; Matches
        </Link>
      </div>
    );
  }

  const zone = zoneAt(replay.zones, t);
  const involves = (e: ReplayEvent) =>
    [e.actor, e.target].some((id) => id != null && chosen.has(byEntity[id]?.team));
  const recent = replay.events.filter((e) => e.t <= t && e.t > t - MARK_S && involves(e));
  const feed = replay.events.filter((e) => e.t <= t && involves(e)).slice(-8).reverse();
  const nameOf = (id: number | null) => (id != null && byEntity[id]?.name) || "Enemy";
  const alive = players.filter((p) => positionAt(p, step, t)).length;

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col lg:flex-row">
      {/* Teams */}
      <aside className="flex shrink-0 gap-1 overflow-x-auto border-b border-line p-2 lg:w-64 lg:flex-col lg:overflow-y-auto lg:border-r lg:border-b-0">
        <Link href="/staff/matches" className="hidden px-2 pb-1 text-xs text-muted hover:text-text lg:block">
          &larr; Matches
        </Link>
        <p className="hidden px-2 pb-1 text-xs text-muted lg:block">
          Click a team to watch it. Shift-click to add more teams.
        </p>
        <div className="flex shrink-0 gap-1 px-2 pb-1 lg:flex-row">
          <button className="btn px-2 py-1 text-xs" onClick={() => setChosen(new Set(replay.teams.map((x) => x.slug)))}>
            All teams
          </button>
          <button className="btn px-2 py-1 text-xs" onClick={() => setLabels((v) => !v)}>
            {labels ? "Hide names" : "Show names"}
          </button>
        </div>
        {replay.teams.map((team) => (
          <button
            key={team.slug}
            onClick={(e) => toggleTeam(team.slug, !(e.shiftKey || e.metaKey || e.ctrlKey))}
            disabled={!team.has_tracks}
            className={`flex shrink-0 items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm disabled:opacity-40 ${
              chosen.has(team.slug) ? "bg-panel-2 ring-1 ring-accent" : "hover:bg-panel"
            }`}
          >
            <span className="h-3 w-3 rounded-full" style={{ background: colors[team.slug] }} />
            <span className="flex-1 truncate">
              #{team.placement} {team.name}
            </span>
          </button>
        ))}
      </aside>

      <div className="flex min-h-[60dvh] flex-1 flex-col">
        {/* Map */}
        <MapCanvas width={view.w} height={view.h} image={view.image} className="flex-1">
          {(px) => (
            <>
              {zone.next && (
                <ZoneRing t={view.t} unit={unit} c={zone.next} stroke="#ffffffaa" width={px(1.5)} dash={[px(6), px(4)]} />
              )}
              {zone.current && <ZoneRing t={view.t} unit={unit} c={zone.current} stroke="#60a5fa" width={px(2.5)} />}
              {players.map((p) =>
                trailAt(p, step, t, TRAIL_S).map((piece, i) => (
                  <Line
                    key={`${p.entity_id}-${i}`}
                    points={piece.flatMap((w) => {
                      const q = toPixel(view.t, w.x, w.z);
                      return [q.px, q.py];
                    })}
                    stroke={colors[p.team]}
                    strokeWidth={px(2)}
                    opacity={0.55}
                    lineCap="round"
                    lineJoin="round"
                    listening={false}
                  />
                )),
              )}
              {recent.map((e, i) => {
                const target = e.target != null ? byEntity[e.target] : undefined;
                const at =
                  e.tx != null && e.tz != null
                    ? { x: e.tx, z: e.tz }
                    : target
                      ? positionAt(target, step, e.t)
                      : null;
                if (!at) return null;
                const q = toPixel(view.t, at.x, at.z);
                const s = px(6);
                const color = e.kind === "KILL" ? "#ef4444" : "#facc15";
                const fade = 1 - (t - e.t) / MARK_S;
                return (
                  <Group key={`e${i}-${e.t}`} x={q.px} y={q.py} opacity={0.3 + 0.7 * fade} listening={false}>
                    <Line points={[-s, -s, s, s]} stroke={color} strokeWidth={px(2.5)} />
                    <Line points={[-s, s, s, -s]} stroke={color} strokeWidth={px(2.5)} />
                  </Group>
                );
              })}
              {players.map((p) => {
                const w = positionAt(p, step, t);
                if (!w) return null;
                const q = toPixel(view.t, w.x, w.z);
                return (
                  <Group key={p.entity_id} x={q.px} y={q.py} listening={false}>
                    <Circle radius={px(6)} fill={colors[p.team]} stroke="#000" strokeWidth={px(1.5)} />
                    {labels && (
                      <Text
                        text={p.name}
                        x={px(9)}
                        y={-px(7)}
                        fontSize={px(12)}
                        fill="#fff"
                        shadowColor="#000"
                        shadowBlur={px(3)}
                        shadowOpacity={1}
                      />
                    )}
                  </Group>
                );
              })}
            </>
          )}
        </MapCanvas>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 border-t border-line p-3">
          <button className="btn min-w-20 px-3 py-1.5" onClick={togglePlay}>
            {playing ? "Pause" : "Play"}
          </button>
          <span className="w-24 text-sm tabular-nums">
            {clock(t)} / {clock(end)}
          </span>
          <input
            type="range"
            aria-label="Match time"
            className="min-w-40 flex-1 accent-[var(--color-accent,#ff2e63)]"
            min={start}
            max={end}
            step={step}
            value={t}
            onChange={(e) => setT(Number(e.target.value))}
          />
          <div className="flex gap-1">
            {SPEEDS.map((s) => (
              <button
                key={s}
                className={`btn px-2 py-1 text-xs ${s === speed ? "ring-1 ring-accent" : ""}`}
                onClick={() => setSpeed(s)}
              >
                {s}x
              </button>
            ))}
          </div>
          <span className="text-xs text-muted">
            {alive} of {players.length} players on the map
          </span>
        </div>
        {feed.length > 0 && (
          <ul className="max-h-32 overflow-y-auto border-t border-line px-3 py-2 text-xs">
            {feed.map((e, i) => (
              <li key={`f${i}-${e.t}`} className="flex gap-2 py-0.5">
                <span className="w-10 text-muted tabular-nums">{clock(e.t)}</span>
                <span className={e.kind === "KILL" ? "text-bad" : "text-yellow-400"}>
                  {e.kind === "KILL" ? "killed" : "knocked"}
                </span>
                <span className="truncate">
                  {nameOf(e.actor)} &rarr; {nameOf(e.target)}
                  {e.headshot ? " (headshot)" : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ZoneRing({
  t,
  unit,
  c,
  stroke,
  width,
  dash,
}: {
  t: import("@/lib/coordinates").Transform;
  unit: number;
  c: { x: number; z: number; r: number };
  stroke: string;
  width: number;
  dash?: number[];
}) {
  const q = toPixel(t, c.x, c.z);
  return <Circle x={q.px} y={q.py} radius={c.r * unit} stroke={stroke} strokeWidth={width} dash={dash} listening={false} />;
}
