"use client";

import Link from "next/link";
import { useState } from "react";

import {
  aiWritten,
  factsByTopic,
  progressText,
  STATUS,
  weekLabel,
  type CoachReport,
  type ReportMatch,
  type TaskProgress,
} from "@/lib/coach";
import Advice from "./Advice";

const title = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** One weekly report: tasks with the evidence behind them, what changed, and every fact. */
export default function ReportView({
  report,
  previous,
  matchHref,
}: {
  report: CoachReport;
  /** The week before, so the team sees how last week's tasks went. */
  previous?: CoachReport;
  matchHref: (id: number) => string;
}) {
  const [showFacts, setShowFacts] = useState(false);
  const byId = new Map<number, ReportMatch>(
    report.matches.map((m) => [m.id, m]),
  );
  const groups = factsByTopic(report.facts);

  const chips = (ids: number[]) => (
    <span className="mt-2 flex flex-wrap gap-1">
      {ids.map((id) => (
        <Link
          key={id}
          href={matchHref(id)}
          className="rounded border border-line px-1.5 py-0.5 text-xs text-muted hover:border-accent hover:text-white"
        >
          {byId.get(id)?.label ?? `Match ${id}`}
          {byId.get(id)?.map ? ` · ${title(byId.get(id)!.map)}` : ""}
        </Link>
      ))}
    </span>
  );

  return (
    <div>
      <p className="text-sm text-muted">
        {weekLabel(report.week_start)} · from {report.matches.length} matches
        {report.edited_by ? " · checked by league staff" : ""}
        {aiWritten(report.writer)
          ? " · advice written by AI and checked against your matches"
          : ""}
      </p>

      <h2 className="mt-6 font-display text-2xl uppercase">
        This week&apos;s tasks
      </h2>
      {report.tasks.length === 0 ? (
        <p className="mt-2 text-sm text-muted">
          Nothing stands out in the data yet. A task needs the same pattern in
          at least 3 matches, and most patterns (drops, zones, death spots) are
          counted per map, so they need 3 matches on one map.
        </p>
      ) : (
        <ol className="mt-3 space-y-3">
          {report.tasks.map((t, i) => (
            <li key={i} className="card p-4">
              <p className="flex gap-3 font-medium">
                <span className="font-display text-xl leading-none text-accent">
                  {i + 1}
                </span>
                <span>{t.title}</span>
              </p>
              <Advice task={t} />
              <ul className="mt-2 space-y-1 pl-7 text-sm text-muted">
                {t.why.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
              <div className="pl-7">{chips(t.matches)}</div>
              {report.progress?.[i] && (
                <div className="mt-3 border-t border-line pt-3 pl-7">
                  <Progress p={report.progress[i]!} label="This week" />
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      {previous && previous.tasks.length > 0 && (
        <>
          <h2 className="mt-8 font-display text-2xl uppercase">
            Last week&apos;s tasks
          </h2>
          <p className="mt-1 text-sm text-muted">
            {weekLabel(previous.week_start)}: how you did on each one in that
            week&apos;s matches.
          </p>
          <ul className="mt-3 space-y-2">
            {previous.tasks.map((t, i) => (
              <li key={i} className="card p-3">
                <p className="font-medium">{t.title}</p>
                {previous.progress?.[i] ? (
                  <div className="mt-2">
                    <Progress p={previous.progress[i]!} />
                    {previous.progress[i]!.matches.length > 0 &&
                      chips(previous.progress[i]!.matches)}
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-muted">
                    This one can&apos;t be checked match by match.
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {report.changes.length > 0 && (
        <>
          <h2 className="mt-8 font-display text-2xl uppercase">
            Since last week
          </h2>
          <ul className="mt-3 space-y-2 text-sm">
            {report.changes.map((c) => (
              <li key={c.text} className="flex gap-2">
                <span className={c.better ? "text-ok" : "text-bad"}>
                  {c.better ? "▲" : "▼"}
                </span>
                <span>{c.text}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <button className="btn mt-8" onClick={() => setShowFacts((v) => !v)}>
        {showFacts ? "Hide" : "Show"} everything the data says (
        {report.facts.length})
      </button>
      {showFacts && (
        <div className="mt-4 space-y-6">
          {groups.map((g) => (
            <div key={g.key}>
              <h3 className="text-sm font-semibold text-muted uppercase">
                {g.label}
              </h3>
              <ul className="mt-2 divide-y divide-line card">
                {g.facts.map((f) => (
                  <li key={f.id} className="px-4 py-2 text-sm">
                    {f.text}
                    <span className="ml-2 text-xs text-muted">
                      ({f.n} of {f.of} matches)
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <p className="mt-8 text-xs text-muted">
        Every line here is worked out from your matches; each one links to or
        counts the matches it comes from.
      </p>
    </div>
  );
}

function Progress({ p, label }: { p: TaskProgress; label?: string }) {
  const status = STATUS[p.status];
  const tone =
    status.tone === "ok"
      ? "text-ok"
      : status.tone === "bad"
        ? "text-bad"
        : "text-muted";
  const bar =
    status.tone === "ok"
      ? "bg-ok"
      : status.tone === "bad"
        ? "bg-bad"
        : "bg-line";
  const share = p.of ? Math.round((p.good / p.of) * 100) : 0;
  return (
    <div>
      <p className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span>
          {label && <span className="eyebrow mr-2">{label}</span>}
          {p.target}
        </span>
        <span
          className={`text-xs font-semibold tracking-wide uppercase ${tone}`}
        >
          {status.label}
        </span>
      </p>
      <div className="mt-1 h-1.5 bg-panel-2" aria-hidden>
        <div className={`h-full ${bar}`} style={{ width: `${share}%` }} />
      </div>
      <p className="mt-1 text-xs text-muted">{progressText(p)}</p>
    </div>
  );
}
