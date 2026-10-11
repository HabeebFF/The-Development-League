import type { Metadata } from "next";

import KillsView from "@/components/league/KillsView";
import PageHeader from "@/components/league/PageHeader";

export const metadata: Metadata = { title: "Kill list" };

export default function KillsPage() {
  return (
    <>
      <PageHeader eyebrow="Every player's kills" title="Kill list" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <KillsView />
      </section>
    </>
  );
}
