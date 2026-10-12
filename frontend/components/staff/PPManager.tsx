"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError, type Paged, type TeamRef } from "@/lib/api";
import { periodRange, rewardText, ruleText, signed, type Op, type PPPeriod, type PPResult, type PPRule, type PPTask } from "@/lib/pp";

type StaffTask = PPTask & { period: number; match_days: number[]; order: number; results: PPResult[] };
type Adjustment = { id: number; period: number; team: number; team_name: string; kind: "START" | "ADJUST"; pp: number; reason: string };
type StartCheck = { matched: { name: string; team: TeamRef; pp: number }[]; missing: string[]; saved: boolean };
type Draft = Omit<PPTask, "id" | "date">;

const RULES: { key: PPRule; label: string }[] = [
  { key: "ZONE_ALIVE", label: "Full squad alive at a zone" },
  { key: "BOOYAH", label: "Booyahs" },
  { key: "DAY_POINTS", label: "Total points for the day" },
  { key: "DAY_KILLS", label: "Kills for the day" },
  { key: "PLACEMENT", label: "Top placements" },
  { key: "MANUAL", label: "Staff tick it" },
];

const PRESETS: { label: string; draft: Draft }[] = [
  {
    label: "Zone 5, 4 of 5 maps",
    draft: { title: "Full squad alive in zone 5 — in 4 out of 5 maps", rule: "ZONE_ALIVE", params: { zone: 5, min_matches: 4 }, pp_done: 1, pp_not_done: -1, is_published: true },
  },
  { label: "Booyah", draft: { title: "Booyah", rule: "BOOYAH", params: { once: false }, pp_done: 2, pp_not_done: 0, is_published: true } },
  {
    label: "Under 45 points",
    draft: { title: "Less than 45 total points", rule: "DAY_POINTS", params: { op: "lt", value: 45 }, pp_done: -1, pp_not_done: 0, is_published: true },
  },
  { label: "Manual", draft: { title: "", rule: "MANUAL", params: {}, pp_done: 1, pp_not_done: 0, is_published: true } },
];

const DEFAULT_PARAMS: Record<PPRule, PPTask["params"]> = {
  ZONE_ALIVE: { zone: 5, min_matches: 4 },
  BOOYAH: { once: false },
  DAY_POINTS: { op: "gte", value: 45 },
  DAY_KILLS: { op: "gte", value: 10 },
  PLACEMENT: { top: 3, min_matches: 2 },
  MANUAL: {},
};

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDays(iso: string, n: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Staff: PP periods, starting PP, each day's tasks with every team's result, and adjustments. */
export default function PPManager() {
  const [periods, setPeriods] = useState<PPPeriod[] | null>(null);
  const [periodId, setPeriodId] = useState<number | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    api<PPPeriod[]>("/admin/pp/periods")
      .then((ps) => {
        setPeriods(ps);
        const now = today();
        setPeriodId((cur) => cur ?? (ps.find((p) => p.starts_on <= now && now <= p.ends_on) ?? ps[0])?.id ?? null);
      })
      .catch((e) => setNote(message(e)));
  }, []);

  const period = periods?.find((p) => p.id === periodId) ?? null;
  if (!periods) return note ? <p className="mt-8 text-bad">{note}</p> : null;

  return (
    <div className="mt-8 space-y-10">
      <section>
        <h2 className="section-title">Period</h2>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {periods.length > 0 && (
            <select className="input w-auto" value={periodId ?? ""} onChange={(e) => setPeriodId(Number(e.target.value))} aria-label="Period">
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({periodRange(p)})
                </option>
              ))}
            </select>
          )}
          <Link href="/protection-points" className="btn px-3 py-2 text-sm">
            See the public page
          </Link>
        </div>
        <NewPeriod
          onMade={(p) => {
            setPeriods([p, ...periods]);
            setPeriodId(p.id);
          }}
        />
      </section>
      {period && (
        <>
          <DayTasks period={period} />
          <Starting period={period} />
          <Adjustments period={period} />
        </>
      )}
    </div>
  );
}

