"use client";

import UidRequests from "@/components/staff/UidRequests";

export default function StaffUid() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Game UID requests</h1>
      <p className="mt-2 text-sm text-muted">
        People who signed up and gave their in-game UID. Approve to link the account to that player, so they show as that player and can&apos;t predict on their
        own team. Until then they can&apos;t predict at all.
      </p>
      <UidRequests />
    </section>
  );
}
