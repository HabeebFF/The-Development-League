"use client";

import PPManager from "@/components/staff/PPManager";

export default function StaffProtectionPoints() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Protection Points</h1>
      <p className="mt-2 text-sm text-muted">
        Set each day&apos;s tasks and the PP they give or take. The site checks every team from the uploaded logs and keeps the public table up to date.
      </p>
      <PPManager />
    </section>
  );
}
