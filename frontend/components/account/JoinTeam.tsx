"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type MyJoin } from "@/lib/api";

const ago = (iso: string) => {
  const mins = Math.max(1, Math.round((Date.now() - Date.parse(iso)) / 60000));
  return mins < 60 ? `${mins} min ago` : mins < 1440 ? `${Math.round(mins / 60)} h ago` : `${Math.round(mins / 1440)} d ago`;
};

/** "Join your team": a linked player asks to join a team (theirs from the logs by default);
 * the team's manager accepts or rejects. Shows the waiting or answered request too. */
export default function JoinTeam({ onJoined }: { onJoined?: () => void }) {
  const [data, setData] = useState<MyJoin | null>(null);
  const [team, setTeam] = useState("");
  const [note, setNote] = useState("");
  const [role, setRole] = useState<"PLAYER" | "MANAGER">("PLAYER");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    api<MyJoin>("/me/join-team")
      .then((d) => {
        if (!live) return;
        setData(d);
        setTeam((t) => t || d.suggested?.slug || "");
        if (d.request?.status === "ACCEPTED") onJoined?.();
      })
      .catch((e) => live && setError(e instanceof Error ? e.message : "Couldn't load your team."));
    return () => {
      live = false;
    };
  }, [version, onJoined]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }

  if (!data) return error ? <p className="text-sm text-bad">{error}</p> : null;
  if (data.on_team) {
    return (
      <div className="card p-4 text-sm">
        <p className="font-display text-lg uppercase">{data.on_team.name}</p>
        <p className="mt-1 text-muted">
          You&apos;re on {data.on_team.name}.{" "}
          <Link href="/team" className="text-accent">
            My team
          </Link>{" "}
          has its coach, matches, rotations and team cards.
        </p>
        {data.on_team.role === "PLAYER" &&
          (data.request?.status === "PENDING" && data.request.role === "MANAGER" ? (
            <p className="mt-2 text-xs text-muted">You asked to manage {data.on_team.name}. TDL staff will answer.</p>
          ) : (
            <button
              type="button"
              className="btn mt-3 px-4 py-1.5 text-xs"
              disabled={busy}
              onClick={() => run(() => api("/me/join-team", { method: "POST", body: { team: data.on_team!.slug, role: "MANAGER" } }))}
            >
              Ask to manage {data.on_team.name}
            </button>
          ))}
        {error && <p className="mt-2 text-xs text-bad">{error}</p>}
      </div>
    );
  }
  // Without a linked UID you can only ask to manage a team (managers don't have to play).
  const asRole = data.player ? role : "MANAGER";

  const req = data.request;
  if (req?.status === "PENDING") {
    return (
      <div className="card p-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-display text-lg uppercase">{req.team.name}</p>
          <span className="chip">{req.role === "MANAGER" ? "Waiting for TDL staff" : "Waiting for your manager"}</span>
        </div>
        <p className="mt-1 text-muted">
          {req.role === "MANAGER"
            ? `You asked to manage ${req.team.name} ${ago(req.created_at)}. TDL staff check every request to manage a team.`
            : `You asked to join ${req.team.name} ${ago(req.created_at)}. Your manager sees it on their Members page.`}{" "}
          You can still use the site as normal.
        </p>
        {error && <p className="mt-2 text-xs text-bad">{error}</p>}
        <button type="button" className="btn mt-3 px-4 py-1.5 text-xs" disabled={busy} onClick={() => run(() => api("/me/join-team", { method: "DELETE" }))}>
          Cancel request
        </button>
      </div>
    );
  }

  const chosen = data.teams.find((t) => t.slug === team);
  return (
    <div className="card border-accent/40 p-4 text-sm">
      <p className="font-display text-xl uppercase">Join your team</p>
      <p className="mt-1 text-muted">
        Being on your team opens its private pages: coach, matches, rotations and team cards.{" "}
        {asRole === "MANAGER" ? "TDL staff check every request to manage a team." : "Your manager accepts or rejects."}
      </p>
      <div className="mt-3 flex flex-wrap gap-4" role="radiogroup" aria-label="Join as">
        <label className={`flex items-center gap-1.5 ${data.player ? "" : "opacity-50"}`}>
          <input type="radio" name="join-role" checked={asRole === "PLAYER"} disabled={!data.player} onChange={() => setRole("PLAYER")} />
          As a player
        </label>
        <label className="flex items-center gap-1.5">
          <input type="radio" name="join-role" checked={asRole === "MANAGER"} onChange={() => setRole("MANAGER")} />
          As the team manager
        </label>
      </div>
      {!data.player && <p className="mt-1 text-xs text-muted">To join as a player, link your Free Fire UID first.</p>}
      {req?.status === "REJECTED" && (
        <p className="mt-3 border-l-[3px] border-bad bg-panel-2 px-3 py-2">
          {req.role === "MANAGER" ? `TDL staff didn't approve your request to manage ${req.team.name}.` : `${req.team.name} turned down your last request.`} Check with
          your manager or TDL staff, or ask another team.
        </p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(() => api("/me/join-team", { method: "POST", body: { team, note, role: asRole } }));
        }}
      >
        <label className="mt-3 block">
          <span className="text-muted">Team</span>
          <select value={team} onChange={(e) => setTeam(e.target.value)} required className="input mt-1">
            <option value="" disabled>
              Pick your team
            </option>
            {data.teams.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.name}
                {data.suggested?.slug === t.slug
                  ? data.suggested.matches > 0
                    ? ` (you played ${data.suggested.matches} match${data.suggested.matches === 1 ? "" : "es"} for them)`
                    : " (your team in the match logs)"
                  : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="mt-3 block">
          <span className="text-muted">{asRole === "MANAGER" ? "Note to TDL staff (optional)" : "Note to the manager (optional)"}</span>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} className="input mt-1" placeholder={data.player ? `${data.player.name} here` : "Who you are, how to reach you"} />
        </label>
        {error && <p className="mt-2 text-xs text-bad">{error}</p>}
        <button type="submit" className="btn btn-primary mt-3 px-4 py-1.5 text-xs" disabled={busy || !team}>
          {asRole === "MANAGER" ? (chosen ? `Ask to manage ${chosen.name}` : "Ask to manage") : chosen ? `Ask to join ${chosen.name}` : "Ask to join"}
        </button>
      </form>
    </div>
  );
}
