import type { Metadata } from "next";

import ResultsView from "@/components/league/ResultsView";

export const metadata: Metadata = { title: "Results" };

export default function ResultsPage() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-4xl uppercase">Results</h1>
      <div className="mt-6">
        <ResultsView />
      </div>
    </section>
  );
}
