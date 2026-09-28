"use client";

import dynamic from "next/dynamic";

// Konva draws on a canvas, so the replay only renders in the browser.
const ReplayViewer = dynamic(() => import("@/components/staff/ReplayViewer"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading the replay...</p>,
});

export default function ReplayLoader({ matchId }: { matchId: number }) {
  return <ReplayViewer matchId={matchId} />;
}
