import type { Metadata } from "next";

import TeamsView from "@/components/league/TeamsView";

export const metadata: Metadata = { title: "Teams" };

export default function TeamsPage() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-4xl uppercase">Teams</h1>
      <div className="mt-6">
        <TeamsView />
      </div>
    </section>
  );
}
