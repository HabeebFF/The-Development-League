import type { Metadata } from "next";

import CardDetail from "@/components/league/CardDetail";
import RatingHistory from "@/components/league/RatingHistory";

export const metadata: Metadata = { title: "Player card" };

export default async function PlayerCardPage({ params, searchParams }: PageProps<"/cards/[id]">) {
  const { id } = await params;
  const { week, as, award } = await searchParams;
  const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : undefined);
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <CardDetail id={id} week={one(week)} as={one(as)} award={one(award)} />
      <RatingHistory id={id} />
    </section>
  );
}
