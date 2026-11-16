"use client";

import Link from "next/link";

import { breakdown, dc, type MyEarnings } from "@/lib/dc";
import { useApi } from "@/lib/useApi";

/** On /account (and the Player shop): DC this player earned by playing, and from which matches. */
export default function MatchEarnings({ compact = false }: { compact?: boolean }) {
  const data = useApi<MyEarnings>("/dc/me");
  const me = data.data;
  if (!me || !me.linked) return null;

  return (
    <div className="card p-4">
      <p className="eyebrow">DC from your matches</p>
      <div className="mt-2 flex flex-wrap items-end gap-x-6 gap-y-2">
        <div>
          <span className="font-display text-3xl text-accent">{dc(me.this_month)}</span>
          <span className="ml-2 text-sm text-muted">this month</span>
        </div>
        <div className="text-sm text-muted">{dc(me.total)} in total</div>
      </div>
      <p className="mt-2 text-xs text-muted">Every match pays for kills, a Booyah, match MVP and just playing. It lands after the upload.</p>
      {!compact && me.latest.length > 0 && (
        <ul className="mt-3 divide-y divide-line border-y border-line text-sm">
          {me.latest.map((e) => (
            <li key={e.match_id} className="flex items-center gap-3 py-2">
              <Link href={`/matches/${e.match_id}`} className="min-w-0 flex-1 truncate hover:text-accent">
                {e.day} · Match {e.number}
                <span className="ml-2 text-muted">{breakdown(e)}</span>
              </Link>
              <span className="font-display text-lg text-accent">+{e.amount.toLocaleString("en-GB")}</span>
            </li>
          ))}
        </ul>
      )}
      {!compact && me.latest.length === 0 && <p className="mt-3 text-sm text-muted">Nothing yet: your next match pays.</p>}
    </div>
  );
}
