import type { Metadata } from "next";

import CalibrateLoader from "./CalibrateLoader";

export const metadata: Metadata = { title: "Calibrate map" };

export default async function CalibratePage({ params }: PageProps<"/staff/maps/[slug]/calibrate">) {
  const { slug } = await params;
  return <CalibrateLoader slug={slug} />;
}
