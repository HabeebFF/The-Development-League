"use client";

import { useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import Tabs from "@/components/ui/Tabs";
import { killsLabel, killsPath, type KillList, type KillRow } from "@/lib/kills";
import { useApi } from "@/lib/useApi";

import KillTable from "./KillTable";
import Loading from "./Loading";
import SearchBox from "./SearchBox";
import { TeamMark } from "./TeamBadge";

const PLACE = ["1st", "2nd", "3rd"];
const PLACE_RING = ["border-gold", "border-silver", "border-bronze"];

/** The top three of the list as big broadcast cards. */
function Leaders({ rows }: { rows: KillRow[] }) {
  const top = rows.filter((p) => p.rank <= 3 && p.kills > 0).slice(0, 3);
  if (!top.length) return null;
  return (
    <ol className="stagger grid gap-3 sm:grid-cols-3">
      {top.map((p, i) => (
        <li key={p.player_id} className={`card relative overflow-hidden border-t-4 p-4 ${PLACE_RING[i]}`}>
          <span aria-hidden className="pointer-events-none absolute -top-6 -right-3 font-display text-[120px] leading-none font-black text-white/[0.04]">
            {p.rank}
          </span>
          <span className="relative flex items-center gap-3">
            {p.team && <TeamMark team={p.team} size="md" />}
            <span className="min-w-0 flex-1">
              <span className="block text-[11px] font-bold tracking-[0.18em] text-muted uppercase">{PLACE[i]}</span>
              <span className="block truncate font-display text-xl leading-tight font-extrabold uppercase">{p.player}</span>
              {p.team && <span className="block truncate text-xs text-muted">{p.team.name}</span>}
            </span>
            <span className="text-right">
              <span className="num block text-4xl leading-none text-accent-hot">{p.kills}</span>
              <span className="text-[10px] font-bold tracking-[0.16em] text-muted uppercase">kills</span>
            </span>
          </span>
        </li>
      ))}
    </ol>
  );
}

const SCOPES = [
  { key: "session", label: "Session" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
] as const;

type Scope = (typeof SCOPES)[number]["key"];

/** Kill lists for a session (8PM or 10PM), a week or a month, with arrows to go back. */
export default function KillsView() {
  const [scope, setScope] = useState<Scope>("session");
  const [at, setAt] = useState<number | string | null>(null);
  const [query, setQuery] = useState("");
  const data = useApi<KillList>(killsPath(scope, at));
  const k = data.data;

  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          label="Period"
          tabs={SCOPES.map((s) => ({ key: s.key, label: s.label }))}
          value={scope}
          onChange={(k) => {
            setScope(k);
            setAt(null);
          }}
        />
        {k && (
          <span className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
            <button className="btn btn-ghost min-w-11 px-3" disabled={k.previous == null} onClick={() => setAt(k.previous ?? null)} aria-label="Earlier">
              &larr;
            </button>
            <span className="min-w-36 flex-1 truncate text-center font-display text-xl font-extrabold uppercase">{killsLabel(k)}</span>
            <button className="btn btn-ghost min-w-11 px-3" disabled={k.next == null} onClick={() => setAt(k.next ?? null)} aria-label="Later">
              &rarr;
            </button>
          </span>
        )}
      </div>

      <div className="mt-4">
        <SearchBox value={query} onChange={setQuery} />
      </div>

      {!k ? (
        <div className="mt-6">
          <Loading error={data.error} count={10} />
        </div>
      ) : (
        <div className="mt-6">
          {k.matches === 0 ? (
            <EmptyState title="No kills yet">No matches were played {scope === "session" ? "yet" : `this ${scope}`}.</EmptyState>
          ) : (
            <div className="space-y-6">
              {!query.trim() && <Leaders rows={k.players} />}
              <KillTable list={k} query={query} />
            </div>
          )}
        </div>
      )}
    </>
  );
}
