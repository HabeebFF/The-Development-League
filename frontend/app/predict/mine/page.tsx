import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";
import MyBets from "@/components/predict/MyBets";

export const metadata: Metadata = { title: "My predictions" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="Predictions" title="My predictions" />
      <section className="mx-auto max-w-6xl px-4 py-8">
        <MyBets />
      </section>
    </>
  );
}
