import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import PredictHome from "@/components/predict/PredictHome";
import ScrimLobby from "@/components/scrims/ScrimLobby";

export const metadata: Metadata = { title: "Predictions" };

export default function PredictPage() {
  return (
    <>
      <PageHeader eyebrow="Development Coins" title="Predictions">
        Pick who gets Booyah, who finishes higher and more, with free DC.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <PredictHome />
        <div className="mt-10">
          <ScrimLobby />
        </div>
      </section>
    </>
  );
}
