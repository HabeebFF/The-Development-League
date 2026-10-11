"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

type Settings = {
  weights: Record<string, Record<string, number>>;
  defaults: Record<string, Record<string, number>>;
  roles: { key: string; label: string; stats: string[] }[];
  stats: Record<string, string>;
};

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** How much each stat counts towards a role's overall rating, and rebuilding a week. */
export default function CardSettings() {
  const [s, setS] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Settings["weights"]>({});
  const [note, setNote] = useState<string | null>(null);
  const [week, setWeek] = useState("");

  useEffect(() => {
    api<Settings>("/admin/cards")
      .then((d) => {
        setS(d);
        setDraft(d.weights);
      })
      .catch((e) => setNote(message(e)));
  }, []);

  async function save(weights: Settings["weights"]) {
    setNote(null);
    try {
      const d = await api<Settings>("/admin/cards", { method: "PUT", body: { weights } });
      setS(d);
      setDraft(d.weights);
      setNote("Saved. Rebuild a week to see the new ratings now, or wait for Saturday.");
    } catch (e) {
      setNote(message(e));
    }
  }

  async function rebuild() {
    setNote(null);
    try {
      await api("/admin/cards", { method: "POST", body: { week } });
      setNote("Rebuilding that week and every week after it. Refresh the cards page in a minute.");
    } catch (e) {
      setNote(message(e));
    }
  }

  if (!s) return note ? <p className="mt-8 text-bad">{note}</p> : null;
  return (
    <div className="mt-10">
      <h2 className="section-title">Overall rating weights</h2>
      <p className="mt-2 text-sm text-muted">Higher numbers count for more. A stat set to 0 doesn&apos;t count.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {s.roles.map((r) => (
          <div key={r.key} className="card p-4">
            <h3 className="font-display text-xl uppercase">{r.label}</h3>
            <div className="mt-2 space-y-1.5">
              {r.stats.map((k) => (
                <label key={k} className="flex items-center gap-2 text-sm">
                  <span className="w-12 font-semibold">{k}</span>
                  <span className="flex-1 text-muted">{s.stats[k]}</span>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    className="input py-1"
                    style={{ width: "5rem" }}
                    value={draft[r.key]?.[k] ?? 0}
                    onChange={(e) => setDraft({ ...draft, [r.key]: { ...draft[r.key], [k]: Number(e.target.value) } })}
                  />
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn btn-primary px-4" onClick={() => save(draft)}>
          Save weights
        </button>
        <button className="btn px-4" onClick={() => save(s.defaults)}>
          Back to the defaults
        </button>
      </div>

      <h2 className="section-title mt-10">Rebuild a week</h2>
      <p className="mt-2 text-sm text-muted">For matches uploaded late, or after changing roles or weights. Later weeks are rebuilt too.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <input type="date" className="input" style={{ width: "auto" }} value={week} onChange={(e) => setWeek(e.target.value)} aria-label="Any day of the week" />
        <button className="btn px-4" disabled={!week} onClick={rebuild}>
          Rebuild
        </button>
      </div>
      {note && <p className="mt-3 text-sm text-muted">{note}</p>}
    </div>
  );
}
