"use client";

import Link from "next/link";
import { useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { Circle, Group, Line, Text } from "react-konva";

import MapCanvas from "@/components/map/MapCanvas";
import { MapLabels, type LabelSpec } from "@/components/map/MapLabel";
import { api, type GameMap, type RotationPlayer, type TeamRotation, type Zone } from "@/lib/api";
import { teamColor } from "@/lib/colors";
import { fitBounds, toPixel, type Transform } from "@/lib/coordinates";
import { boxOf, headAt, lighten, span, statusAt, upTo, type TPoint } from "@/lib/livepath";
import { clock, zoneAt } from "@/lib/replay";
import { LABELS, routeLines, SHORT, type RotationPoint } from "@/lib/rotation";

const CANVAS = 1024;
const SPEEDS = [1, 2, 4, 8];
const FOLLOW_MIN_M = 160; // the followed team is framed at least this wide
// Player labels only when few teams are shown, so the map stays readable.
const PLAYER_LABEL_TEAMS = 2;

type Mode = "team" | "players" | "both";
const MODES: { mode: Mode; label: string }[] = [
  { mode: "team", label: "Team" },
  { mode: "players", label: "Players" },
  { mode: "both", label: "Both" },
];

type Loaded = { map: GameMap | null; zones: Zone[]; rotations: TeamRotation[] };

/**
 * Every team's route in one match: the team line (centre of its players), each player's
 * own line, drop, zone and end spots, and where players died. Plays back over time with
 * the safe zone, and can follow a team with the camera.
 */
export default function RotationsView({
  matchId,
  focusTeam,
  backHref = "/team",
}: {
  matchId: number;
  focusTeam: string | null;
  backHref?: string;
}) {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<Mode>("both");
  const [highlight, setHighlight] = useState<number | null>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const [follow, setFollow] = useState(true);
  const [held, setHeld] = useState(false); // following paused because the map was moved by hand

  useEffect(() => {
    (async () => {
      try {
        const [rotations, zones] = await Promise.all([
          api<{ map: { slug: string } | null; rotations: TeamRotation[] }>(`/matches/${matchId}/rotations`),
          api<{ zones: Zone[] }>(`/matches/${matchId}/zones`),
        ]);
        const map = rotations.map ? await api<GameMap>(`/maps/${rotations.map.slug}`) : null;
        setData({ map, zones: zones.zones, rotations: rotations.rotations });
        const own = rotations.rotations.find((r) => r.team.slug === focusTeam);
        setChosen(new Set(own ? [own.team.slug] : rotations.rotations.map((r) => r.team.slug)));
        const [, last] = span(rotations.rotations.flatMap((r) => [r.path ?? [], ...(r.players ?? []).map((p) => p.path)]));
        setT(last);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Couldn't load this match.");
      }
    })();
  }, [matchId, focusTeam]);

  const rotations = useMemo(() => data?.rotations ?? [], [data]);
  const shrinks = useMemo(() => (data?.zones ?? []).filter((z) => z.state === "SHRINK"), [data]);
  const colors = useMemo(
    () => Object.fromEntries(rotations.map((r, i) => [r.team.slug, teamColor(i, r.team.primary_color)])),
    [rotations],
  );
  const [start, end] = useMemo(
    () => span(rotations.flatMap((r) => [r.path ?? [], ...(r.players ?? []).map((p) => p.path)])),
    [rotations],
  );
  const canPlay = end > start;

  // World -> content pixels: the calibrated image, or a plain grid fitted to the routes.
  const view = useMemo(() => {
    const map = data?.map;
    if (map?.image && map.transform && map.image_width && map.image_height) {
      return { t: map.transform, w: map.image_width, h: map.image_height, image: map.image };
    }
    const world = [
      ...rotations.flatMap((r) => r.points),
      ...rotations.flatMap((r) => (r.path ?? []).flat().map(([, x, z]) => ({ x, z }))),
      ...shrinks.flatMap((z) => [
        { x: z.inner_x - z.inner_radius, z: z.inner_z - z.inner_radius },
        { x: z.inner_x + z.inner_radius, z: z.inner_z + z.inner_radius },
      ]),
    ];
    return { t: fitBounds(world, CANVAS, CANVAS), w: CANVAS, h: CANVAS, image: null };
  }, [data, rotations, shrinks]);
  const unit = Math.sqrt(Math.abs(view.t.a * view.t.e - view.t.b * view.t.d)); // px per world unit

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

  function togglePlay() {
    if (!playing && t >= end) setT(start);
    setPlaying((p) => !p);
  }

  const onKey = useEffectEvent((e: KeyboardEvent) => {
    if (!canPlay || (e.target instanceof HTMLInputElement && e.target.type !== "range")) return;
    if (e.key === " ") {
      e.preventDefault();
      togglePlay();
    }
  });
  useEffect(() => {
    const listener = (e: KeyboardEvent) => onKey(e);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  function pick(slug: string, add: boolean) {
    setHighlight(null);
    setFollow(true);
    setHeld(false);
    setChosen((current) => {
      if (!add) return new Set([slug]);
      const next = new Set(current);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  if (error) return <p className="p-6 text-bad">{error}</p>;
  if (!data) return <p className="p-6 text-muted">Loading rotations...</p>;
  if (!rotations.length) {
    return (
      <div className="p-6">
        <p className="text-muted">No rotations for this match yet.</p>
        <Link href={backHref} className="mt-4 inline-block text-accent">
          &larr; Matches
        </Link>
      </div>
    );
  }

  const shown = rotations.filter((r) => chosen.has(r.team.slug));
  const single = shown.length === 1 ? shown[0] : null;
  const full = !canPlay || t >= end;
  const zone = full ? null : zoneAt(data.zones, t);
  const px0 = (w: { x: number; z: number }) => toPixel(view.t, w.x, w.z);
  const showTeam = mode !== "players";
  const showPlayers = mode !== "team";

  // Where each shown team and player is now (live), or where they finished (full view).
  const teamAt = (r: TeamRotation) => {
    const segs = (r.path ?? []) as TPoint[][];
    if (!full) return headAt(segs, t);
    const lastSeg = segs[segs.length - 1];
    if (lastSeg?.length) return { x: lastSeg[lastSeg.length - 1][1], z: lastSeg[lastSeg.length - 1][2] };
    const end = r.points[r.points.length - 1];
    return end ? { x: end.x, z: end.z } : null;
  };
  const playerAt = (p: RotationPlayer) => {
    const segs = p.path as TPoint[][];
    const now = headAt(segs, t);
    if (now) return { at: now, onMap: true };
    const walked = segs.flatMap((s) => upTo(s, t));
    const lastSeen = walked[walked.length - 1];
    return lastSeen ? { at: { x: lastSeen[1], z: lastSeen[2] }, onMap: false } : null;
  };

  // Camera follow: the picked team's players now, or its whole route when the match is over.
  let focus = null;
  if (single && follow && !held) {
    const pts = full
      ? [...(single.path ?? []).flat(), ...(single.players ?? []).flatMap((p) => p.path.flat())].map(([, x, z]) => px0({ x, z }))
      : [
          ...(single.players ?? [])
            .map((p) => headAt(p.path as TPoint[][], t))
            .filter((w): w is { x: number; z: number } => w != null)
            .map(px0),
          ...[teamAt(single)].filter((w): w is { x: number; z: number } => w != null).map(px0),
        ];
    focus = boxOf(pts, FOLLOW_MIN_M * unit);
  }

  const order = [...shown].sort((a, b) => Number(a === single) - Number(b === single));

  return (
    <div className="flex h-[calc(100dvh-var(--header-h)-var(--bottom-nav-h))] flex-col lg:flex-row">
      <aside className="flex shrink-0 gap-1 overflow-x-auto border-b border-line p-2 lg:w-64 lg:flex-col lg:overflow-y-auto lg:border-r lg:border-b-0">
        <Link href={backHref} className="hidden px-2 pb-1 text-xs text-muted hover:text-text lg:block">
          &larr; Matches
        </Link>
        <p className="hidden px-2 pb-1 text-xs text-muted lg:block">
          Click a team to see its route. Shift-click to compare teams.
        </p>
        <button
          className="btn shrink-0 px-2 py-1 text-xs"
          onClick={() => {
            setHighlight(null);
            setChosen(new Set(rotations.map((r) => r.team.slug)));
          }}
        >
          All teams
        </button>
        {rotations.map((r) => (
          <button
            key={r.team.slug}
            onClick={(e) => pick(r.team.slug, e.shiftKey)}
            className={`flex shrink-0 items-center gap-2 px-2 py-1.5 text-left text-sm ${
              chosen.has(r.team.slug) ? "bg-panel-2" : "text-muted hover:bg-panel"
            }`}
          >
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colors[r.team.slug] }} />
            <span className="flex-1 truncate">{r.team.name}</span>
            {r.placement != null && <span className="text-xs text-muted">#{r.placement}</span>}
          </button>
        ))}
      </aside>

      <div className="flex min-h-[55dvh] min-w-0 flex-1 flex-col">
        <MapCanvas
          width={view.w}
          height={view.h}
          image={view.image}
          className="flex-1"
          focus={focus}
          resetKey={[...chosen].sort().join(",")}
          onManualMove={() => single && follow && setHeld(true)}
          buttons={
            single && follow && held ? (
              <button className="btn px-2 py-1 text-xs" onClick={() => setHeld(false)}>
                Re-centre
              </button>
            ) : null
          }
        >
          {(px) => {
            const labels: LabelSpec[] = [];
            return (
              <>
                {full
                  ? shrinks.map((z) => {
                      const c = toPixel(view.t, z.inner_x, z.inner_z);
                      return (
                        <Group key={`z${z.stage_index}`} listening={false}>
                          <Circle x={c.px} y={c.py} radius={z.inner_radius * unit} stroke="#ffffff66" strokeWidth={px(1.5)} dash={[px(6), px(4)]} />
                          <Text x={c.px + px(4)} y={c.py - z.inner_radius * unit - px(14)} text={`Z${z.stage_index + 1}`} fill="#ffffffaa" fontSize={px(12)} />
                        </Group>
                      );
                    })
                  : zone && (
                      <Group listening={false}>
                        {zone.next && <Ring t={view.t} unit={unit} c={zone.next} stroke="#ffffffaa" width={px(1.5)} dash={[px(6), px(4)]} />}
                        {zone.current && <Ring t={view.t} unit={unit} c={zone.current} stroke="#60a5fa" width={px(2.5)} />}
                      </Group>
                    )}
                {order.map((r) => {
                  const color = colors[r.team.slug];
                  const focused = r === single;
                  const players = r.players ?? [];
                  const dimTeam = highlight != null && players.some((p) => p.entity_id === highlight);
                  const head = teamAt(r);
                  if (head && showTeam) {
                    const q = px0(head);
                    labels.push({
                      id: `team-${r.team.slug}`,
                      x: q.px,
                      y: q.py,
                      kind: "team",
                      text: shown.length > 3 ? r.team.tag || r.team.name : r.team.name,
                      tag: r.team.tag || r.team.name,
                      logo: r.team.logo,
                      color,
                      focus: focused,
                    });
                  }
                  return (
                    <Group key={r.team.slug} listening={false}>
                      {showPlayers &&
                        players.map((p, i) => {
                          const lit = highlight === p.entity_id;
                          const shade = lit ? lighten(color, 0.15) : lighten(color, 0.3 + 0.12 * (i % 4));
                          const faded = highlight != null && !lit;
                          const now = playerAt(p);
                          if (now && (shown.length <= PLAYER_LABEL_TEAMS || lit)) {
                            const q = px0(now.at);
                            labels.push({
                              id: `p-${p.entity_id}`,
                              x: q.px,
                              y: q.py,
                              kind: "player",
                              text: p.name,
                              tag: r.team.tag || r.team.name,
                              logo: r.team.logo,
                              color,
                              status: statusAt(t, now.onMap, p.deaths.map((d) => d[0]), p.knocks),
                              focus: focused || lit,
                            });
                          }
                          return (
                            <Group key={p.entity_id} opacity={faded ? 0.18 : 1}>
                              {(p.path as TPoint[][]).map((seg, j) => (
                                <Line
                                  key={j}
                                  points={upTo(seg, t).flatMap(([, x, z]) => {
                                    const q = px0({ x, z });
                                    return [q.px, q.py];
                                  })}
                                  stroke={shade}
                                  strokeWidth={px(lit ? 3.2 : 1.5)}
                                  opacity={lit ? 1 : 0.9}
                                  shadowColor="#000"
                                  shadowBlur={lit ? px(4) : 0}
                                  shadowOpacity={0.9}
                                  lineCap="round"
                                  lineJoin="round"
                                />
                              ))}
                              {p.deaths
                                .filter((d) => d[0] <= t)
                                .map((d, j) => (
                                  <Cross key={`d${j}`} at={px0({ x: d[1], z: d[2] })} color={shade} px={px} />
                                ))}
                              {!full && now?.onMap && <Circle x={px0(now.at).px} y={px0(now.at).py} radius={px(3.5)} fill={shade} stroke="#000" strokeWidth={px(1)} />}
                            </Group>
                          );
                        })}
                      {showTeam && (
                        <Group opacity={dimTeam ? 0.35 : 1}>
                          {teamLines(r, t, view.t).map((line, i) => (
                            <Line key={i} points={line} stroke={color} strokeWidth={px(3)} lineCap="round" lineJoin="round" />
                          ))}
                          <Markers points={r.points.filter((p) => p.game_time_s == null || p.game_time_s <= t || full)} t={view.t} color={color} px={px} />
                          {!full && head && <Circle x={px0(head).px} y={px0(head).py} radius={px(5)} fill={color} stroke="#000" strokeWidth={px(1.5)} />}
                        </Group>
                      )}
                    </Group>
                  );
                })}
                <MapLabels labels={labels} px={px} />
              </>
            );
          }}
        </MapCanvas>

        <div className="flex flex-wrap items-center gap-2 border-t border-line p-2 sm:gap-3 sm:p-3">
          {canPlay && (
            <>
              <button className="btn min-w-16 px-3 py-1.5" onClick={togglePlay}>
                {playing ? "Pause" : t >= end ? "Play" : "Resume"}
              </button>
              <span className="text-sm whitespace-nowrap tabular-nums">
                {clock(t)} / {clock(end)}
              </span>
              <input
                type="range"
                aria-label="Match time"
                className="min-w-32 flex-1 accent-[var(--color-accent,#ff2e63)]"
                min={start}
                max={end}
                step={0.5}
                value={t}
                onChange={(e) => setT(Math.min(end, Math.max(start, Number(e.target.value))))}
              />
              <div className="flex gap-1">
                {SPEEDS.map((s) => (
                  <button key={s} className={`btn px-2 py-1 text-xs ${s === speed ? "ring-1 ring-accent" : ""}`} onClick={() => setSpeed(s)}>
                    {s}x
                  </button>
                ))}
              </div>
            </>
          )}
          <div className="flex gap-1" role="group" aria-label="Lines to show">
            {MODES.map((m) => (
              <button
                key={m.mode}
                className={`btn px-2 py-1 text-xs ${m.mode === mode ? "ring-1 ring-accent text-white" : "text-muted"}`}
                onClick={() => setMode(m.mode)}
                aria-pressed={m.mode === mode}
              >
                {m.label}
              </button>
            ))}
          </div>
          {single && (
            <label className="flex items-center gap-1.5 text-xs text-muted">
              <input
                type="checkbox"
                checked={follow}
                onChange={(e) => {
                  setFollow(e.target.checked);
                  setHeld(false);
                }}
              />
              Follow team
            </label>
          )}
        </div>
      </div>

      {single && (
        <aside className="max-h-[35dvh] shrink-0 overflow-y-auto border-t border-line p-3 text-sm lg:max-h-none lg:w-72 lg:border-t-0 lg:border-l">
          <h2 className="font-display text-xl uppercase">{single.team.name}</h2>
          <p className="text-xs text-muted">
            {single.placement != null ? `#${single.placement} · ` : ""}
            {single.status === "CONFIRMED" ? "Checked by league staff" : "Worked out from the match logs"}
          </p>
          {(single.players ?? []).length > 0 && (
            <>
              <h3 className="mt-3 text-xs font-semibold text-muted uppercase">Players</h3>
              <p className="text-xs text-muted">Tap a name to highlight their path.</p>
              <ul className="mt-1 space-y-1">
                {(single.players ?? []).map((p, i) => {
                  const lit = highlight === p.entity_id;
                  const deaths = p.deaths.filter((d) => d[0] <= t).length;
                  return (
                    <li key={p.entity_id}>
                      <button
                        className={`flex w-full items-center gap-2 px-2 py-1 text-left ${lit ? "bg-panel-2 ring-1 ring-accent" : "bg-panel hover:bg-panel-2"}`}
                        onClick={() => {
                          setHighlight(lit ? null : p.entity_id);
                          if (mode === "team") setMode("both");
                        }}
                        aria-pressed={lit}
                      >
                        <span className="h-2 w-4 shrink-0" style={{ background: lighten(colors[single.team.slug], 0.3 + 0.12 * (i % 4)) }} />
                        <span className="flex-1 truncate font-medium">{p.name}</span>
                        {deaths > 0 && <span className="text-xs text-muted">{deaths === 1 ? "died" : `died ${deaths}x`}</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
          <h3 className="mt-3 text-xs font-semibold text-muted uppercase">Route</h3>
          <ul className="mt-1 space-y-1">
            {single.points.map((p, i) => (
              <li key={`${p.checkpoint}-${i}`} className="flex items-center gap-2 bg-panel px-2 py-1">
                <span className="w-20 font-medium">{LABELS[p.checkpoint]}</span>
                <span className="flex-1 truncate text-xs text-muted">
                  {p.area ?? `${Math.round(p.x)}, ${Math.round(p.z)}`}
                  {p.game_time_s != null && ` · ${clock(p.game_time_s)}`}
                </span>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}

/** The team line up to t: its replay path, or straight lines between its checkpoints. */
function teamLines(r: TeamRotation, t: number, transform: Transform): number[][] {
  const path = (r.path ?? []) as TPoint[][];
  if (!path.length) return routeLines(r.points, [], transform);
  return routeLines(r.points, path.map((seg) => upTo(seg, t)).filter((s) => s.length > 1), transform);
}

function Markers({ points, t, color, px }: { points: RotationPoint[]; t: Transform; color: string; px: (n: number) => number }) {
  const r = px(9);
  return (
    <>
      {points.map((p, i) => {
        const q = toPixel(t, p.x, p.z);
        return (
          <Group key={`${p.checkpoint}-${i}`} x={q.px} y={q.py}>
            <Circle radius={r} fill="#0b0b0f" stroke={color} strokeWidth={px(2.5)} />
            <Text
              text={SHORT[p.checkpoint]}
              fill="#fff"
              fontSize={px(10)}
              fontStyle="bold"
              width={r * 2}
              height={r * 2}
              offsetX={r}
              offsetY={r}
              align="center"
              verticalAlign="middle"
            />
          </Group>
        );
      })}
    </>
  );
}

/** Where a player died: a small X with a dark outline so it reads on any map colour. */
export function Cross({ at, color, px }: { at: { px: number; py: number }; color: string; px: (n: number) => number }) {
  const s = px(4.5);
  return (
    <Group x={at.px} y={at.py}>
      <Line points={[-s, -s, s, s]} stroke="#000" strokeWidth={px(4)} lineCap="round" />
      <Line points={[-s, s, s, -s]} stroke="#000" strokeWidth={px(4)} lineCap="round" />
      <Line points={[-s, -s, s, s]} stroke={color} strokeWidth={px(2)} lineCap="round" />
      <Line points={[-s, s, s, -s]} stroke={color} strokeWidth={px(2)} lineCap="round" />
    </Group>
  );
}

function Ring({
  t,
  unit,
  c,
  stroke,
  width,
  dash,
}: {
  t: Transform;
  unit: number;
  c: { x: number; z: number; r: number };
  stroke: string;
  width: number;
  dash?: number[];
}) {
  const q = toPixel(t, c.x, c.z);
  return <Circle x={q.px} y={q.py} radius={c.r * unit} stroke={stroke} strokeWidth={width} dash={dash} listening={false} />;
}
