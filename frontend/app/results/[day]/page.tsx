import type { Metadata } from "next";
import { notFound } from "next/navigation";

import MatchDayView from "@/components/league/MatchDayView";

export const metadata: Metadata = { title: "Match day" };

export default async function MatchDayPage({ params }: PageProps<"/results/[day]">) {
  const { day } = await params;
  if (!/^\d+$/.test(day)) notFound();
  return <MatchDayView id={Number(day)} />;
}
