"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type Paged } from "@/lib/api";

type Claim = {
  id: number;
  user: string;
  user_name: string;
  game_uid: string;
  player_name: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
};

const TABS = [
  { key: "PENDING", label: "Waiting" },
  { key: "", label: "All" },
] as const;

function when(iso: string) {
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Staff: approve or reject the game UIDs people gave when they signed up. */
export default function UidRequests() {
  const [tab, setTab] = useState<string>("PENDING");
  const [rows, setRows] = useState<Claim[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const [version, setVersion] = useState(0);
  const reload = () => setVersion((v) => v + 1);

  useEffect(() => {
    let live = true;
    api<Paged<Claim>>(`/admin/player-claims?page_size=100${tab ? `&status=${tab}` : ""}`)
      .then((p) => live && setRows(p.results))
      .catch((e) => live && setError(e instanceof ApiError ? e.message : "Couldn't load the requests."));
    return () => {
      live = false;
    };
  }, [tab, version]);

  async function review(claim: Claim, action: "approve" | "reject") {
    setBusy(claim.id);
    setError(null);
    try {
      await api(`/admin/player-claims/${claim.id}/${action}`, { method: "POST" });
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-6">
      <div className="flex gap-1.5">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            aria-pressed={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`border px-3 py-1 text-sm font-semibold ${tab === t.key ? "border-accent bg-accent/15 text-white" : "border-line text-muted hover:text-white"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      {!rows ? (
        <p className="mt-4 text-sm text-muted">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="mt-4 text-muted">{tab === "PENDING" ? "Nobody is waiting." : "No requests yet."}</p>
      ) : (
        <div className="mt-4 grid gap-2">
          {rows.map((c) => (
            <div key={c.id} className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{c.user_name || c.user}</p>
                <p className="truncate text-xs text-muted">{c.user}</p>
                <p className="mt-1 text-sm">
                  UID <span className="font-mono">{c.game_uid}</span>
                  {" · "}
                  {c.player_name ? (
                    <>
                      plays as <span className="font-semibold">{c.player_name}</span>
                    </>
                  ) : (
                    <span className="text-muted">not in any uploaded match yet</span>
                  )}
                </p>
                <p className="mt-1 text-xs text-muted">
                  Asked {when(c.created_at)}
                  {c.reviewed_at &&
                    ` · ${c.status === "APPROVED" ? "approved" : "rejected"} ${when(c.reviewed_at)}${c.reviewed_by ? ` by ${c.reviewed_by}` : ""}`}
                </p>
              </div>
              {c.status === "PENDING" ? (
                <div className="flex shrink-0 gap-2">
                  <button type="button" className="btn btn-primary" disabled={busy === c.id} onClick={() => review(c, "approve")}>
                    Approve
                  </button>
                  <button type="button" className="btn" disabled={busy === c.id} onClick={() => review(c, "reject")}>
                    Reject
                  </button>
                </div>
              ) : (
                <span className={`chip shrink-0 ${c.status === "APPROVED" ? "text-ok" : "text-muted"}`}>
                  {c.status === "APPROVED" ? "Approved" : "Rejected"}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
