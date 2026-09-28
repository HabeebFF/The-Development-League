import type { Metadata } from "next";
import { notFound } from "next/navigation";

import PlotLoader from "./PlotLoader";

export const metadata: Metadata = { title: "Plot rotations" };

export default async function PlotPage({ params }: PageProps<"/staff/matches/[id]/plot">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return <PlotLoader matchId={Number(id)} />;
}
