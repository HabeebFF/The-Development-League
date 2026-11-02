// Player awards for a week or a month (``/awards``).

export type AwardPlayer = {
  /** Null on team awards (Team of the week, Top kill team): the team is the winner. */
  player: string | null;
  player_id?: number | null;
  team: string | null;
  team_slug: string | null;
  team_tag: string;
  team_color: string;
  logo: string | null;
  value: number;
  detail: string;
  matches: number[];
};

export type Award = {
  key: string;
  title: string;
  rule: string;
  top: AwardPlayer[];
  blocked?: string;
  /** Best IGL only: how many league teams staff have marked an IGL for. */
  teams_with_igl?: number;
};

export type Awards = {
  period: "week" | "month";
  start: string;
  end: string;
  matches: number;
  previous: string;
  next: string | null;
  awards: Award[];
  /** Best average rating with enough matches. */
  mvp: Award;
  /** Team of the week/month, Top kill team, Best IGL. */
  team_awards: Award[];
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
  if (key === "player" || key === "kill_team") return one ? "kill" : "kills";
  if (key === "mvp") return "rating";
  if (key === "team") return one ? "point" : "points";
  if (key === "igl") return "pts per match";
  if (key === "rusher") return "rush points";
  if (key === "sniper") return one ? "sniper kill" : "sniper kills";
  return one ? "explosive kill" : "explosive kills";
}

/** A team award won, as listed on the team's page. */
export type Trophy = {
  kind: "week" | "month";
  start: string;
  end: string;
  key: string;
  title: string;
  player: string | null;
  detail: string;
};

/** "MVP 8.0" ratings keep one decimal; counts stay whole. */
export function headline(key: string, value: number): string {
  return key === "mvp" ? value.toFixed(1) : String(value);
}
