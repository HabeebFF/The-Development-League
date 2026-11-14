import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import PlayerShopView from "@/components/shop/PlayerShopView";

export const metadata: Metadata = { title: "Player shop" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="League players only · pay with DC" title="Player shop">
        Designs and extras for your own FUT card. Looks only: your numbers never change.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <PlayerShopView />
      </section>
    </>
  );
}
