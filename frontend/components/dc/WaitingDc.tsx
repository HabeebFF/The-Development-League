"use client";

import Link from "next/link";

import { dc } from "@/lib/dc";
import { useApi } from "@/lib/useApi";

/** On a player's card: DC they've earned in matches but can't spend until they sign up and link
 * their UID. Shows nothing for linked players (they're paid straight away). */
export default function WaitingDc({ playerId }: { playerId: number }) {
  const data = useApi<{ waiting: Record<string, number> }>("/dc/waiting");
  const amount = data.data?.waiting[String(playerId)];
  if (!amount) return null;
  return (
    <p className="mt-3 border-l-[3px] border-accent bg-panel-2 px-3 py-2 text-sm">
      <b className="text-accent">{dc(amount)} waiting</b> from their matches. Is
      this you?{" "}
      <Link href="/auth/signup" className="underline">
        Sign up
      </Link>{" "}
      and link your UID to claim it.
    </p>
  );
}
