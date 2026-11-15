"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type JoinRequest, type Paged } from "@/lib/api";

function rows<T>(data: Paged<T> | T[]): T[] {
  return Array.isArray(data) ? data : data.results;
}

const ago = (iso: string) => {
  const mins = Math.max(1, Math.round((Date.now() - Date.parse(iso)) / 60000));
  return mins < 60 ? `${mins} min ago` : mins < 1440 ? `${Math.round(mins / 60)} h ago` : `${Math.round(mins / 1440)} d ago`;
};

/** Players asking to join: a team's waiting requests for its managers (``slug``), or, for
 * staff (no slug), the ones on teams nobody manages. ``compact`` is the "N asked to join"
 * line on My team. */
export default function JoinRequests({ slug, compact = false, onAnswered }: { slug?: string; compact?: boolean; onAnswered?: () => void }) {
  const [list, setList] = useState<JoinRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const path = slug ? `/teams/${slug}/join-requests?page_size=100` : "/admin/join-requests?unmanaged=1&page_size=100";

  useEffect(() => {
    let live = true;
    api<Paged<JoinRequest> | JoinRequest[]>(path)
      .then((d) => live && setList(rows(d)))
      .catch(() => live && setList([]));
    return () => {
      live = false;
    };
  }, [path, version]);

  async function answer(r: JoinRequest, how: "accept" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await api(`/teams/${r.team.slug}/join-requests/${r.id}/${how}`, { method: "POST" });
      setVersion((v) => v + 1);
      onAnswered?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }

  if (!list || list.length === 0) return null;
  if (compact) {
    return (
      <div className="card mt-4 flex flex-wrap items-center gap-3 border-accent/40 p-3 text-sm">
        <p className="min-w-0 flex-1 font-semibold">
          {list.length} player{list.length === 1 ? "" : "s"} asked to join {list[0].team.name}
        </p>
        <Link href="/team/members" className="btn btn-primary px-4 py-1.5 text-xs">
          Review
        </Link>
      </div>
    );
  }
  return (
    <div className="card mb-6 border-accent/40 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-display text-xl uppercase">Join requests</h2>
        <span className="chip chip-gold">{list.length} waiting</span>
      </div>
      {!slug && <p className="mt-1 text-xs text-muted">Teams with no manager: league staff answer these.</p>}
      {error && <p className="mt-2 text-xs text-bad">{error}</p>}
      <ul className="mt-3 space-y-2">
        {list.map((r) => {
          const p = r.player;
          const played = p ? p.matches_for_team : 0;
          return (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 bg-panel-2 p-3">
              <div className="min-w-0">
                <p className="font-display text-lg">
                  {r.user_name || r.email} {p && <span className="text-sm text-muted">plays as</span>} {p?.name}
                  {!slug && <span className="text-sm text-muted"> · for {r.team.name}</span>}
                </p>
                <p className="text-xs text-muted">
                  {p ? `UID ${p.game_uid} · ` : ""}
                  {played > 0 ? (
                    `${played} match${played === 1 ? "" : "es"} for ${r.team.name}`
                  ) : p?.current_team?.slug === r.team.slug ? (
                    `${r.team.name} is their team in the match logs`
                  ) : (
                    <span className="text-bad">
                      never played for {r.team.name}
                      {p?.current_team ? ` (last team ${p.current_team.name})` : ""}
                    </span>
                  )}
                  {r.note ? ` · "${r.note}"` : ""} · {ago(r.created_at)}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button type="button" className="btn btn-primary px-4 py-1.5 text-xs" disabled={busy} onClick={() => answer(r, "accept")}>
                  Accept
                </button>
                <button type="button" className="btn px-4 py-1.5 text-xs" disabled={busy} onClick={() => answer(r, "reject")}>
                  Reject
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
