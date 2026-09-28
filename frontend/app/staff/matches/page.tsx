"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type AdminMatch, type Paged } from "@/lib/api";

export default function StaffMatches() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paged<AdminMatch> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Paged<AdminMatch>>(`/admin/matches?status=PUBLISHED&page=${page}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [page]);

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-4xl uppercase">Plot rotations</h1>
      <p className="mt-2 text-sm text-muted">Published matches and how many team rotations are confirmed.</p>
      {error && <p className="mt-6 text-bad">{error}</p>}
      {!data && !error && <p className="mt-6 text-muted">Loading...</p>}
      {data && data.results.length === 0 && (
        <p className="mt-6 text-muted">No published matches yet. Upload some match logs first.</p>
      )}
      <ul className="mt-6 divide-y divide-line rounded-lg border border-line bg-panel">
        {data?.results.map((m) => {
          const total = m.rotations.AUTO + m.rotations.DRAFT + m.rotations.CONFIRMED;
          const done = m.rotations.CONFIRMED;
          return (
            <li key={m.id} className="flex items-center">
              <Link
                href={`/staff/matches/${m.id}/plot`}
                className="flex flex-1 items-center justify-between gap-4 px-4 py-3 hover:bg-panel-2"
              >
                <span>
                  <span className="block font-medium">{m.label}</span>
                  <span className="text-xs text-muted uppercase">{m.map ?? "No map"}</span>
                </span>
                <span className={done === total && total > 0 ? "text-ok" : "text-muted"}>
                  {done}/{total} confirmed
                </span>
              </Link>
              <Link
                href={`/staff/matches/${m.id}/replay`}
                className="self-stretch border-l border-line px-4 py-3 text-sm text-accent hover:bg-panel-2"
              >
                Live replay
              </Link>
            </li>
          );
        })}
      </ul>
      {data && (data.next || data.previous) && (
        <div className="mt-4 flex gap-2">
          <button className="btn" disabled={!data.previous} onClick={() => setPage(page - 1)}>
            Newer
          </button>
          <button className="btn" disabled={!data.next} onClick={() => setPage(page + 1)}>
            Older
          </button>
        </div>
      )}
    </section>
  );
}
