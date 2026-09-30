"use client";

import { useEffect, useState } from "react";

import TeamPeople from "@/components/team/TeamPeople";
import { api, type Paged, type TeamRef } from "@/lib/api";

export default function StaffTeams() {
  const [teams, setTeams] = useState<TeamRef[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api<Paged<TeamRef>>("/admin/teams?page_size=100")
      .then((page) => setTeams(page.results))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <section className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-display text-4xl uppercase">Teams and invites</h1>
      <p className="mt-2 text-sm text-muted">
        Invite each team&apos;s manager here. Managers then invite their own players from the team area.
      </p>
      {error && <p className="mt-6 text-bad">{error}</p>}
      {!teams && !error && <p className="mt-6 text-muted">Loading...</p>}
      <ul className="mt-6 space-y-2">
        {teams?.map((team) => (
          <li key={team.slug} className="rounded-lg border border-line bg-panel">
            <button
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-panel-2"
              onClick={() => setOpen(open === team.slug ? null : team.slug)}
            >
              <span className="font-medium">{team.name}</span>
              <span className="text-sm text-muted">{open === team.slug ? "Close" : "Members and invites"}</span>
            </button>
            {open === team.slug && (
              <div className="border-t border-line p-4">
                <TeamPeople slug={team.slug} canManage canInviteManagers />
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
