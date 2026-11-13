import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import ShopView from "@/components/predict/ShopView";

export const metadata: Metadata = { title: "Card shop" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="Spend your DC" title="Card shop" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <ShopView />
      </section>
    </>
  );
}
