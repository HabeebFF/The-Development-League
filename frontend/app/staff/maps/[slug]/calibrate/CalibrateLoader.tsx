"use client";

import dynamic from "next/dynamic";

const CalibrationTool = dynamic(() => import("@/components/staff/CalibrationTool"), {
  ssr: false,
  loading: () => <p className="p-6 text-muted">Loading the calibration tool...</p>,
});

export default function CalibrateLoader({ slug }: { slug: string }) {
  return <CalibrationTool slug={slug} />;
}
