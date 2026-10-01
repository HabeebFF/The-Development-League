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

import Loading from "./Loading";
import TeamBadge from "./TeamBadge";

const RECENT = 5;

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-3 py-2">
      <p className="text-xs text-muted uppercase">{label}</p>
      <p className="font-display text-2xl">{value}</p>
    </div>
  );
}

/** One recent match, with this team's own placement, kills and points. */
function RecentMatch({ match, teamId }: { match: MatchListItem; teamId: number }) {
  const detail = useApi<MatchDetail>(`/matches/${match.id}`);
  const own = detail.data?.results.find((r) => r.team.id === teamId);
  return (
    <li>
      <Link href={`/matches/${match.id}`} className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-panel-2">
        <span className={`w-16 shrink-0 font-display text-lg ${own?.booyah ? "text-accent-2" : "text-muted"}`}>
          {own ? (own.booyah ? "Booyah" : ordinal(own.placement)) : "..."}
        </span>
        <span className="min-w-0 flex-1 truncate">
          Match {match.number} · {mapName(match.map)}
          <span className="block text-xs text-muted">{shortDate(match.started_at)}</span>
        </span>
        {own && (
          <span className="text-right text-xs text-muted">
            {plural(own.kills, "kill")}
            <span className="block font-bold text-text">{own.total_points} pts</span>
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

  if (!team.data) return <Loading error={team.error} />;
  const t = team.data;
  const record = table.data?.rows.find((r) => r.team.id === t.id);
  const recent = matches.data ? rows(matches.data) : [];
  const socials = Object.entries(t.socials ?? {}).filter(([, url]) => /^https?:\/\//.test(url));

  return (
    <>
      <Link href="/teams" className="text-sm text-muted hover:text-text">
        &larr; Teams
      </Link>
      <div className="mt-3 flex items-center gap-4">
        <TeamBadge team={t} size="lg" />
        <div className="min-w-0">
          <h1 className="font-display text-4xl leading-tight uppercase">{t.name}</h1>
          <p className="text-sm text-muted">
            {t.tag}
            {socials.map(([name, url]) => (
              <a key={name} href={url} target="_blank" rel="noreferrer" className="ml-3 text-accent capitalize">
                {name}
              </a>
            ))}
          </p>
        </div>
      </div>

      {season && (
        <>
          <h2 className="mt-8 font-display text-2xl uppercase">{season.name}</h2>
          {record ? (
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
              <Stat label="Rank" value={ordinal(record.rank)} />
              <Stat label="Points" value={record.total_points} />
              <Stat label="Booyahs" value={record.booyahs} />
              <Stat label="Kills" value={record.kills} />
              <Stat label="Matches" value={record.matches_played} />
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted">{table.loading ? "Loading..." : "No matches this season yet."}</p>
          )}
        </>
      )}

      <div className="mt-8 grid gap-8 md:grid-cols-2 [&>*]:min-w-0">
        <div>
          <h2 className="font-display text-2xl uppercase">Recent matches</h2>
          {recent.length ? (
            <ul className="mt-3 divide-y divide-line rounded-lg border border-line bg-panel">
              {recent.map((m) => (
                <RecentMatch key={m.id} match={m} teamId={t.id} />
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">{matches.loading ? "Loading..." : "No matches yet."}</p>
          )}
        </div>
        <div>
          <h2 className="font-display text-2xl uppercase">Roster</h2>
          {t.roster.length ? (
            <ul className="mt-3 divide-y divide-line rounded-lg border border-line bg-panel">
              {t.roster.map((r) => (
                <li key={r.player.id} className="flex items-center gap-2 px-4 py-2.5 text-sm">
                  <span className="flex-1 truncate">{r.player.display_name || r.player.game_uid}</span>
                  {r.role && <span className="text-xs text-muted uppercase">{r.role}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">No roster yet.</p>
          )}
        </div>
      </div>
    </>
  );
}
