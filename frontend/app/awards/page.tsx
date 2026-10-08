import type { Metadata } from "next";

import AwardsView from "@/components/league/AwardsView";
import PageHeader from "@/components/league/PageHeader";

export const metadata: Metadata = { title: "Awards" };

export default function AwardsPage() {
  return (
    <>
      <PageHeader eyebrow="Player awards" title="Awards" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <AwardsView />
      </section>
    </>
  );
}
