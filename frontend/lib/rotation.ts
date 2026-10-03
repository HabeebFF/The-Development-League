// Plotting-tool state: pure functions, so they can be tested without a browser.

import type { Transform } from "./coordinates";

export const ZONE_CHECKPOINTS = [
  "ZONE_1",
  "ZONE_2",
  "ZONE_3",
  "ZONE_4",
  "ZONE_5",
  "ZONE_6",
  "ZONE_7",
  "ZONE_8",
] as const;
export const CHECKPOINTS = ["DROP", ...ZONE_CHECKPOINTS, "EXTRA", "FINAL", "ELIMINATED"] as const;
export type Checkpoint = (typeof CHECKPOINTS)[number];

export type RotationPoint = {
  checkpoint: Checkpoint;
  x: number;
  z: number;
  game_time_s: number | null;
  area?: string | null;
  source: "MANUAL" | "AUTO";
  evidence?: Record<string, number>;
  note: string;
};

export const LABELS: Record<Checkpoint, string> = {
  DROP: "Drop",
  ZONE_1: "Zone 1",
  ZONE_2: "Zone 2",
  ZONE_3: "Zone 3",
  ZONE_4: "Zone 4",
  ZONE_5: "Zone 5",
  ZONE_6: "Zone 6",
  ZONE_7: "Zone 7",
  ZONE_8: "Zone 8",
  EXTRA: "Extra",
  FINAL: "Final",
  ELIMINATED: "Eliminated",
};

export const SHORT: Record<Checkpoint, string> = {
  DROP: "D",
  ZONE_1: "1",
  ZONE_2: "2",
  ZONE_3: "3",
  ZONE_4: "4",
  ZONE_5: "5",
  ZONE_6: "6",
  ZONE_7: "7",
  ZONE_8: "8",
  EXTRA: "+",
  FINAL: "W",
  ELIMINATED: "X",
};

/** Keyboard: Q W E R T = Drop, Zone 1-4; U I = Zone 5-6; Y = Final; X = Eliminated; A = Extra. */
export const CHECKPOINT_KEYS: Record<string, Checkpoint> = {
  q: "DROP",
  w: "ZONE_1",
  e: "ZONE_2",
  r: "ZONE_3",
  t: "ZONE_4",
  u: "ZONE_5",
  i: "ZONE_6",
  y: "FINAL",
  x: "ELIMINATED",
  a: "EXTRA",
};

const RANK = Object.fromEntries(CHECKPOINTS.map((c, i) => [c, i])) as Record<Checkpoint, number>;

function sorted(points: RotationPoint[]): RotationPoint[] {
  // Stable: EXTRA points keep the order they were added in.
  return points
    .map((p, i) => ({ p, i }))
    .sort((a, b) => RANK[a.p.checkpoint] - RANK[b.p.checkpoint] || a.i - b.i)
    .map(({ p }) => p);
}

/** Put a point for a checkpoint. Single checkpoints are replaced; Final and Eliminated
 * exclude each other; Extra points add up. */
export function placePoint(
  points: RotationPoint[],
  checkpoint: Checkpoint,
  x: number,
  z: number,
): RotationPoint[] {
  const point: RotationPoint = {
    checkpoint,
    x: round(x),
    z: round(z),
    game_time_s: null,
    source: "MANUAL",
    note: "",
  };
  let rest = points;
  if (checkpoint !== "EXTRA") {
    const clash = checkpoint === "FINAL" ? "ELIMINATED" : checkpoint === "ELIMINATED" ? "FINAL" : null;
    rest = points.filter((p) => p.checkpoint !== checkpoint && p.checkpoint !== clash);
    const old = points.find((p) => p.checkpoint === checkpoint);
    if (old) point.note = old.note;
  }
  return sorted([...rest, point]);
}

export function movePoint(points: RotationPoint[], index: number, x: number, z: number) {
  return points.map((p, i) =>
    i === index ? { ...p, x: round(x), z: round(z), source: "MANUAL" as const, evidence: {} } : p,
  );
}

export function removePoint(points: RotationPoint[], index: number): RotationPoint[] {
  return points.filter((_, i) => i !== index);
}

/** "C": the team stayed put, so the checkpoint goes where its previous point is. */
export function copyLast(points: RotationPoint[], checkpoint: Checkpoint): RotationPoint[] {
  const before = points.filter((p) => RANK[p.checkpoint] < RANK[checkpoint]);
  const last = before[before.length - 1];
  return last ? placePoint(points, checkpoint, last.x, last.z) : points;
}

/** The next checkpoint to plot: the first of Drop and the match's zones not yet placed. */
export function nextCheckpoint(points: RotationPoint[], zoneCount: number): Checkpoint | null {
  const wanted: Checkpoint[] = ["DROP", ...ZONE_CHECKPOINTS.slice(0, zoneCount)];
  return wanted.find((c) => !points.some((p) => p.checkpoint === c)) ?? null;
}

function round(v: number): number {
  return Math.round(v * 100) / 100;
}

/** A team's path from the replay: segments of [game seconds, x, z]. */
export type ReplayPath = [number, number, number][][];

/**
 * The lines to draw for a team, as flat pixel arrays for Konva: its real path from the
 * replay when there is one, else straight lines between its checkpoints (extras skipped).
 */
export function routeLines(points: RotationPoint[], path: ReplayPath | undefined, t: Transform): number[][] {
  const flat = (xz: { x: number; z: number }[]) =>
    xz.flatMap((p) => [t.a * p.x + t.b * p.z + t.c, t.d * p.x + t.e * p.z + t.f]); // toPixel
  if (path?.length) return path.filter((s) => s.length > 1).map((s) => flat(s.map(([, x, z]) => ({ x, z }))));
  return [flat(points.filter((p) => p.checkpoint !== "EXTRA"))];
}
