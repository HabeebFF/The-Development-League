import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { replayStart } from "@/lib/replay";

import ReplayLoader from "./ReplayLoader";

export const metadata: Metadata = { title: "Live replay" };

export default async function MatchReplayPage({ params, searchParams }: PageProps<"/matches/[id]/replay">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return <ReplayLoader matchId={Number(id)} start={replayStart(await searchParams)} />;
}
