"use client";

import UidRequests from "@/components/staff/UidRequests";

export default function StaffUid() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Game UIDs</h1>
      <p className="mt-2 text-sm text-muted">
        When someone gives their in-game UID at sign-up, their account is linked to that player straight away, so they show as that player and can&apos;t
        predict on their own team. Only a UID another account already has waits here for you. Unlink anyone who gave a UID that isn&apos;t theirs.
      </p>
      <UidRequests />
    </section>
  );
}
