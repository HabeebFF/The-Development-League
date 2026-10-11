// Live replay maths: where a player is at time t, and what the zone looks like.

import type { Zone } from "./api";

export type ReplayPlayer = {
  entity_id: number;
  name: string;
  team: string;
  start_s: number;
  /** [x, z] in world decimetres every step, null while not recorded (dead, gap). */
  points: ([number, number] | null)[];
};

export type ReplayEvent = {
  kind: "KILL" | "KNOCK";
  t: number;
  actor: number | null;
  target: number | null;
  headshot: boolean | null;
  x: number | null;
  z: number | null;
  tx: number | null;
  tz: number | null;
};

export type ReplayTeam = {
  slug: string;
  name: string;
  tag: string;
  color: string | null;
  logo?: string | null;
  placement: number;
  has_tracks: boolean;
};

export type ReplayObject = {
  kind: "PLAYER_UAV" | "GENERAL_UAV" | "BOLT_MAKER" | "DINOCULARS";
  owner: number | null;
  owner_name: string | null;
  team: string | null;
  start_s: number;
  end_s: number;
  /** Where it starts: a Bolt Maker's centre, the spot a Dinoculars scan looked at. */
  x: number;
  z: number;
  /** Metres a UAV or Dinoculars scans, or how far a Bolt Maker zone reaches. */
  radius: number | null;
  /** [t, x_dm, z_dm]: a UAV's path, or a Bolt Maker's strikes (empty for a scan). */
  points: [number, number, number][];
};

export type Replay = {
  match: number;
  map: { slug: string; name: string } | null;
  duration_s: number | null;
  step_s: number | null;
  teams: ReplayTeam[];
  players: ReplayPlayer[];
  zones: Zone[];
  events: ReplayEvent[];
  objects?: ReplayObject[];
};

export type World = { x: number; z: number };

/** World position at time t, interpolated between grid points; null when not recorded. */
export function positionAt(p: ReplayPlayer, step: number, t: number): World | null {
  const f = (t - p.start_s) / step;
  if (f < 0 || f > p.points.length - 1) return null;
  const i = Math.floor(f);
  const a = p.points[i];
  if (!a) return null;
  const b = p.points[Math.min(i + 1, p.points.length - 1)];
  const k = f - i;
  if (!b || k === 0) return { x: a[0] / 10, z: a[1] / 10 };
  return { x: (a[0] + (b[0] - a[0]) * k) / 10, z: (a[1] + (b[1] - a[1]) * k) / 10 };
}

/** The recorded path over the last ``seconds`` before t, split where it has gaps. */
export function trailAt(p: ReplayPlayer, step: number, t: number, seconds: number): World[][] {
  const end = Math.min(Math.floor((t - p.start_s) / step), p.points.length - 1);
  const begin = Math.max(0, Math.ceil((t - seconds - p.start_s) / step));
  const pieces: World[][] = [];
  let piece: World[] = [];
  for (let i = begin; i <= end; i++) {
    const v = p.points[i];
    if (v) piece.push({ x: v[0] / 10, z: v[1] / 10 });
    else {
      if (piece.length > 1) pieces.push(piece);
      piece = [];
    }
  }
  const now = positionAt(p, step, t);
  if (now && piece.length) piece.push(now);
  if (piece.length > 1) pieces.push(piece);
  return pieces;
}

/** First and last recorded time over all players. */
export function timeRange(players: ReplayPlayer[], step: number): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const p of players) {
    lo = Math.min(lo, p.start_s);
    hi = Math.max(hi, p.start_s + (p.points.length - 1) * step);
  }
  return Number.isFinite(lo) ? [lo, hi] : [0, 0];
}

export type ZoneNow = {
  /** The circle players must be inside now (moving while it shrinks). */
  current: { x: number; z: number; r: number } | null;
  /** Where it will end up next. */
  next: { x: number; z: number; r: number } | null;
};

