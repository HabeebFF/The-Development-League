"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type Paged } from "@/lib/api";

type Season = { id: number; name: string; slug: string; starts_on: string | null; ends_on: string | null; is_active: boolean };
type Stage = { id: number; season: string; name: string; order: number; kind: string };
type Day = { id: number; stage: number; group: number | null; number: number; date: string | null; title: string };
type Data = { seasons: Season[]; stages: Stage[]; days: Day[] };

function message(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

const all = <T,>(page: Paged<T>) => page.results;

/**
 * Seasons, their stages and match days. The current season is the one the public pages
 * show. Match days can move to another stage or season (uploads put them where staff
 * picked at the time, e.g. a test season).
 */
export default function SeasonSetup() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const [seasons, stages, days] = await Promise.all([
          api<Paged<Season>>("/admin/seasons?page_size=100").then(all),
          api<Paged<Stage>>("/admin/stages?page_size=100").then(all),
          api<Paged<Day>>("/admin/match-days?page_size=100").then(all),
        ]);
        if (live) setData({ seasons, stages, days });
      } catch (e) {
        if (live) setError(message(e));
      }
    })();
    return () => {
      live = false;
    };
  }, [version]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setVersion((v) => v + 1);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  function addSeason(form: FormData) {
    const name = String(form.get("name") ?? "").trim();
    if (!name) return;
    run(async () => {
      const season = await api<Season>("/admin/seasons", {
        method: "POST",
        body: { name, is_active: form.get("current") === "on" },
      });
      await api("/admin/stages", { method: "POST", body: { season: season.slug, name: "League" } });
    });
  }

  if (!data) return error ? <p className="text-bad">{error}</p> : <p className="text-muted">Loading...</p>;

  const seasonName = Object.fromEntries(data.seasons.map((s) => [s.slug, s.name]));
  const stageLabel = (st: Stage) => `${seasonName[st.season] ?? st.season} · ${st.name}`;

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-bad">{error}</p>}

      {data.seasons.map((season) => {
        const stages = data.stages.filter((st) => st.season === season.slug).sort((a, b) => a.order - b.order);
        return (
          <div key={season.id} className="card">
            <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
              <form
                action={(form) =>
                  run(() =>
                    api(`/admin/seasons/${season.slug}`, { method: "PATCH", body: { name: String(form.get("name")).trim() } }),
                  )
                }
                className="flex min-w-0 flex-1 gap-2"
              >
                <input name="name" defaultValue={season.name} required className="input min-w-0 flex-1 font-medium" />
                <button type="submit" disabled={busy} className="btn px-2 py-1 text-xs">
                  Rename
                </button>
              </form>
              {season.is_active ? (
                <span className="bg-accent px-2 py-1 text-xs font-semibold text-white">Current season</span>
              ) : (
                <button
                  className="btn px-2 py-1 text-xs"
                  disabled={busy}
                  onClick={() => run(() => api(`/admin/seasons/${season.slug}`, { method: "PATCH", body: { is_active: true } }))}
                >
                  Make current
                </button>
              )}
            </div>

            <div className="space-y-4 p-4">
              {stages.map((stage) => {
                const days = data.days.filter((d) => d.stage === stage.id).sort((a, b) => a.number - b.number);
                return (
                  <div key={stage.id}>
                    <form
                      action={(form) =>
                        run(() =>
                          api(`/admin/stages/${stage.id}`, { method: "PATCH", body: { name: String(form.get("name")).trim() } }),
                        )
                      }
                      className="flex gap-2"
                    >
                      <input name="name" defaultValue={stage.name} required className="input flex-1 text-sm" />
                      <button type="submit" disabled={busy} className="btn px-2 py-1 text-xs">
                        Rename stage
                      </button>
                    </form>
                    {days.length === 0 && <p className="mt-2 text-xs text-muted">No match days.</p>}
                    <ul className="mt-2 divide-y divide-line border border-line">
                      {days.map((day) => (
                        <li key={day.id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                          <span className="min-w-0 flex-1 truncate">
                            {day.title || `Day ${day.number}`}
                            {day.date ? <span className="text-xs text-muted"> · {day.date}</span> : null}
                          </span>
                          <select
                            className="input text-xs sm:w-64"
                            value=""
                            disabled={busy}
                            onChange={(e) => {
                              const to = Number(e.target.value);
                              if (to) run(() => api(`/admin/match-days/${day.id}`, { method: "PATCH", body: { stage: to, group: null } }));
                            }}
                          >
                            <option value="">Move to...</option>
                            {data.stages
                              .filter((st) => st.id !== stage.id)
                              .map((st) => (
                                <option key={st.id} value={st.id}>
                                  {stageLabel(st)}
                                </option>
                              ))}
                          </select>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
              <form
                action={(form) => {
                  const name = String(form.get("name") ?? "").trim();
                  if (name)
                    run(() =>
                      api("/admin/stages", { method: "POST", body: { season: season.slug, name, order: stages.length + 1 } }),
                    );
                }}
                className="flex gap-2"
              >
                <input name="name" placeholder="New stage, e.g. Finals" className="input flex-1 text-sm" />
                <button type="submit" disabled={busy} className="btn px-2 py-1 text-xs">
                  Add stage
                </button>
              </form>
            </div>
          </div>
        );
      })}

      <form action={addSeason} className="border border-dashed border-line p-4">
        <p className="font-medium">New season</p>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <input name="name" placeholder="e.g. TDL Season 1" required className="input flex-1" />
          <button type="submit" disabled={busy} className="btn btn-primary">
            Create
          </button>
        </div>
        <label className="mt-2 flex items-center gap-2 text-sm">
          <input name="current" type="checkbox" defaultChecked /> Make it the current season
        </label>
      </form>
    </div>
  );
}
