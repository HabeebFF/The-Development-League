"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { dc, type Perk, type PerkPurchase } from "@/lib/dc";

type Admin = { perks: Perk[]; pending: PerkPurchase[]; recent: PerkPurchase[] };

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

function summary(r: PerkPurchase): string {
  if (r.key === "SHOUTOUT") return `“${r.data.text}”`;
  if (r.key === "NAME_COLOUR") return String(r.data.colour);
  if (r.key === "THEME") return `${r.data.primary} / ${r.data.secondary}`;
  if (r.key === "PIN")
    return `match ${r.data.match_id}${r.data.note ? `: ${r.data.note}` : ""}`;
  return "";
}

/** Staff: perk prices and switches, shoutouts to check, and taking a perk down. */
export default function DcPerksManager() {
  const [data, setData] = useState<Admin | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Admin>("/admin/dc/perks")
      .then(setData)
      .catch((e) => setError(message(e)));
  }, []);

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      setData(await api<Admin>("/admin/dc/perks"));
    } catch (e) {
      setError(message(e));
    }
  }

  const review = (
    r: PerkPurchase,
    action: "approve" | "reject" | "remove",
    refund = false,
  ) => {
    const note =
      action === "approve"
        ? ""
        : (window.prompt("Note for the player (optional)") ?? "");
    return act(() =>
      api(`/admin/dc/purchases/${r.id}`, {
        method: "POST",
        body: { action, note, refund },
      }),
    );
  };

  if (!data)
    return <p className="mt-6 text-sm text-muted">{error ?? "Loading..."}</p>;
  return (
    <div className="mt-6 space-y-6">
      <div className="card p-4">
        <h2 className="font-display text-2xl uppercase">
          Shoutouts to check ({data.pending.length})
        </h2>
        {data.pending.length === 0 && (
          <p className="mt-2 text-sm text-muted">Nothing waiting.</p>
        )}
        <ul className="mt-2 divide-y divide-line text-sm">
          {data.pending.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-2 py-2">
              <span className="min-w-0 flex-1">
                <b>{r.player}</b>: {summary(r)}
              </span>
              <button
                className="btn btn-primary px-3 py-1 text-xs"
                onClick={() => review(r, "approve")}
              >
                Approve
              </button>
              <button
                className="btn px-3 py-1 text-xs"
                onClick={() => review(r, "reject")}
              >
                Turn down (refund)
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="card p-4">
        <h2 className="font-display text-2xl uppercase">Perks</h2>
        <ul className="mt-2 divide-y divide-line text-sm">
          {data.perks.map((p) => (
            <li key={p.key} className="flex flex-wrap items-center gap-2 py-2">
              <span className="min-w-0 flex-1">
                <b>{p.name}</b> {p.for_team ? "· team pot" : ""}{" "}
                {p.days ? `· ${p.days} day${p.days === 1 ? "" : "s"}` : ""}
              </span>
              <input
                type="number"
                min={1}
                defaultValue={p.price}
                className="input py-1"
                style={{ width: "8rem" }}
                aria-label={`${p.name} price`}
                onBlur={(e) =>
                  Number(e.target.value) !== p.price &&
                  act(() =>
                    api("/admin/dc/perks", {
                      method: "PATCH",
                      body: { key: p.key, price: Number(e.target.value) },
                    }),
                  )
                }
              />
              <label className="flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={p.enabled}
                  onChange={(e) =>
                    act(() =>
                      api("/admin/dc/perks", {
                        method: "PATCH",
                        body: { key: p.key, enabled: e.target.checked },
                      }),
                    )
                  }
                />
                On sale
              </label>
            </li>
          ))}
        </ul>
      </div>

      <div className="card p-4">
        <h2 className="font-display text-2xl uppercase">Recent</h2>
        <ul className="mt-2 divide-y divide-line text-sm">
          {data.recent.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-2 py-2">
              <span className="min-w-0 flex-1">
                <b>{r.name}</b> · {r.player ?? r.buyer}
                {r.from_pot && r.team ? ` (${r.team} pot)` : ""} · {dc(r.price)}{" "}
                · <span className="text-muted">{r.status_label}</span>
                {summary(r) && (
                  <span className="text-muted"> · {summary(r)}</span>
                )}
                {r.image && (
                  <a
                    href={r.image}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-1 underline"
                  >
                    image
                  </a>
                )}
              </span>
              {r.status === "ACTIVE" && (
                <>
                  <button
                    className="btn px-3 py-1 text-xs"
                    onClick={() => review(r, "remove", true)}
                  >
                    Take down + refund
                  </button>
                  <button
                    className="btn px-3 py-1 text-xs"
                    onClick={() => review(r, "remove", false)}
                  >
                    Take down
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
    </div>
  );
}
