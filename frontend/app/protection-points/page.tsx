import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import PPView from "@/components/league/PPView";

export const metadata: Metadata = { title: "Protection Points" };

export default function ProtectionPointsPage() {
  return (
    <>
      <PageHeader eyebrow="Daily tasks" title="Protection Points" />
      <section className="mx-auto max-w-4xl px-4 py-8">
        <PPView />
      </section>
    </>
  );
}
