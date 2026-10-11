import type { Metadata } from "next";

import CardDetail from "@/components/league/CardDetail";

export const metadata: Metadata = { title: "Player card" };

export default async function PlayerCardPage({ params, searchParams }: PageProps<"/cards/[id]">) {
  const { id } = await params;
  const { week } = await searchParams;
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <CardDetail id={id} week={typeof week === "string" ? week : undefined} />
    </section>
  );
}
