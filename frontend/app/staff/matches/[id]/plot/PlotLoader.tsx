"use client";

import dynamic from "next/dynamic";

// Konva draws on a canvas, so the tool only renders in the browser.
const PlottingTool = dynamic(() => import("@/components/staff/PlottingTool"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading the plotting tool...</p>,
});

export default function PlotLoader({ matchId }: { matchId: number }) {
  return <PlottingTool matchId={matchId} />;
}
