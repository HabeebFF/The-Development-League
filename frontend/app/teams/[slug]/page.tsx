import type { Metadata } from "next";

import TeamView from "@/components/league/TeamView";

export const metadata: Metadata = { title: "Team" };

export default async function TeamPage({ params }: PageProps<"/teams/[slug]">) {
  const { slug } = await params;
  return <TeamView slug={slug} />;
}
