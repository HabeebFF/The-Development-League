"use client";

import { useEffect, useState } from "react";

import TeamEditor, { type AdminTeam } from "@/components/staff/TeamEditor";
import TeamPeople from "@/components/team/TeamPeople";
import { api, type Paged } from "@/lib/api";

type Panel = { slug: string; tab: "edit" | "people" } | null;

export default function StaffTeams() {
  const [teams, setTeams] = useState<AdminTeam[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Panel>(null);
  const [version, setVersion] = useState(0); // bumped to reload after a change

  useEffect(() => {
    api<Paged<AdminTeam>>("/admin/teams?page_size=100")
      .then((page) => setTeams([...page.results].sort((a, b) => a.name.localeCompare(b.name))))
      .catch((e) => setError(e.message));
  }, [version]);

  function toggle(slug: string, tab: "edit" | "people") {
    setOpen(open?.slug === slug && open.tab === tab ? null : { slug, tab });
  }

  return (
    <section className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-display text-4xl uppercase">Teams</h1>
      <p className="mt-2 text-sm text-muted">
        Teams are created from in-game names when matches are uploaded. Give each one its proper name, logo
        and colour, merge spellings of the same team, and invite each team&apos;s manager.
      </p>
      {error && <p className="mt-6 text-bad">{error}</p>}
      {!teams && !error && <p className="mt-6 text-muted">Loading...</p>}
      <ul className="mt-6 space-y-2">
        {teams?.map((team) => (
          <li key={team.slug} className="rounded-lg border border-line bg-panel">
            <div className="flex flex-wrap items-center gap-2 px-4 py-3">
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{team.name}</span>
                <span className="text-xs text-muted">
                  {team.matches_played} {team.matches_played === 1 ? "match" : "matches"}
                  {team.is_league_member ? "" : " · not a league team"}
                </span>
              </span>
              <button className="btn px-2 py-1 text-xs" onClick={() => toggle(team.slug, "edit")}>
                {open?.slug === team.slug && open.tab === "edit" ? "Close" : "Edit or merge"}
              </button>
              <button className="btn px-2 py-1 text-xs" onClick={() => toggle(team.slug, "people")}>
                {open?.slug === team.slug && open.tab === "people" ? "Close" : "Members and invites"}
              </button>
            </div>
            {open?.slug === team.slug && (
              <div className="border-t border-line p-4">
                {open.tab === "edit" ? (
                  <TeamEditor
                    team={team}
                    teams={teams}
                    onChanged={(removed) => {
                      if (removed) setOpen(null);
                      setVersion((v) => v + 1);
                    }}
                  />
                ) : (
                  <TeamPeople slug={team.slug} canManage canInviteManagers />
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
