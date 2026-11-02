"use client";

import Link from "next/link";

import { BLANK_PHOTO } from "@/lib/cards";
import type { MatchMvp as Mvp } from "@/lib/mvp";
import { useApi } from "@/lib/useApi";

function Num({ label, value }: { label: string; value: string | number }) {
  return (
    <span>
      <span className="block font-display text-2xl leading-none text-white sm:text-3xl">{value}</span>
      <span className="block text-[9px] font-bold tracking-widest text-muted uppercase">{label}</span>
    </span>
  );
}

/** The match MVP: best match rating, their numbers, weapons and abilities seen in the replay. */
export default function MatchMvp({ id }: { id: number }) {
  const data = useApi<{ mvp: Mvp | null }>(`/matches/${id}/mvp`);
  const m = data.data?.mvp;
  if (!m) return null;
  const colour = m.team.primary_color || "#ff5a1f";
  return (
    <section className="card relative mt-6 overflow-hidden">
      <div className="pointer-events-none absolute inset-0" style={{ background: `linear-gradient(115deg, ${colour}55, transparent 60%)` }} />
      <div className="relative flex flex-col gap-5 p-5 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4">
          <span className="relative h-24 w-24 shrink-0 overflow-hidden sm:h-28 sm:w-28" style={{ background: `linear-gradient(135deg, ${colour}, #181b26)`, clipPath: "polygon(0 0, 100% 0, 100% 80%, 80% 100%, 0 100%)" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={m.photo || BLANK_PHOTO} alt="" className="h-full w-full object-cover object-top" />
          </span>
          <div className="min-w-0">
            <p className="eyebrow text-accent-2">Match MVP</p>
            <Link href={`/cards/${m.player_id}`} className="block truncate font-display text-3xl leading-tight uppercase hover:text-accent sm:text-4xl">
              {m.name}
            </Link>
            <Link href={`/teams/${m.team.slug}`} className="text-sm text-muted hover:text-accent">
              {m.team.name}
            </Link>
          </div>
        </div>
        <div className="grid flex-1 grid-cols-5 gap-2 text-center sm:ml-auto sm:max-w-md">
          <Num label="Rating" value={m.rating == null ? "–" : m.rating.toFixed(1)} />
          <Num label="Kills" value={m.kills} />
          <Num label="Knocks" value={m.knocks ?? "–"} />
          <Num label="HS%" value={m.hs_pct == null ? "–" : `${m.hs_pct}%`} />
          <Num label="Damage" value={m.damage == null ? "–" : m.damage.toLocaleString()} />
        </div>
      </div>
      <div className="relative grid gap-4 border-t border-line p-5 sm:grid-cols-2">
        <div>
          <p className="text-[10px] font-bold tracking-widest text-muted uppercase">Weapons used</p>
          {m.weapons.length ? (
            <ul className="mt-2 flex flex-wrap gap-2">
              {m.weapons.map((w) => (
                <li key={w.id} className="chip">
                  <span className="font-semibold text-white">{w.name}</span>
                  <span className="ml-1.5 text-muted">
                    {w.kills}K · {w.knocks}N
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">No named weapons in this match.</p>
          )}
        </div>
        <div>
          <p className="text-[10px] font-bold tracking-widest text-muted uppercase">Skills seen in the replay</p>
          {m.skills.length ? (
            <ul className="mt-2 flex flex-wrap gap-2">
              {m.skills.map((s) => (
                <li key={s.kind} className="chip">
                  <span className="font-semibold text-white">{s.label}</span>
                  {s.count > 1 && <span className="ml-1.5 text-muted">×{s.count}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">None seen.</p>
          )}
        </div>
      </div>
      <p className="relative px-5 pb-4 text-xs text-muted">
        MVP is the best match rating. K = kills, N = knocks. The logs don&apos;t list equipped character skills; only Bolt Maker,
        Dinoculars and UAVs show up in the replay file.
      </p>
    </section>
  );
}
