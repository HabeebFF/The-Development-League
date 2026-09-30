import type { Metadata } from "next";
import { notFound } from "next/navigation";

import RotationsLoader from "./RotationsLoader";

export const metadata: Metadata = { title: "Rotations" };

export default async function TeamRotationsPage({ params }: PageProps<"/team/matches/[id]/rotations">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return <RotationsLoader matchId={Number(id)} />;
}
