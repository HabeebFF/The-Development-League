"use client";

import Link from "next/link";
import { useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { Circle, Group, Line, Rect, Text } from "react-konva";

import MapCanvas from "@/components/map/MapCanvas";
import { api, type GameMap } from "@/lib/api";
import { teamColor } from "@/lib/colors";
import { fitBounds, toPixel } from "@/lib/coordinates";
import {
  clock,
  enemiesInScan,
  positionAt,
  strikesAt,
  timeRange,
  trailAt,
  uavAt,
  uavTrail,
  zoneAt,
  type Replay,
  type ReplayEvent,
  type ReplayObject,
} from "@/lib/replay";

const CANVAS = 1024;
const SPEEDS = [1, 2, 4, 8, 16];
const TRAIL_S = 20;
const MARK_S = 8; // how long a kill or knock stays on the map
const UAV_TRAIL_S = 6;
const NEUTRAL = "#e5e7eb";
const BOLT = "#fde047";
const SCAN = "#34d399";
const SCAN_SHOW_S = 8; // a Dinoculars scan lasts 3 s; keep it up longer so it's seen at speed

type FeedItem = { t: number; kind: "KILL" | "KNOCK" | "UAV" | "BOLT" | "SCAN"; text: string; headshot?: boolean };

type Loaded = { replay: Replay; map: GameMap | null };

/** Every player's movement over the match, played back on the map like a replay. */
export default function ReplayViewer({
  matchId,
  backHref = "/staff/matches",
  focusTeams = [],
}: {
  matchId: number;
  /** Where the "Matches" link goes (the staff list, or the team area). */
  backHref?: string;
  /** Teams to watch first, e.g. the signed-in player's own team. */
  focusTeams?: string[];
}) {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const [labels, setLabels] = useState(true);
  const [gadgets, setGadgets] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const replay = await api<Replay>(`/matches/${matchId}/replay`);
        const map = replay.map ? await api<GameMap>(`/maps/${replay.map.slug}`) : null;
        setData({ replay, map });
        const first =
          replay.teams.find((team) => team.has_tracks && focusTeams.includes(team.slug)) ??
          replay.teams.find((team) => team.has_tracks);
        if (first) setChosen(new Set([first.slug]));
        if (replay.step_s) setT(timeRange(replay.players, replay.step_s)[0]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Couldn't load this match.");
      }
    })();
    // focusTeams only picks the first team shown; it shouldn't reload the replay.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        <Link href={backHref} className="mt-4 inline-block text-accent">
          &larr; Matches
        </Link>
      </div>
    );
  }

  const zone = zoneAt(replay.zones, t);
  const involves = (e: ReplayEvent) =>
    [e.actor, e.target].some((id) => id != null && chosen.has(byEntity[id]?.team));
  const recent = replay.events.filter((e) => e.t <= t && e.t > t - MARK_S && involves(e));
  const nameOf = (id: number | null) => (id != null && byEntity[id]?.name) || "Enemy";
  const objects = gadgets ? (replay.objects ?? []) : [];
  const shownUntil = (o: ReplayObject) =>
    o.kind === "DINOCULARS" ? Math.max(o.end_s, o.start_s + SCAN_SHOW_S) : o.end_s;
  const liveObjects = objects.filter((o) => o.start_s <= t && t <= shownUntil(o));
  const ownerName = (o: ReplayObject) => o.owner_name ?? (o.owner != null ? nameOf(o.owner) : "Someone");
  const enemies = (o: ReplayObject) => {
    const n = enemiesInScan(o, replay.players, step);
    return `${n} ${n === 1 ? "enemy" : "enemies"}`;
  };
  const objectFeed = (o: ReplayObject): Pick<FeedItem, "kind" | "text"> =>
    o.kind === "BOLT_MAKER"
      ? { kind: "BOLT", text: `${ownerName(o)} called a Bolt Maker` }
      : o.kind === "DINOCULARS"
        ? { kind: "SCAN", text: `${ownerName(o)} scanned with Dinoculars: ${enemies(o)}` }
        : { kind: "UAV", text: `${ownerName(o)} launched a UAV` };
  const feed: FeedItem[] = [
    ...replay.events
      .filter((e) => e.t <= t && involves(e))
      .map((e) => ({
        t: e.t,
        kind: e.kind,
        text: `${nameOf(e.actor)} \u2192 ${nameOf(e.target)}`,
        headshot: !!e.headshot,
      })),
    ...objects
      .filter((o) => o.start_s <= t && o.kind !== "GENERAL_UAV" && o.team != null && chosen.has(o.team))
      .map((o) => ({ t: o.start_s, ...objectFeed(o) })),
  ]
    .sort((a, b) => a.t - b.t)
    .slice(-8)
    .reverse();
  const alive = players.filter((p) => positionAt(p, step, t)).length;

  return (
    <div className="flex h-[calc(100dvh-var(--header-h))] flex-col lg:flex-row">
      {/* Teams */}
      <aside className="flex shrink-0 gap-1 overflow-x-auto border-b border-line p-2 lg:w-64 lg:flex-col lg:overflow-y-auto lg:border-r lg:border-b-0">
        <Link href={backHref} className="hidden px-2 pb-1 text-xs text-muted hover:text-text lg:block">
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
          <button className="btn px-2 py-1 text-xs" onClick={() => setGadgets((v) => !v)}>
            {gadgets ? "Hide gadgets" : "Show gadgets"}
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
              {liveObjects
                .filter((o) => o.kind === "BOLT_MAKER")
                .map((o, i) => {
                  const c = toPixel(view.t, o.x, o.z);
                  const color = o.team ? colors[o.team] : BOLT;
                  const r = Math.max(px(10), (o.radius ?? 20) * unit);
                  return (
                    <Group key={`bolt${i}-${o.start_s}`} listening={false}>
                      <Circle
                        x={c.px}
                        y={c.py}
                        radius={r}
                        fill={BOLT}
                        opacity={0.15}
                      />
                      <Circle
                        x={c.px}
                        y={c.py}
                        radius={r}
                        stroke={color}
                        strokeWidth={px(2.5)}
                        dash={[px(4), px(3)]}
                      />
                      {strikesAt(o, t).map((s, j) => {
                        const q = toPixel(view.t, s.x, s.z);
                        return (
                          <Circle key={j} x={q.px} y={q.py} radius={Math.max(px(4), 4.4 * unit)} fill={BOLT} opacity={1 - s.age} />
                        );
                      })}
                      <Text text={"\u26A1"} x={c.px - px(7)} y={c.py - px(8)} fontSize={px(14)} />
                    </Group>
                  );
                })}
              {liveObjects
                .filter((o) => o.kind === "DINOCULARS")
                .map((o, i) => {
                  const c = toPixel(view.t, o.x, o.z);
                  const color = o.team ? colors[o.team] : SCAN;
                  const r = Math.max(px(8), (o.radius ?? 50) * unit);
                  const fade = t <= o.end_s ? 1 : 1 - (t - o.end_s) / (shownUntil(o) - o.end_s);
                  return (
                    <Group key={`scan${i}-${o.start_s}`} opacity={0.35 + 0.65 * fade} listening={false}>
                      <Circle x={c.px} y={c.py} radius={r} fill={SCAN} opacity={0.15} />
                      <Circle x={c.px} y={c.py} radius={r} stroke={color} strokeWidth={px(2)} dash={[px(2), px(3)]} />
                      <Circle x={c.px} y={c.py} radius={px(3)} fill={SCAN} />
                      {labels && (
                        <Text
                          text={`Dinoculars · ${ownerName(o)} · ${enemies(o)}`}
                          x={c.px + px(6)}
                          y={c.py - r - px(14)}
                          fontSize={px(11)}
                          fill={SCAN}
                          shadowColor="#000"
                          shadowBlur={px(3)}
                          shadowOpacity={1}
                        />
                      )}
                    </Group>
                  );
                })}
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
              {liveObjects
                .filter((o) => o.kind === "PLAYER_UAV" || o.kind === "GENERAL_UAV")
                .map((o, i) => {
                  const w = uavAt(o, t);
                  if (!w) return null;
                  const q = toPixel(view.t, w.x, w.z);
                  const general = o.kind === "GENERAL_UAV";
                  const color = general ? NEUTRAL : o.team ? colors[o.team] : NEUTRAL;
                  const size = px(general ? 9 : 7);
                  const trail = uavTrail(o, t, UAV_TRAIL_S).flatMap((p) => {
                    const r = toPixel(view.t, p.x, p.z);
                    return [r.px, r.py];
                  });
                  const range = (o.radius ?? (general ? 100 : 65)) * unit;
                  return (
                    <Group key={`uav${i}-${o.start_s}`} listening={false}>
                      <Circle x={q.px} y={q.py} radius={range} fill={color} opacity={0.1} />
                      <Circle
                        x={q.px}
                        y={q.py}
                        radius={range}
                        stroke={color}
                        strokeWidth={px(general ? 2.5 : 1.5)}
                        dash={[px(6), px(4)]}
                        opacity={0.9}
                      />
                      {trail.length >= 4 && (
                        <Line points={trail} stroke={color} strokeWidth={px(1.5)} dash={[px(3), px(3)]} opacity={0.8} />
                      )}
                      <Rect
                        x={q.px}
                        y={q.py}
                        width={size}
                        height={size}
                        offsetX={size / 2}
                        offsetY={size / 2}
                        rotation={45}
                        fill={color}
                        stroke="#000"
                        strokeWidth={px(1.5)}
                      />
                      {labels && (
                        <Text
                          text={general ? "UAV" : `UAV \u00B7 ${ownerName(o)}`}
                          x={q.px + px(9)}
                          y={q.py + px(4)}
                          fontSize={px(11)}
                          fill={color}
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
                <span className={FEED_STYLE[e.kind].className}>{FEED_STYLE[e.kind].label}</span>
                <span className="truncate">
                  {e.text}
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

const FEED_STYLE: Record<FeedItem["kind"], { label: string; className: string }> = {
  KILL: { label: "killed", className: "text-bad" },
  KNOCK: { label: "knocked", className: "text-yellow-400" },
  UAV: { label: "UAV", className: "text-sky-300" },
  BOLT: { label: "bolt", className: "text-yellow-300" },
  SCAN: { label: "scan", className: "text-emerald-300" },
};

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
