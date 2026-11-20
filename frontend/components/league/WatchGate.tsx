"use client";

import type { ReactNode } from "react";

import type { Me } from "@/lib/api";
import { canWatchMatch } from "@/lib/watch";
import type { MatchDetail } from "@/lib/league";
import { useApi } from "@/lib/useApi";

import ReplayLock from "./ReplayLock";

/** Replays and rotations of a match are for the teams that played it, plus staff and teams
 * staff allowed to watch every match (SCRIM-VIEWING). Everyone else sees why it's locked. */
export default function WatchGate({
  matchId,
  me,
  backHref,
  loading,
  children,
}: {
  matchId: number;
  me: Me | null;
  backHref: string;
  loading: string;
  children: ReactNode;
}) {
  const everyMatch = !!me?.can_watch_replays && me.scrim_team_ids === null;
  // Only look the match up when the answer depends on which teams played it.
  const match = useApi<MatchDetail>(me?.can_watch_replays && !everyMatch ? `/matches/${matchId}` : null);
  if (!me?.can_watch_replays) return <ReplayLock me={me} backHref={backHref} />;
  if (everyMatch) return <>{children}</>;
  if (match.error) return <p className="p-6 text-bad">{match.error}</p>;
  if (!match.data) return <p className="p-6 text-muted">{loading}</p>;
  const teams = match.data.results.map((r) => r.team.id);
  if (!canWatchMatch(me, teams)) return <ReplayLock me={me} backHref={backHref} notTheirMatch />;
  return <>{children}</>;
}
