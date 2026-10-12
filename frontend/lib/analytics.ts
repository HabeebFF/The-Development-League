// Visitor analytics: what the tracker sends, and the staff page's data (``/analytics``).

export type Range = "today" | "7d" | "30d" | "90d" | "all";

export const RANGES: { key: Range; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
  { key: "90d", label: "90 days" },
  { key: "all", label: "All time" },
];

export type Count = { name: string; views: number; visitors: number };
export type PageCount = Count & { path: string };

export type Analytics = {
  range: Range;
  start: string;
  end: string;
  totals: { views: number; visitors: number; pages_per_visitor: number; online_now: number; staff_views: number };
  by_day: { date: string; views: number; visitors: number }[];
  hours: { hour: number; views: number }[];
  pages: PageCount[];
  sources: Count[];
  devices: Count[];
  browsers: Count[];
  systems: Count[];
  audience: Count[];
};

export type Hit = { path: string; referrer?: string; ref?: string };

/** One page view for the tracker. The referrer only counts on the first page of a visit. */
export function hitFor(path: string, search: string, referrer: string, first: boolean): Hit {
  const params = new URLSearchParams(search);
  const ref = params.get("ref") ?? params.get("utm_source") ?? "";
  const hit: Hit = { path };
  if (first && referrer) hit.referrer = referrer;
  if (ref) hit.ref = ref;
  return hit;
}

/** "1,234", "12.5k". */
export function compact(n: number): string {
  if (n >= 10000) return `${(n / 1000).toFixed(n >= 100000 ? 0 : 1).replace(/\.0$/, "")}k`;
  return n.toLocaleString("en-GB");
}

/** "Mon 12 Oct". */
export function dayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
}

/** "8pm", "12am". */
export function hourLabel(hour: number): string {
  const h = hour % 12 || 12;
  return `${h}${hour < 12 ? "am" : "pm"}`;
}

const NAMES: Record<string, string> = {
  phone: "Phone",
  tablet: "Tablet",
  desktop: "Computer",
  guest: "Visitors",
  member: "Team members",
};

/** Friendly names for the device and audience codes. */
export function friendly(name: string): string {
  return NAMES[name] ?? name;
}

/** Share of the largest value, as a bar width in percent (never 0 for a non-zero value). */
export function share(value: number, max: number): number {
  if (!max || !value) return 0;
  return Math.max(2, Math.round((value / max) * 100));
}
