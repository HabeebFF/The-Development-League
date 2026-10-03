"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Circle, Group, Line, Text } from "react-konva";

import MapCanvas from "@/components/map/MapCanvas";
import { api, ApiError, type GameMap, type Paged } from "@/lib/api";
import { type RotationAdvice } from "@/lib/coach";
import { TEAM_COLORS } from "@/lib/colors";
import { fitBounds, toPixel } from "@/lib/coordinates";
import { clock } from "@/lib/replay";

const CANVAS = 1000;
const ACCENT = "#ff6a1a";

/** When to rotate on a map: each drop spot, when the teams that did well from it left, and their routes. */
export default function RotateView({ matchHref }: { matchHref: (id: number) => string }) {
  const [maps, setMaps] = useState<GameMap[] | null>(null);
  const [slug, setSlug] = useState("");
  const [advice, setAdvice] = useState<RotationAdvice | null>(null);
  const [pick, setPick] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Paged<GameMap> | GameMap[]>("/maps?page_size=50")
      .then((d) => {
        const list = Array.isArray(d) ? d : d.results;
        setMaps(list);
        setSlug((s) => s || list[0]?.slug || "");
      })
      .catch(() => setMaps([]));
  }, []);

  useEffect(() => {
    if (!slug) return;
    let live = true;
    api<RotationAdvice>(`/coach/maps/${slug}/rotate`)
      .then((a) => {
        if (!live) return;
        setAdvice(a);
        setPick(0);
        setError(null);
      })
      .catch((e) => live && setError(e instanceof ApiError ? e.message : "Couldn't load this map."));
    return () => {
      live = false;
    };
  }, [slug]);

  const map = maps?.find((m) => m.slug === slug) ?? null;
  const current = advice && advice.map === slug ? advice : null;
  const drop = current?.drops[pick] ?? null;
  const labels = new Map((current?.matches ?? []).map((m) => [m.id, m.label]));

  const view = useMemo(() => {
    if (map?.image && map.transform && map.image_width && map.image_height) {
      return { t: map.transform, w: map.image_width, h: map.image_height, image: map.image };
    }
    const pts = (current?.drops ?? []).map((d) => ({ x: d.x, z: d.z }));
    const world =
      pts.length > 1
        ? pts
        : [
            { x: -1000, z: -1000 },
            { x: 1000, z: 1000 },
          ];
    return { t: fitBounds(world, CANVAS, CANVAS), w: CANVAS, h: CANVAS, image: null };
  }, [map, current]);
  const at = (x: number, z: number) => toPixel(view.t, x, z);
  const scale = Math.hypot(view.t.a, view.t.d);

  const chips = (ids: number[]) => (
    <span className="mt-2 flex flex-wrap gap-1">
      {ids.map((id) => (
        <Link
          key={id}
          href={matchHref(id)}
          className="rounded border border-line px-1.5 py-0.5 text-xs text-muted hover:border-accent hover:text-white"
        >
          {labels.get(id) ?? `Match ${id}`}
        </Link>
      ))}
    </span>
  );

  return (
    <div>
      <label className="block max-w-xs text-sm">
        <span className="text-muted">Map</span>
        <select className="input mt-1 w-full" value={slug} onChange={(e) => setSlug(e.target.value)} disabled={!maps}>
          {maps?.map((m) => (
            <option key={m.slug} value={m.slug}>
              {m.name}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="mt-4 text-bad">{error}</p>}
      {!current && !error && <p className="mt-4 text-muted">Loading...</p>}
      {current && current.drops.length === 0 && (
        <p className="mt-4 text-sm text-muted">
          Not enough replays on {current.name} yet. A drop shows up once teams have landed there in at least 3 matches with replay files.
        </p>
      )}
      {current && current.drops.length > 0 && (
        <div className="mt-6 grid gap-6 lg:grid-cols-[22rem_1fr]">
          <ol className="space-y-2 lg:max-h-[70dvh] lg:overflow-y-auto">
            {current.drops.map((d, i) => (
              <li key={d.place}>
                <button
                  className={`card w-full p-3 text-left ${i === pick ? "border-accent" : "hover:border-muted"}`}
                  onClick={() => setPick(i)}
                  aria-pressed={i === pick}
                >
                  <span className="block font-medium">{d.place}</span>
                  <span className="block text-xs text-muted">
                    {d.team_matches} drops in {d.matches.length} matches · average placement {d.avg_placement} · {d.top_finishes} top 5
                  </span>
                  {i === pick && (
                    <>
                      <ul className="mt-2 space-y-1 text-sm">
                        {d.advice.map((a) => (
                          <li key={a}>{a}</li>
                        ))}
                      </ul>
                      {chips(d.top_matches.length ? d.top_matches : d.matches)}
                    </>
                  )}
                </button>
              </li>
            ))}
          </ol>
          <div>
            <div className="aspect-square w-full lg:aspect-auto lg:h-[70dvh]">
              <MapCanvas width={view.w} height={view.h} image={view.image} className="h-full w-full" resetKey={slug}>
                {(px) => (
                  <>
                    {current.zone_ends.map((z) => {
                      const c = at(z.x, z.z);
                      return (
                        <Group key={z.match}>
                          <Circle x={c.px} y={c.py} radius={z.r * scale} stroke="#ffffff" strokeWidth={px(1.5)} opacity={0.6} dash={[px(5), px(4)]} />
                          <Circle x={c.px} y={c.py} radius={px(3)} fill="#ffffff" opacity={0.8} />
                        </Group>
                      );
                    })}
                    {drop?.routes.map((r, i) =>
                      r.path.map((seg, j) => (
                        <Line
                          key={`${r.match}-${i}-${j}`}
                          points={seg.flatMap(([, x, z]) => {
                            const p = at(x, z);
                            return [p.px, p.py];
                          })}
                          stroke={TEAM_COLORS[i % TEAM_COLORS.length]}
                          strokeWidth={px(3)}
                          lineCap="round"
                          lineJoin="round"
                          opacity={0.9}
                        />
                      )),
                    )}
                    {current.drops.map((d, i) => {
                      const c = at(d.x, d.z);
                      const on = i === pick;
                      return (
                        <Circle
                          key={d.place}
                          x={c.px}
                          y={c.py}
                          radius={px(on ? 9 : 5)}
                          fill={on ? ACCENT : "#ffffff"}
                          stroke="#000000"
                          strokeWidth={px(1.5)}
                          onClick={() => setPick(i)}
                          onTap={() => setPick(i)}
                        />
                      );
                    })}
                    {drop && (
                      <Text
                        x={at(drop.x, drop.z).px + px(12)}
                        y={at(drop.x, drop.z).py - px(8)}
                        text={drop.place}
                        fontSize={px(14)}
                        fontStyle="bold"
                        fill="#ffffff"
                        shadowColor="#000000"
                        shadowBlur={px(4)}
                      />
                    )}
                  </>
                )}
              </MapCanvas>
            </div>
            {drop && drop.routes.length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                {drop.routes.map((r, i) => (
                  <li key={`${r.match}-${r.team}`} className="flex items-center gap-1.5">
                    <span className="h-2 w-4" style={{ background: TEAM_COLORS[i % TEAM_COLORS.length] }} />
                    {r.team}, {r.label}, placed {r.placement}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-muted">
              Dashed white circles: where the last zone ended in each of {current.matches.length} matches. Routes run until Zone 3 closed.
              {drop?.left_s != null ? ` Leave time ${clock(drop.left_s)} is the median of the top 5 teams from ${drop.place}.` : ""}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
