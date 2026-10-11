"use client";

import CardPlayers from "@/components/staff/CardPlayers";
import CardSettings from "@/components/staff/CardSettings";

export default function StaffCards() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Player cards</h1>
      <p className="mt-2 text-sm text-muted">
        Cards rebuild every Monday morning from the week before. Add player photos, pick each player&apos;s role (or leave the site&apos;s
        suggestion), and set how much each stat counts towards the overall rating.
      </p>
      <CardPlayers />
      <CardSettings />
    </section>
  );
}
