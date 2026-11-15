"use client";

import TournamentsManager from "@/components/staff/TournamentsManager";

export default function StaffTournaments() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Tournaments</h1>
      <p className="mt-2 text-sm text-muted">
        A cup with its own table and prizes. Matches are uploaded with the normal upload; cash prizes are shown only, DC prizes are paid when you
        confirm.
      </p>
      <TournamentsManager />
    </section>
  );
}
