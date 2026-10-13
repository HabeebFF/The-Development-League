"use client";

import RatingSettings from "@/components/staff/RatingSettings";

export default function StaffRatings() {
  return (
    <section className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Player ratings</h1>
      <p className="mt-2 text-sm text-muted">
        Every player gets a rating out of 10 for each match, and a daily rating that is the average of their matches that day. These are the points
        behind it. The defaults were tuned on 41 league matches so a normal match is about 6.5 and 10.0 is rare.
      </p>
      <RatingSettings />
    </section>
  );
}
