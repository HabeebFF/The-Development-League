"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type Paged } from "@/lib/api";
import { BLANK_PHOTO, ROLES, type CardWeek, type Role } from "@/lib/cards";

type AdminPlayer = {
  id: number;
  game_uid: string;
  display_name: string;
  current_team: string | null;
  photo: string | null;
  card_role: Role | "";
};

/** Find a player, then set their photo and card role. */
export default function CardPlayers() {
  const [search, setSearch] = useState("");
  const [players, setPlayers] = useState<AdminPlayer[] | null>(null);
  const [suggested, setSuggested] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CardWeek>("/cards")
      .then((w) => setSuggested(Object.fromEntries(w.cards.map((c) => [c.player_id, ROLES.find((r) => r.key === c.suggested_role)?.label ?? ""]))))
      .catch(() => setSuggested({}));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      api<Paged<AdminPlayer>>(`/admin/players?page_size=50&search=${encodeURIComponent(search.trim())}`)
        .then((p) => setPlayers(p.results))
        .catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [search]);

  return (
    <div className="mt-8">
      <h2 className="section-title">Players</h2>
      <input className="input mt-4" placeholder="Search by name or game UID" value={search} onChange={(e) => setSearch(e.target.value)} />
      {error && <p className="mt-3 text-bad">{error}</p>}
      {!players && !error && <p className="mt-3 text-muted">Loading...</p>}
      <ul className="mt-3 space-y-2">
        {players?.map((p) => (
          <PlayerRow key={p.id} player={p} suggested={suggested[p.id]} />
        ))}
      </ul>
      {players?.length === 50 && <p className="mt-2 text-xs text-muted">Showing the first 50. Search to find others.</p>}
    </div>
  );
}

function PlayerRow({ player, suggested }: { player: AdminPlayer; suggested?: string }) {
  const [p, setP] = useState(player);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function patch(body: FormData) {
    setBusy(true);
    setNote(null);
    try {
      setP(await api<AdminPlayer>(`/admin/players/${p.id}`, { method: "PATCH", body }));
      setNote("Saved. Shows on the card at the next rebuild.");
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Couldn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="card flex flex-wrap items-center gap-3 px-4 py-3">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={p.photo || BLANK_PHOTO} alt="" className="h-12 w-12 shrink-0 bg-panel-2 object-cover object-top" />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{p.display_name}</span>
        <span className="text-xs text-muted">
          UID {p.game_uid}
          {p.current_team ? ` · ${p.current_team}` : ""}
        </span>
      </span>
      <select
        className="input py-1.5"
        style={{ width: "auto" }}
        value={p.card_role}
        disabled={busy}
        aria-label={`Card role for ${p.display_name}`}
        onChange={(e) => {
          const body = new FormData();
          body.set("card_role", e.target.value);
          patch(body);
        }}
      >
        <option value="">{suggested ? `Suggested: ${suggested}` : "Suggested by the site"}</option>
        {ROLES.map((r) => (
          <option key={r.key} value={r.key}>
            {r.label}
          </option>
        ))}
      </select>
      <label className="btn cursor-pointer px-2 py-1 text-xs">
        {p.photo ? "Change photo" : "Add photo"}
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            const body = new FormData();
            body.set("photo", file);
            patch(body);
            e.target.value = "";
          }}
        />
      </label>
      {p.photo && (
        <button
          className="btn px-2 py-1 text-xs"
          disabled={busy}
          onClick={() => {
            const body = new FormData();
            body.set("photo", "");
            patch(body);
          }}
        >
          Remove photo
        </button>
      )}
      {note && <p className="w-full text-xs text-muted">{note}</p>}
    </li>
  );
}
