import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import PredictHome from "@/components/predict/PredictHome";

export const metadata: Metadata = { title: "Predictions" };

export default function PredictPage() {
  return (
    <>
      <PageHeader eyebrow="Play coins" title="Predictions">
        Pick who gets Booyah, who finishes higher and more, with free coins.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <PredictHome />
      </section>
    </>
  );
}
