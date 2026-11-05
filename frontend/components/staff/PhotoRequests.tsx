"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { BLANK_PHOTO } from "@/lib/cards";
import type { StaffPhotoRequest } from "@/lib/photos";

type List = { pending: number; results: StaffPhotoRequest[] };

/** Photos players sent for their own card: approve to put it on the card, or reject. */
export default function PhotoRequests() {
  const [list, setList] = useState<List | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<List>("/admin/photo-requests")
      .then(setList)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  return (
    <div className="mt-8">
      <h2 className="section-title">
        Photos from players{list && list.pending > 0 ? ` (${list.pending})` : ""}
      </h2>
      <p className="mt-2 text-sm text-muted">
        Players linked to their game UID can send a new photo from My card. Nothing shows on their card until you
        approve it; the background is then cut out as usual.
      </p>
      {error && <p className="mt-3 text-bad">{error}</p>}
      {!list && !error && <p className="mt-3 text-muted">Loading...</p>}
      {list && list.results.length === 0 && <p className="mt-3 text-muted">No photos waiting.</p>}
      <ul className="mt-3 space-y-2">
        {list?.results.map((r) => (
          <RequestRow key={r.id} req={r} onDone={load} />
        ))}
      </ul>
    </div>
  );
}

function RequestRow({ req, onDone }: { req: StaffPhotoRequest; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState<string | null>(null);

  async function review(verdict: "approve" | "reject") {
    setBusy(true);
    setNote(null);
    try {
      await api(`/admin/photo-requests/${req.id}/${verdict}`, {
        method: "POST",
        body: verdict === "reject" ? { reason } : {},
      });
      onDone();
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Couldn't save. Try again.");
      setBusy(false);
    }
  }

  const p = req.player;
  return (
    <li className="card flex flex-wrap items-center gap-4 px-4 py-3">
      <figure className="text-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={p.photo || BLANK_PHOTO} alt={`${p.name} now`} className="h-20 w-20 bg-panel-2 object-cover object-top" />
        <figcaption className="mt-1 text-[11px] text-muted">Now</figcaption>
      </figure>
      <span className="text-muted" aria-hidden>
        &rarr;
      </span>
      <figure className="text-center">
        {req.image ? (
          <a href={req.image} target="_blank" rel="noreferrer">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={req.image} alt={`New photo from ${p.name}`} className="h-20 w-20 bg-panel-2 object-cover object-top" />
          </a>
        ) : (
          <span className="block h-20 w-20 bg-panel-2" />
        )}
        <figcaption className="mt-1 text-[11px] text-muted">New</figcaption>
      </figure>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{p.name}</span>
        <span className="block text-xs text-muted">
          UID {p.game_uid}
          {p.team ? ` · ${p.team}` : ""}
        </span>
        <span className="block text-xs text-muted">
          Sent by {req.requested_by ?? "a deleted account"} on {new Date(req.created_at).toLocaleString()}
        </span>
      </span>
      <span className="flex flex-wrap gap-2">
        <button type="button" className="btn btn-primary px-3 py-1.5 text-sm" disabled={busy} onClick={() => review("approve")}>
          Approve
        </button>
        <button type="button" className="btn px-3 py-1.5 text-sm" disabled={busy} onClick={() => setRejecting(!rejecting)}>
          Reject
        </button>
      </span>
      {rejecting && (
        <span className="flex w-full flex-wrap gap-2">
          <input
            className="input flex-1"
            maxLength={200}
            placeholder="Reason the player will see (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <button type="button" className="btn px-3 py-1.5 text-sm" disabled={busy} onClick={() => review("reject")}>
            Reject photo
          </button>
        </span>
      )}
      {note && <p className="w-full text-xs text-bad">{note}</p>}
    </li>
  );
}
