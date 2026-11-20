"use client";

import dynamic from "next/dynamic";

import { useAuth } from "@/components/Auth";
import WatchGate from "@/components/league/WatchGate";

const RotationsView = dynamic(() => import("@/components/team/RotationsView"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading rotations...</p>,
});

/** Rotations for the teams that played the match: a player starts on their own team;
 * everyone else sees why it's locked. */
export default function RotationsLoader({ matchId }: { matchId: number }) {
  const { me, status } = useAuth();
  if (status === "loading") return <p className="p-6 text-muted">Loading rotations...</p>;
  const team = me?.memberships.find((m) => m.is_active)?.team.slug ?? null;
  return (
    <WatchGate matchId={matchId} me={me} backHref={`/matches/${matchId}`} loading="Loading rotations...">
      <RotationsView matchId={matchId} backHref={`/matches/${matchId}`} focusTeam={team} />
    </WatchGate>
  );
}
