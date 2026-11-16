"use client";

import Link from "next/link";

import { useLivePerks } from "@/lib/dcBoard";

/** Home page: shoutouts players bought with DC (staff checked), running for a day each. */
export default function Shoutouts() {
  const live = useLivePerks();
  const rows = live?.shoutouts ?? [];
  if (!rows.length) return null;
  return (
    <section aria-label="Shoutouts">
      <div className="card flex items-stretch overflow-hidden">
        <span className="flex shrink-0 items-center bg-accent px-3 font-display text-sm font-extrabold tracking-wide text-black uppercase">
          Shoutouts
        </span>
        <ul className="flex min-w-0 flex-1 snap-x gap-6 overflow-x-auto px-4 py-3 text-sm [scrollbar-width:none]">
          {rows.map((s) => (
            <li key={s.id} className="shrink-0 snap-start whitespace-nowrap">
              <span className="text-white">&ldquo;{s.text}&rdquo;</span>{" "}
              <span className="text-muted">
                &mdash;{" "}
                {s.player_id ? (
                  <Link
                    href={`/cards/${s.player_id}`}
                    className="hover:text-accent"
                  >
                    {s.name}
                  </Link>
                ) : (
                  s.name
                )}
                {s.team ? `, ${s.team}` : ""}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
