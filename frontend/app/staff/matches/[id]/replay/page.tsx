import type { Metadata } from "next";
import { notFound } from "next/navigation";

import ReplayLoader from "./ReplayLoader";

export const metadata: Metadata = { title: "Live replay" };

export default async function ReplayPage({ params }: PageProps<"/staff/matches/[id]/replay">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return <ReplayLoader matchId={Number(id)} />;
}
