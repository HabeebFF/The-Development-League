import type { Metadata } from "next";

import AcceptInvite from "./AcceptInvite";

export const metadata: Metadata = { title: "Join your team" };

export default async function InvitePage({ params }: PageProps<"/invite/[token]">) {
  const { token } = await params;
  return (
    <section className="mx-auto max-w-sm px-4 py-16">
      <AcceptInvite token={token} />
    </section>
  );
}
