"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { blankForm, countryName, formFrom, statusText, type MyNewTeam, type NewTeam as Team } from "@/lib/newTeam";

import { useAuth } from "../Auth";
import NewTeamForm from "./NewTeamForm";

/** A new team in TDL: the "Create your team" form, or the team that's waiting for staff
 * (with Edit and Withdraw). ``compact`` is the short card on My account. */
export default function NewTeam({ compact = false }: { compact?: boolean }) {
  const { refresh } = useAuth();
  const [data, setData] = useState<MyNewTeam | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    api<MyNewTeam>("/me/new-team")
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e instanceof Error ? e.message : "Couldn't load your team."));
    return () => {
      live = false;
    };
  }, [version]);

  if (!data) return error ? <p className="text-sm text-bad">{error}</p> : null;

  async function saved() {
    setEditing(false);
    setVersion((v) => v + 1);
    await refresh(); // the menu's My team follows the new membership
  }

  if (data.team) {
    if (editing) {
      return (
        <div className="card p-4">
          <p className="mb-4 font-display text-xl uppercase">Edit {data.team.name}</p>
          <NewTeamForm limits={data} start={formFrom(data.team)} editing onSaved={saved} onCancel={() => setEditing(false)} />
        </div>
      );
    }
    return <Waiting team={data.team} onEdit={() => setEditing(true)} onWithdrawn={saved} />;
  }

  if (compact) {
    if (!data.can_create) return null;
    return (
      <div className="card p-4 text-sm">
        <p className="font-display text-lg uppercase">New team in TDL?</p>
        <p className="mt-1 text-muted">Managers: create your team with its roster and UIDs, so we recognise your players in every match. Then sign up for scrims.</p>
        <Link href="/create-team" className="btn btn-primary mt-3 px-4 py-1.5 text-xs">
          Create your team
        </Link>
      </div>
    );
  }

  if (data.on_team) {
    return (
      <p className="card p-4 text-sm text-muted">
        You&apos;re already on {data.on_team.name}. Open{" "}
        <Link href="/team" className="text-accent">
          My team
        </Link>
        .
      </p>
    );
  }
  if (!data.can_create) return <p className="card p-4 text-sm text-muted">League staff add teams from Staff &gt; Teams.</p>;
  return (
    <div className="card p-4">
      <NewTeamForm limits={data} start={blankForm(data.min_players)} onSaved={saved} />
    </div>
  );
}

export function Waiting({ team, onEdit, onWithdrawn }: { team: Team; onEdit: () => void; onWithdrawn: () => void }) {
  const [busy, setBusy] = useState(false);
  const [sure, setSure] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const text = statusText(team);

  async function withdraw() {
    setBusy(true);
    setError(null);
    try {
      await api("/me/new-team", { method: "DELETE" });
      onWithdrawn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
      setBusy(false);
    }
  }

  return (
    <div className={`card p-4 text-sm ${team.status === "REJECTED" ? "border-bad/60" : "border-accent/40"}`}>
      <div className="flex flex-wrap items-center gap-3">
        {team.logo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={team.logo} alt="" className="h-12 w-12 rounded object-contain" />
        ) : (
          <span className="grid h-12 w-12 place-items-center rounded bg-panel-2 font-display text-accent">{team.tag}</span>
        )}
        <div className="min-w-0 flex-1">
          <p className="font-display text-2xl leading-none uppercase">{team.name}</p>
          <p className="mt-1 text-xs text-muted">
            {team.tag} · {countryName(team.country)}
            {team.lobby_name ? ` · lobby name ${team.lobby_name}` : ""}
          </p>
        </div>
        <span className={`chip ${team.status === "REJECTED" ? "border-bad/60 text-bad" : ""}`}>{text.title}</span>
      </div>
      <p className="mt-3 text-muted">{text.body}</p>
      <ul className="mt-3 divide-y divide-line rounded border border-line">
        {team.players.map((p) => (
          <li key={p.uid} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
            <span className="min-w-0 flex-1 font-medium">
              {p.name}
              {p.igl && <span className="ml-2 text-xs text-accent">IGL</span>}
            </span>
            <span className="font-mono text-xs text-muted">{p.uid}</span>
            <span className="text-xs text-muted">{p.role.replace("_", "-").toLowerCase()}</span>
            {(p.error || p.flag) && <span className={`w-full text-xs ${p.error ? "text-bad" : "text-accent"}`}>{p.error ?? p.flag}</span>}
          </li>
        ))}
      </ul>
      {error && <p className="mt-2 text-xs text-bad">{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="btn btn-primary px-4 py-1.5 text-xs" onClick={onEdit} disabled={busy}>
          {team.status === "REJECTED" ? "Fix and send again" : "Edit"}
        </button>
        {sure ? (
          <>
            <button type="button" className="btn px-4 py-1.5 text-xs text-bad" onClick={withdraw} disabled={busy}>
              Yes, delete {team.name}
            </button>
            <button type="button" className="btn px-4 py-1.5 text-xs" onClick={() => setSure(false)} disabled={busy}>
              Keep it
            </button>
          </>
        ) : (
          <button type="button" className="btn px-4 py-1.5 text-xs" onClick={() => setSure(true)}>
            Withdraw
          </button>
        )}
      </div>
    </div>
  );
}
