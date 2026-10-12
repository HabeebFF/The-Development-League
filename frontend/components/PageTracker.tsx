"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { hitFor } from "@/lib/analytics";
import { api } from "@/lib/api";

// The last page sent, so a re-render (or React's dev double run) never counts a page twice.
let lastPath: string | null = null;

/** Counts each page opened for the staff analytics page. No cookies; failures are ignored. */
export default function PageTracker() {
  const path = usePathname();
  useEffect(() => {
    if (!path || path === lastPath) return;
    const first = lastPath === null;
    lastPath = path;
    api("/analytics/hit", { method: "POST", body: hitFor(path, window.location.search, document.referrer, first), retry: false }).catch(() => {});
  }, [path]);
  return null;
}
