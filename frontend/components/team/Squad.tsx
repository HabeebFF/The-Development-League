"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { cleanUid, type Squad as SquadData } from "@/lib/newTeam";

const ROLES: [string, string][] = [
  ["RUSHER", "Rusher"],
  ["SNIPER", "Sniper"],
  ["GRENADER", "Grenader"],
  ["ALL_ROUNDER", "All-rounder"],
];

/** The team's roster this season, by UID: uploads put these players on this team. Managers
 * (and staff) add and remove players; everyone on the team can see it. */
export default function Squad({ slug, canManage }: { slug: string; canManage: boolean }) {
  const [data, setData] = useState<SquadData | null>(null);
  const [row, setRow] = useState({ uid: "", name: "", role: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    api<SquadData>(`/teams/${slug}/squad`)
      .then((d) => live && setData(d))
      .catch(() => live && setData(null));
    return () => {
      live = false;
    };
  }, [slug]);

  async function run(action: () => Promise<SquadData>) {
    setBusy(true);
    setError(null);
    try {
      setData(await action());
      setRow({ uid: "", name: "", role: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }

  if (!data) return null;
  const full = data.players.length >= data.max;
  return (
    <div className="card mb-6 p-4 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-display text-lg uppercase">Roster</p>
        <p className="text-xs text-muted">
          {data.players.length} of {data.max}
          {data.season ? ` · ${data.season}` : ""}
        </p>
      </div>
      <p className="mt-1 text-muted">Players are matched to your team by UID in every uploaded match.</p>
      {data.players.length === 0 && <p className="mt-3 text-muted">No one on the roster yet.</p>}
      <ul className="mt-3 divide-y divide-line rounded border border-line">
        {data.players.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
            <span className="min-w-0 flex-1 font-medium">{p.name}</span>
            <span className="font-mono text-xs text-muted">{p.game_uid}</span>
            {p.role && <span className="text-xs text-muted">{p.role}</span>}
            {canManage && (
              <button
                type="button"
                className="text-xs text-muted hover:text-bad"
                disabled={busy}
                onClick={() => run(() => api<SquadData>(`/teams/${slug}/squad?player=${p.id}`, { method: "DELETE" }))}
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
      {canManage && !full && (
        <form
          className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-[1fr_1fr_9rem_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            run(() => api<SquadData>(`/teams/${slug}/squad`, { method: "POST", body: row }));
          }}
        >
          <input value={row.name} onChange={(e) => setRow({ ...row, name: e.target.value })} maxLength={30} required placeholder="In-game name" aria-label="In-game name" className="input" />
          <input value={row.uid} onChange={(e) => setRow({ ...row, uid: cleanUid(e.target.value) })} inputMode="numeric" required placeholder="UID" aria-label="UID" className="input font-mono" />
          <select value={row.role} onChange={(e) => setRow({ ...row, role: e.target.value })} required aria-label="Role" className="input">
            <option value="">Role</option>
            {ROLES.map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-primary px-4 py-1.5 text-xs" disabled={busy}>
            Add player
          </button>
        </form>
      )}
      {canManage && full && <p className="mt-3 text-xs text-muted">The roster is full. Remove someone to add a player.</p>}
      {error && <p className="mt-2 text-xs text-bad">{error}</p>}
      {canManage && data.from_logs.length > 0 && (
        <p className="mt-3 text-xs text-muted">
          Also played for you lately, not on the roster: {data.from_logs.map((p) => `${p.name} (${p.game_uid})`).join(", ")}
        </p>
      )}
    </div>
  );
}
