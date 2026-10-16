"use client";

import PredictionsManager from "@/components/staff/PredictionsManager";

export default function StaffPredictions() {
  return (
    <section className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Predictions</h1>
      <p className="mt-2 text-sm text-muted">
        Plan fixtures, open markets with odds, then settle them from the uploaded match. Coins are free play only: no money in or out.
      </p>
      <PredictionsManager />
    </section>
  );
}
