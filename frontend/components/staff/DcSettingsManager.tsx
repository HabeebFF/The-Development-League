"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { dc, type DcSettings } from "@/lib/dc";

type Preview = {
  matches: number;
  dc: number;
  linked_dc: number;
  waiting_dc: number;
};
const RATES: {
  key: "per_kill" | "booyah" | "mvp" | "played";
  label: string;
  hint: string;
}[] = [
  { key: "per_kill", label: "Per kill", hint: "Each kill in a match" },
  { key: "booyah", label: "Booyah", hint: "Every player on the winning team" },
  {
    key: "mvp",
    label: "Match MVP",
    hint: "The best-rated player of the match",
  },
  { key: "played", label: "Played", hint: "Every player in the match" },
];

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** Staff: what playing pays in DC, the switch, and back-pay for matches before the start day. */
export default function DcSettingsManager() {
  const [conf, setConf] = useState<DcSettings | null>(null);
  const [draft, setDraft] = useState<Partial<DcSettings>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [since, setSince] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [paid, setPaid] = useState<string | null>(null);

  useEffect(() => {
    api<DcSettings>("/admin/dc/settings")
      .then(setConf)
      .catch((e) => setError(message(e)));
  }, []);

  async function save() {
    setError(null);
    setSaved(false);
    try {
      setConf(
        await api<DcSettings>("/admin/dc/settings", {
          method: "PATCH",
          body: draft,
        }),
      );
      setDraft({});
      setSaved(true);
    } catch (e) {
      setError(message(e));
    }
  }

  async function check() {
    setError(null);
    setPaid(null);
    try {
      setPreview(await api<Preview>(`/admin/dc/backpay?since=${since}`));
    } catch (e) {
      setError(message(e));
    }
  }

  async function pay() {
    setError(null);
    try {
      const r = await api<Preview & { start_date: string }>(
        "/admin/dc/backpay",
        { method: "POST", body: { since } },
      );
      setPaid(
        `Paid ${r.matches} matches. Matches from ${r.start_date} now earn DC.`,
      );
      setPreview(null);
      setConf((c) => (c ? { ...c, start_date: r.start_date } : c));
    } catch (e) {
      setError(message(e));
    }
  }

  if (!conf)
    return <p className="mt-6 text-sm text-muted">{error ?? "Loading..."}</p>;
  const value = { ...conf, ...draft };

  return (
    <div className="mt-6 space-y-6">
      {!conf.on && (
        <p className="card border-l-[3px] border-bad p-3 text-sm">
          DC for playing is switched off on this server (DC_MATCH_REWARDS).
        </p>
      )}
      <div className="card p-4">
        <label className="flex items-center gap-2 text-sm font-semibold">
          <input
            type="checkbox"
            checked={value.rewards_enabled}
            onChange={(e) =>
              setDraft({ ...draft, rewards_enabled: e.target.checked })
            }
          />
          Pay DC after each upload
        </label>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {RATES.map((r) => (
            <label key={r.key} className="block text-sm">
              <span className="font-semibold">{r.label}</span>
              <span className="ml-2 text-xs text-muted">{r.hint}</span>
              <input
                type="number"
                min={0}
                max={100000}
                className="input mt-1"
                value={value[r.key]}
                onChange={(e) =>
                  setDraft({ ...draft, [r.key]: Number(e.target.value) })
                }
              />
            </label>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted">
          Example: 4 kills, a Booyah and MVP pay{" "}
          {dc(value.played + 4 * value.per_kill + value.booyah + value.mvp)}.
          New rates count from the next upload; a re-uploaded match is paid at
          the new rates. Players without an account keep theirs waiting until
          they link their UID.
        </p>
        <div className="mt-3 flex items-center gap-3">
          <button
            className="btn btn-primary px-4"
            onClick={save}
            disabled={!Object.keys(draft).length}
          >
            Save
          </button>
          {saved && <span className="text-sm text-ok">Saved.</span>}
        </div>
      </div>

      <div className="card p-4">
        <h2 className="font-display text-2xl uppercase">Back-pay</h2>
        <p className="mt-1 text-sm text-muted">
          Matches from {conf.start_date} earn DC. Pick an earlier day to pay the
          matches before it too (each match is only ever paid once).
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            type="date"
            className="input"
            style={{ width: "auto" }}
            value={since}
            max={conf.start_date}
            onChange={(e) => setSince(e.target.value)}
          />
          <button className="btn px-4" onClick={check} disabled={!since}>
            See what it pays
          </button>
        </div>
        {preview && (
          <div className="mt-3 text-sm">
            <p>
              {preview.matches} matches: <b>{dc(preview.dc)}</b> in all,{" "}
              {dc(preview.linked_dc)} straight to players with accounts and{" "}
              {dc(preview.waiting_dc)} waiting for players who haven&apos;t
              linked yet.
            </p>
            <button
              className="btn btn-primary mt-2 px-4"
              onClick={pay}
              disabled={!preview.matches}
            >
              Pay these matches
            </button>
          </div>
        )}
        {paid && <p className="mt-3 text-sm text-ok">{paid}</p>}
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
    </div>
  );
}
