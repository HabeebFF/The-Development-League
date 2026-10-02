"use client";

import Link from "next/link";

import type { Paged } from "@/lib/api";
import {
  currentSeason,
  mapName,
  ordinal,
  plural,
  rows,
  shortDate,
  type MatchDetail,
  type MatchListItem,
  type Season,
  type Standings,
  type TeamDetail,
} from "@/lib/league";
import { useApi } from "@/lib/useApi";

import Loading, { Skeleton } from "./Loading";
import { Form } from "./StandingsTable";
import { TeamMark } from "./TeamBadge";

const RECENT = 5;

function Stat({ label, value, hot = false }: { label: string; value: string | number; hot?: boolean }) {
  return (
    <div className="card px-4 py-3">
      <p className="text-[10px] font-bold tracking-widest text-muted uppercase">{label}</p>
      <p className={`font-display text-3xl leading-tight ${hot ? "text-accent-2" : "text-white"}`}>{value}</p>
    </div>
  );
}

/** One recent match, with this team's own placement, kills and points. */
function RecentMatch({ match, teamId }: { match: MatchListItem; teamId: number }) {
  const detail = useApi<MatchDetail>(`/matches/${match.id}`);
  const own = detail.data?.results.find((r) => r.team.id === teamId);
  return (
    <li>
      <Link href={`/matches/${match.id}`} className="flex items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-white/[0.03]">
        <span className={`w-16 shrink-0 font-display text-xl uppercase ${own?.booyah ? "text-accent-2" : "text-muted"}`}>
          {own ? (own.booyah ? "Booyah" : ordinal(own.placement)) : "..."}
        </span>
        <span className="min-w-0 flex-1 truncate">
          Match {match.number} · {mapName(match.map)}
          <span className="block text-xs text-muted">{shortDate(match.started_at)}</span>
        </span>
        {own && (
          <span className="text-right text-xs text-muted">
            {plural(own.kills, "kill")}
            <span className="block font-display text-lg text-white">{own.total_points} pts</span>
          </span>
        )}
      </Link>
    </li>
  );
}

/** A team's page: roster, this season's record and recent matches. */
export default function TeamView({ slug }: { slug: string }) {
  const enc = encodeURIComponent(slug);
  const team = useApi<TeamDetail>(`/teams/${enc}`);
  const seasons = useApi<Paged<Season>>("/seasons?page_size=100");
  const season = seasons.data ? currentSeason(rows(seasons.data)) : null;
  const sEnc = season ? encodeURIComponent(season.slug) : null;
  const table = useApi<Standings>(sEnc && `/seasons/${sEnc}/standings`);
  const matches = useApi<Paged<MatchListItem>>(sEnc && `/matches?season=${sEnc}&team=${enc}&page_size=${RECENT}`);

  if (!team.data)
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        {team.error ? <Loading error={team.error} /> : <Skeleton className="h-48" />}
      </div>
    );
  const t = team.data;
  const record = table.data?.rows.find((r) => r.team.id === t.id);
  const recent = matches.data ? rows(matches.data) : [];
  const socials = Object.entries(t.socials ?? {}).filter(([, url]) => /^https?:\/\//.test(url));
  const colour = t.primary_color || "#ff5a1f";

  return (
    <>
      <section className="relative overflow-hidden border-b border-line">
        <div className="pointer-events-none absolute inset-0" style={{ background: `linear-gradient(115deg, ${colour}66, ${colour}1a 45%, transparent 75%)` }} />
        <div className="pointer-events-none absolute -right-16 top-0 h-full w-1/2 -skew-x-[20deg] bg-[repeating-linear-gradient(90deg,rgb(255_255_255/0.04)_0_2px,transparent_2px_16px)]" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1" style={{ background: colour, boxShadow: `0 0 24px ${colour}` }} />
        <div className="relative mx-auto max-w-6xl px-4 py-8 sm:py-12">
          <Link href="/teams" className="text-xs font-bold tracking-widest text-white/70 uppercase hover:text-white">
            &larr; Teams
          </Link>
          <div className="mt-4 flex items-center gap-4 sm:gap-6">
            <TeamMark team={t} size="xl" />
            <div className="min-w-0">
              {t.tag && <p className="eyebrow text-white/80">{t.tag}</p>}
              <h1 className="font-display text-4xl leading-none font-extrabold break-words uppercase sm:text-6xl">{t.name}</h1>
              {record?.form.length ? (
                <div className="mt-3 flex items-center gap-2">
                  <span className="text-[10px] font-bold tracking-widest text-white/70 uppercase">Form</span>
                  <Form placements={record.form} className="" />
                </div>
              ) : null}
              {socials.length > 0 && (
                <p className="mt-3 flex flex-wrap gap-2">
                  {socials.map(([name, url]) => (
                    <a key={name} href={url} target="_blank" rel="noreferrer" className="chip capitalize hover:border-accent hover:text-accent">
                      {name}
                    </a>
                  ))}
                </p>
              )}
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl space-y-10 px-4 py-8">
        {season && (
          <section>
            <h2 className="section-title">{season.name}</h2>
            {record ? (
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
                <Stat label="Rank" value={ordinal(record.rank)} />
                <Stat label="Points" value={record.total_points} />
                <Stat label="Booyahs" value={record.booyahs} hot={record.booyahs > 0} />
                <Stat label="Kills" value={record.kills} />
                <Stat label="Matches" value={record.matches_played} />
              </div>
            ) : table.loading ? (
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
                {Array.from({ length: 5 }, (_, i) => (
                  <Skeleton key={i} className="h-20" />
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted">No matches this season yet.</p>
            )}
          </section>
        )}

        <section>
          <h2 className="section-title">Roster</h2>
          {t.roster.length ? (
            <ul className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
              {t.roster.map((r) => (
                <li key={r.player.id} className="card card-hover overflow-hidden p-4">
                  <span className="pointer-events-none absolute inset-x-0 top-0 h-1" style={{ background: colour }} />
                  <span
                    className="flex h-12 w-12 items-center justify-center font-display text-xl text-white"
                    style={{ background: `linear-gradient(135deg, ${colour}, #181b26)`, clipPath: "polygon(0 0, 100% 0, 100% 75%, 75% 100%, 0 100%)" }}
                    aria-hidden
                  >
                    {(r.player.display_name || r.player.game_uid).slice(0, 1).toUpperCase()}
                  </span>
                  <p className="mt-3 truncate font-display text-xl leading-tight uppercase">{r.player.display_name || r.player.game_uid}</p>
                  <p className="text-[11px] font-semibold tracking-widest text-muted uppercase">{r.role || "Player"}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">No roster yet.</p>
          )}
        </section>

        <section>
          <h2 className="section-title">Recent matches</h2>
          {recent.length ? (
            <ul className="card mt-4 divide-y divide-line">
              {recent.map((m) => (
                <RecentMatch key={m.id} match={m} teamId={t.id} />
              ))}
            </ul>
          ) : matches.loading ? (
            <div className="mt-4">
              <Loading count={RECENT} />
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted">No matches yet.</p>
          )}
        </section>
      </div>
    </>
  );
}
