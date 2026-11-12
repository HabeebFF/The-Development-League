"use client";

import Link from "next/link";
import { useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import { mapArt } from "@/components/ui/MatchCard";
import Tabs from "@/components/ui/Tabs";
import { mapPeriodLabel, mapStatsPath, type MapLeader, type MapPeriod, type MapStats } from "@/lib/maps";
import { useApi } from "@/lib/useApi";

import KillTable from "./KillTable";
import Loading from "./Loading";
import { TeamMark } from "./TeamBadge";

const PERIODS: { key: MapPeriod; label: string }[] = [
  { key: "all", label: "All time" },
  { key: "month", label: "Month" },
  { key: "week", label: "Week" },
];

/** Top fraggers, best ratings, most damage, best teams and most used weapons on one map. */
export default function MapsView() {
  const [map, setMap] = useState<string | null>(null);
  const [period, setPeriod] = useState<MapPeriod>("all");
  const [at, setAt] = useState<string | null>(null);
  const data = useApi<MapStats>(mapStatsPath(map, period, at));
  const s = data.data;
  const current = map ?? s?.map?.slug ?? null;

  return (
    <>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" role="tablist" aria-label="Maps">
        {(s?.maps ?? []).map((m) => {
          const on = current === m.slug;
          const art = mapArt(m.slug);
          return (
            <button
              key={m.slug}
              role="tab"
              aria-selected={on}
              className={`group relative flex min-h-16 items-end overflow-hidden border px-3 py-2 text-left transition-colors ${
                on ? "border-lion shadow-[0_0_18px_rgb(245_165_36/0.35)]" : "border-line hover:border-lion/60"
              }`}
              style={{ clipPath: "polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))" }}
              onClick={() => setMap(m.slug)}
            >
              {art && (
                <span
                  aria-hidden
                  className={`absolute inset-0 bg-cover bg-center transition-opacity ${on ? "opacity-70" : "opacity-35 group-hover:opacity-55"}`}
                  style={{ backgroundImage: `url(${art})` }}
                />
              )}
              <span aria-hidden className="absolute inset-0 bg-[linear-gradient(180deg,transparent,rgb(7_8_12/0.85))]" />
              <span className="relative flex w-full items-baseline justify-between gap-2">
                <span className={`font-display text-lg leading-none font-black uppercase ${on ? "text-accent-hot" : ""}`}>{m.name}</span>
                <span className="text-xs text-muted tabular-nums">{m.matches}</span>
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Tabs
          label="Period"
          tabs={PERIODS}
          value={period}
          onChange={(k) => {
            setPeriod(k);
            setAt(null);
          }}
        />
        {s && s.period !== "all" && (
          <span className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
            <button className="btn btn-ghost min-w-11 px-3" disabled={!s.previous} onClick={() => setAt(s.previous)} aria-label="Earlier">
              &larr;
            </button>
            <span className="min-w-36 flex-1 truncate text-center font-display text-lg uppercase">{mapPeriodLabel(s)}</span>
            <button className="btn btn-ghost min-w-11 px-3" disabled={!s.next} onClick={() => setAt(s.next)} aria-label="Later">
              &rarr;
            </button>
          </span>
        )}
      </div>

      {!s ? (
        <div className="mt-6">
          <Loading error={data.error} count={8} />
        </div>
      ) : !s.map ? (
        <div className="mt-6">
          <EmptyState title="No maps yet">Map leaders show up after the first match is uploaded.</EmptyState>
        </div>
      ) : (
        <div className="mt-6 space-y-10">
          <section className="card relative overflow-hidden px-5 py-10 sm:py-14">
            {(s.map.image || mapArt(s.map.slug)) && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={s.map.image || mapArt(s.map.slug)!} alt="" className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-45" />
            )}
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,var(--panel)_20%,transparent)]" />
            <div className="relative">
              <p className="eyebrow">{mapPeriodLabel(s)}</p>
              <h2 className="font-display text-6xl leading-none font-black uppercase sm:text-7xl">{s.map.name}</h2>
              <p className="mt-2 text-sm text-muted">
                {s.matches} {s.matches === 1 ? "match" : "matches"} · {s.kills} kills
              </p>
            </div>
          </section>

          {s.matches === 0 ? (
            <EmptyState title={`Nothing on ${s.map.name}`}>No matches on {s.map.name} in this period.</EmptyState>
          ) : (
            <>
              <section>
                <h2 className="section-title">Top fraggers</h2>
                <div className="mt-4">
                  <KillTable list={{ scope: "match", matches: s.matches, kills: s.kills, players: s.fraggers }} />
                </div>
              </section>

              <div className="grid gap-8 lg:grid-cols-2">
                <Leaders title="Best average rating" rows={s.ratings} unit={(v) => v.toFixed(1)} min={s.min_matches} />
                <Leaders title="Most damage per match" rows={s.damage} unit={(v) => v.toLocaleString()} min={s.min_matches} />
              </div>

              <div className="grid gap-8 lg:grid-cols-2">
                <section>
                  <h2 className="section-title">Most used weapons</h2>
                  {s.weapons.length ? (
                    <ul className="card mt-4 space-y-3 p-4">
                      {s.weapons.map((w, i) => (
                        <li key={w.id} className="text-sm">
                          <span className="flex items-baseline justify-between gap-3">
                            <span className="font-semibold">
                              <span className="mr-2 font-display text-lg text-muted">{i + 1}</span>
                              {w.name}
                            </span>
                            <span className="text-xs text-muted">
                              {w.kills} kills · {w.knocks} knocks · {w.share}%
                            </span>
                          </span>
                          <span className="mt-1 block h-1.5 bg-white/5">
                            <span className="block h-full bg-accent" style={{ width: `${Math.max(2, (100 * w.uses) / s.weapons[0].uses)}%` }} />
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-muted">No named weapons yet.</p>
                  )}
                  <p className="mt-2 text-xs text-muted">Kills and knocks on enemies, with weapons staff have named. The share is out of all named kills and knocks on this map.</p>
                </section>

                <section>
                  <h2 className="section-title">Best teams</h2>
                  {s.teams.length ? (
                    <ul className="card mt-4 divide-y divide-line">
                      {s.teams.map((t, i) => (
                        <li key={t.team.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                          <span className={`w-6 font-display text-lg ${i < 3 ? "text-accent-2" : "text-muted"}`}>{i + 1}</span>
                          <TeamMark team={t.team} />
                          <Link href={`/teams/${t.team.slug}`} className="min-w-0 flex-1 truncate font-semibold hover:text-accent">
                            {t.team.name}
                          </Link>
                          <span className="text-right text-xs text-muted">
                            <span className="font-display text-lg text-white">{t.booyahs}</span> Booyah{t.booyahs === 1 ? "" : "s"}
                            <span className="block">
                              avg {t.avg_placement} · {t.matches} played
                            </span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-muted">Not enough matches yet.</p>
                  )}
                </section>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}

function Leaders({ title, rows, unit, min }: { title: string; rows: MapLeader[]; unit: (v: number) => string; min: number }) {
  return (
    <section>
      <h2 className="section-title">{title}</h2>
      {rows.length ? (
        <ol className="card mt-4 divide-y divide-line">
          {rows.slice(0, 5).map((r, i) => (
            <li key={r.player_id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className={`w-6 font-display text-lg ${i < 3 ? "text-accent-2" : "text-muted"}`}>{i + 1}</span>
              {r.team && <TeamMark team={r.team} />}
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{r.player}</span>
                <span className="block text-xs text-muted">{r.matches} matches</span>
              </span>
              <span className="font-display text-2xl">{unit(r.value)}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-muted">Nobody has {min} matches on this map yet.</p>
      )}
      <p className="mt-2 text-xs text-muted">Players with at least {min} matches on this map.</p>
    </section>
  );
}
