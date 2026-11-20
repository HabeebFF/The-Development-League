import type { Metadata } from "next";

import ExploreGrid from "@/components/league/ExploreGrid";
import PageHeader from "@/components/league/PageHeader";
import { SECTIONS } from "@/lib/nav";

export const metadata: Metadata = { title: "Players" };

export default function PlayersPage() {
  return (
    <>
      <PageHeader eyebrow="Every player in the league" title="Players">
        Pick what you want to see. Each page has a search box to find one player or team.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <ExploreGrid links={SECTIONS.find((s) => s.key === "players")?.links ?? []} className="lg:grid-cols-2" />
      </section>
    </>
  );
}
