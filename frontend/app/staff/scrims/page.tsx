"use client";

import ScrimsManager from "@/components/staff/ScrimsManager";

export default function StaffScrims() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Scrims</h1>
      <p className="mt-2 text-sm text-muted">
        Teams sign up for 8PM and 10PM from 12:01pm on scrim days. Add or remove a team for any session, suspend teams, and change the sign-up
        times. Predictions use the teams playing once sign-up closes.
      </p>
      <ScrimsManager />
    </section>
  );
}
