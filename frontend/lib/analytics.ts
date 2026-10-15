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
export type PageCount = Count & { path: string; avg_s: number };
export type ActionCount = { name: string; times: number; people: number };

export type Who = "everyone" | "signed_in" | "guests" | "staff";

export const WHO: { key: Who; label: string }[] = [
  { key: "everyone", label: "Everyone" },
  { key: "signed_in", label: "Signed in" },
  { key: "guests", label: "Not signed in" },
  { key: "staff", label: "Staff" },
];

export type VisitStats = { visits: number; avg_visit_s: number; bounce_rate: number };

export type Analytics = {
  range: Range;
  start: string;
  end: string;
  totals: { views: number; visitors: number; pages_per_visitor: number; online_now: number; staff_views: number; actions: number } & VisitStats;
  by_day: { date: string; views: number; visitors: number }[];
  hours: { hour: number; views: number }[];
  pages: PageCount[];
  sources: Count[];
  devices: Count[];
  browsers: Count[];
  systems: Count[];
  audience: Count[];
  actions: ActionCount[];
};

export type Person = { key: string; name: string; team: string; signed_in: boolean; staff: boolean };

export type DayPerson = Person & {
  device: string;
  browser: string;
  os: string;
  source: string;
  first: string;
  last: string;
  pages: number;
  actions: number;
  seconds: number;
  visits: number;
};

export type DayReport = {
  date: string;
  who: Who;
  totals: { views: number; people: number; signed_in: number; actions: number; seconds: number } & VisitStats;
  hours: { hour: number; views: number; actions: number }[];
  pages: { path: string; name: string; views: number; visitors: number; avg_s: number }[];
  actions: ActionCount[];
  people: DayPerson[];
};

export type TimelineAction = { at: string; name: string; detail: string };
export type TimelinePage = { at: string; path: string; name: string; seconds: number | null; source: string; actions: TimelineAction[] };

export type Timeline = {
  date: string;
  person: Person & { device: string; browser: string; os: string };
  visits: { start: string; seconds: number; pages: TimelinePage[] }[];
};

export type Account = {
  key: string;
  name: string;
  team: string;
  staff: boolean;
  new: boolean;
  pages: number;
  actions: number;
  seconds: number;
  days_active: number;
  last: string;
  by_day: { date: string; pages: number }[];
};

export type ActionsReport = {
  who: Who;
  path: string;
  total: number;
  actions: (ActionCount & { details: { detail: string; times: number }[] })[];
  by_day: { date: string; actions: number }[];
  pages: { path: string; name: string; actions: number }[];
};

const LEAGUE_TZ = "Africa/Lagos";

/** "20:14" in league time. */
export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: LEAGUE_TZ });
}

/** Today's date in league time, as YYYY-MM-DD. */
export function leagueToday(now: Date = new Date()): string {
  return now.toLocaleDateString("en-CA", { timeZone: LEAGUE_TZ });
}

/** The day before or after a YYYY-MM-DD date. */
export function shiftDay(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** "Android phone, Chrome". */
export function deviceLine(p: { device: string; os: string; browser: string }): string {
  const device = p.device === "desktop" ? "computer" : p.device;
  return `${p.os === "Other" ? "" : `${p.os} `}${device}, ${p.browser}`;
}

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
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" }).replace(",", "");
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

// -- What people do on a page ----------------------------------------------------------------

export type Act = { name: string; detail?: string; api?: { method: string; path: string; ok: boolean } };

/** What the tracker can see about a clicked element. */
export type ClickInfo = {
  tag: string; // "button", "a", ...
  label: string; // aria-label, title or visible text
  href?: string | null;
  origin?: string; // this site's origin, to tell links that leave it
  track?: string | null; // data-track: a name chosen in the code
  trackDetail?: string | null;
};

/** What the tracker can see about a changed form control. */
export type ChangeInfo = {
  tag: string; // "select", "input"
  type?: string; // input type
  label: string; // the control's label
  value?: string; // picked option text, search text
  checked?: boolean;
  files?: number;
};

export function clean(text: string | null | undefined, max = 60): string {
  const t = (text ?? "").replace(/\s+/g, " ").trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

/** A click as an action, or null when it isn't worth recording. */
export function describeClick(c: ClickInfo): Act | null {
  const label = clean(c.label);
  if (c.track) return { name: clean(c.track, 80), detail: clean(c.trackDetail ?? label, 120) || undefined };
  if (c.tag === "a") {
    if (!c.href) return null;
    let url: URL;
    try {
      url = new URL(c.href, c.origin);
    } catch {
      return null;
    }
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    if (c.origin && url.origin !== c.origin) return { name: "Opened a link to another site", detail: clean(`${url.host}${url.pathname}`, 120) };
    return { name: label ? `Clicked "${label}"` : "Clicked a link", detail: clean(url.pathname + url.search, 120) };
  }
  return { name: label ? `Pressed "${label}"` : "Pressed a button" };
}

/** A changed select, tick box, slider, search box or file picker as an action. */
export function describeChange(c: ChangeInfo): Act | null {
  const label = clean(c.label, 50);
  if (c.tag === "select") return { name: `Picked "${clean(c.value, 50)}"`, detail: label || undefined };
  switch (c.type) {
    case "checkbox":
    case "radio":
      return { name: `${c.checked ? "Ticked" : "Unticked"} "${label || "an option"}"` };
    case "range":
      return { name: `Moved "${label || "a slider"}"`, detail: clean(c.value, 20) || undefined };
    case "search":
      return c.value ? { name: "Searched", detail: clean(c.value, 40) } : null;
    case "file":
      return c.files ? { name: `Chose ${c.files} file${c.files === 1 ? "" : "s"}`, detail: label || undefined } : null;
    default:
      return null; // typing in text boxes (names, passwords) is never recorded
  }
}

/** "1m 20s", "45s", "2h 05m". */
export function duration(seconds: number | null | undefined): string {
  if (seconds == null) return "–";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}m`;
}

// The page's API writes (saves, sign-ins) are reported by lib/api.ts through this hook.
type ApiListener = (method: string, path: string, ok: boolean) => void;
let apiListener: ApiListener | null = null;

export function onApiWrite(listener: ApiListener | null): void {
  apiListener = listener;
}

export function reportApiWrite(method: string, path: string, ok: boolean): void {
  if (method === "GET" || path.startsWith("/analytics/")) return;
  apiListener?.(method, path, ok);
}
