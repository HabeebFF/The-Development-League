"use client";

import dynamic from "next/dynamic";

import { useAuth } from "@/components/Auth";
import WatchGate from "@/components/league/WatchGate";
import type { ReplayStart } from "@/lib/replay";

// Konva draws on a canvas, so the replay only renders in the browser.
const ReplayViewer = dynamic(() => import("@/components/staff/ReplayViewer"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading the replay...</p>,
});

/** The replay for the teams that played the match (they start on their own team); everyone
 * else sees why it's locked. */
export default function ReplayLoader({ matchId, start }: { matchId: number; start: ReplayStart }) {
  const { me, status } = useAuth();
  if (status === "loading") return <p className="p-6 text-muted">Loading the replay...</p>;
  const team = me?.memberships.find((m) => m.is_active)?.team.slug;
  return (
    <WatchGate matchId={matchId} me={me} backHref={`/matches/${matchId}`} loading="Loading the replay...">
      <ReplayViewer
        matchId={matchId}
        backHref={`/matches/${matchId}`}
        focusTeams={[start.team, team].filter((s): s is string => !!s)}
        startAt={start.startAt}
      />
    </WatchGate>
  );
}
