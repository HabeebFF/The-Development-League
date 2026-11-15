"use client";

import dynamic from "next/dynamic";

import { useAuth } from "@/components/Auth";
import ReplayLock from "@/components/league/ReplayLock";
import type { ReplayStart } from "@/lib/replay";

// Konva draws on a canvas, so the replay only renders in the browser.
const ReplayViewer = dynamic(() => import("@/components/staff/ReplayViewer"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading the replay...</p>,
});

/** The replay for league team members (they start on their own team); everyone else sees
 * why it's locked. */
export default function ReplayLoader({ matchId, start }: { matchId: number; start: ReplayStart }) {
  const { me, status } = useAuth();
  if (status === "loading") return <p className="p-6 text-muted">Loading the replay...</p>;
  if (!me?.can_watch_replays) return <ReplayLock me={me} backHref={`/matches/${matchId}`} />;
  const team = me?.memberships.find((m) => m.is_active)?.team.slug;
  return (
    <ReplayViewer
      matchId={matchId}
      backHref={`/matches/${matchId}`}
      focusTeams={[start.team, team].filter((s): s is string => !!s)}
      startAt={start.startAt}
    />
  );
}
