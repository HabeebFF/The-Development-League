import type { Metadata } from "next";

import CreateTeam from "@/components/account/CreateTeam";
import PageHeader from "@/components/league/PageHeader";

export const metadata: Metadata = { title: "Create your team" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="New teams" title="Create your team">
        Add your team and its roster with each player&apos;s UID. TDL staff check it, then you can sign up for scrims and every match you play counts for your team.
      </PageHeader>
      <section className="mx-auto max-w-3xl px-4 py-8">
        <CreateTeam />
      </section>
    </>
  );
}
