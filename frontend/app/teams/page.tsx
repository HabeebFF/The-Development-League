import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import TeamsView from "@/components/league/TeamsView";

export const metadata: Metadata = { title: "Teams" };

export default function TeamsPage() {
  return (
    <>
      <PageHeader eyebrow="The league" title="Teams" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <TeamsView />
      </section>
    </>
  );
}
