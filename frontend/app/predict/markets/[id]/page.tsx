import type { Metadata } from "next";
import { notFound } from "next/navigation";

import MarketView from "@/components/predict/MarketView";

export const metadata: Metadata = { title: "Prediction market" };

export default async function MarketPage({ params }: PageProps<"/predict/markets/[id]">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <MarketView id={Number(id)} />
    </section>
  );
}
