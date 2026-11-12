"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import Tabs from "@/components/ui/Tabs";
import { AWARD_ICON } from "@/components/ui/TrophyCard";
import { headline, periodLabel, unit, type Award, type Awards } from "@/lib/awards";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import { TeamMark } from "./TeamBadge";

/** Team awards (team of the period, top kill team, best IGL) and player awards (MVP, top player,
 * rusher, sniper, grenader) of a week or a month, with a picker to go back. */
export default function AwardsView() {
  const [period, setPeriod] = useState<"week" | "month">("week");
  const [date, setDate] = useState<string | null>(null);
  // A link from a team's "Awards won" opens that week or month (?period=&date=).
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const d = q.get("date");
    /* eslint-disable react-hooks/set-state-in-effect -- read once from the URL on first load */
    if (q.get("period") === "month") setPeriod("month");
    if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) setDate(d);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);
  const data = useApi<Awards>(`/awards?period=${period}${date ? `&date=${date}` : ""}`);

  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          label="Period"
          tabs={[
            { key: "week", label: "Week" },
            { key: "month", label: "Month" },
          ]}
          value={period}
          onChange={(p) => {
            setPeriod(p);
            setDate(null);
          }}
        />
        {data.data && (
          <span className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
            <button className="btn btn-ghost min-w-11 px-3" onClick={() => setDate(data.data!.previous)} aria-label="Earlier">
              &larr;
            </button>
            <span className="min-w-36 flex-1 truncate text-center font-display text-xl font-extrabold uppercase">{periodLabel(data.data)}</span>
            <button className="btn btn-ghost min-w-11 px-3" disabled={!data.data.next} onClick={() => setDate(data.data!.next)} aria-label="Later">
              &rarr;
            </button>
          </span>
        )}
      </div>

      {!data.data ? (
        <div className="mt-6">
          <Loading error={data.error} count={4} />
        </div>
      ) : (
        <>
          <p className="mt-3 text-sm text-muted">
            {data.data.matches === 0
              ? `No matches were played this ${period}.`
              : `From ${data.data.matches} match${data.data.matches === 1 ? "" : "es"} this ${period}.`}
          </p>
          <h2 className="section-title mt-8">Trophy case</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <AwardCard award={data.data.mvp} />
            </div>
            {data.data.awards.map((a) => (
              <AwardCard key={a.key} award={a} />
            ))}
          </div>
          <h2 className="section-title mt-12">Team awards</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.data.team_awards.map((a) => (
              <AwardCard key={a.key} award={a} />
            ))}
          </div>
          {data.data.unidentified_kills > 0 && (
            <p className="mt-4 text-xs text-muted">
              {data.data.unidentified_kills} of {data.data.kills} kills this {period} were with weapons that aren&apos;t named yet, so they can&apos;t
              count towards Top sniper or Top grenader.
            </p>
          )}
        </>
      )}
    </>
  );
}

/** One award: the winner big, runners-up below, and how it's decided. */
export function AwardCard({ award, compact = false }: { award: Award; compact?: boolean }) {
  const [winner, ...rest] = award.top;
  const isTeam = winner ? winner.player === null : false;
  return (
    <div className={`card relative overflow-hidden border-t-4 p-4 sm:p-5 ${winner ? "border-lion" : "border-line"}`}>
      <span className="pointer-events-none absolute inset-0 bg-[radial-gradient(80%_60%_at_100%_0%,rgb(245_165_36/0.16),transparent_70%)]" />
      <div className="relative flex items-start justify-between gap-3">
        <p className="eyebrow">{award.title}</p>
        <span
          className="flex h-11 w-11 shrink-0 items-center justify-center bg-accent/[0.12] text-accent"
          style={{ clipPath: "polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%)" }}
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden>
            <path d={AWARD_ICON[award.key] ?? AWARD_ICON.player} />
          </svg>
        </span>
      </div>
      {award.blocked ? (
        <p className="relative mt-3 text-sm text-muted">{award.blocked}</p>
      ) : !winner ? (
        <p className="relative mt-3 text-sm text-muted">
          {award.key === "igl" && award.teams_with_igl ? "No IGL has played this period yet." : "No one yet."}
        </p>
      ) : (
        <div className="relative mt-3 flex items-center gap-3">
          <TeamMark
            team={{
              id: 0,
              name: winner.team ?? "",
              tag: winner.team_tag,
              slug: winner.team_slug ?? "",
              logo: winner.logo,
              primary_color: winner.team_color,
            }}
            size={compact ? "md" : "lg"}
          />
          <div className="min-w-0 flex-1">
            <p className={`truncate font-display font-black uppercase ${compact ? "text-xl" : "text-3xl"}`}>{winner.player ?? winner.team}</p>
            {winner.team_slug ? (
              <Link href={`/teams/${winner.team_slug}`} className="block truncate text-sm text-muted hover:text-accent">
                {isTeam ? "Team page" : winner.team}
              </Link>
            ) : (
              <p className="text-sm text-muted">{winner.team}</p>
            )}
          </div>
          <div className="text-right">
            <p className={`num leading-none text-accent-hot ${compact ? "text-3xl" : "text-5xl"}`}>{headline(award.key, winner.value)}</p>
            <p className="text-[10px] font-bold tracking-widest text-muted uppercase">{unit(award.key, winner.value)}</p>
          </div>
        </div>
      )}
      {winner && !compact && (
        <>
          <p className="relative mt-2 text-sm">{winner.detail}</p>
          {/* A whole week of a team's matches is too many links to be useful. */}
          {winner.matches.length <= 12 && (
            <p className="relative mt-2 flex flex-wrap gap-1">
              {winner.matches.map((id, i) => (
                <Link
                  key={id}
                  href={`/matches/${id}`}
                  className="chip transition-colors hover:border-accent hover:text-text"
                >
                  Match {i + 1}
                </Link>
              ))}
            </p>
          )}
          {rest.length > 0 && (
            <ol start={2} className="relative mt-4 space-y-1 border-t border-line pt-3 text-sm">
              {rest.map((p, i) => (
                <li key={p.player ?? p.team ?? i} className="flex gap-2">
                  <span className="w-4 text-muted">{i + 2}</span>
                  <span className="min-w-0 flex-1 truncate">
                    {p.player ?? p.team}
                    {p.player && p.team ? <span className="text-muted"> · {p.team}</span> : null}
                  </span>
                  <span className="font-semibold">{headline(award.key, p.value)}</span>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
      {!compact && <p className="relative mt-3 text-xs text-muted">{award.rule}</p>}
      {!compact && award.key === "igl" && award.teams_with_igl ? (
        <p className="relative mt-1 text-xs text-muted">
          {award.teams_with_igl} {award.teams_with_igl === 1 ? "team has" : "teams have"} an IGL marked. Team managers pick theirs in the Team area.
        </p>
      ) : null}
    </div>
  );
}
