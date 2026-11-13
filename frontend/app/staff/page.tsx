"use client";

import Link from "next/link";

import { useStaff } from "./StaffGate";

export default function StaffHome() {
  const me = useStaff();
  const cards = [
    { href: "/staff/upload", title: "Upload matches", text: "Send a match day's log files and build the results, rotations and replays." },
    { href: "/staff/matches", title: "Plot rotations", text: "Check each team's auto route, fix it and confirm." },
    { href: "/staff/uid", title: "Game UIDs", text: "Who is linked to which player. UIDs link automatically at sign-up; unlink one that isn't theirs." },
    { href: "/staff/teams", title: "Teams", text: "Name teams, add logos, merge spellings of the same team and invite managers." },
    { href: "/staff/seasons", title: "Seasons", text: "Set up the season and its stages, and move match days into it." },
    { href: "/staff/pp", title: "Protection Points", text: "Each day's tasks, starting PP and adjustments. Teams' PP is worked out from the logs." },
    { href: "/staff/cards", title: "Player cards", text: "Player photos, card roles and how the weekly ratings are weighted." },
    { href: "/staff/ratings", title: "Player ratings", text: "The points behind each player's rating out of 10: kills, knocks, placement, time alive." },
    { href: "/staff/analytics", title: "Analytics", text: "Who is visiting the website: visitors, top pages, where they came from and their devices." },
    { href: "/staff/coach", title: "Coach", text: "Weekly team reports, and what the coach knows: utility, weapons, the zone and named drop spots." },
    { href: "/staff/scrims", title: "Scrims", text: "Who signed up for 8PM and 10PM, add or remove teams for a session, and suspend teams." },
    { href: "/staff/shop", title: "Card shop", text: "Card designs bought with DC: add, price and hide designs, see sales, refund and gift." },
    { href: "/staff/predictions", title: "Predictions", text: "Fixtures, markets and odds, settling from the match result, corrections and coin wallets." },
    ...(me.is_super_admin ? [{ href: "/staff/maps", title: "Map images and calibration", text: "Upload map images and line them up with the game." }] : []),
  ];
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Staff</h1>
      <p className="mt-2 text-sm text-muted">Signed in as {me.email}</p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {cards.map((c) => (
          <Link key={c.href} href={c.href} className="card card-hover p-5">
            <h2 className="font-display text-2xl uppercase">{c.title}</h2>
            <p className="mt-2 text-sm text-muted">{c.text}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
