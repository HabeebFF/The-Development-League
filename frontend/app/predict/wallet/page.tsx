import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import WalletView from "@/components/predict/WalletView";

export const metadata: Metadata = { title: "My coins" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="Predictions" title="My coins" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <WalletView />
      </section>
    </>
  );
}
