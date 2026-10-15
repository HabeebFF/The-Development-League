import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import LeaderboardView from "@/components/predict/LeaderboardView";

export const metadata: Metadata = { title: "Leaderboard" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="Predictions" title="Leaderboard" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <LeaderboardView />
      </section>
    </>
  );
}
