import type { Metadata } from "next";
import { Suspense } from "react";

import AccountView from "@/components/account/AccountView";
import PageHeader from "@/components/league/PageHeader";

export const metadata: Metadata = { title: "My account" };

export default function Page() {
  return (
    <>
      <PageHeader eyebrow="Your account" title="My account">
        Your name, how you sign in, and whether you play in the league.
      </PageHeader>
      <section className="mx-auto max-w-2xl px-4 py-8">
        <Suspense>
          <AccountView />
        </Suspense>
      </section>
    </>
  );
}
