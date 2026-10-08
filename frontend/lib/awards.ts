// Player awards for a week or a month (``/awards``).

export type AwardPlayer = {
  player: string;
  team: string | null;
  team_slug: string | null;
  team_tag: string;
  team_color: string;
  logo: string | null;
  value: number;
  detail: string;
  matches: number[];
};

export type Award = { key: string; title: string; rule: string; top: AwardPlayer[]; blocked?: string };

export type Awards = {
  period: "week" | "month";
  start: string;
  end: string;
  matches: number;
  previous: string;
  next: string | null;
  awards: Award[];
  /** Kills with weapons staff haven't named yet (they can't count for sniper or grenader). */
  unidentified_kills: number;
  kills: number;
};

const day = (iso: string) => new Date(`${iso}T00:00:00`);

/** "6 – 12 Oct" for a week, "October 2026" for a month. */
export function periodLabel(a: Pick<Awards, "period" | "start" | "end">): string {
  const start = day(a.start);
  if (a.period === "month") return start.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
  const end = day(a.end);
  const sameMonth = start.getMonth() === end.getMonth();
  const from = start.toLocaleDateString("en-GB", sameMonth ? { day: "numeric" } : { day: "numeric", month: "short" });
  return `${from} – ${end.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
}

/** What the headline number counts, per award. */
export function unit(key: string, n: number): string {
  const one = n === 1;
  if (key === "player") return one ? "kill" : "kills";
  if (key === "rusher") return "rush points";
  if (key === "sniper") return one ? "sniper kill" : "sniper kills";
  return one ? "explosive kill" : "explosive kills";
}
