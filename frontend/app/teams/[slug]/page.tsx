import type { Metadata } from "next";

import TeamView from "@/components/league/TeamView";

export const metadata: Metadata = { title: "Team" };

export default async function TeamPage({ params }: PageProps<"/teams/[slug]">) {
  const { slug } = await params;
  return (
    <section className="mx-auto max-w-5xl px-4 py-10">
      <TeamView slug={slug} />
    </section>
  );
}
