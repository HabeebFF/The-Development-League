import type { Metadata } from "next";

import PerksView from "@/components/dc/PerksView";
import PageHeader from "@/components/league/PageHeader";

export const metadata: Metadata = { title: "Perks" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="League players only · pay with DC" title="Perks">
        Spend the DC you earn from your matches on things people see: your name, your moment, your team&apos;s banner and colours.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <PerksView />
      </section>
    </>
  );
}
