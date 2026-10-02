import type { Metadata } from "next";
import { notFound } from "next/navigation";

import MatchView from "@/components/league/MatchView";

export const metadata: Metadata = { title: "Match result" };

export default async function MatchPage({ params }: PageProps<"/matches/[id]">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return <MatchView id={Number(id)} />;
}
