"use client";

import { useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";
import {
  blankRow,
  cleanUid,
  COUNTRIES,
  filledRows,
  formData,
  setIgl,
  type CheckedRow,
  type MyNewTeam,
  type NewTeam,
  type TeamCheck,
  type TeamForm,
} from "@/lib/newTeam";

type Field = keyof TeamCheck["errors"];

/** "Create your team": name, tag, logo, country, lobby name, contact and a 4-6 player
 * roster (in-game name, UID, role). Checks names and UIDs as the manager types. ``editing``
 * is set when a team waiting for staff (or rejected) is changed and sent again. */
export default function NewTeamForm({
  limits,
  start,
  editing = false,
  onSaved,
  onCancel,
}: {
  limits: Pick<MyNewTeam, "min_players" | "max_players" | "roles">;
  start: TeamForm;
  editing?: boolean;
  onSaved: (team: NewTeam) => void;
  onCancel?: () => void;
}) {
  const [form, setForm] = useState<TeamForm>(start);
  const [logo, setLogo] = useState<File | null>(null);
  const [check, setCheck] = useState<TeamCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const typed = useRef(false);

  // Check names and UIDs a moment after the manager stops typing.
  useEffect(() => {
    if (!typed.current) return;
    const timer = setTimeout(() => {
      api<TeamCheck>("/me/new-team/check", { method: "POST", body: { ...form, roster: filledRows(form.roster) } })
        .then(setCheck)
        .catch(() => undefined);
    }, 600);
    return () => clearTimeout(timer);
  }, [form]);

  function change(patch: Partial<TeamForm>) {
    typed.current = true;
    setForm((f) => ({ ...f, ...patch }));
  }

  function changeRow(index: number, patch: Partial<TeamForm["roster"][number]>) {
    typed.current = true;
    setForm((f) => ({ ...f, roster: f.roster.map((r, i) => (i === index ? { ...r, ...patch } : r)) }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const team = await api<NewTeam>("/me/new-team", { method: editing ? "PATCH" : "POST", body: formData(form, logo) });
      onSaved(team);
    } catch (err) {
      if (err instanceof ApiError && err.data && typeof err.data === "object" && "players" in err.data) {
        const data = err.data as TeamCheck["errors"] & { players: CheckedRow[]; roster?: string };
        const { players, roster, ...errors } = data;
        setCheck({ errors, players, roster: roster ?? null });
        setError(roster ?? "Fix the fields marked in red.");
      } else {
        setError(err instanceof Error ? err.message : "That didn't work.");
      }
    } finally {
      setBusy(false);
    }
  }

  const fieldError = (name: Field) => check?.errors[name];
  // Checked rows come back for the filled rows only, in order.
  const filled = form.roster.map((r) => !!(r.uid.trim() || r.name.trim()));
  const checkedRow = (index: number): CheckedRow | undefined => {
    if (!filled[index]) return undefined;
    const position = filled.slice(0, index).filter(Boolean).length;
    const row = check?.players[position];
    return row && row.uid === cleanUid(form.roster[index].uid) ? row : undefined;
  };
  const count = filledRows(form.roster).length;

  return (
    <form onSubmit={submit} className="space-y-5 text-sm">
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Team name" value={form.name} onChange={(v) => change({ name: v })} error={fieldError("name")} max={40} placeholder="Nairobi Kings" />
        <Input label="Tag" value={form.tag} onChange={(v) => change({ tag: v.toUpperCase() })} error={fieldError("tag")} max={6} placeholder="NBK" hint="2 to 6 letters or numbers" />
        <Input
          label="Name in the game lobby"
          value={form.lobby_name}
          onChange={(v) => change({ lobby_name: v })}
          error={fieldError("lobby_name")}
          max={40}
          optional
          hint="Only if it's different, e.g. NBK ESPORTS"
        />
        <label className="block">
          <span className="text-muted">Country</span>
          <select value={form.country} onChange={(e) => change({ country: e.target.value })} className="input mt-1">
            {COUNTRIES.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
          {fieldError("country") && <span className="mt-1 block text-xs text-bad">{fieldError("country")}</span>}
        </label>
        <Input
          label="WhatsApp or Discord"
          value={form.contact}
          onChange={(v) => change({ contact: v })}
          error={fieldError("contact")}
          max={120}
          placeholder="+234 801 234 5678"
          hint="Only TDL staff see this, to check your team"
        />
        <label className="block">
          <span className="text-muted">
            Logo <span className="text-xs">(optional)</span>
          </span>
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setLogo(e.target.files?.[0] ?? null)} className="input mt-1 py-1.5 text-xs" />
          <span className="mt-1 block text-xs text-muted">PNG, JPEG or WebP, up to 2 MB</span>
        </label>
      </div>

      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-display text-lg uppercase">Roster</p>
          <p className="text-xs text-muted">
            {count} of {limits.min_players} to {limits.max_players} players
          </p>
        </div>
        <p className="mt-1 text-xs text-muted">
          Copy each UID from the player&apos;s Free Fire profile. Their card name comes from the game, so it updates after their first match.
        </p>
        <ul className="mt-3 space-y-2">
          {form.roster.map((row, i) => {
            const checked = checkedRow(i);
            return (
              <li key={i} className={`card p-3 ${checked?.error ? "border-bad/60" : checked?.flag ? "border-accent/50" : ""}`}>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_1fr_9rem_auto]">
                  <input value={row.name} onChange={(e) => changeRow(i, { name: e.target.value })} maxLength={30} placeholder="In-game name" aria-label={`Player ${i + 1} in-game name`} className="input" />
                  <input
                    value={row.uid}
                    onChange={(e) => changeRow(i, { uid: cleanUid(e.target.value) })}
                    inputMode="numeric"
                    placeholder="UID"
                    aria-label={`Player ${i + 1} UID`}
                    className="input font-mono"
                  />
                  <select value={row.role} onChange={(e) => changeRow(i, { role: e.target.value })} aria-label={`Player ${i + 1} role`} className="input">
                    <option value="">Role</option>
                    {Object.entries(limits.roles).map(([code, label]) => (
                      <option key={code} value={code}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-1.5 text-xs">
                      <input
                        type="checkbox"
                        checked={row.igl}
                        onChange={(e) => {
                          typed.current = true;
                          setForm((f) => ({ ...f, roster: setIgl(f.roster, i, e.target.checked) }));
                        }}
                      />
                      IGL
                    </label>
                    {form.roster.length > limits.min_players && (
                      <button type="button" className="text-xs text-muted hover:text-bad" onClick={() => change({ roster: form.roster.filter((_, j) => j !== i) })} aria-label={`Remove player ${i + 1}`}>
                        Remove
                      </button>
                    )}
                  </div>
                </div>
                {checked?.error && <p className="mt-2 text-xs text-bad">{checked.error}</p>}
                {!checked?.error && checked?.flag && <p className="mt-2 text-xs text-accent">{checked.flag} TDL staff will check this.</p>}
                {!checked?.error && !checked?.flag && checked?.known && <p className="mt-2 text-xs text-ok">Found: {checked.known.name}</p>}
                {checked && !checked.error && !checked.known && <p className="mt-2 text-xs text-muted">New player: they&apos;ll show up after their first match.</p>}
              </li>
            );
          })}
        </ul>
        {form.roster.length < limits.max_players && (
          <button type="button" className="btn mt-2 px-4 py-1.5 text-xs" onClick={() => change({ roster: [...form.roster, blankRow()] })}>
            Add a player
          </button>
        )}
        {check?.roster && <p className="mt-2 text-xs text-bad">{check.roster}</p>}
      </div>

      {error && <p className="border-l-[3px] border-bad bg-panel-2 px-3 py-2 text-bad">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn btn-primary px-5 py-2" disabled={busy}>
          {busy ? "Sending…" : editing ? "Send it again" : "Send to TDL staff"}
        </button>
        {onCancel && (
          <button type="button" className="btn px-5 py-2" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
      <p className="text-xs text-muted">You become the team&apos;s manager. TDL staff check every new team before it can sign up for scrims.</p>
    </form>
  );
}

function Input({
  label,
  value,
  onChange,
  error,
  max,
  placeholder,
  hint,
  optional = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  max: number;
  placeholder?: string;
  hint?: string;
  optional?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-muted">
        {label}
        {optional && <span className="text-xs"> (optional)</span>}
      </span>
      <input value={value} onChange={(e) => onChange(e.target.value)} maxLength={max} placeholder={placeholder} required={!optional} className={`input mt-1 ${error ? "border-bad" : ""}`} />
      {error ? <span className="mt-1 block text-xs text-bad">{error}</span> : hint ? <span className="mt-1 block text-xs text-muted">{hint}</span> : null}
    </label>
  );
}
