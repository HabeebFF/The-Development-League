"use client";

import dynamic from "next/dynamic";

import { useTeam } from "@/app/team/TeamGate";
import ReplayLock from "@/components/league/ReplayLock";
import type { ReplayStart } from "@/lib/replay";

// Konva draws on a canvas, so the replay only renders in the browser.
const ReplayViewer = dynamic(() => import("@/components/staff/ReplayViewer"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading the replay...</p>,
});

export default function ReplayLoader({ matchId, start }: { matchId: number; start: ReplayStart }) {
  const { me, membership } = useTeam();
  if (!me.can_watch_replays) return <ReplayLock me={me} backHref="/team" />;
  return (
    <ReplayViewer
      matchId={matchId}
      backHref="/team"
      focusTeams={[start.team, membership?.team.slug].filter((s): s is string => !!s)}
      startAt={start.startAt}
    />
  );
}
