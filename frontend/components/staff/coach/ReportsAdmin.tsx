"use client";

import { useCallback, useEffect, useState } from "react";

import ReportView from "@/components/coach/ReportView";
import { api, ApiError } from "@/lib/api";
import type { CoachReport, CoachTask } from "@/lib/coach";

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

  const load = useCallback(() => {
    api<{ week_start: string; reports: CoachReport[] }>(`/coach/reports?week=${day}`)
      .then(setData)
      .catch((e) => setError(message(e)));
  }, [day]);
  useEffect(load, [load]);

  async function write() {
    setBusy(true);
    setError(null);
    try {
      await api("/coach/reports", { method: "POST", body: { week: day } });
      load();
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
        <div key={i} className="flex gap-2">
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
      ))}
      <button className="btn btn-primary" disabled={!changed} onClick={() => onSave(tasks)}>
        Save tasks
      </button>
    </div>
  );
}
