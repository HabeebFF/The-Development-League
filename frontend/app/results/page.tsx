import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import ResultsView from "@/components/league/ResultsView";

export const metadata: Metadata = { title: "Results" };

export default function ResultsPage() {
  return (
    <>
      <PageHeader eyebrow="Every match day" title="Results" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <ResultsView />
      </section>
    </>
  );
}
