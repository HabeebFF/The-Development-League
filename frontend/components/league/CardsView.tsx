"use client";

import Link from "next/link";
import { useState } from "react";

import { ROLES, weekLabel, type CardWeek, type Role } from "@/lib/cards";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import PlayerCard from "./PlayerCard";
import TeamOfMonth from "./TeamOfMonth";

/** The weekly cards gallery, and a Team of the Month tab (not on a team page). */
export default function CardsView({ team }: { team?: string }) {
  const [view, setView] = useState<"week" | "month">("week");
  if (team) return <WeekCards team={team} />;
  return (
    <>
      <div className="mb-5 flex gap-1 border-b border-line">
        {(
          [
            ["week", "Weekly cards"],
            ["month", "Team of the Month"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={`-mb-px border-b-2 px-3 py-2 font-display text-lg uppercase ${view === key ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {view === "week" ? <WeekCards /> : <TeamOfMonth />}
    </>
  );
}

/** Every player's card for a week, best first, with a role filter and a week picker. */
function WeekCards({ team }: { team?: string }) {
  const [week, setWeek] = useState<string | null>(null);
  const [role, setRole] = useState<Role | "">("");
  const [search, setSearch] = useState("");
  const params = new URLSearchParams();
  if (week) params.set("week", week);
  if (role) params.set("role", role);
  if (team) params.set("team", team);
  const data = useApi<CardWeek>(`/cards?${params}`);
  const q = search.trim().toLowerCase();
  const cards = (data.data?.cards ?? []).filter(
    (c) =>
      !q ||
      c.name.toLowerCase().includes(q) ||
      c.team?.name.toLowerCase().includes(q) ||
      c.team?.tag.toLowerCase().includes(q),
  );

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <button
          className={`btn px-3 py-1.5 text-sm uppercase ${role === "" ? "btn-primary" : ""}`}
          onClick={() => setRole("")}
        >
          All
        </button>
        {ROLES.map((r) => (
          <button
            key={r.key}
            className={`btn px-3 py-1.5 text-sm uppercase ${role === r.key ? "btn-primary" : ""}`}
            onClick={() => setRole(r.key)}
          >
            {r.label}
          </button>
        ))}
        {data.data?.week && (
          <span className="ml-auto flex items-center gap-2">
            <button
              className="btn px-3 py-1.5 text-sm"
              disabled={!data.data.previous}
              onClick={() => setWeek(data.data!.previous)}
              aria-label="Earlier week"
            >
              &larr;
            </button>
            <span className="min-w-32 text-center font-display text-lg uppercase">
              {weekLabel(data.data.week)}
            </span>
            <button
              className="btn px-3 py-1.5 text-sm"
              disabled={!data.data.next}
              onClick={() => setWeek(data.data!.next)}
              aria-label="Later week"
            >
              &rarr;
            </button>
          </span>
        )}
      </div>
      <input
        className="input mt-3 sm:max-w-xs"
        placeholder="Find a player or team"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {!data.data ? (
        <div className="mt-6">
          <Loading error={data.error} count={4} />
        </div>
      ) : !data.data.week ? (
        <p className="mt-6 text-muted">
          No cards yet. They are built every Monday from the week before.
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm text-muted">
            {cards.length} {cards.length === 1 ? "card" : "cards"}. Ratings
            compare every player with the whole league over the last four weeks;
            the week shown counts double.
          </p>
          <div className="mt-6 grid grid-cols-2 justify-items-center gap-x-3 gap-y-5 sm:grid-cols-3 lg:grid-cols-5">
            {cards.map((c) => (
              <Link
                key={c.player_id}
                href={`/cards/${c.player_id}?week=${c.week}`}
                className="transition duration-200 hover:-translate-y-1"
                aria-label={`${c.name}, ${c.overall} ${c.role_label}`}
              >
                <span className="sm:hidden">
                  <PlayerCard card={c} size={0.64} />
                </span>
                <span className="hidden sm:block">
                  <PlayerCard card={c} size={0.78} />
                </span>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
  );
}
