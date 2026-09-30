"use client";

import dynamic from "next/dynamic";

import { useTeam } from "@/app/team/TeamGate";

const RotationsView = dynamic(() => import("@/components/team/RotationsView"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading rotations...</p>,
});

export default function RotationsLoader({ matchId }: { matchId: number }) {
  const { membership } = useTeam();
  return <RotationsView matchId={matchId} focusTeam={membership?.team.slug ?? null} />;
}
