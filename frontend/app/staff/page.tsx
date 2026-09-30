"use client";

import Link from "next/link";

import { useStaff } from "./StaffGate";

export default function StaffHome() {
  const me = useStaff();
  const cards = [
    { href: "/staff/matches", title: "Plot rotations", text: "Check each team's auto route, fix it and confirm." },
    { href: "/staff/teams", title: "Teams and invites", text: "Invite each team's manager and see who has joined." },
    ...(me.is_super_admin
      ? [{ href: "/staff/maps", title: "Map images and calibration", text: "Upload map images and line them up with the game." }]
      : []),
  ];
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-4xl uppercase">Staff</h1>
      <p className="mt-2 text-sm text-muted">Signed in as {me.email}</p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {cards.map((c) => (
          <Link key={c.href} href={c.href} className="rounded-lg border border-line bg-panel p-5 hover:border-accent">
            <h2 className="font-display text-xl uppercase">{c.title}</h2>
            <p className="mt-2 text-sm text-muted">{c.text}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
