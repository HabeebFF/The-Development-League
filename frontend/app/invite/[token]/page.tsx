import type { Metadata } from "next";

import AuthShell from "@/components/ui/AuthShell";

import AcceptInvite from "./AcceptInvite";

export const metadata: Metadata = { title: "Join your team" };

export default async function InvitePage({ params }: PageProps<"/invite/[token]">) {
  const { token } = await params;
  return (
    <AuthShell>
      <AcceptInvite token={token} />
    </AuthShell>
  );
}
