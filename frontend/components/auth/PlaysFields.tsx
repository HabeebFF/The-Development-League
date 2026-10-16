"use client";

import { useState } from "react";

/** "Do you play in the league?" Players give their game UID, which staff confirm; until then
 * they can't predict, and afterwards never on a match or session their team plays in. */
export default function PlaysFields({ error }: { error?: string }) {
  const [plays, setPlays] = useState(false);
  return (
    <fieldset className="block text-sm">
      <legend className="text-muted">Do you play in the league?</legend>
      <div className="mt-1 flex gap-2">
        {[false, true].map((v) => (
          <label key={String(v)} className={`btn flex-1 cursor-pointer px-3 py-1.5 ${plays === v ? "btn-primary" : "text-muted"}`}>
            <input type="radio" name="plays" value={v ? "yes" : "no"} checked={plays === v} onChange={() => setPlays(v)} className="sr-only" />
            {v ? "Yes, I play" : "No, I'm a fan"}
          </label>
        ))}
      </div>
      {plays && (
        <label className="mt-3 block">
          <span className="text-muted">Your Free Fire UID</span>
          <input name="game_uid" required inputMode="numeric" pattern="[0-9]*" maxLength={20} className="input mt-1" />
          <span className="mt-1 block text-xs text-muted">
            Staff check it and link you to your player and team. Until then you can&apos;t make predictions, and after that never on a match or session your
            team plays in.
          </span>
        </label>
      )}
      {error && <span className="mt-1 block text-xs text-bad">{error}</span>}
    </fieldset>
  );
}
