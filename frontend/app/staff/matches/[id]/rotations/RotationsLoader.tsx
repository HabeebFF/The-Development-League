"use client";

import dynamic from "next/dynamic";

const RotationsView = dynamic(() => import("@/components/team/RotationsView"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading rotations...</p>,
});

export default function RotationsLoader({ matchId }: { matchId: number }) {
  return <RotationsView matchId={matchId} focusTeam={null} backHref="/staff/matches" />;
}
