"use client";

import Link from "next/link";
import { useState } from "react";

import JoinRequests from "@/components/team/JoinRequests";
import Squad from "@/components/team/Squad";
import TeamPeople from "@/components/team/TeamPeople";

import { useTeam } from "../TeamGate";

export default function TeamMembers() {
  const { me, membership } = useTeam();
  const [answered, setAnswered] = useState(0); // reloads the member list after an accept
  if (!membership) {
    return (
      <section className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-muted">You aren&apos;t on a team. League staff manage teams from the Staff area.</p>
        <Link href="/staff/teams" className="mt-4 inline-block text-accent">
          Staff: teams
        </Link>
      </section>
    );
  }
  const staff = !!me.staff_role;
  return (
    <section className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/team" className="text-xs text-muted hover:text-text">
        &larr; Team
      </Link>
      <h1 className="mt-2 font-display text-5xl leading-none font-extrabold uppercase">{membership.team.name}</h1>
      <div className="mt-6">
        <Squad slug={membership.team.slug} canManage={membership.role === "MANAGER" || staff} />
        {(membership.role === "MANAGER" || staff) && <JoinRequests slug={membership.team.slug} onAnswered={() => setAnswered((n) => n + 1)} />}
        <TeamPeople
          key={answered}
          slug={membership.team.slug}
          canManage={membership.role === "MANAGER" || staff}
          canInviteManagers={staff}
        />
      </div>
    </section>
  );
}
