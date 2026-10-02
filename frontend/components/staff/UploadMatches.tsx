"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { api, ApiError, csrfToken, type Paged } from "@/lib/api";
import {
  chunk,
  daysIn,
  formatBytes,
  inPlayOrder,
  numberFor,
  pickMatchFiles,
  sameDayName,
  sessionsOf,
  type PreviewMatch,
} from "@/lib/upload";

const CHUNK_BYTES = 40 * 1024 * 1024; // per request, so slow connections don't time out
const POLL_MS = 2000;

type BatchStatus = "UPLOADING" | "GROUPING" | "READY" | "PROCESSING" | "DONE" | "FAILED";
type Result = { game_match_id: string; match_id?: number; status: string; error?: string };
type Batch = {
  id: number;
  status: BatchStatus;
  error: string;
  preview: { matches?: PreviewMatch[]; unassigned_files?: unknown[]; results?: Result[] };
};
type Stage = { id: number; season: string; name: string };
type Day = { id: number; stage: number; number: number; date: string | null; title: string };
type Row = { include: boolean; number: number };
/** Where one session's matches go: an existing match day id, or "new" with its details. */
type Plan = { choice: string; title: string; number: string; date: string; stage: string };

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Sends one group of files to the batch, reporting bytes sent. */
function send(batchId: number, files: File[], token: string, onBytes: (n: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/v1/uploads/batches/${batchId}/files`);
    xhr.setRequestHeader("X-CSRFToken", token);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => onBytes(e.loaded);
    xhr.onload = () => {
      if (xhr.status < 300) return resolve();
      let detail = `Upload failed (${xhr.status})`;
      try {
        const data = JSON.parse(xhr.responseText);
        detail = data.detail ?? (data.files ? String(data.files) : detail);
      } catch {}
      reject(new Error(detail));
    };
    xhr.onerror = () => reject(new Error("The connection dropped during the upload. Try again."));
    xhr.send(form);
  });
}

async function waitWhile(batchId: number, busy: BatchStatus[]): Promise<Batch> {
  for (;;) {
    const batch = await api<Batch>(`/uploads/batches/${batchId}`);
    if (!busy.includes(batch.status)) return batch;
    await sleep(POLL_MS);
  }
}

function clockTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "?";
}

/** Staff: upload a match day's log files, check what was found, then build the matches. */
export default function UploadMatches() {
  const [picked, setPicked] = useState<File[]>([]);
  const [days, setDays] = useState<Set<string>>(new Set());
  const [step, setStep] = useState<"pick" | "uploading" | "preview" | "building" | "done">("pick");
  const [progress, setProgress] = useState({ sent: 0, total: 0, label: "" });
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [stages, setStages] = useState<Stage[]>([]);
  const [matchDays, setMatchDays] = useState<Day[]>([]);
  const [plans, setPlans] = useState<Record<string, Plan>>({});
  const [rows, setRows] = useState<Record<string, Row>>({});

  const allDays = useMemo(() => daysIn(picked), [picked]);
  const files = useMemo(() => pickMatchFiles(picked, days), [picked, days]);
  const totalBytes = files.reduce((n, f) => n + f.size, 0);
  // A debugger log covers the whole session (scrims too): only matches with a result
  // file, or already on the site, can be built.
  const all = useMemo(() => inPlayOrder(batch?.preview.matches ?? []), [batch]);
  const matches = all.filter((m) => m.ready);
  const sessions = useMemo(() => sessionsOf(all.filter((m) => m.ready)), [all]);
  const skipped = all.length - matches.length;

  useEffect(() => {
    Promise.all([
      api<Paged<Stage>>("/admin/stages?page_size=100"),
      api<Paged<Day>>("/admin/match-days?page_size=100"),
    ])
      .then(([s, d]) => {
        setStages(s.results);
        setMatchDays(d.results);
      })
      .catch((e) => setError(e.message));
  }, []);

  function choose(list: FileList | null) {
    const all = Array.from(list ?? []);
    setPicked(all);
    const newest = daysIn(all)[0];
    setDays(new Set(newest ? [newest] : []));
    setError(null);
  }

  async function upload() {
    setError(null);
    setStep("uploading");
    try {
      const created = await api<Batch>("/uploads/batches", { method: "POST", body: { note: "Upload page" } });
      const groups = chunk(files, CHUNK_BYTES);
      let done = 0;
      for (const [i, group] of groups.entries()) {
        await api("/me"); // refreshes the sign-in if a long upload outlived it
        const label = `Uploading part ${i + 1} of ${groups.length}`;
        await send(created.id, group, await csrfToken(), (n) => setProgress({ sent: done + n, total: totalBytes, label }));
        done += group.reduce((n, f) => n + f.size, 0);
        setProgress({ sent: done, total: totalBytes, label: "Reading the files" });
        const ready = await waitWhile(created.id, ["GROUPING"]);
        if (ready.status === "FAILED") throw new Error(ready.error || "The server couldn't read these files.");
      }
      const ready = await api<Batch>(`/uploads/batches/${created.id}`);
      setBatch(ready);
      const ordered = inPlayOrder(ready.preview.matches ?? []).filter((m) => m.ready);
      // Each session (the 8pm and 10pm scrims) is its own match day, found by its name
      // ("TDL DAY 12 8PM"), never by number alone.
      const today = new Date().toISOString().slice(0, 10);
      const stage = stages.length ? String(stages[stages.length - 1].id) : "";
      let next = Math.max(0, ...matchDays.map((d) => d.number));
      const plan: Record<string, Plan> = {};
      const numbers: Record<string, number> = {};
      for (const session of sessionsOf(ordered)) {
        const known = session.name ? matchDays.find((d) => sameDayName(d.title, session.name)) : undefined;
        plan[session.key] = known
          ? { choice: String(known.id), title: known.title, number: String(known.number), date: today, stage }
          : { choice: "new", title: session.name, number: String(++next), date: today, stage };
        Object.assign(numbers, numberFor(session.matches, known?.id ?? null));
      }
      setPlans(plan);
      setRows(Object.fromEntries(ordered.map((m) => [m.game_match_id, { include: true, number: numbers[m.game_match_id] }])));
      setStep("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
      setStep("pick");
    }
  }

  async function confirm() {
    if (!batch) return;
    setError(null);
    const chosen = matches.filter((m) => rows[m.game_match_id]?.include);
    if (!chosen.length) return setError("Tick at least one match.");
    for (const session of sessions) {
      const numbers = session.matches.filter((m) => rows[m.game_match_id]?.include).map((m) => rows[m.game_match_id].number);
      if (new Set(numbers).size !== numbers.length) return setError(`${session.name || "A session"}: two matches have the same number.`);
    }
    setStep("building");
    try {
      const assignments = [];
      for (const session of sessions) {
        const picked = session.matches.filter((m) => rows[m.game_match_id]?.include);
        if (!picked.length) continue;
        const plan = plans[session.key];
        let matchDay = Number(plan.choice);
        if (plan.choice === "new") {
          if (!plan.stage || !plan.number || !plan.title.trim()) throw new Error("Give each new match day a name and number.");
          const made = await api<Day>("/admin/match-days", {
            method: "POST",
            body: { stage: Number(plan.stage), number: Number(plan.number), date: plan.date || null, title: plan.title.trim() },
          });
          setMatchDays((d) => [...d, made]);
          setPlans((p) => ({ ...p, [session.key]: { ...plan, choice: String(made.id) } }));
          matchDay = made.id;
        }
        // Matches already on the site move to the chosen day too.
        for (const m of picked)
          assignments.push({ game_match_id: m.game_match_id, match_day: matchDay, number: rows[m.game_match_id].number });
      }
      await api(`/uploads/batches/${batch.id}/confirm`, { method: "POST", body: { matches: assignments } });
      setBatch(await waitWhile(batch.id, ["PROCESSING", "READY"]));
      setStep("done");
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");
      setStep("preview");
    }
  }

  const stageName = (id: number) => {
    const s = stages.find((x) => x.id === id);
    return s ? `${s.season} · ${s.name}` : "";
  };

  return (
    <section className="mx-auto max-w-4xl px-4 py-10">
      <Link href="/staff" className="text-xs text-muted hover:text-text">
        &larr; Staff
      </Link>
      <h1 className="mt-2 font-display text-5xl leading-none font-extrabold uppercase">Upload matches</h1>
      {error && <p className="mt-4 border border-bad/40 bg-bad/10 p-3 text-sm text-bad">{error}</p>}

      {step === "pick" && (
        <div className="mt-6 space-y-6">
          <p className="text-sm text-muted">
            Choose the game&apos;s <span className="text-text">Free Fire_64_Data</span> folder, or pick the files
            yourself. Only match files (MatchResult, ReplayInfo .json and .bin, SafeZone, MatchId) and debugger
            logs are sent.
          </p>
          <div className="flex flex-wrap gap-2">
            <label className="btn btn-primary cursor-pointer">
              Choose folder
              <input
                type="file"
                className="hidden"
                multiple
                {...({ webkitdirectory: "" } as Record<string, string>)}
                onChange={(e) => choose(e.target.files)}
              />
            </label>
            <label className="btn cursor-pointer">
              Choose files
              <input type="file" className="hidden" multiple onChange={(e) => choose(e.target.files)} />
            </label>
          </div>

          {picked.length > 0 && allDays.length === 0 && (
            <p className="text-sm text-bad">None of these files are match logs.</p>
          )}
          {allDays.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-muted uppercase">Which days?</h2>
              <p className="mt-1 text-xs text-muted">
                Files are dated by when the game wrote them. If the match day went past midnight, tick both dates.
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {allDays.map((d) => (
                  <label key={d} className="flex items-center gap-2 border border-line px-3 py-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={days.has(d)}
                      onChange={(e) =>
                        setDays((cur) => {
                          const next = new Set(cur);
                          if (e.target.checked) next.add(d);
                          else next.delete(d);
                          return next;
                        })
                      }
                    />
                    {new Date(`${d}T12:00:00`).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" })}
                    <span className="text-xs text-muted">
                      {(() => {
                        const n = pickMatchFiles(picked, new Set([d])).length;
                        return `${n} ${n === 1 ? "file" : "files"}`;
                      })()}
                    </span>
                  </label>
                ))}
              </div>
              <button className="btn btn-primary mt-4" disabled={!files.length} onClick={upload}>
                Upload {files.length} files ({formatBytes(totalBytes)})
              </button>
            </div>
          )}
        </div>
      )}

      {step === "uploading" && (
        <div className="mt-8">
          <p className="text-sm">{progress.label || "Starting..."}</p>
          <div className="mt-2 h-2 overflow-hidden bg-panel-2">
            <div
              className="h-full bg-accent transition-all"
              style={{ width: `${progress.total ? Math.min(100, (100 * progress.sent) / progress.total) : 0}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-muted">
            {formatBytes(progress.sent)} of {formatBytes(progress.total)}. Keep this page open.
          </p>
        </div>
      )}

      {(step === "preview" || step === "building") && batch && (
        <div className="mt-6 space-y-6">
          <p className="text-sm text-muted">
            Found {matches.length} {matches.length === 1 ? "match" : "matches"}, in the order they were played. Untick
            any you don&apos;t want, check the numbers, then confirm.
            {skipped > 0 &&
              ` ${skipped} other ${skipped === 1 ? "game" : "games"} in the debugger log had no result file and ${skipped === 1 ? "was" : "were"} left out.`}
          </p>

          {sessions.map((session) => {
            const plan = plans[session.key];
            if (!plan) return null;
            const setPlan = (patch: Partial<Plan>) => setPlans((p) => ({ ...p, [session.key]: { ...plan, ...patch } }));
            return (
              <div key={session.key} className="space-y-3">
                <div className="card p-4">
                  <h2 className="text-sm font-semibold text-muted uppercase">
                    {sessions.length > 1 ? `${session.name || "Session"} · ` : ""}Match day
                  </h2>
                  <select
                    className="input mt-2"
                    value={plan.choice}
                    disabled={step === "building"}
                    onChange={(e) => {
                      setPlan({ choice: e.target.value });
                      const numbers = numberFor(session.matches, e.target.value === "new" ? null : Number(e.target.value));
                      setRows((r) => ({
                        ...r,
                        ...Object.fromEntries(session.matches.map((m) => [m.game_match_id, { ...r[m.game_match_id], number: numbers[m.game_match_id] }])),
                      }));
                    }}
                  >
                    <option value="new">New match day...</option>
                    {matchDays.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.title || `Day ${d.number}`}
                        {d.date ? ` (${d.date})` : ""}
                        {stages.length > 1 ? ` · ${stageName(d.stage)}` : ""}
                      </option>
                    ))}
                  </select>
                  {plan.choice === "new" && (
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      <label className="text-sm sm:col-span-3">
                        <span className="text-muted">Name (from the room name)</span>
                        <input
                          className="input mt-1"
                          value={plan.title}
                          placeholder="TDL DAY 12 8PM"
                          onChange={(e) => setPlan({ title: e.target.value })}
                        />
                      </label>
                      {stages.length > 1 && (
                        <label className="text-sm">
                          <span className="text-muted">Season</span>
                          <select className="input mt-1" value={plan.stage} onChange={(e) => setPlan({ stage: e.target.value })}>
                            {stages.map((st) => (
                              <option key={st.id} value={st.id}>
                                {st.season} · {st.name}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      <label className="text-sm">
                        <span className="text-muted">Day number</span>
                        <input
                          className="input mt-1"
                          type="number"
                          min={1}
                          value={plan.number}
                          onChange={(e) => setPlan({ number: e.target.value })}
                        />
                      </label>
                      <label className="text-sm">
                        <span className="text-muted">Date</span>
                        <input
                          className="input mt-1"
                          type="date"
                          value={plan.date}
                          onChange={(e) => setPlan({ date: e.target.value })}
                        />
                      </label>
                    </div>
                  )}
                </div>

              <ul className="divide-y divide-line card">
                {session.matches.map((m) => {
                  const row = rows[m.game_match_id] ?? { include: false, number: 1 };
                  const set = (patch: Partial<Row>) => setRows((r) => ({ ...r, [m.game_match_id]: { ...row, ...patch } }));
                  return (
                    <li key={m.game_match_id} className="flex flex-wrap items-start gap-3 px-4 py-3 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={row.include}
                        disabled={step === "building"}
                        onChange={(e) => set({ include: e.target.checked })}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">
                          {m.room_name || `Match ${m.game_match_id}`}
                          <span className="ml-2 text-xs text-muted">
                            {clockTime(m.started_at)} · {m.map?.name ?? "Map unknown"} · {m.teams.length} teams
                          </span>
                        </p>
                        <p className="mt-0.5 text-xs text-muted">
                          {[
                            m.has_match_result ? "Result" : null,
                            m.has_replay_info ? "Replay" : null,
                            m.has_debugger ? "Debugger log" : null,
                          ]
                            .filter(Boolean)
                            .join(" · ") || "No files"}
                          {m.existing_match ? ` · Already on the site: it will be updated and filed under this match day` : ""}
                        </p>
                        {m.warnings.map((w) => (
                          <p key={w} className="mt-0.5 text-xs text-accent-2">
                            {w}
                          </p>
                        ))}
                      </div>
                      <label className="flex items-center gap-1 text-xs text-muted">
                        Match
                        <input
                          className="input w-16 py-1"
                          type="number"
                          min={1}
                          value={row.number}
                          disabled={!row.include || step === "building"}
                          onChange={(e) => set({ number: Number(e.target.value) })}
                        />
                      </label>
                    </li>
                  );
                })}
              </ul>
              </div>
            );
          })}

          {matches.length === 0 && (
            <p className="text-sm text-bad">
              None of these games has a MatchResult file, so nothing can be built. Include the MatchResult logs and
              upload again.
            </p>
          )}
          <button className="btn btn-primary" disabled={step === "building" || !matches.length} onClick={confirm}>
            {step === "building" ? "Building the matches..." : "Confirm and build"}
          </button>
          {step === "building" && (
            <p className="text-xs text-muted">
              Results, standings, rotations and the live replay are being built. This can take a few minutes.
            </p>
          )}
        </div>
      )}

      {step === "done" && batch && (
        <div className="mt-6 space-y-4">
          <ul className="divide-y divide-line card">
            {(batch.preview.results ?? []).map((r) => {
              const m = matches.find((x) => x.game_match_id === r.game_match_id);
              const ok = r.status !== "FAILED";
              return (
                <li key={r.game_match_id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                  <span className={`h-2.5 w-2.5 rounded-full ${ok ? "bg-ok" : "bg-bad"}`} />
                  <span className="flex-1">
                    {m?.room_name || r.game_match_id}
                    {!ok && <span className="block text-xs text-bad">{r.error}</span>}
                    {ok && r.status === "WARNINGS" && <span className="block text-xs text-muted">Built with warnings</span>}
                  </span>
                  {ok && r.match_id && (
                    <Link href={`/staff/matches/${r.match_id}/replay`} className="text-accent">
                      Live replay
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
          <div className="flex gap-2">
            <Link href="/staff/matches" className="btn btn-primary">
              Check rotations
            </Link>
            <button
              className="btn"
              onClick={() => {
                setPicked([]);
                setBatch(null);
                setStep("pick");
              }}
            >
              Upload more
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
