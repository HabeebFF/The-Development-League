"use client";

import Link from "next/link";

import { clockTime } from "@/lib/dc";
import { useLivePerks } from "@/lib/dcBoard";

/** On a player's card page: the moment they pinned with DC. */
export default function PinnedMoment({ playerId }: { playerId: number }) {
  const live = useLivePerks();
  const pin = live?.pins[String(playerId)];
  if (!pin) return null;
  return (
    <Link
      href={`/matches/${pin.match_id}`}
      className="card card-hover mt-3 block border-l-[3px] border-accent p-3 text-sm"
    >
      <span className="eyebrow">Pinned moment</span>
      <span className="mt-1 block">
        <b>{pin.label}</b>
        {pin.at_s != null ? ` · at ${clockTime(pin.at_s)}` : ""}
      </span>
      {pin.note && (
        <span className="mt-0.5 block text-muted">
          &ldquo;{pin.note}&rdquo;
        </span>
      )}
    </Link>
  );
}
