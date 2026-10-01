"use client";

import { useState } from "react";

import { api, ApiError } from "@/lib/api";

export type AdminTeam = {
  id: number;
  name: string;
  tag: string;
  slug: string;
  logo: string | null;
  primary_color: string;
  is_league_member: boolean;
  aliases: string[];
  matches_played: number;
};

function message(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** Edit one team (name, tag, colour, logo, league member) or merge it into another. */
export default function TeamEditor({
  team,
  teams,
  onChanged,
}: {
  team: AdminTeam;
  teams: AdminTeam[];
  onChanged: (removed: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [into, setInto] = useState("");

  async function save(form: FormData) {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const body = new FormData();
      body.set("name", String(form.get("name") ?? "").trim());
      body.set("tag", String(form.get("tag") ?? "").trim());
      body.set("primary_color", String(form.get("primary_color") ?? ""));
      body.set("is_league_member", form.get("is_league_member") ? "true" : "false");
      const logo = form.get("logo");
      if (logo instanceof File && logo.size > 0) body.set("logo", logo);
      await api(`/admin/teams/${team.slug}`, { method: "PATCH", body });
      setSaved(true);
      onChanged(false);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  async function merge() {
    const target = teams.find((t) => t.slug === into);
    if (!target) return;
    if (!confirm(`Merge "${team.name}" into "${target.name}"? Its results and names move over and "${team.name}" is removed.`)) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/admin/teams/${team.slug}/merge`, { method: "POST", body: { into } });
      onChanged(true);
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }

  const others = teams.filter((t) => t.slug !== team.slug).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="space-y-6">
      <form action={save} className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm sm:col-span-2">
          <span className="text-muted">Team name (as fans should see it)</span>
          <input name="name" defaultValue={team.name} required maxLength={80} className="input mt-1" />
        </label>
        <label className="block text-sm">
          <span className="text-muted">Tag</span>
          <input name="tag" defaultValue={team.tag} maxLength={12} className="input mt-1" />
        </label>
        <label className="block text-sm">
          <span className="text-muted">Colour</span>
          <input name="primary_color" type="color" defaultValue={team.primary_color || "#1C1C26"} className="input mt-1 h-10 p-1" />
        </label>
        <label className="block text-sm sm:col-span-2">
          <span className="text-muted">Logo (PNG or JPG, square works best)</span>
          <input name="logo" type="file" accept="image/png,image/jpeg,image/webp" className="input mt-1" />
        </label>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input name="is_league_member" type="checkbox" defaultChecked={team.is_league_member} />
          League team (shown on the public Teams page)
        </label>
        <div className="flex items-center gap-3 sm:col-span-2">
          <button type="submit" disabled={busy} className="btn btn-primary">
            {busy ? "Saving..." : "Save"}
          </button>
          {saved && <span className="text-sm text-ok">Saved.</span>}
        </div>
      </form>

      {team.aliases.length > 0 && (
        <p className="text-xs text-muted">
          In-game names that count as this team: {team.aliases.join(", ")}
        </p>
      )}

      <div className="rounded-lg border border-line p-3">
        <p className="text-sm font-medium">Same team under another name?</p>
        <p className="mt-1 text-xs text-muted">
          Merging moves this team&apos;s results, members and in-game names to the team you pick, then
          removes this one. Future uploads with either name count for the kept team.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <select value={into} onChange={(e) => setInto(e.target.value)} className="input flex-1">
            <option value="">Merge into...</option>
            {others.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.name} ({t.matches_played} {t.matches_played === 1 ? "match" : "matches"})
              </option>
            ))}
          </select>
          <button className="btn" disabled={busy || !into} onClick={merge}>
            Merge
          </button>
        </div>
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
    </div>
  );
}
