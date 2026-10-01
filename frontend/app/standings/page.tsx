import type { Metadata } from "next";

import StandingsView from "@/components/league/StandingsView";

export const metadata: Metadata = { title: "Standings" };

export default function StandingsPage() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-4xl uppercase">Standings</h1>
      <div className="mt-6">
        <StandingsView />
      </div>
    </section>
  );
}
