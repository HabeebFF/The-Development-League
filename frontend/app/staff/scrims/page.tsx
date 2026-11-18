"use client";

import ScrimsManager from "@/components/staff/ScrimsManager";

export default function StaffScrims() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Scrims</h1>
      <p className="mt-2 text-sm text-muted">
        Teams sign up for 8PM and 10PM from 8:00pm the night before, paying the sign-up fee. Add, invite or remove a team for any session,
        suspend teams, and change the sign-up times and fee. Predictions use the teams playing as soon as a session is full, or once sign-up
        closes.
      </p>
      <ScrimsManager />
    </section>
  );
}
