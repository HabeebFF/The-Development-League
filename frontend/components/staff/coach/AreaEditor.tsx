"use client";

import { useMemo, useState } from "react";
import { Circle, Group, Line, Text } from "react-konva";

import MapCanvas from "@/components/map/MapCanvas";
import { api, ApiError, type GameMap, type MapArea } from "@/lib/api";
import { fitBounds, toPixel, toWorld } from "@/lib/coordinates";

const CANVAS = 1000;
const ACCENT = "#ff6a1a";
const SUGGESTED = "#ffc23d";

/**
 * Named places on a map (drop spots, high ground, route landmarks): click the map to
 * outline one, name it and save. The coach and the rotation pages use these names.
 * Outlines suggested from guides are dashed until staff confirm them.
 */
export default function AreaEditor({ maps, onChanged }: { maps: GameMap[]; onChanged: () => void }) {
  const [slug, setSlug] = useState(maps[0]?.slug ?? "");
  const map = maps.find((m) => m.slug === slug) ?? null;
  const [areas, setAreas] = useState<Record<string, MapArea[]>>({});
  const shown = areas[slug] ?? map?.areas ?? [];
  const [points, setPoints] = useState<[number, number][]>([]);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const view = useMemo(() => {
    if (map?.image && map.transform && map.image_width && map.image_height) {
      return {
        t: map.transform,
        w: map.image_width,
        h: map.image_height,
        image: map.image,
      };
    }
    const world = (map?.areas ?? []).flatMap((a) => a.polygon.map(([x, z]) => ({ x, z })));
    return {
      t: fitBounds(
        world.length
          ? world
          : [
              { x: -1000, z: -1000 },
              { x: 1000, z: 1000 },
            ],
        CANVAS,
        CANVAS,
      ),
      w: CANVAS,
      h: CANVAS,
      image: null,
    };
  }, [map]);

  function pick(next: string) {
    setSlug(next);
    setPoints([]);
    setSelected(null);
    setName("");
  }

  function place(px: number, py: number) {
    if (selected !== null) return;
    const w = toWorld(view.t, px, py);
    setPoints((p) => [...p, [Math.round(w.x * 10) / 10, Math.round(w.z * 10) / 10]]);
  }

  async function reload() {
    const fresh = await api<MapArea[]>(`/admin/maps/${slug}/areas`);
    setAreas((all) => ({ ...all, [slug]: fresh }));
    onChanged();
  }

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await reload();
      setPoints([]);
      setSelected(null);
      setName("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    run(() =>
      selected !== null
        ? api(`/admin/maps/${slug}/areas/${selected}`, {
            method: "PATCH",
            body: { name: name.trim() },
          })
        : api(`/admin/maps/${slug}/areas`, {
            method: "POST",
            body: { name: name.trim(), polygon: points },
          }),
    );
  const confirmArea = (area: MapArea) => run(() => api(`/admin/maps/${slug}/areas/${area.id}`, { method: "PATCH", body: { status: "CONFIRMED" } }));
  const suggested = shown.filter((a) => a.status === "SUGGESTED");
  const confirmed = shown.filter((a) => a.status !== "SUGGESTED");
  const remove = (area: MapArea) => confirm(`Delete "${area.name}"?`) && run(() => api(`/admin/maps/${slug}/areas/${area.id}`, { method: "DELETE" }));

  const flat = (poly: [number, number][]) =>
    poly.flatMap(([x, z]) => {
      const p = toPixel(view.t, x, z);
      return [p.px, p.py];
    });

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <div className="min-w-0 flex-1">
        <MapCanvas
          width={view.w}
          height={view.h}
          image={view.image}
          onClick={place}
          className="aspect-square w-full lg:aspect-auto lg:h-[70dvh]"
          resetKey={slug}
        >
          {(px) => (
            <>
              {shown.map((a) => {
                const c = toPixel(view.t, a.centre_x, a.centre_z);
                const lit = a.id === selected;
                const guess = a.status === "SUGGESTED";
                return (
                  <Group key={a.id} listening={false}>
                    <Line
                      points={flat(a.polygon)}
                      closed
                      stroke={lit ? ACCENT : guess ? SUGGESTED : "#ffffffcc"}
                      strokeWidth={px(lit ? 2.5 : 1.5)}
                      dash={guess ? [px(6), px(4)] : undefined}
                      fill={lit ? "#ff6a1a33" : guess ? "#ffc23d14" : "#ffffff14"}
                    />
                    <Text
                      x={c.px}
                      y={c.py}
                      text={a.name}
                      fontSize={px(12)}
                      fontStyle="bold"
                      fill="#ffffff"
                      offsetX={px(a.name.length * 3.2)}
                      offsetY={px(6)}
                      shadowColor="#000"
                      shadowBlur={px(3)}
                    />
                  </Group>
                );
              })}
              {points.length > 0 && (
                <Group listening={false}>
                  <Line points={flat(points)} closed={points.length > 2} stroke={ACCENT} strokeWidth={px(2)} dash={[px(6), px(4)]} fill="#ff6a1a22" />
                  {points.map(([x, z], i) => {
                    const p = toPixel(view.t, x, z);
                    return <Circle key={i} x={p.px} y={p.py} radius={px(4)} fill={ACCENT} />;
                  })}
                </Group>
              )}
            </>
          )}
        </MapCanvas>
        {!map?.transform && <p className="mt-2 text-xs text-accent-2">This map has no calibrated image yet, so areas are drawn on a plain grid.</p>}
      </div>

      <aside className="space-y-4 text-sm lg:w-72">
        <select className="input" value={slug} onChange={(e) => pick(e.target.value)} aria-label="Map">
          {maps.map((m) => (
            <option key={m.slug} value={m.slug}>
              {m.name}
            </option>
          ))}
        </select>

        <div className="card space-y-2 p-3">
          <p className="font-medium">{selected !== null ? "Rename area" : "New area"}</p>
          {selected === null && (
            <p className="text-xs text-muted">Click around the place on the map to outline it ({points.length} points, at least 3).</p>
          )}
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Clock Tower" aria-label="Area name" />
          {error && <p className="text-xs text-bad">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" disabled={busy || !name.trim() || (selected === null && points.length < 3)} onClick={save}>
              Save
            </button>
            {selected === null && (
              <button className="btn" disabled={!points.length} onClick={() => setPoints((p) => p.slice(0, -1))}>
                Undo point
              </button>
            )}
            <button
              className="btn"
              disabled={!points.length && selected === null}
              onClick={() => {
                setPoints([]);
                setSelected(null);
                setName("");
              }}
            >
              Cancel
            </button>
          </div>
        </div>

        {suggested.length > 0 && (
          <div>
            <p className="mb-1 text-xs text-accent-2">
              {suggested.length} suggested from guides. Check each one against the map, move it if needed (delete and redraw), then confirm it.
            </p>
            <ul className="space-y-1">
              {suggested.map((a) => (
                <li key={a.id} className={`rounded border border-dashed px-2 py-1 ${a.id === selected ? "border-accent" : "border-accent-2/50"}`}>
                  <div className="flex items-center gap-2">
                    <button
                      className="min-w-0 flex-1 truncate text-left"
                      onClick={() => {
                        setSelected(a.id);
                        setName(a.name);
                        setPoints([]);
                      }}
                    >
                      {a.name}
                    </button>
                    <button className="text-xs text-ok" disabled={busy} onClick={() => confirmArea(a)}>
                      Confirm
                    </button>
                    <button className="text-xs text-bad" disabled={busy} onClick={() => remove(a)}>
                      Delete
                    </button>
                  </div>
                  {a.id === selected && a.note && <p className="mt-1 text-xs text-muted">{a.note}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <p className="mb-2 text-xs text-muted">
            {confirmed.length} named {confirmed.length === 1 ? "area" : "areas"} on {map?.name}
          </p>
          <ul className="space-y-1">
            {confirmed.map((a) => (
              <li key={a.id} className={`flex items-center gap-2 rounded border px-2 py-1 ${a.id === selected ? "border-accent" : "border-line"}`}>
                <button
                  className="min-w-0 flex-1 truncate text-left"
                  onClick={() => {
                    setSelected(a.id);
                    setName(a.name);
                    setPoints([]);
                  }}
                >
                  {a.name}
                </button>
                <button className="text-xs text-bad" disabled={busy} onClick={() => remove(a)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