/** The zone at time t. A shrink runs from its SHRINK row to the next row's time. */
export function zoneAt(zones: Zone[], t: number): ZoneNow {
  const timed = zones.filter((z) => z.game_time_s != null).sort((a, b) => a.game_time_s! - b.game_time_s!);
  let i = -1;
  for (let k = 0; k < timed.length; k++) if (timed[k].game_time_s! <= t) i = k;
  if (i < 0) {
    const first = timed[0];
    return { current: null, next: first ? circle(first, "inner") : null };
  }
  const z = timed[i];
  const next = circle(z, "inner");
  if (z.state !== "SHRINK" || z.outer_radius == null) {
    return { current: z.outer_radius != null ? circle(z, "outer") : null, next };
  }
  const end = timed[i + 1]?.game_time_s ?? z.game_time_s! + 60;
  const k = Math.min(1, Math.max(0, (t - z.game_time_s!) / Math.max(1, end - z.game_time_s!)));
  return {
    current: {
      x: z.outer_x + (z.inner_x - z.outer_x) * k,
      z: z.outer_z + (z.inner_z - z.outer_z) * k,
      r: z.outer_radius + (z.inner_radius - z.outer_radius) * k,
    },
    next,
  };
}

function circle(z: Zone, which: "inner" | "outer") {
  return which === "inner"
    ? { x: z.inner_x, z: z.inner_z, r: z.inner_radius }
    : { x: z.outer_x, z: z.outer_z, r: z.outer_radius ?? z.inner_radius };
}

export function clock(t: number): string {
  const s = Math.max(0, Math.floor(t));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** A UAV's position at t, or null when it isn't flying. Holds still across gaps (hovering). */
export function uavAt(o: ReplayObject, t: number): World | null {
  if (t < o.start_s || t > o.end_s || !o.points.length) return null;
  const pts = o.points;
  let i = 0;
  while (i + 1 < pts.length && pts[i + 1][0] <= t) i++;
  const a = pts[i];
  const b = pts[i + 1];
  if (!b || b[0] - a[0] > 2) return { x: a[1] / 10, z: a[2] / 10 };
  const k = (t - a[0]) / (b[0] - a[0]);
  return { x: (a[1] + (b[1] - a[1]) * k) / 10, z: (a[2] + (b[2] - a[2]) * k) / 10 };
}

/** A UAV's path over the last ``seconds`` before t. */
export function uavTrail(o: ReplayObject, t: number, seconds: number): World[] {
  const out = o.points.filter((p) => p[0] <= t && p[0] >= t - seconds).map((p) => ({ x: p[1] / 10, z: p[2] / 10 }));
  const now = uavAt(o, t);
  if (now) out.push(now);
  return out;
}

/** How many enemies of the scanner were inside a Dinoculars scan when it went off. */
export function enemiesInScan(o: ReplayObject, players: ReplayPlayer[], step: number): number {
  const r = o.radius ?? 50;
  return players.filter((p) => {
    if (p.entity_id === o.owner || (o.team != null && p.team === o.team)) return false;
    const w = positionAt(p, step, o.start_s);
    return w != null && Math.hypot(w.x - o.x, w.z - o.z) <= r;
  }).length;
}

/** Bolt Maker strikes that landed in the last ``seconds`` before t. */
export function strikesAt(o: ReplayObject, t: number, seconds = 1.2): { x: number; z: number; age: number }[] {
  return o.points
    .filter((p) => p[0] <= t && p[0] > t - seconds)
    .map((p) => ({ x: p[1] / 10, z: p[2] / 10, age: (t - p[0]) / seconds }));
}

/** Where a "Watch this" link opens the replay: `?t=<game second>&team=<slug>`. */
export type ReplayStart = { startAt?: number; team?: string };

export function replayStart(query: { t?: string | string[]; team?: string | string[] }): ReplayStart {
  const one = (v?: string | string[]) => (Array.isArray(v) ? v[0] : v);
  const t = Number(one(query.t));
  const team = one(query.team);
  return {
    startAt: one(query.t) && Number.isFinite(t) && t >= 0 ? t : undefined,
    team: team && /^[a-z0-9-]+$/.test(team) ? team : undefined,
  };
}

export function replayHref(base: string, startAt: number, team?: string): string {
  const q = new URLSearchParams({ t: String(Math.max(0, Math.round(startAt))) });
  if (team) q.set("team", team);
  return `${base}?${q}`;
}

/** Kills each player (by entity id) has made by time ``t``. Self-kills don't count. */
export function killsAt(events: ReplayEvent[], t: number, teamOf: Record<number, string> = {}): Record<number, number> {
  const out: Record<number, number> = {};
  for (const e of events) {
    if (e.kind !== "KILL" || e.t > t || e.actor == null || e.actor === e.target) continue;
    // Zone, fall and own-explosive deaths can be logged against a teammate: not a kill.
    if (e.target != null && teamOf[e.actor] != null && teamOf[e.actor] === teamOf[e.target]) continue;
    out[e.actor] = (out[e.actor] ?? 0) + 1;
  }
  return out;
}
