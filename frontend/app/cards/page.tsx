import type { Metadata } from "next";

import CardsView from "@/components/league/CardsView";
import PageHeader from "@/components/league/PageHeader";

export const metadata: Metadata = { title: "Player cards" };

export default function CardsPage() {
  return (
    <>
      <PageHeader eyebrow="Rated every week" title="Player cards">
        Every player rated 0 to 99 on how they played, updated every Saturday at
        midnight.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <CardsView />
      </section>
    </>
  );
}
