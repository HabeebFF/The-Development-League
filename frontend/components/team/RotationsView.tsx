"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Circle, Group, Line, Text } from "react-konva";

import MapCanvas from "@/components/map/MapCanvas";
import { api, type GameMap, type TeamRotation, type Zone } from "@/lib/api";
import { teamColor } from "@/lib/colors";
import { fitBounds, toPixel, type Transform } from "@/lib/coordinates";
import { clock } from "@/lib/replay";
import { LABELS, SHORT, type RotationPoint } from "@/lib/rotation";

const CANVAS = 1024;

type Loaded = { map: GameMap | null; zones: Zone[]; rotations: TeamRotation[] };

/** Every team's route in one match (drop, zone spots, end spot), read-only. */
export default function RotationsView({ matchId, focusTeam }: { matchId: number; focusTeam: string | null }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());

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

  // World -> content pixels: the calibrated image, or a plain grid fitted to the routes.
  const view = useMemo(() => {
    const map = data?.map;
    if (map?.image && map.transform && map.image_width && map.image_height) {
      return { t: map.transform, w: map.image_width, h: map.image_height, image: map.image };
    }
    const world = [
      ...rotations.flatMap((r) => r.points),
      ...shrinks.flatMap((z) => [
        { x: z.inner_x - z.inner_radius, z: z.inner_z - z.inner_radius },
        { x: z.inner_x + z.inner_radius, z: z.inner_z + z.inner_radius },
      ]),
    ];
    return { t: fitBounds(world, CANVAS, CANVAS), w: CANVAS, h: CANVAS, image: null };
  }, [data, rotations, shrinks]);
  const unit = Math.sqrt(Math.abs(view.t.a * view.t.e - view.t.b * view.t.d)); // px per world unit

  function pick(slug: string, add: boolean) {
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
        <Link href="/team" className="mt-4 inline-block text-accent">
          &larr; Matches
        </Link>
      </div>
    );
  }

  const shown = rotations.filter((r) => chosen.has(r.team.slug));
  const single = shown.length === 1 ? shown[0] : null;

  return (
    <div className="flex h-[calc(100dvh-var(--header-h)-var(--bottom-nav-h))] flex-col lg:flex-row">
      <aside className="flex shrink-0 gap-1 overflow-x-auto border-b border-line p-2 lg:w-64 lg:flex-col lg:overflow-y-auto lg:border-r lg:border-b-0">
        <Link href="/team" className="hidden px-2 pb-1 text-xs text-muted hover:text-text lg:block">
          &larr; Matches
        </Link>
        <p className="hidden px-2 pb-1 text-xs text-muted lg:block">
          Click a team to see its route. Shift-click to compare teams.
        </p>
        <button
          className="btn shrink-0 px-2 py-1 text-xs"
          onClick={() => setChosen(new Set(rotations.map((r) => r.team.slug)))}
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

      <MapCanvas width={view.w} height={view.h} image={view.image} className="min-h-[50dvh] flex-1">
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
            {shown.map((r) => (
              <Route key={r.team.slug} points={r.points} t={view.t} color={colors[r.team.slug]} px={px} />
            ))}
          </>
        )}
      </MapCanvas>

      {single && (
        <aside className="shrink-0 overflow-y-auto border-t border-line p-3 text-sm lg:w-72 lg:border-t-0 lg:border-l">
          <h2 className="font-display text-xl uppercase">{single.team.name}</h2>
          <p className="text-xs text-muted">
            {single.placement != null ? `#${single.placement} · ` : ""}
            {single.status === "CONFIRMED" ? "Checked by league staff" : "Worked out from the match logs"}
          </p>
          <ul className="mt-3 space-y-1">
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

function Route({
  points,
  t,
  color,
  px,
}: {
  points: RotationPoint[];
  t: Transform;
  color: string;
  px: (n: number) => number;
}) {
  const pixels = points.map((p) => toPixel(t, p.x, p.z));
  const route = pixels.filter((_, i) => points[i].checkpoint !== "EXTRA").flatMap((p) => [p.px, p.py]);
  const r = px(9);
  return (
    <Group listening={false}>
      <Line points={route} stroke={color} strokeWidth={px(3)} lineCap="round" lineJoin="round" />
      {points.map((p, i) => (
        <Group key={`${p.checkpoint}-${i}`} x={pixels[i].px} y={pixels[i].py}>
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
      ))}
    </Group>
  );
}
