import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import StandingsView from "@/components/league/StandingsView";

export const metadata: Metadata = { title: "Standings" };

export default function StandingsPage() {
  return (
    <>
      <PageHeader eyebrow="Latest match day" title="Standings" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <StandingsView />
      </section>
    </>
  );
}
