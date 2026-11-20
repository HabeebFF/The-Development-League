import type { Metadata } from "next";
import Link from "next/link";

import PageHeader from "@/components/league/PageHeader";
import TeamsView from "@/components/league/TeamsView";

export const metadata: Metadata = { title: "Teams" };

export default function TeamsPage() {
  return (
    <>
      <PageHeader eyebrow="The league" title="Teams">
        New team in TDL?{" "}
        <Link href="/create-team" className="text-accent hover:underline">
          Create your team
        </Link>{" "}
        and sign up for scrims.
      </PageHeader>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <TeamsView />
      </section>
    </>
  );
}
