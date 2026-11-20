"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { countryName, type NewTeam } from "@/lib/newTeam";

type List = { waiting: NewTeam[]; recent: NewTeam[] };

/** Staff > Teams: teams that created themselves, waiting for approval. Approving puts their
 * roster UIDs on the team (so uploads find them) and lets them sign up for scrims. */
export default function NewTeams({ onApproved }: { onApproved?: () => void }) {
  const [list, setList] = useState<List | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    api<List>("/admin/new-teams")
      .then((d) => live && setList(d))
      .catch(() => live && setList({ waiting: [], recent: [] }));
    return () => {
      live = false;
    };
  }, [version]);

  if (!list || (list.waiting.length === 0 && list.recent.length === 0)) return null;
  return (
    <div className="space-y-3">
      <h2 className="font-display text-2xl uppercase">
        New teams{" "}
        {list.waiting.length > 0 && <span className="chip ml-1 border-accent/60 align-middle text-accent">{list.waiting.length} waiting</span>}
      </h2>
      {list.waiting.length === 0 && <p className="text-sm text-muted">No new team is waiting.</p>}
      {list.waiting.map((team) => (
        <Review
          key={team.slug}
          team={team}
          onDone={(approved) => {
            setVersion((v) => v + 1);
            if (approved) onApproved?.();
          }}
        />
      ))}
      {list.recent.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted">Reviewed in the last 30 days ({list.recent.length})</summary>
          <ul className="mt-2 space-y-1">
            {list.recent.map((t) => (
              <li key={t.slug} className="text-muted">
                <span className="text-text">{t.name}</span> · {t.status === "APPROVED" ? "approved" : `rejected: ${t.review_note}`}
                {t.reviewed_by ? ` by ${t.reviewed_by}` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Review({ team, onDone }: { team: NewTeam; onDone: (approved: boolean) => void }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const flagged = team.players.filter((p) => p.error || p.flag).length;

  async function act(how: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await api(`/admin/new-teams/${team.slug}/${how}`, { method: "POST", body: how === "reject" ? { reason } : {} });
      onDone(how === "approve");
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
      setBusy(false);
    }
  }

  return (
    <div className="card border-accent/40 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        {team.logo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={team.logo} alt="" className="h-12 w-12 rounded object-contain" />
        ) : (
          <span className="grid h-12 w-12 place-items-center rounded bg-panel-2 font-display text-accent">{team.tag}</span>
        )}
        <div className="min-w-0 flex-1">
          <p className="font-display text-xl leading-none uppercase">{team.name}</p>
          <p className="mt-1 text-xs text-muted">
            {team.tag} · {countryName(team.country)}
            {team.lobby_name ? ` · lobby name ${team.lobby_name}` : ""} · asked {new Date(team.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
          </p>
        </div>
        {flagged > 0 && <span className="chip border-accent/60 text-accent">{flagged} to check</span>}
      </div>
      <p className="mt-3">
        <span className="text-muted">Manager:</span> {team.manager ? `${team.manager.name || team.manager.email} (${team.manager.email})` : "none"}
        <br />
        <span className="text-muted">Contact:</span> <span className="select-all">{team.contact}</span>
      </p>
      <ul className="mt-3 divide-y divide-line rounded border border-line">
        {team.players.map((p) => (
          <li key={p.uid} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
            <span className="min-w-0 flex-1 font-medium">
              {p.name}
              {p.igl && <span className="ml-2 text-xs text-accent">IGL</span>}
            </span>
            <span className="font-mono text-xs text-muted">{p.uid}</span>
            <span className="text-xs text-muted">{p.role.replace("_", "-").toLowerCase()}</span>
            <span className={`w-full text-xs ${p.error ? "text-bad" : p.flag ? "text-accent" : p.known ? "text-ok" : "text-muted"}`}>
              {p.error ?? p.flag ?? (p.known ? `Known: ${p.known.name}${p.known.last ? `, last played for ${p.known.last.team.name}` : ""}` : "New UID, never played in TDL")}
            </span>
          </li>
        ))}
      </ul>
      {error && <p className="mt-2 text-xs text-bad">{error}</p>}
      {rejecting ? (
        <div className="mt-3 space-y-2">
          <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} placeholder="Why? The manager sees this" className="input" autoFocus />
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn px-4 py-1.5 text-xs text-bad" disabled={busy || !reason.trim()} onClick={() => act("reject")}>
              Reject {team.name}
            </button>
            <button type="button" className="btn px-4 py-1.5 text-xs" disabled={busy} onClick={() => setRejecting(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" className="btn btn-primary px-4 py-1.5 text-xs" disabled={busy} onClick={() => act("approve")}>
            Approve
          </button>
          <button type="button" className="btn px-4 py-1.5 text-xs" disabled={busy} onClick={() => setRejecting(true)}>
            Reject
          </button>
        </div>
      )}
      <p className="mt-2 text-xs text-muted">Approving makes it a league team, puts these UIDs on its roster (moving anyone on another roster) and opens scrim sign-up.</p>
    </div>
  );
}
