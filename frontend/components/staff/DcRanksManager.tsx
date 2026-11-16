"use client";

import { useEffect, useState } from "react";

import RankIcon from "@/components/dc/RankIcon";
import { api, ApiError } from "@/lib/api";
import {
  dc,
  kingMonth,
  type DcKing,
  type DcSettings,
  type RankStep,
} from "@/lib/dc";

type Spot = DcKing & { id: number; hidden: boolean };

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** Staff: the DC ranks (name and DC earned to reach each) and every DC King so far. */
export default function DcRanksManager() {
  const [steps, setSteps] = useState<RankStep[] | null>(null);
  const [spots, setSpots] = useState<Spot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<DcSettings & { rank_steps: RankStep[] }>("/admin/dc/settings")
      .then((c) => setSteps(c.rank_steps))
      .catch((e) => setError(message(e)));
    api<Spot[]>("/admin/dc/spotlights")
      .then(setSpots)
      .catch((e) => setError(message(e)));
  }, []);

  async function save() {
    setError(null);
    setSaved(false);
    try {
      const c = await api<{ rank_steps: RankStep[] }>("/admin/dc/settings", {
        method: "PATCH",
        body: { rank_steps: steps },
      });
      setSteps(c.rank_steps);
      setSaved(true);
    } catch (e) {
      setError(message(e));
    }
  }

  async function spot(method: "PATCH" | "POST", body?: unknown) {
    setError(null);
    try {
      setSpots(await api<Spot[]>("/admin/dc/spotlights", { method, body }));
    } catch (e) {
      setError(message(e));
    }
  }

  return (
    <div className="mt-6 space-y-6">
      <div className="card p-4">
        <h2 className="font-display text-2xl uppercase">Ranks</h2>
        <p className="mt-1 text-sm text-muted">
          Badges beside names, by DC earned (playing, predicting, bonuses).
          Spending in a shop never lowers a rank.
        </p>
        {steps && (
          <ul className="mt-3 space-y-2">
            {steps.map((s, i) => (
              <li key={i} className="flex items-center gap-2">
                <RankIcon step={s} size={18} />
                <input
                  className="input py-1"
                  style={{ width: "10rem" }}
                  value={s.name}
                  aria-label="Rank name"
                  onChange={(e) =>
                    setSteps(
                      steps.map((x, j) =>
                        j === i ? { ...x, name: e.target.value } : x,
                      ),
                    )
                  }
                />
                <input
                  type="number"
                  min={1}
                  className="input py-1"
                  style={{ width: "9rem" }}
                  value={s.min}
                  aria-label="DC earned to reach it"
                  onChange={(e) =>
                    setSteps(
                      steps.map((x, j) =>
                        j === i ? { ...x, min: Number(e.target.value) } : x,
                      ),
                    )
                  }
                />
                <span className="text-xs text-muted">DC earned</span>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex items-center gap-3">
          <button
            className="btn btn-primary px-4"
            onClick={save}
            disabled={!steps}
          >
            Save ranks
          </button>
          {saved && <span className="text-sm text-ok">Saved.</span>}
        </div>
      </div>

      <div className="card p-4">
        <h2 className="font-display text-2xl uppercase">DC Kings</h2>
        <p className="mt-1 text-sm text-muted">
          The player who earned the most DC in a month. Crowned early on the 1st
          and shown on the home page all that month. Hide one if they
          shouldn&apos;t be featured.
        </p>
        {spots && spots.length === 0 && (
          <p className="mt-3 text-sm text-muted">No DC King yet.</p>
        )}
        <ul className="mt-3 divide-y divide-line border-y border-line text-sm">
          {spots?.map((s) => (
            <li key={s.id} className="flex items-center gap-3 py-2">
              <span className="w-24 font-display">{kingMonth(s.month)}</span>
              <span className="min-w-0 flex-1 truncate">
                <b>{s.name}</b> · {dc(s.earned)}
              </span>
              <button
                className="btn px-3 py-1 text-xs"
                onClick={() => spot("PATCH", { id: s.id, hidden: !s.hidden })}
              >
                {s.hidden ? "Show" : "Hide"}
              </button>
            </li>
          ))}
        </ul>
        <button className="btn mt-3 px-4" onClick={() => spot("POST")}>
          Crown last month now
        </button>
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
    </div>
  );
}
