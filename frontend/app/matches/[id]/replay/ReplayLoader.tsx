"use client";

import dynamic from "next/dynamic";

import { useAuth } from "@/components/Auth";
import type { ReplayStart } from "@/lib/replay";

// Konva draws on a canvas, so the replay only renders in the browser.
const ReplayViewer = dynamic(() => import("@/components/staff/ReplayViewer"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading the replay...</p>,
});

/** The public replay: a signed-in player starts on their own team, visitors on everyone. */
export default function ReplayLoader({ matchId, start }: { matchId: number; start: ReplayStart }) {
  const { me } = useAuth();
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
