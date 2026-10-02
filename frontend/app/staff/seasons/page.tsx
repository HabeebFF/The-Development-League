import type { Metadata } from "next";

import SeasonSetup from "@/components/staff/SeasonSetup";

export const metadata: Metadata = { title: "Seasons" };

export default function SeasonsPage() {
  return (
    <section className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Seasons</h1>
      <p className="mt-2 text-sm text-muted">
        The current season is the one fans see on Standings and Results. Rename the test season, or create
        the real one and move its match days into it. Standings update by themselves.
      </p>
      <div className="mt-6">
        <SeasonSetup />
      </div>
    </section>
  );
}
