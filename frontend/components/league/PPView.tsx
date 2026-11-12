"use client";

import Link from "next/link";
import { useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import { groups, outcome, periodRange, ppLedger, rewardText, ruleText, signed, type PPRow, type PPTable, type PPTeam } from "@/lib/pp";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import TeamBadge from "./TeamBadge";

const TONE = {
  up: { text: "text-up", bar: "bg-up", label: "Positive PP" },
  zero: { text: "text-muted", bar: "bg-muted", label: "Zero PP" },
  down: { text: "text-down", bar: "bg-down", label: "Negative PP" },
} as const;

function dayLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" });
}

/** The Protection Points table in three groups, the latest day's tasks, and each team's story. */
export default function PPView() {
  const [period, setPeriod] = useState<number | null>(null);
  const data = useApi<PPTable>(`/pp${period ? `?period=${period}` : ""}`);
  const [open, setOpen] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (!data.data) return <Loading error={data.error} count={8} />;
  const t = data.data;
  if (!t.period) return <EmptyState title="No period yet">No Protection Points period has started yet.</EmptyState>;

  async function copy() {
    try {
      await navigator.clipboard.writeText(t.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {t.periods.length > 1 ? (
          <select
            className="input w-full sm:w-auto"
            value={t.period.id}
            onChange={(e) => setPeriod(Number(e.target.value))}
            aria-label="Period"
          >
            {t.periods.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({periodRange(p)})
              </option>
            ))}
          </select>
        ) : (
          <span className="font-display text-2xl font-extrabold uppercase">
            {t.period.name} <span className="text-muted">· {periodRange(t.period)}</span>
          </span>
        )}
        <button className="btn btn-ghost sm:ml-auto" onClick={copy}>
          {copied ? "Copied" : "Copy as text"}
        </button>
      </div>

      {t.tasks.length > 0 && (
        <section className="mt-6">
          <h2 className="section-title">Tasks · {dayLabel(t.tasks[0].date)}</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {t.tasks.map((task) => (
              <div key={task.id} className="card relative overflow-hidden border-t-4 border-lion p-4">
                <span className="pointer-events-none absolute inset-0 bg-[linear-gradient(160deg,rgb(245_165_36/0.12),transparent_55%)]" />
                <p className="relative font-display text-xl leading-tight font-extrabold uppercase">{task.title}</p>
                <p className="relative mt-1 text-sm text-muted">{ruleText(task)}</p>
                <p className="relative mt-2 text-sm font-semibold text-accent">{rewardText(task)}</p>
                {!task.is_published && <p className="relative mt-1 text-xs text-muted">Hidden from teams</p>}
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mt-8 space-y-6">
        {t.rows.length === 0 && <EmptyState title="No points yet">No teams have Protection Points yet.</EmptyState>}
        {groups(t.rows).map((g) => (
          <div key={g.key}>
            <h2 className={`text-xs font-bold tracking-widest uppercase ${TONE[g.key as keyof typeof TONE].text}`}>
              {TONE[g.key as keyof typeof TONE].label} · {g.rows.length} {g.rows.length === 1 ? "team" : "teams"}
            </h2>
            <ol className="mt-2 space-y-1.5">
              {g.rows.map((r) => (
                <TeamLine
                  key={r.team.id}
                  row={r}
                  tone={g.key as keyof typeof TONE}
                  period={t.period!.id}
                  open={open === r.team.slug}
                  onToggle={() => setOpen(open === r.team.slug ? null : r.team.slug)}
                />
              ))}
            </ol>
          </div>
        ))}
      </section>
      <p className="mt-8 text-xs text-muted">
        Teams gain or lose Protection Points from each day&apos;s tasks. Most tasks are checked from the match logs as soon as a day is uploaded. Tap a
        team to see how it got its points.
      </p>
    </>
  );
}

function TeamLine({
  row,
  tone,
  period,
  open,
  onToggle,
}: {
  row: PPRow;
  tone: keyof typeof TONE;
  period: number;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <li className="card overflow-hidden">
      <div className="flex items-center gap-3 px-3 py-2.5 sm:px-4">
        <span className={`h-8 w-1 shrink-0 ${TONE[tone].bar}`} aria-hidden />
        <span className="w-7 shrink-0 text-center font-display text-xl font-black text-muted">{row.rank}</span>
        <span className="min-w-0 flex-1">
          <TeamBadge team={row.team} />
        </span>
        <span className={`num text-3xl leading-none ${TONE[tone].text}`}>{signed(row.pp)}</span>
        <span className="hidden text-xs text-muted sm:inline">PP</span>
        <button className="btn btn-ghost min-h-11 px-3 text-xs" onClick={onToggle} aria-expanded={open}>
          {open ? "Hide" : "Ledger"}
        </button>
      </div>
      {open && <TeamStory slug={row.team.slug} period={period} />}
    </li>
  );
}

function TeamStory({ slug, period }: { slug: string; period: number }) {
  const data = useApi<PPTeam>(`/pp/teams/${encodeURIComponent(slug)}?period=${period}`);
  if (!data.data)
    return (
      <div className="border-t border-line p-3">
        <Loading error={data.error} count={2} />
      </div>
    );
  const lines = ppLedger(data.data);
  const tone = (n: number) => (n > 0 ? "text-up" : n < 0 ? "text-down" : "text-muted");
  return (
    <div className="border-t border-line bg-panel-2/40 text-sm">
      {lines.length === 0 ? (
        <p className="p-3 text-muted sm:px-4">Nothing yet this period.</p>
      ) : (
        <ol>
          <li aria-hidden className="hidden grid-cols-[3.5rem_1fr_3.5rem] gap-3 px-3 pt-2 text-[10px] font-bold tracking-[0.16em] text-muted uppercase sm:grid sm:px-4">
            <span className="text-right">PP</span>
            <span>Task</span>
            <span className="text-right">Total</span>
          </li>
          {lines.map((l, i) => (
            <li key={i} className="grid grid-cols-[3rem_1fr_3rem] gap-3 border-b border-line/60 px-3 py-2.5 last:border-0 sm:grid-cols-[3.5rem_1fr_3.5rem] sm:px-4">
              <span className={`num text-right text-lg leading-tight ${tone(l.pp)}`}>{signed(l.pp)}</span>
              <div className="min-w-0">
                {l.kind === "task" ? (
                  <>
                    <p>
                      <span className="font-semibold">{l.task.title}</span> <span className="text-muted">· {dayLabel(l.date)}</span>
                    </p>
                    <p className="text-muted">
                      {outcome(l.task, l.task.result.done)}
                      {l.task.result.detail ? ` · ${l.task.result.detail}` : ""}
                      {l.task.result.override !== null && l.task.result.note ? ` · ${l.task.result.note}` : ""}
                    </p>
                    {l.task.result.evidence.length > 0 && (
                      <p className="mt-1 flex flex-wrap gap-1">
                        {l.task.result.evidence.map((e) => (
                          <Link
                            key={e.match}
                            href={`/matches/${e.match}`}
                            title={e.note}
                            className={`chip transition-colors hover:text-text ${
                              e.ok === true ? "border-up/50 text-up" : e.ok === false ? "border-down/50 text-down" : ""
                            }`}
                          >
                            {e.label.split(" ").pop()} · {e.note}
                          </Link>
                        ))}
                      </p>
                    )}
                  </>
                ) : (
                  <p>
                    <span className="font-semibold">{l.kind === "START" ? "Starting PP" : "Staff adjustment"}</span>
                    {l.reason && l.kind !== "START" ? <span className="text-muted"> · {l.reason}</span> : null}
                  </p>
                )}
              </div>
              <span className={`num text-right text-lg leading-tight ${tone(l.total)}`} title="Running total">
                {signed(l.total)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
