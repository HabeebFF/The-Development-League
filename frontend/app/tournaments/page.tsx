import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import TournamentList from "@/components/league/TournamentList";

export const metadata: Metadata = { title: "Tournaments" };

export default function TournamentsPage() {
  return (
    <>
      <PageHeader eyebrow="Cups and finals" title="Tournaments" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <TournamentList />
      </section>
    </>
  );
}
