// Protection Points (``/protection-points``): the table, the day's tasks and each team's story.

import type { TeamRef } from "./api";

export type PPPeriod = { id: number; name: string; starts_on: string; ends_on: string };

export type PPRule = "ZONE_ALIVE" | "BOOYAH" | "DAY_POINTS" | "DAY_KILLS" | "PLACEMENT" | "MANUAL";

export type PPTask = {
  id: number;
  date: string;
  title: string;
  rule: PPRule;
  params: { zone?: number; min_matches?: number; once?: boolean; op?: Op; value?: number; top?: number };
  pp_done: number;
  pp_not_done: number;
  is_published: boolean;
};

export type Op = "lt" | "lte" | "gt" | "gte";

export type PPRow = { rank: number; team: TeamRef; pp: number; start: number; tasks: number; adjusted: number };

export type PPTable = { period: PPPeriod | null; periods: PPPeriod[]; rows: PPRow[]; tasks: PPTask[]; text: string };

export type PPEvidence = { match: number; label: string; ok: boolean | null; note: string };

export type PPResult = {
  id: number;
  team: TeamRef;
  /** Staff's tick if there is one, else the logs'. null: not decided yet (manual tasks). */
  done: boolean | null;
  auto_done: boolean | null;
  override: boolean | null;
  note: string;
  count: number;
  detail: string;
  evidence: PPEvidence[];
  matches: number;
  pp: number;
};

export type PPTeam = {
  team: TeamRef;
  period: PPPeriod;
  pp: number;
  adjustments: { kind: "START" | "ADJUST"; date: string; pp: number; reason: string }[];
  tasks: (PPTask & { result: PPResult })[];
};

/** "+2", "0", "-1". */
export function signed(n: number): string {
  return n > 0 ? `+${n}` : String(n);
}

/** Positive, zero and negative groups, as the league posts them. */
export function groups(rows: PPRow[]) {
  return [
    { key: "up", title: "Positive", rows: rows.filter((r) => r.pp > 0) },
    { key: "zero", title: "Zero", rows: rows.filter((r) => r.pp === 0) },
    { key: "down", title: "Negative", rows: rows.filter((r) => r.pp < 0) },
  ].filter((g) => g.rows.length > 0);
}

const OP_WORDS: Record<Op, string> = { lt: "less than", lte: "at most", gt: "more than", gte: "at least" };

/** What the site checks, in plain words. */
export function ruleText(t: Pick<PPTask, "rule" | "params">): string {
  const p = t.params;
  switch (t.rule) {
    case "ZONE_ALIVE":
      return `Every player alive when zone ${p.zone} appears, in at least ${p.min_matches} match${p.min_matches === 1 ? "" : "es"}`;
    case "BOOYAH":
      return p.once ? "At least one booyah" : "Each booyah counts";
    case "DAY_POINTS":
      return `${OP_WORDS[p.op ?? "gte"]} ${p.value} points for the day`.replace(/^./, (c) => c.toUpperCase());
    case "DAY_KILLS":
      return `${OP_WORDS[p.op ?? "gte"]} ${p.value} kills for the day`.replace(/^./, (c) => c.toUpperCase());
    case "PLACEMENT":
      return `Top ${p.top} in at least ${p.min_matches} match${p.min_matches === 1 ? "" : "es"}`;
    default:
      return "Staff check this one";
  }
}

/** The reward line: "+1 PP · -1 PP if not done", "+2 PP each". */
export function rewardText(t: Pick<PPTask, "rule" | "params" | "pp_done" | "pp_not_done">): string {
  const each = t.rule === "BOOYAH" && !t.params.once ? " each" : "";
  const parts = [`${signed(t.pp_done)} PP${each}`];
  if (t.pp_not_done) parts.push(`${signed(t.pp_not_done)} PP if not done`);
  return parts.join(" · ");
}

/** "12 – 25 Oct". */
export function periodRange(p: Pick<PPPeriod, "starts_on" | "ends_on">): string {
  const day = (iso: string) => new Date(`${iso}T00:00:00`);
  const a = day(p.starts_on);
  const b = day(p.ends_on);
  const from = a.toLocaleDateString("en-GB", a.getMonth() === b.getMonth() ? { day: "numeric" } : { day: "numeric", month: "short" });
  return `${from} – ${b.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
}

/** How a team did, in words that fit the task: a penalty task is "Penalty" or "Safe". */
export function outcome(t: Pick<PPTask, "pp_done">, done: boolean | null): string {
  if (done === null) return "Waiting for staff";
  if (t.pp_done < 0) return done ? "Penalty" : "Safe";
  return done ? "Done" : "Not done";
}

export type LedgerLine =
  | { kind: "task"; date: string; pp: number; total: number; task: PPTeam["tasks"][number] }
  | { kind: "START" | "ADJUST"; date: string; pp: number; total: number; reason: string };

/**
 * A team's period as a ledger: starting PP first, then every task and staff adjustment by date,
 * each with the running total after it.
 */
export function ppLedger(team: Pick<PPTeam, "tasks" | "adjustments">): LedgerLine[] {
  type Entry = { kind: "task" | "START" | "ADJUST"; date: string; pp: number; order: number; task?: PPTeam["tasks"][number]; reason?: string };
  const entries: Entry[] = [
    ...team.adjustments.map((a, i) => ({ kind: a.kind, date: a.date, pp: a.pp, reason: a.reason, order: a.kind === "START" ? -1 : 1000 + i })),
    ...team.tasks.map((t, i) => ({ kind: "task" as const, date: t.date, pp: t.result.pp, task: t, order: i })),
  ];
  entries.sort((a, b) => (a.kind === "START" ? -1 : 0) - (b.kind === "START" ? -1 : 0) || a.date.localeCompare(b.date) || a.order - b.order);
  let total = 0;
  return entries.map((e) => {
    total += e.pp;
    return e.kind === "task"
      ? { kind: "task", date: e.date, pp: e.pp, total, task: e.task! }
      : { kind: e.kind, date: e.date, pp: e.pp, total, reason: e.reason ?? "" };
  });
}
