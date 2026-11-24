"use client";

import { useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";
import Tabs from "@/components/ui/Tabs";
import type { MatchDay, Paged } from "@/lib/api";
import { rows, type Standings } from "@/lib/league";
import { dateSpan, dc, naira, VIA_LABEL, type Entry, type Prize, type Tournament } from "@/lib/tournaments";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import MatchDayCard from "./MatchDayCard";
import StandingsTable from "./StandingsTable";
import TeamBadge from "./TeamBadge";
import TournamentRegister from "./TournamentRegister";

type Tab = "table" | "teams" | "prizes" | "matches" | "players";
type Top = {
  kills: { player: string; team: string | null; kills: number }[];
  ratings: { player: string; team: string | null; rating: number; matches: number }[];
};

const STATUS: Record<Tournament["status"], { label: string; cls: string }> = {
  upcoming: { label: "Coming up", cls: "chip chip-gold" },
  live: { label: "● Live", cls: "chip chip-hot" },
  finished: { label: "Finished", cls: "chip" },
  cancelled: { label: "Cancelled", cls: "chip" },
};

/** A tournament: prize pool, its own table, the prizes (winners once paid), matches, top players. */
export default function TournamentView({ slug }: { slug: string }) {
  // Registering changes the places and team lists: fetch again (keeping the page shown).
  const [version, setVersion] = useState(0);
  const t = useApi<Tournament>(`/tournaments/${encodeURIComponent(slug)}${version ? `?v=${version}` : ""}`);
  const [last, setLast] = useState<Tournament | null>(null);
  if (t.data && t.data !== last) setLast(t.data);
  const [tab, setTab] = useState<Tab>("table");
  const d = t.data ?? last;
  if (!d) return <Loading error={t.error} count={6} />;
  const status = STATUS[d.status];
  const left = Math.max(d.planned_matches - d.matches, 0);
  return (
    <>
      <section className="mx-auto max-w-6xl px-4 pt-8">
        <p className="eyebrow">Tournament{d.starts_on ? ` · ${dateSpan(d.starts_on, d.ends_on)}` : ""}</p>
        <h1 className="mt-1 font-display text-5xl leading-[0.95] font-black uppercase sm:text-6xl">
          <span className="text-lion-gradient">{d.name}</span>
        </h1>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className={status.cls}>{status.label}</span>
          {d.teams.length > 0 && <span className="chip">{d.teams.length} teams</span>}
          {d.format_note && <span className="chip">{d.format_note}</span>}
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="card col-span-2 p-4 sm:col-span-1">
            <p className="text-[11px] font-bold tracking-[0.18em] text-muted uppercase">Prize pool</p>
            <p className="num text-lion-gradient text-4xl">{naira(d.total_cash)}</p>
            <p className="text-xs text-muted">Cash, paid by TDL staff</p>
          </div>
          <div className="card p-4">
            <p className="text-[11px] font-bold tracking-[0.18em] text-muted uppercase">Bonus</p>
            <p className="num text-3xl text-accent-2 sm:text-4xl">{dc(d.total_dc)}</p>
            <p className="text-xs text-muted">Paid to players&apos; wallets</p>
          </div>
          <div className="card p-4">
            <p className="text-[11px] font-bold tracking-[0.18em] text-muted uppercase">Matches</p>
            <p className="num text-3xl sm:text-4xl">
              {d.matches} / {d.planned_matches}
            </p>
            <p className="text-xs text-muted">{d.status === "finished" ? "All played" : left ? `${left} to play` : "All uploaded"}</p>
          </div>
        </div>
        {d.registration.state !== "off" && d.status !== "finished" && (
          <div className="mt-5">
            <TournamentRegister
              slug={d.slug}
              name={d.name}
              onChanged={() => setVersion((v) => v + 1)}
            />
          </div>
        )}
        <Tabs
          className="mt-6"
          label="Tournament"
          value={tab}
          onChange={setTab}
          tabs={[
            { key: "table", label: "Standings" },
            { key: "teams", label: "Teams" },
            { key: "prizes", label: "Prizes" },
            { key: "matches", label: "Matches" },
            { key: "players", label: "Top players" },
          ]}
        />
      </section>
      <section className="mx-auto max-w-6xl px-4 py-6">
        {tab === "table" && <Table season={d.season} stages={d.stages} />}
        {tab === "teams" && <Teams t={d} />}
        {tab === "prizes" && <Prizes prizes={d.prizes} confirmed={!!d.confirmed_at} />}
        {tab === "matches" && <Matches season={d.season} />}
        {tab === "players" && <Players slug={d.slug} />}
      </section>
    </>
  );
}

function Table({ season, stages }: { season: string; stages: Tournament["stages"] }) {
  // A tournament with a qualifier has a table per stage; the final's is shown first.
  const [stage, setStage] = useState<number | null>(stages.length > 1 ? stages[stages.length - 1].id : null);
  const table = useApi<Standings>(`/seasons/${encodeURIComponent(season)}/standings${stage ? `?stage=${stage}` : ""}`);
  return (
    <>
      <SectionHeader title="Standings" />
      {stages.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {[...stages].reverse().map((s) => (
            <button key={s.id} type="button" className={`btn px-3 py-1.5 text-sm ${stage === s.id ? "btn-primary" : ""}`} onClick={() => setStage(s.id)}>
              {s.name}
            </button>
          ))}
        </div>
      )}
      {!table.data ? (
        <Loading error={table.error} />
      ) : table.data.rows.length ? (
        <StandingsTable rows={table.data.rows} />
      ) : (
        <EmptyState title="No matches yet">The table fills in as the matches are uploaded.</EmptyState>
      )}
    </>
  );
}

