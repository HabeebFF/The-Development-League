import type { Metadata } from "next";
import { Suspense } from "react";

import PageHeader from "@/components/league/PageHeader";
import CollectionView from "@/components/shop/CollectionView";

export const metadata: Metadata = { title: "Player shop collection" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="Player shop · players only" title="The collection">
        Card designs only league players can own. Looks only: your numbers never change.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <Suspense>
          <CollectionView />
        </Suspense>
      </section>
    </>
  );
}
