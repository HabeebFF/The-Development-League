import type { Metadata } from "next";

import TournamentView from "@/components/league/TournamentView";

export const metadata: Metadata = { title: "Tournament" };

export default async function TournamentPage({ params }: PageProps<"/tournaments/[slug]">) {
  const { slug } = await params;
  return <TournamentView slug={slug} />;
}
