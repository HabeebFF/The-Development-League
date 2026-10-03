"use client";

import dynamic from "next/dynamic";

import { useAuth } from "@/components/Auth";

const RotationsView = dynamic(() => import("@/components/team/RotationsView"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading rotations...</p>,
});

/** The public rotations map: a signed-in player starts on their own team. */
export default function RotationsLoader({ matchId }: { matchId: number }) {
  const { me } = useAuth();
  const team = me?.memberships.find((m) => m.is_active)?.team.slug ?? null;
  return <RotationsView matchId={matchId} backHref={`/matches/${matchId}`} focusTeam={team} />;
}
