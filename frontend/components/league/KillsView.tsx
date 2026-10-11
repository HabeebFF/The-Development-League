"use client";

import { useState } from "react";

import { killsLabel, killsPath, type KillList } from "@/lib/kills";
import { useApi } from "@/lib/useApi";

import KillTable from "./KillTable";
import Loading from "./Loading";

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
  const data = useApi<KillList>(killsPath(scope, at));
  const k = data.data;

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {SCOPES.map((s) => (
          <button
            key={s.key}
            className={`btn px-4 py-1.5 text-sm uppercase ${scope === s.key ? "btn-primary" : ""}`}
            onClick={() => {
              setScope(s.key);
              setAt(null);
            }}
          >
            {s.label}
          </button>
        ))}
        {k && (
          <span className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto">
            <button className="btn px-3 py-1.5 text-sm" disabled={k.previous == null} onClick={() => setAt(k.previous ?? null)} aria-label="Earlier">
              &larr;
            </button>
            <span className="min-w-36 flex-1 truncate text-center font-display text-lg uppercase">{killsLabel(k)}</span>
            <button className="btn px-3 py-1.5 text-sm" disabled={k.next == null} onClick={() => setAt(k.next ?? null)} aria-label="Later">
              &rarr;
            </button>
          </span>
        )}
      </div>

      {!k ? (
        <div className="mt-6">
          <Loading error={data.error} count={10} />
        </div>
      ) : (
        <div className="mt-6">
          {k.matches === 0 ? (
            <p className="text-sm text-muted">No matches were played {scope === "session" ? "yet" : `this ${scope}`}.</p>
          ) : (
            <KillTable list={k} />
          )}
        </div>
      )}
    </>
  );
}
