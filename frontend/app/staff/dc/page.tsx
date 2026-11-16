"use client";

import DcRanksManager from "@/components/staff/DcRanksManager";
import DcSettingsManager from "@/components/staff/DcSettingsManager";

export default function StaffDc() {
  return (
    <section className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">DC for players</h1>
      <p className="mt-2 text-sm text-muted">
        Players earn DC for every match they play, paid automatically after the upload. A re-upload pays or takes back only the difference.
      </p>
      <DcSettingsManager />
      <DcRanksManager />
    </section>
  );
}