function NewPeriod({ onMade }: { onMade: (p: PPPeriod) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [start, setStart] = useState(today());
  const [end, setEnd] = useState(addDays(today(), 13));
  const [note, setNote] = useState<string | null>(null);
  if (!open)
    return (
      <button className="btn mt-3 px-3 py-1.5 text-sm" onClick={() => setOpen(true)}>
        New period
      </button>
    );
  return (
    <form
      className="card mt-3 flex flex-wrap items-end gap-3 p-4"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          onMade(await api<PPPeriod>("/admin/pp/periods", { method: "POST", body: { name, starts_on: start, ends_on: end } }));
          setOpen(false);
        } catch (err) {
          setNote(message(err));
        }
      }}
    >
      <label className="text-sm">
        Name
        <input className="input mt-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Weeks 41–42" required />
      </label>
      <label className="text-sm">
        Starts
        <input
          type="date"
          className="input mt-1"
          value={start}
          onChange={(e) => {
            setStart(e.target.value);
            setEnd(addDays(e.target.value, 13));
          }}
        />
      </label>
      <label className="text-sm">
        Ends
        <input type="date" className="input mt-1" value={end} onChange={(e) => setEnd(e.target.value)} />
      </label>
      <button className="btn btn-primary px-4 py-2 text-sm">Create</button>
      {note && <p className="w-full text-sm text-bad">{note}</p>}
    </form>
  );
}

