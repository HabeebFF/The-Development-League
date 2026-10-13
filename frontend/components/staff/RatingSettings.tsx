"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

type Points = Record<string, number | number[]>;
type Settings = { points: Points; defaults: Points; limits: Record<string, [number, number]> };

const FIELDS: { key: string; label: string; help: string }[] = [
  { key: "base", label: "Everyone starts on", help: "Before anything happens in the match" },
  { key: "kill", label: "Each kill", help: "" },
  { key: "knock", label: "Each knock", help: "" },
  { key: "headshot", label: "Each headshot knock", help: "On top of the knock" },
  { key: "opening", label: "Each fight opened", help: "First knock or kill between two teams" },
  { key: "trade", label: "Each trade", help: "Hit back after a teammate went down nearby (needs replay files)" },
  { key: "survival", label: "Time alive", help: "Out at the start is minus this, alive to the end is plus this" },
  { key: "alone_down", label: "Knocked while alone", help: "Use a minus number (needs replay files)" },
  { key: "first_down", label: "First down on the team", help: "Use a minus number" },
  { key: "floor", label: "Lowest rating", help: "" },
  { key: "ceiling", label: "Highest rating", help: "" },
  { key: "potd_min", label: "Player of the Day needs", help: "Matches that day (or every match, if fewer were played)" },
];

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** Staff: the points behind player ratings. Saving rates every match again. */
export default function RatingSettings() {
  const [s, setS] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Points>({});
  const [places, setPlaces] = useState("");
  const [note, setNote] = useState<string | null>(null);

  function load(d: Settings) {
    setS(d);
    setDraft(d.points);
    setPlaces((d.points.placement as number[]).join(", "));
  }

  useEffect(() => {
    api<Settings>("/admin/ratings")
      .then(load)
      .catch((e) => setNote(message(e)));
  }, []);

  async function save(points: Points) {
    setNote(null);
    try {
      load(await api<Settings>("/admin/ratings", { method: "PUT", body: { points } }));
      setNote("Saved. Every match is being rated again; refresh the ratings page in a minute.");
    } catch (e) {
      setNote(message(e));
    }
  }

  function saveDraft() {
    const placement = places
      .split(/[,\s]+/)
      .filter(Boolean)
      .map(Number);
    if (!placement.length || placement.some((n) => Number.isNaN(n))) {
      setNote("Placement points must be numbers separated by commas.");
      return;
    }
    save({ ...draft, placement });
  }

  if (!s) return note ? <p className="mt-8 text-bad">{note}</p> : null;
  return (
    <div className="mt-8">
      <div className="card divide-y divide-line">
        {FIELDS.map((f) => (
          <label key={f.key} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span className="min-w-0 flex-1">
              <span className="block font-semibold">{f.label}</span>
              {f.help && <span className="block text-xs text-muted">{f.help}</span>}
            </span>
            <input
              type="number"
              step={f.key === "potd_min" ? 1 : 0.01}
              min={s.limits[f.key]?.[0]}
              max={s.limits[f.key]?.[1]}
              className="input py-1"
              style={{ width: "6rem" }}
              value={draft[f.key] as number}
              onChange={(e) => setDraft({ ...draft, [f.key]: Number(e.target.value) })}
            />
          </label>
        ))}
        <label className="block px-4 py-2.5 text-sm">
          <span className="block font-semibold">Team placement</span>
          <span className="block text-xs text-muted">Points for 1st (Booyah), 2nd, 3rd... in order. The last number covers every place after it.</span>
          <input className="input mt-2 w-full" value={places} onChange={(e) => setPlaces(e.target.value)} />
        </label>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn btn-primary px-4" onClick={saveDraft}>
          Save and rate again
        </button>
        <button className="btn px-4" onClick={() => save(s.defaults)}>
          Back to the defaults
        </button>
      </div>
      {note && <p className="mt-3 text-sm text-muted">{note}</p>}
    </div>
  );
}
