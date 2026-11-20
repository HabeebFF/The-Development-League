"use client";

import dynamic from "next/dynamic";

import { useTeam } from "@/app/team/TeamGate";
import WatchGate from "@/components/league/WatchGate";

const RotationsView = dynamic(() => import("@/components/team/RotationsView"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading rotations...</p>,
});

export default function RotationsLoader({ matchId }: { matchId: number }) {
  const { me, membership } = useTeam();
  return (
    <WatchGate matchId={matchId} me={me} backHref="/team" loading="Loading rotations...">
      <RotationsView matchId={matchId} focusTeam={membership?.team.slug ?? null} />
    </WatchGate>
  );
}
