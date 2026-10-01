import type { Metadata } from "next";

import UploadMatches from "@/components/staff/UploadMatches";

export const metadata: Metadata = { title: "Upload matches" };

export default function UploadPage() {
  return <UploadMatches />;
}
