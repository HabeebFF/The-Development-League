"use client";

import { useCallback, useEffect, useState } from "react";

import ReportView from "@/components/coach/ReportView";
import { api, ApiError } from "@/lib/api";
import { aiWritten, type AiUsage, type CoachReport, type CoachTask } from "@/lib/coach";

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function message(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** Staff: write a week's reports, read each team's, reword or drop tasks, hide a report. */
export default function ReportsAdmin() {
  const [day, setDay] = useState(today());
  const [data, setData] = useState<{ week_start: string; reports: CoachReport[] } | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [usage, setUsage] = useState<AiUsage | null>(null);

  const loadUsage = useCallback(() => {
    api<AiUsage>("/coach/ai-usage")
      .then(setUsage)
      .catch(() => setUsage(null));
  }, []);
  useEffect(loadUsage, [loadUsage]);

  const load = useCallback(() => {
    api<{ week_start: string; reports: CoachReport[] }>(`/coach/reports?week=${day}`)
      .then(setData)
      .catch((e) => setError(message(e)));
  }, [day]);
  useEffect(load, [load]);

  async function write() {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const done = await api<{ written: number; ai_written: number }>("/coach/reports", { method: "POST", body: { week: day } });
      if (usage?.on) setNote(`${done.ai_written} of ${done.written} reports have AI-written advice. The rest keep the rule-based text.`);
      load();
      loadUsage();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  async function save(report: CoachReport, change: Partial<Pick<CoachReport, "tasks" | "is_published">>) {
    setError(null);
    try {
      const updated = await api<CoachReport>(`/coach/reports/${report.id}`, { method: "PATCH", body: change });
      setData((d) => d && { ...d, reports: d.reports.map((r) => (r.id === updated.id ? updated : r)) });
    } catch (e) {
      setError(message(e));
    }
  }

  return (
    <div>
      <p className="text-sm text-muted">
        Reports are written from each team&apos;s matches by fixed rules, so every task names the facts and matches behind it. Writing them again
        refreshes the numbers but keeps any report staff have edited.
      </p>
      {usage && <UsageCard usage={usage} />}
      <div className="mt-4 flex flex-wrap items-end gap-2">
        <label className="text-sm">
          <span className="mb-1 block text-muted">Week containing</span>
          <input type="date" className="input" value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <button className="btn btn-primary" disabled={busy} onClick={write}>
          {busy ? "Writing..." : "Write this week's reports"}
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      {note && <p className="mt-3 text-sm text-muted">{note}</p>}
      {data && data.reports.length === 0 && <p className="mt-4 text-sm text-muted">No reports for this week yet.</p>}
      <ul className="mt-4 space-y-2">
        {data?.reports.map((r) => (
          <li key={r.id} className="card">
            <div className="flex flex-wrap items-center gap-2 px-4 py-3">
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{r.team}</span>
                <span className="text-xs text-muted">
                  {r.tasks.length} {r.tasks.length === 1 ? "task" : "tasks"} · {r.matches.length} matches
                  {r.is_published ? "" : " · hidden from the team"}
                  {r.edited_by ? ` · edited by ${r.edited_by}` : ""}
                  {aiWritten(r.writer) ? " · AI advice" : ""}
                </span>
              </span>
              <button className="btn px-2 py-1 text-xs" onClick={() => setOpen(open === r.id ? null : r.id)}>
                {open === r.id ? "Close" : "Open"}
              </button>
            </div>
            {open === r.id && (
              <div className="border-t border-line p-4">
                <TaskEditor report={r} onSave={(tasks) => save(r, { tasks })} />
                <label className="mt-3 flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={r.is_published} onChange={(e) => save(r, { is_published: e.target.checked })} />
                  Team can see this report
                </label>
                <div className="mt-6 border-t border-line pt-4">
                  <ReportView report={r} matchHref={(id) => `/staff/matches/${id}/rotations`} />
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TaskEditor({ report, onSave }: { report: CoachReport; onSave: (tasks: CoachTask[]) => void }) {
  const [tasks, setTasks] = useState(report.tasks);
  const changed = JSON.stringify(tasks) !== JSON.stringify(report.tasks);
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Tasks (reword or remove; the evidence stays attached)</p>
      {tasks.map((t, i) => (
        <div key={i} className="space-y-1">
          <div className="flex gap-2">
            <input
              className="input"
              value={t.title}
              onChange={(e) => setTasks(tasks.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))}
              aria-label={`Task ${i + 1}`}
            />
            <button className="btn px-2 text-xs text-bad" onClick={() => setTasks(tasks.filter((_, j) => j !== i))}>
              Remove
            </button>
          </div>
          {t.advice !== undefined && (
            <textarea
              className="input min-h-16 text-sm"
              value={t.advice}
              onChange={(e) => setTasks(tasks.map((x, j) => (j === i ? { ...x, advice: e.target.value } : x)))}
              aria-label={`Advice for task ${i + 1}`}
              placeholder="No advice (only the evidence is shown)"
            />
          )}
        </div>
      ))}
      <button className="btn btn-primary" disabled={!changed} onClick={() => onSave(tasks)}>
        Save tasks
      </button>
    </div>
  );
}

/** Whether the AI writer is on, and how much of today's and this month's allowance it has used. */
function UsageCard({ usage }: { usage: AiUsage }) {
  const last = usage.recent[0];
  return (
    <div className="card mt-4 p-4 text-sm">
      <p className="font-medium">
        AI writer: {usage.on ? <span className="text-ok">on</span> : <span className="text-muted">off</span>}
        {usage.on && <span className="text-muted"> · {usage.model}</span>}
      </p>
      {usage.on ? (
        <>
          <p className="mt-1 text-muted">
            Today {usage.today} of {usage.daily_limit} requests (at most {usage.per_minute} a minute)
            {usage.monthly_cap_usd > 0
              ? ` · this month $${usage.month_cost_usd.toFixed(2)} of the $${usage.monthly_cap_usd.toFixed(2)} cap`
              : " · free tier, no spending"}
          </p>
          {usage.blocked && <p className="mt-1 text-bad">{usage.blocked} Reports keep the rule-based text until then.</p>}
          {last && (
            <p className="mt-1 text-xs text-muted">
              Last call {new Date(last.at).toLocaleString()}:{" "}
              {last.ok ? `${last.kept} of ${last.items} items passed the fact check` : `failed (${last.error})`}
            </p>
          )}
        </>
      ) : (
        <p className="mt-1 text-muted">
          Reports use the rule-based text. To turn it on, set COACH_WRITER=gemini and a free Gemini key (GEMINI_API_KEY) in the server&apos;s
          settings.
        </p>
      )}
      <p className="mt-2 text-xs text-muted">
        The AI only rewords tasks the rules already chose. Any sentence with a number or fact it can&apos;t back up from your matches or approved
        coach notes is thrown away and the rule-based text stays.
      </p>
    </div>
  );
}
