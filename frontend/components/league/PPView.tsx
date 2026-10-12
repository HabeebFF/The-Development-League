"use client";

import Link from "next/link";
import { useState } from "react";

import { groups, outcome, periodRange, rewardText, ruleText, signed, type PPRow, type PPTable, type PPTeam } from "@/lib/pp";
import { useApi } from "@/lib/useApi";

import Loading from "./Loading";
import TeamBadge from "./TeamBadge";

const TONE = {
  up: { text: "text-ok", bar: "bg-ok", label: "Positive PP" },
  zero: { text: "text-muted", bar: "bg-muted", label: "Zero PP" },
  down: { text: "text-bad", bar: "bg-bad", label: "Negative PP" },
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
  if (!t.period) return <p className="text-muted">No Protection Points period has started yet.</p>;

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
            className="input w-auto py-1.5 text-sm"
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
          <span className="font-display text-xl uppercase">
            {t.period.name} <span className="text-muted">· {periodRange(t.period)}</span>
          </span>
        )}
        <button className="btn ml-auto px-4 py-1.5 text-sm" onClick={copy}>
          {copied ? "Copied" : "Copy as text"}
        </button>
      </div>

      {t.tasks.length > 0 && (
        <section className="mt-6">
          <h2 className="section-title">Tasks · {dayLabel(t.tasks[0].date)}</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {t.tasks.map((task) => (
              <div key={task.id} className="card relative overflow-hidden p-4">
                <span className="pointer-events-none absolute inset-0 bg-[linear-gradient(160deg,rgb(255_90_31/0.12),transparent_55%)]" />
                <p className="relative font-display text-xl leading-tight uppercase">{task.title}</p>
                <p className="relative mt-1 text-sm text-muted">{ruleText(task)}</p>
                <p className="relative mt-2 text-sm font-semibold text-accent">{rewardText(task)}</p>
                {!task.is_published && <p className="relative mt-1 text-xs text-muted">Hidden from teams</p>}
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mt-8 space-y-6">
        {t.rows.length === 0 && <p className="text-muted">No teams have Protection Points yet.</p>}
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
        <span className="w-6 shrink-0 text-center font-display text-lg text-muted">{row.rank}</span>
        <span className="min-w-0 flex-1">
          <TeamBadge team={row.team} />
        </span>
        <span className={`font-display text-2xl leading-none ${TONE[tone].text}`}>{signed(row.pp)}</span>
        <span className="hidden text-xs text-muted sm:inline">PP</span>
        <button className="btn px-2 py-1 text-xs" onClick={onToggle} aria-expanded={open}>
          {open ? "Hide" : "Why"}
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
  const d = data.data;
  return (
    <div className="space-y-2 border-t border-line bg-panel-2/40 p-3 text-sm sm:px-4">
      {d.tasks.length === 0 && d.adjustments.length === 0 && <p className="text-muted">Nothing yet this period.</p>}
      {d.tasks.map((t) => (
        <div key={t.id} className="flex gap-3">
          <span className={`w-9 shrink-0 text-right font-semibold ${t.result.pp > 0 ? "text-ok" : t.result.pp < 0 ? "text-bad" : "text-muted"}`}>
            {signed(t.result.pp)}
          </span>
          <div className="min-w-0 flex-1">
            <p>
              <span className="font-semibold">{t.title}</span> <span className="text-muted">· {dayLabel(t.date)}</span>
            </p>
            <p className="text-muted">
              {outcome(t, t.result.done)}
              {t.result.detail ? ` · ${t.result.detail}` : ""}
              {t.result.override !== null && t.result.note ? ` · ${t.result.note}` : ""}
            </p>
            {t.result.evidence.length > 0 && (
              <p className="mt-1 flex flex-wrap gap-1">
                {t.result.evidence.map((e) => (
                  <Link
                    key={e.match}
                    href={`/matches/${e.match}`}
                    title={e.note}
                    className={`rounded border px-1.5 py-0.5 text-xs hover:text-white ${
                      e.ok === true ? "border-ok/50 text-ok" : e.ok === false ? "border-bad/50 text-bad" : "border-line text-muted"
                    }`}
                  >
                    {e.label.split(" ").pop()} · {e.note}
                  </Link>
                ))}
              </p>
            )}
          </div>
        </div>
      ))}
      {d.adjustments.map((a, i) => (
        <div key={i} className="flex gap-3">
          <span className={`w-9 shrink-0 text-right font-semibold ${a.pp > 0 ? "text-ok" : a.pp < 0 ? "text-bad" : "text-muted"}`}>{signed(a.pp)}</span>
          <p className="min-w-0 flex-1">
            <span className="font-semibold">{a.kind === "START" ? "Starting PP" : "Staff adjustment"}</span>
            {a.reason && a.kind !== "START" ? <span className="text-muted"> · {a.reason}</span> : null}
          </p>
        </div>
      ))}
    </div>
  );
}
