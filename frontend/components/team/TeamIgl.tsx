"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

type IglState = { igl: number | null; igl_name: string | null; players: { id: number; name: string; matches: number }[] };

/** The team's IGL for the Best IGL award: managers pick it, everyone else on the team sees it. */
export default function TeamIgl({ slug, canPick }: { slug: string; canPick: boolean }) {
  const [state, setState] = useState<IglState | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    api<IglState>(`/teams/${encodeURIComponent(slug)}/igl`)
      .then(setState)
      .catch(() => setState(null));
  }, [slug]);

  async function pick(value: string) {
    setBusy(true);
    setNote(null);
    try {
      const next = await api<IglState>(`/teams/${encodeURIComponent(slug)}/igl`, {
        method: "PUT",
        body: { igl: value ? Number(value) : null },
      });
      setState(next);
      setNote("Saved.");
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!state) return null;
  return (
    <div className="card mt-6 max-w-xl p-4">
      <p className="text-xs font-bold tracking-widest text-accent uppercase">Team IGL</p>
      {canPick ? (
        <>
          <p className="mt-1 text-sm text-muted">
            Who calls for your team? They can win{" "}
            <Link href="/awards" className="text-accent">
              Best IGL
            </Link>{" "}
            on your team&apos;s results in the matches they play.
          </p>
          <div className="mt-3 flex items-center gap-3">
            <select value={state.igl ?? ""} disabled={busy} onChange={(e) => pick(e.target.value)} className="input flex-1">
              <option value="">Not set</option>
              {state.players.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.matches} {p.matches === 1 ? "match" : "matches"})
                </option>
              ))}
            </select>
            {note && <span className={`text-sm ${note === "Saved." ? "text-ok" : "text-bad"}`}>{note}</span>}
          </div>
        </>
      ) : (
        <p className="mt-1 text-sm">
          {state.igl_name ?? "Not set yet."}
          <span className="block text-xs text-muted">Your team manager picks the IGL for the Best IGL award.</span>
        </p>
      )}
    </div>
  );
}
