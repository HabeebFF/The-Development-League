"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { pct, utilityText, versus, type PlayerCard, type PlayerRates, type TeamPlayers } from "@/lib/coach";
import { replayHref } from "@/lib/replay";

type Period = "30" | "all";

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** One card per player: how they play against the league, and one thing to work on. */
export default function PlayerCards({ teamSlug, replayBase }: { teamSlug: string; replayBase: (id: number) => string }) {
  const [period, setPeriod] = useState<Period>("30");
  const [data, setData] = useState<TeamPlayers | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<TeamPlayers>(`/coach/teams/${teamSlug}/players?period=${period}`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load the player cards."));
  }, [teamSlug, period]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1" role="group" aria-label="Period">
          {(
            [
              ["30", "Last 30 days"],
              ["all", "All matches"],
            ] as const
          ).map(([key, label]) => (
            <button key={key} className={`btn text-sm ${period === key ? "btn-primary" : ""}`} onClick={() => setPeriod(key)}>
              {label}
            </button>
          ))}
        </div>
        {data && (
          <p className="text-sm text-muted">
            From {plural(data.matches, "match", "matches")}, compared with every player in the league.
          </p>
        )}
      </div>
      {error && <p className="mt-4 text-bad">{error}</p>}
      {!data && !error && <p className="mt-4 text-muted">Loading...</p>}
      {data && data.pending > 0 && (
        <p className="mt-4 text-sm text-muted">Still adding {data.pending} matches. Open this page again in a minute for the full numbers.</p>
      )}
      {data && data.players.length === 0 && <p className="mt-4 text-muted">No matches in this period yet.</p>}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {data?.players.map((p) => (
          <Card key={p.player ?? p.name} card={p} league={data.league} replayBase={replayBase} teamSlug={teamSlug} />
        ))}
      </div>
    </div>
  );
}

function Card({
  card,
  league,
  replayBase,
  teamSlug,
}: {
  card: PlayerCard;
  league: PlayerRates;
  replayBase: (id: number) => string;
  teamSlug: string;
}) {
  const used = utilityText(card.utility);
  return (
    <section className="card flex flex-col p-4">
      <header>
        <h3 className="font-display text-2xl leading-none uppercase">{card.name}</h3>
        <p className="mt-1 text-sm text-muted">
          {plural(card.matches, "match", "matches")} · {plural(card.kills, "kill", "kills")} ({card.kills_per_match} a match)
          {card.alive_clock ? ` · alive until ${card.alive_clock} on average` : ""}
        </p>
      </header>

      <dl className="mt-4 grid grid-cols-2 gap-2">
        <Stat
          label="Caught alone"
          value={pct(card.rates.alone)}
          detail={`${card.alone_downs} of ${card.known_downs} downs`}
          league={league.alone}
          verdict={versus(card.rates.alone, league.alone, true)}
        />
        <Stat
          label="Trades"
          value={pct(card.rates.trade)}
          detail={`${card.trades} of ${card.trade_chances} chances`}
          league={league.trade}
          verdict={versus(card.rates.trade, league.trade, false)}
        />
        <Stat
          label="First down"
          value={pct(card.rates.first)}
          detail={`${card.first_downs} of ${plural(card.matches, "match", "matches")}`}
          league={league.first}
          verdict={versus(card.rates.first, league.first, true)}
        />
        <Stat
          label="Far from team"
          value={pct(card.rates.far)}
          detail={card.spacing_m != null ? `usually ${card.spacing_m} m away` : "no replay data"}
          league={league.far}
          verdict={versus(card.rates.far, league.far, true)}
        />
      </dl>

      {(card.weapons.length > 0 || used) && (
        <p className="mt-3 text-sm text-muted">
          {card.weapons.length > 0 && <>Kills with {card.weapons.map((w) => `${w.name} (${w.kills})`).join(", ")}</>}
          {card.weapons.length > 0 && used ? " · " : ""}
          {used && <>Used {used}</>}
        </p>
      )}

      {card.strengths.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {card.strengths.map((s) => (
            <li key={s} className="flex gap-2">
              <span className="text-ok">▲</span>
              <span>{s}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 border-t border-line pt-3">
        <p className="eyebrow">Work on</p>
        {card.task ? (
          <>
            <p className="mt-1 font-medium">{card.task.title}</p>
            <p className="mt-1 text-sm text-muted">{card.task.why}</p>
            {card.task.clips.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {card.task.clips.map((c) => (
                  <Link key={`${c.match}-${c.t}`} href={replayHref(replayBase(c.match), c.watch_s, teamSlug)} className="btn text-sm">
                    Watch {c.label} · {c.clock}
                  </Link>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="mt-1 text-sm text-muted">Nothing stands out against the league yet. Cards need at least 3 downs or 4 matches before they point at something.</p>
        )}
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  detail,
  league,
  verdict,
}: {
  label: string;
  value: string;
  detail: string;
  league: number | null;
  verdict: "better" | "worse" | "even" | null;
}) {
  const color = verdict === "better" ? "text-ok" : verdict === "worse" ? "text-bad" : "";
  return (
    <div className="border border-line bg-panel-2 p-2">
      <dt className="text-[11px] font-semibold tracking-wide text-muted uppercase">{label}</dt>
      <dd className={`font-display text-2xl leading-tight ${color}`}>{value}</dd>
      <dd className="text-xs text-muted">
        {detail}
        {league != null ? ` · league ${pct(league)}` : ""}
      </dd>
    </div>
  );
}
