import type { Metadata } from "next";

import MapsView from "@/components/league/MapsView";
import PageHeader from "@/components/league/PageHeader";

export const metadata: Metadata = { title: "Map leaders" };

export default function MapsPage() {
  return (
    <>
      <PageHeader eyebrow="Top players, teams and weapons on each map" title="Map leaders" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <MapsView />
      </section>
    </>
  );
}
