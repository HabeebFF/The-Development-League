import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import RatingsView from "@/components/league/RatingsView";

export const metadata: Metadata = { title: "Player ratings" };

export default async function RatingsPage({ searchParams }: PageProps<"/ratings">) {
  const { date, session } = await searchParams;
  const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : undefined);
  const s = Number(one(session));
  return (
    <>
      <PageHeader eyebrow="Out of 10, like football" title="Player ratings" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <RatingsView date={one(date) ?? null} session={Number.isInteger(s) && s > 0 ? s : null} />
      </section>
    </>
  );
}
