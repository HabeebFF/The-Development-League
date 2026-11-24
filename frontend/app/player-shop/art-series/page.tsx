import type { Metadata } from "next";
import { Suspense } from "react";

import PageHeader from "@/components/league/PageHeader";
import CollectionView from "@/components/shop/CollectionView";
import { ART_SERIES, ART_TIERS, CUP_DESIGNS } from "@/lib/playerDesigns";

export const metadata: Metadata = { title: "Player shop art series" };

// Preview of the 30 art designs before they go on sale.
export default function Page() {
  return (
    <>
      <PageHeader eyebrow="Player shop · players only · new" title="The art series">
        30 new card designs, from 5,000 DC to 10M DC, plus earned TDL Cup cards. Looks only: your numbers never change.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <Suspense>
          <CollectionView designs={[...ART_SERIES, ...CUP_DESIGNS]} tiers={ART_TIERS} photo="/sample-player.svg" />
        </Suspense>
      </section>
    </>
  );
}