function Teams({ t }: { t: Tournament }) {
  const stages = [...t.stages].reverse();
  if (!t.entries.length) return <EmptyState title="No teams yet">Invited and registered teams show here.</EmptyState>;
  return (
    <div className="grid gap-6 md:grid-cols-2">
      {stages.map((s) => {
        const list = t.entries.filter((e) => e.stage === s.id);
        const inn = list.filter((e) => e.status === "IN");
        const waiting = list.filter((e) => e.status === "WAITLIST");
        return (
          <div key={s.id}>
            <SectionHeader title={`${s.name} (${inn.length})`} as="h3" />
            {inn.length ? <TeamList rows={inn} /> : <p className="text-sm text-muted">No teams yet.</p>}
            {waiting.length > 0 && (
              <>
                <p className="mt-3 text-xs font-bold tracking-[0.14em] text-muted uppercase">Waitlist</p>
                <TeamList rows={waiting} />
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

function TeamList({ rows }: { rows: Entry[] }) {
  return (
    <ol className="card px-3 py-1">
      {rows.map((e) => (
        <li key={e.id} className="flex items-center gap-3 border-t border-line py-2 first:border-0">
          <span className="min-w-0 flex-1">
            <TeamBadge team={e.team} />
          </span>
          <span className={`chip ${e.via === "INVITED" || e.via === "QUALIFIED" ? "chip-gold" : ""}`}>{VIA_LABEL[e.via]}</span>
        </li>
      ))}
    </ol>
  );
}

function Prizes({ prizes, confirmed }: { prizes: Prize[]; confirmed: boolean }) {
  return (
    <>
      <SectionHeader title="Prizes" />
      <div className="card px-3 py-1">
        <table className="table">
          <thead>
            <tr>
              <th className="text-left">Prize</th>
              <th className="text-left">Winner</th>
              <th className="text-right">Cash</th>
              <th className="text-right">DC</th>
            </tr>
          </thead>
          <tbody>
            {prizes.map((p) => (
              <tr key={p.key} className="[&>td]:px-2 [&>td]:py-2.5">
                <td className="font-display font-extrabold tracking-[0.06em] uppercase">{p.label}</td>
                <td className="text-sm">
                  {p.winners.length
                    ? p.winners.map((w, i) => (
                        <span key={i} className="block">
                          {w.team ? w.team.name : w.players.join(", ")}
                        </span>
                      ))
                    : <span className="text-muted">{confirmed ? "–" : "After the final"}</span>}
                </td>
                <td className="num text-right">
                  {p.cash ? naira(p.cash) : <span className="text-muted">–</span>}
                  {p.cash > 0 && p.cash_paid && <span className="chip chip-gold ml-2 align-middle">Paid</span>}
                </td>
                <td className="num text-right text-accent-2">
                  {p.dc ? `${p.dc.toLocaleString("en-GB")}${p.each ? " each" : ""}` : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-sm text-muted">
        A team&apos;s DC is shared equally by the players who played for it in the tournament. DC is play money for predictions and the
        shops, never cash. Cash prizes are paid by TDL staff.
      </p>
    </>
  );
}

function Matches({ season }: { season: string }) {
  const days = useApi<Paged<MatchDay>>(`/seasons/${encodeURIComponent(season)}/fixtures?page_size=50`);
  if (!days.data) return <Loading error={days.error} />;
  const list = rows(days.data);
  if (!list.length) return <EmptyState title="No matches yet">Results and replays show here after each night.</EmptyState>;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {list.map((d) => (
        <MatchDayCard key={d.id} day={d} link={false} />
      ))}
    </div>
  );
}

function Players({ slug }: { slug: string }) {
  const top = useApi<Top>(`/tournaments/${encodeURIComponent(slug)}/players`);
  if (!top.data) return <Loading error={top.error} />;
  if (!top.data.kills.length) return <EmptyState title="No matches yet" />;
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <SectionHeader title="Most kills" as="h3" />
        <ol className="card px-3 py-1">
          {top.data.kills.map((p, i) => (
            <li key={`${p.player}-${i}`} className="flex items-center gap-3 border-t border-line py-2 first:border-0">
              <span className="num w-6 text-muted">{i + 1}</span>
              <span className="min-w-0 flex-1 truncate">
                {p.player} {p.team && <span className="text-xs text-muted">· {p.team}</span>}
              </span>
              <span className="num text-xl">{p.kills}</span>
            </li>
          ))}
        </ol>
      </div>
      <div>
        <SectionHeader title="Best rating" as="h3" />
        <ol className="card px-3 py-1">
          {top.data.ratings.map((p, i) => (
            <li key={`${p.player}-${i}`} className="flex items-center gap-3 border-t border-line py-2 first:border-0">
              <span className="num w-6 text-muted">{i + 1}</span>
              <span className="min-w-0 flex-1 truncate">
                {p.player} <span className="text-xs text-muted">· {p.matches} matches</span>
              </span>
              <span className="num text-xl">{p.rating.toFixed(1)}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