function DayTasks({ period }: { period: PPPeriod }) {
  const now = today();
  const [date, setDate] = useState(now >= period.starts_on && now <= period.ends_on ? now : period.starts_on);
  const [tasks, setTasks] = useState<StaffTask[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [copyFrom, setCopyFrom] = useState(addDays(date, -1));

  const [reloads, setReloads] = useState(0);
  useEffect(() => {
    api<StaffTask[]>(`/admin/pp/tasks?date=${date}`)
      .then(setTasks)
      .catch((e) => setNote(message(e)));
  }, [date, reloads]);

  const replace = (t: StaffTask) => setTasks((ts) => (ts ?? []).map((x) => (x.id === t.id ? t : x)));

  return (
    <section>
      <h2 className="section-title">Tasks for a day</h2>
      <p className="mt-2 text-sm text-muted">
        Teams that play that day are checked against the uploaded logs, again whenever the day is re-uploaded. Teams that don&apos;t play get nothing.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="text-sm">
          Day
          <input
            type="date"
            className="input mt-1"
            value={date}
            min={period.starts_on}
            max={period.ends_on}
            onChange={(e) => {
              setDate(e.target.value);
              setCopyFrom(addDays(e.target.value, -1));
            }}
          />
        </label>
        <span className="flex-1" />
        <label className="text-sm">
          Copy tasks from
          <input type="date" className="input mt-1" value={copyFrom} onChange={(e) => setCopyFrom(e.target.value)} />
        </label>
        <button
          className="btn px-3 py-2 text-sm"
          onClick={async () => {
            setNote(null);
            try {
              const made = await api<StaffTask[]>("/admin/pp/tasks/copy", { method: "POST", body: { from: copyFrom, to: date } });
              setNote(made.length ? `Copied ${made.length} task${made.length === 1 ? "" : "s"}.` : "That day had no tasks.");
              setReloads((n) => n + 1);
            } catch (e) {
              setNote(message(e));
            }
          }}
        >
          Copy
        </button>
      </div>
      {note && <p className="mt-2 text-sm text-muted">{note}</p>}
      <div className="mt-4 space-y-4">
        {tasks?.length === 0 && <p className="text-sm text-muted">No tasks for this day yet.</p>}
        {tasks?.map((t) => (
          <TaskCard key={t.id} task={t} onChange={replace} onDelete={() => setTasks((ts) => (ts ?? []).filter((x) => x.id !== t.id))} />
        ))}
      </div>
      <NewTask date={date} onMade={(t) => setTasks((ts) => [...(ts ?? []), t])} />
    </section>
  );
}

function NewTask({ date, onMade }: { date: string; onMade: (t: StaffTask) => void }) {
  const [d, setD] = useState<Draft>(PRESETS[0].draft);
  const [note, setNote] = useState<string | null>(null);
  const num = (v: string) => (v === "" ? 0 : Number(v));
  const p = d.params;
  const setP = (patch: Partial<PPTask["params"]>) => setD({ ...d, params: { ...p, ...patch } });

  return (
    <form
      className="card mt-4 space-y-3 p-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setNote(null);
        try {
          onMade(await api<StaffTask>("/admin/pp/tasks", { method: "POST", body: { ...d, date } }));
          setNote("Added and checked.");
        } catch (err) {
          setNote(message(err));
        }
      }}
    >
      <h3 className="font-display text-xl uppercase">Add a task</h3>
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((x) => (
          <button key={x.label} type="button" className="btn px-3 py-1 text-xs" onClick={() => setD(x.draft)}>
            {x.label}
          </button>
        ))}
      </div>
      <label className="block text-sm">
        Title (as teams see it)
        <input className="input mt-1" value={d.title} onChange={(e) => setD({ ...d, title: e.target.value })} required />
      </label>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Checked by
          <select className="input mt-1" value={d.rule} onChange={(e) => setD({ ...d, rule: e.target.value as PPRule, params: DEFAULT_PARAMS[e.target.value as PPRule] })}>
            {RULES.map((r) => (
              <option key={r.key} value={r.key}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        {d.rule === "ZONE_ALIVE" && (
          <>
            <NumberField label="Zone" value={p.zone} onChange={(v) => setP({ zone: num(v) })} />
            <NumberField label="In at least … matches" value={p.min_matches} onChange={(v) => setP({ min_matches: num(v) })} />
          </>
        )}
        {d.rule === "PLACEMENT" && (
          <>
            <NumberField label="Top" value={p.top} onChange={(v) => setP({ top: num(v) })} />
            <NumberField label="In at least … matches" value={p.min_matches} onChange={(v) => setP({ min_matches: num(v) })} />
          </>
        )}
        {(d.rule === "DAY_POINTS" || d.rule === "DAY_KILLS") && (
          <>
            <label className="text-sm">
              Done when the day is
              <select className="input mt-1" value={p.op} onChange={(e) => setP({ op: e.target.value as Op })}>
                <option value="lt">less than</option>
                <option value="lte">at most</option>
                <option value="gte">at least</option>
                <option value="gt">more than</option>
              </select>
            </label>
            <NumberField label={d.rule === "DAY_POINTS" ? "Points" : "Kills"} value={p.value} onChange={(v) => setP({ value: num(v) })} />
          </>
        )}
        {d.rule === "BOOYAH" && (
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input type="checkbox" checked={!!p.once} onChange={(e) => setP({ once: e.target.checked })} />
            Once only (not per booyah)
          </label>
        )}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <NumberField label="PP if done" value={d.pp_done} signedInput onChange={(v) => setD({ ...d, pp_done: num(v) })} />
        <NumberField label="PP if not done" value={d.pp_not_done} signedInput onChange={(v) => setD({ ...d, pp_not_done: num(v) })} />
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={d.is_published} onChange={(e) => setD({ ...d, is_published: e.target.checked })} />
          Teams can see it
        </label>
      </div>
      <p className="text-xs text-muted">
        {ruleText(d)} · {rewardText(d)}
      </p>
      <button className="btn btn-primary px-4 py-2 text-sm">Add task</button>
      {note && <p className="text-sm text-muted">{note}</p>}
    </form>
  );
}

function NumberField({ label, value, onChange, signedInput = false }: { label: string; value?: number; onChange: (v: string) => void; signedInput?: boolean }) {
  return (
    <label className="text-sm">
      {label}
      <input
        type="number"
        min={signedInput ? undefined : 0}
        className="input mt-1"
        style={{ width: "6rem" }}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function TaskCard({ task, onChange, onDelete }: { task: StaffTask; onChange: (t: StaffTask) => void; onDelete: () => void }) {
  const [note, setNote] = useState<string | null>(null);

  async function act(fn: () => Promise<StaffTask | void>) {
    setNote(null);
    try {
      const t = await fn();
      if (t) onChange(t);
    } catch (e) {
      setNote(message(e));
    }
  }

  async function setResult(r: PPResult, override: boolean | null, why: string) {
    await act(async () => {
      await api("/admin/pp/results", { method: "POST", body: { task: task.id, team: r.team.id, override, note: why } });
      return api<StaffTask>(`/admin/pp/tasks/${task.id}`);
    });
  }

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-display text-xl leading-tight uppercase">{task.title}</p>
          <p className="text-sm text-muted">
            {ruleText(task)} · {rewardText(task)}
          </p>
        </div>
        <label className="flex items-center gap-1.5 text-xs">
          <input
            type="checkbox"
            checked={task.is_published}
            onChange={(e) => act(() => api<StaffTask>(`/admin/pp/tasks/${task.id}`, { method: "PATCH", body: { is_published: e.target.checked } }))}
          />
          Teams can see it
        </label>
        <button className="btn px-2 py-1 text-xs" onClick={() => act(() => api<StaffTask>(`/admin/pp/tasks/${task.id}/recheck`, { method: "POST" }))}>
          Check again
        </button>
        <button
          className="btn px-2 py-1 text-xs"
          onClick={() =>
            confirm(`Delete “${task.title}”? Teams lose or get back the PP it gave.`) &&
            act(async () => {
              await api(`/admin/pp/tasks/${task.id}`, { method: "DELETE" });
              onDelete();
            })
          }
        >
          Delete
        </button>
      </div>
      {note && <p className="mt-2 text-sm text-bad">{note}</p>}
      {task.results.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No uploaded matches for this day yet. Results appear as soon as the day is uploaded.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="table w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">Team</th>
                <th className="text-left">From the logs</th>
                <th className="text-left">Result</th>
                <th className="text-right">PP</th>
              </tr>
            </thead>
            <tbody>
              {task.results.map((r) => (
                <tr key={r.id}>
                  <td className="py-1.5 font-semibold">{r.team.name}</td>
                  <td className="py-1.5 text-muted">{r.detail || (task.rule === "MANUAL" ? "Tick it" : "")}</td>
                  <td className="py-1.5">
                    <select
                      className="input w-auto py-1 text-xs"
                      value={r.override === null ? "auto" : r.override ? "yes" : "no"}
                      onChange={(e) => {
                        const v = e.target.value;
                        const override = v === "auto" ? null : v === "yes";
                        const why = override === null ? "" : (prompt("Why? (teams see this)", r.note) ?? "");
                        setResult(r, override, why);
                      }}
                    >
                      <option value="auto">
                        {task.rule === "MANUAL" ? "Not ticked" : `Logs: ${r.auto_done === null ? "—" : r.auto_done ? "done" : "not done"}`}
                      </option>
                      <option value="yes">Done</option>
                      <option value="no">Not done</option>
                    </select>
                  </td>
                  <td className={`py-1.5 text-right font-semibold ${r.pp > 0 ? "text-ok" : r.pp < 0 ? "text-bad" : "text-muted"}`}>{signed(r.pp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Starting({ period }: { period: PPPeriod }) {
  const [text, setText] = useState("");
  const [check, setCheck] = useState<StartCheck | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function send(dryRun: boolean) {
    setNote(null);
    try {
      const c = await api<StartCheck>(`/admin/pp/periods/${period.id}/starting`, { method: "POST", body: { text, dry_run: dryRun } });
      setCheck(c);
      if (c.saved) setNote(`Saved starting PP for ${c.matched.length} teams.`);
    } catch (e) {
      setNote(message(e));
    }
  }

  return (
    <section>
      <h2 className="section-title">Starting PP</h2>
      <p className="mt-2 text-sm text-muted">
        Paste the table you post (lines like “1. BERSERK GEN — +4 PP”). Saving replaces this period&apos;s starting PP. Check the names first: teams
        the site can&apos;t find are listed so you can fix the spelling.
      </p>
      <textarea className="input mt-3 h-40 font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="mt-2 flex gap-2">
        <button className="btn px-3 py-1.5 text-sm" onClick={() => send(true)} disabled={!text.trim()}>
          Check names
        </button>
        <button className="btn btn-primary px-3 py-1.5 text-sm" onClick={() => send(false)} disabled={!check || check.missing.length > 0}>
          Save starting PP
        </button>
      </div>
      {note && <p className="mt-2 text-sm text-muted">{note}</p>}
      {check && (
        <div className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          {check.missing.map((m) => (
            <p key={m} className="text-bad">
              Not found: {m}
            </p>
          ))}
          {check.matched.map((m) => (
            <p key={m.name}>
              {m.name} <span className="text-muted">→ {m.team.name}</span> <span className="font-semibold">{signed(m.pp)}</span>
            </p>
          ))}
        </div>
      )}
    </section>
  );
}

function Adjustments({ period }: { period: PPPeriod }) {
  const [rows, setRows] = useState<Adjustment[] | null>(null);
  const [teams, setTeams] = useState<TeamRef[]>([]);
  const [team, setTeam] = useState("");
  const [pp, setPp] = useState("1");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    api<Adjustment[]>(`/admin/pp/adjustments?period=${period.id}`)
      .then(setRows)
      .catch((e) => setNote(message(e)));
    api<Paged<TeamRef>>("/teams?page_size=100")
      .then((p) => setTeams(p.results))
      .catch(() => {});
  }, [period.id]);

  const extra = (rows ?? []).filter((r) => r.kind === "ADJUST");
  return (
    <section>
      <h2 className="section-title">Adjustments</h2>
      <p className="mt-2 text-sm text-muted">One-off PP for anything tasks don&apos;t cover. Teams see the reason.</p>
      <form
        className="mt-3 flex flex-wrap items-end gap-2"
        onSubmit={async (e) => {
          e.preventDefault();
          setNote(null);
          try {
            const a = await api<Adjustment>("/admin/pp/adjustments", {
              method: "POST",
              body: { period: period.id, team: Number(team), pp: Number(pp), reason, kind: "ADJUST" },
            });
            setRows([...(rows ?? []), a]);
            setReason("");
          } catch (err) {
            setNote(message(err));
          }
        }}
      >
        <select className="input w-auto" value={team} onChange={(e) => setTeam(e.target.value)} required aria-label="Team">
          <option value="">Team…</option>
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
        <input type="number" className="input" style={{ width: "5rem" }} value={pp} onChange={(e) => setPp(e.target.value)} aria-label="PP" />
        <input className="input min-w-48 flex-1" placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
        <button className="btn btn-primary px-4 py-2 text-sm">Add</button>
      </form>
      {note && <p className="mt-2 text-sm text-bad">{note}</p>}
      <ul className="mt-3 space-y-1 text-sm">
        {extra.map((a) => (
          <li key={a.id} className="flex items-center gap-3">
            <span className={`w-8 text-right font-semibold ${a.pp > 0 ? "text-ok" : "text-bad"}`}>{signed(a.pp)}</span>
            <span className="font-semibold">{a.team_name}</span>
            <span className="flex-1 text-muted">{a.reason}</span>
            <button
              className="btn px-2 py-0.5 text-xs"
              onClick={async () => {
                await api(`/admin/pp/adjustments/${a.id}`, { method: "DELETE" });
                setRows((rows ?? []).filter((x) => x.id !== a.id));
              }}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
