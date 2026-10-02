"use client";

import Link from "next/link";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, type Paged } from "@/lib/api";
import {
  canOpenFolder,
  fromFileList,
  mayRead,
  openFolder,
  rememberedFolder,
  rememberFolder,
  scanFolder,
  type Folder,
  type Picked,
} from "@/lib/folder";
import {
  alreadyThere,
  sendAll,
  type SendState,
  type Skipped,
} from "@/lib/sender";
import {
  formatBytes,
  inPlayOrder,
  numberFor,
  sameDayName,
  sessionsOf,
  speed,
  timeLeft,
  type PreviewMatch,
} from "@/lib/upload";

const POLL_MS = 2000;
const RESUME_KEY = "tdl-upload-resume";

type BatchStatus =
  | "UPLOADING"
  | "GROUPING"
  | "READY"
  | "PROCESSING"
  | "DONE"
  | "FAILED";
type Result = {
  game_match_id: string;
  match_id?: number;
  status: string;
  error?: string;
};
type Batch = {
  id: number;
  status: BatchStatus;
  error: string;
  preview: {
    matches?: PreviewMatch[];
    unassigned_files?: unknown[];
    results?: Result[];
  };
};
type Stage = { id: number; season: string; name: string };
type Day = {
  id: number;
  stage: number;
  number: number;
  date: string | null;
  title: string;
};
type Row = { include: boolean; number: number };
/** Where one session's matches go: an existing match day id, or "new" with its details. */
type Plan = {
  choice: string;
  title: string;
  number: string;
  date: string;
  stage: string;
};
/** An upload that hasn't reached the preview yet, kept so a refresh can carry on. */
type Resume = { batchId: number; days: string[]; files: number; bytes: number };
type Progress = {
  total: number;
  bytes: number;
  already: number;
  send: SendState;
  samples: [number, number][];
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function loadResume(): Resume | null {
  try {
    const raw = localStorage.getItem(RESUME_KEY);
    return raw ? (JSON.parse(raw) as Resume) : null;
  } catch {
    return null;
  }
}

function saveResume(r: Resume | null) {
  try {
    if (r) localStorage.setItem(RESUME_KEY, JSON.stringify(r));
    else localStorage.removeItem(RESUME_KEY);
  } catch {}
}

async function waitWhile(batchId: number, busy: BatchStatus[]): Promise<Batch> {
  for (;;) {
    const batch = await api<Batch>(`/uploads/batches/${batchId}`);
    if (!busy.includes(batch.status)) return batch;
    await sleep(POLL_MS);
  }
}

function clockTime(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "?";
}

function dayLabel(d: string): string {
  return new Date(`${d}T12:00:00`).toLocaleDateString([], {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** Staff: upload a match day's log files, check what was found, then build the matches. */
export default function UploadMatches() {
  const [items, setItems] = useState<Picked[]>([]);
  const [days, setDays] = useState<Set<string>>(new Set());
  const [step, setStep] = useState<
    | "pick"
    | "scanning"
    | "uploading"
    | "reading"
    | "preview"
    | "building"
    | "done"
  >("pick");
  const [scan, setScan] = useState({ checked: 0, found: 0 });
  const [progress, setProgress] = useState<Progress | null>(null);
  const [skippedFiles, setSkippedFiles] = useState<Skipped[]>([]);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resume, setResume] = useState<Resume | null>(null);
  const folder = useRef<Folder | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const [stages, setStages] = useState<Stage[]>([]);
  const [matchDays, setMatchDays] = useState<Day[]>([]);
  const [plans, setPlans] = useState<Record<string, Plan>>({});
  const [rows, setRows] = useState<Record<string, Row>>({});

  const perDay = useMemo(() => {
    const out = new Map<string, { files: number; bytes: number }>();
    for (const f of items) {
      if (!f.day) continue;
      const d = out.get(f.day) ?? { files: 0, bytes: 0 };
      out.set(f.day, { files: d.files + 1, bytes: d.bytes + f.size });
    }
    return new Map([...out.entries()].sort((a, b) => b[0].localeCompare(a[0])));
  }, [items]);
  const files = useMemo(
    () => items.filter((f) => f.day && days.has(f.day)),
    [items, days],
  );
  const totalBytes = files.reduce((n, f) => n + f.size, 0);
  // A debugger log covers the whole session (scrims too): only matches with a result
  // file, or already on the site, can be built.
  const all = useMemo(() => inPlayOrder(batch?.preview.matches ?? []), [batch]);
  const matches = all.filter((m) => m.ready);
  const sessions = useMemo(() => sessionsOf(all.filter((m) => m.ready)), [all]);
  const skipped = all.length - matches.length;
  const ticked = matches.filter((m) => rows[m.game_match_id]?.include).length;

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
    // An upload cut off by a refresh or a closed tab: offer to carry on.
    const saved = loadResume();
    if (saved)
      api<Batch>(`/uploads/batches/${saved.batchId}`)
        .then((b) =>
          ["UPLOADING", "GROUPING", "READY"].includes(b.status)
            ? setResume(saved)
            : saveResume(null),
        )
        .catch(() => saveResume(null));
  }, []);

  // Ticks once a second while uploading, so the time left and the bar never sit still.
  useEffect(() => {
    if (step !== "uploading" && step !== "reading") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [step]);

  function takeItems(found: Picked[], preferDays?: string[]) {
    setItems(found);
    const known = new Set(found.map((f) => f.day).filter(Boolean) as string[]);
    const keep = (preferDays ?? []).filter((d) => known.has(d));
    const newest = [...known].sort().reverse()[0];
    setDays(new Set(keep.length ? keep : newest ? [newest] : []));
    setStep("pick");
  }

  async function chooseFolder(preferDays?: string[]): Promise<Picked[] | null> {
    setError(null);
    const dir = await openFolder();
    if (!dir) return null;
    return readFolder(dir, preferDays);
  }

  async function readFolder(
    dir: Folder,
    preferDays?: string[],
  ): Promise<Picked[]> {
    folder.current = dir;
    setScan({ checked: 0, found: 0 });
    setStep("scanning");
    try {
      const found = await scanFolder(dir, (checked, n) =>
        setScan({ checked, found: n }),
      );
      await rememberFolder(dir);
      takeItems(found, preferDays);
      return found;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't read that folder.");
      setStep("pick");
      return [];
    }
  }

  function chooseList(list: FileList | null) {
    setError(null);
    folder.current = null;
    takeItems(fromFileList(list ?? []), resume?.days);
  }

  /** Carry on an upload that was cut off: same folder, same days, same batch. */
  async function carryOn() {
    if (!resume) return;
    setError(null);
    const dir = await rememberedFolder();
    let found: Picked[] | null = null;
    if (dir && (await mayRead(dir).catch(() => false)))
      found = await readFolder(dir, resume.days);
    else if (canOpenFolder()) found = await chooseFolder(resume.days);
    if (!found) {
      setError(
        "Pick the same folder again (Choose folder) and the upload carries on where it stopped.",
      );
      return;
    }
    const chosen = found.filter((f) => f.day && resume.days.includes(f.day));
    if (chosen.length) await upload(chosen, resume.batchId);
  }

  async function upload(chosen: Picked[] = files, batchId?: number) {
    setError(null);
    setSkippedFiles([]);
    const bytes = chosen.reduce((n, f) => n + f.size, 0);
    const start: Progress = {
      total: chosen.length,
      bytes,
      already: 0,
      send: {
        done: 0,
        sent: 0,
        active: [],
        note: "Checking which files the server already has...",
        skipped: [],
      },
      samples: [[Date.now(), 0]],
    };
    setProgress(start);
    setStep("uploading");
    try {
      let id = batchId ?? resume?.batchId;
      if (id) {
        const b = await api<Batch>(`/uploads/batches/${id}`).catch(() => null);
        if (!b || !["UPLOADING", "READY", "FAILED"].includes(b.status))
          id = undefined;
      }
      id ??= (
        await api<Batch>("/uploads/batches", {
          method: "POST",
          body: { note: "Upload page" },
        })
      ).id;
      const daysSent = [
        ...new Set(chosen.map((f) => f.day).filter(Boolean) as string[]),
      ];
      saveResume({ batchId: id, days: daysSent, files: chosen.length, bytes });
      setResume(null);

      // Files from earlier uploads (or the part of this one that already arrived) aren't sent again.
      const have = await alreadyThere(id, chosen);
      const todo = chosen.filter((f) => !have.has(f.name));
      const already = chosen.length - todo.length;
      const base = chosen
        .filter((f) => have.has(f.name))
        .reduce((n, f) => n + f.size, 0);
      const t0 = Date.now();
      setProgress({
        ...start,
        already,
        send: { ...start.send, note: null },
        samples: [[t0, 0]],
      });

      const skippedNow = await sendAll(id, todo, (s) =>
        setProgress(
          (p) =>
            p && {
              ...p,
              already,
              send: { ...s, done: s.done + already, sent: s.sent + base },
              samples: [
                ...p.samples.filter(([t]) => t > Date.now() - 30000),
                [Date.now(), s.sent],
              ],
            },
        ),
      );
      setSkippedFiles(skippedNow);
      if (skippedNow.length === chosen.length)
        throw new Error(
          "None of the files could be sent. Check the connection and try again.",
        );

      setStep("reading");
      await api(`/uploads/batches/${id}/group`, { method: "POST" });
      const ready = await waitWhile(id, ["GROUPING"]);
      if (ready.status === "FAILED")
        throw new Error(ready.error || "The server couldn't read these files.");
      saveResume(null);
      setBatch(ready);
      plan(ready);
      setStep("preview");
    } catch (e) {
      setError(
        `${e instanceof Error ? e.message : "Upload failed."} Nothing is lost: click Carry on to continue from where it stopped.`,
      );
      setResume(loadResume());
      setStep("pick");
    }
  }

  /** Each session (the 8pm and 10pm scrims) is its own match day, found by its name
   * ("TDL DAY 12 8PM"), never by number alone. Other rooms (HYDRA SCRIMS) start unticked. */
  function plan(ready: Batch) {
    const ordered = inPlayOrder(ready.preview.matches ?? []).filter(
      (m) => m.ready,
    );
    const today = new Date().toISOString().slice(0, 10);
    const stage = stages.length ? String(stages[stages.length - 1].id) : "";
    let next = Math.max(0, ...matchDays.map((d) => d.number));
    const out: Record<string, Plan> = {};
    const numbers: Record<string, number> = {};
    const include: Record<string, boolean> = {};
    for (const session of sessionsOf(ordered)) {
      const known = session.name
        ? matchDays.find((d) => sameDayName(d.title, session.name))
        : undefined;
      out[session.key] = known
        ? {
            choice: String(known.id),
            title: known.title,
            number: String(known.number),
            date: today,
            stage,
          }
        : {
            choice: "new",
            title: session.name,
            number: String(session.league ? ++next : next + 1),
            date: today,
            stage,
          };
      Object.assign(numbers, numberFor(session.matches, known?.id ?? null));
      for (const m of session.matches)
        include[m.game_match_id] = session.league;
    }
    setPlans(out);
    setRows(
      Object.fromEntries(
        ordered.map((m) => [
          m.game_match_id,
          {
            include: include[m.game_match_id],
            number: numbers[m.game_match_id],
          },
        ]),
      ),
    );
  }

  async function confirm() {
    if (!batch) return;
    setError(null);
    const chosen = matches.filter((m) => rows[m.game_match_id]?.include);
    if (!chosen.length) return setError("Tick at least one match.");
    for (const session of sessions) {
      const numbers = session.matches
        .filter((m) => rows[m.game_match_id]?.include)
        .map((m) => rows[m.game_match_id].number);
      if (new Set(numbers).size !== numbers.length)
        return setError(
          `${session.name || "A session"}: two matches have the same number.`,
        );
    }
    setStep("building");
    try {
      const assignments = [];
      for (const session of sessions) {
        const picked = session.matches.filter(
          (m) => rows[m.game_match_id]?.include,
        );
        if (!picked.length) continue;
        const plan = plans[session.key];
        let matchDay = Number(plan.choice);
        if (plan.choice === "new") {
          if (!plan.stage || !plan.number || !plan.title.trim())
            throw new Error("Give each new match day a name and number.");
          const made = await api<Day>("/admin/match-days", {
            method: "POST",
            body: {
              stage: Number(plan.stage),
              number: Number(plan.number),
              date: plan.date || null,
              title: plan.title.trim(),
            },
          });
          setMatchDays((d) => [...d, made]);
          setPlans((p) => ({
            ...p,
            [session.key]: { ...plan, choice: String(made.id) },
          }));
          matchDay = made.id;
        }
        // Matches already on the site move to the chosen day too.
        for (const m of picked)
          assignments.push({
            game_match_id: m.game_match_id,
            match_day: matchDay,
            number: rows[m.game_match_id].number,
          });
      }
      await api(`/uploads/batches/${batch.id}/confirm`, {
        method: "POST",
        body: { matches: assignments },
      });
      setBatch(await waitWhile(batch.id, ["PROCESSING", "READY"]));
      setStep("done");
    } catch (e) {
      setError(
        e instanceof ApiError || e instanceof Error
          ? e.message
          : "Something went wrong.",
      );
      setStep("preview");
    }
  }

  const stageName = (id: number) => {
    const s = stages.find((x) => x.id === id);
    return s ? `${s.season} · ${s.name}` : "";
  };

  const p = progress;
  const rate = p ? speed(p.samples) : null;
  const sentNow = p ? p.send.sent : 0;
  const left = p && rate ? (p.bytes - sentNow) / rate : Infinity;
  const pct = p && p.bytes ? Math.min(100, (100 * sentNow) / p.bytes) : 0;
  const elapsed = p ? Math.max(0, Math.round((now - p.samples[0][0]) / 1000)) : 0;

  return (
    <section className="mx-auto max-w-4xl px-4 py-10">
      <Link href="/staff" className="text-xs text-muted hover:text-text">
        &larr; Staff
      </Link>
      <h1 className="mt-2 font-display text-5xl leading-none font-extrabold uppercase">
        Upload matches
      </h1>
      {error && (
        <p className="mt-4 border border-bad/40 bg-bad/10 p-3 text-sm text-bad">
          {error}
        </p>
      )}

      {skippedFiles.length > 0 && step !== "uploading" && (
        <div className="mt-4 border border-accent/40 bg-accent/10 p-3 text-sm">
          <p className="font-semibold">
            {skippedFiles.length}{" "}
            {skippedFiles.length === 1 ? "file was" : "files were"} skipped.
            Everything else went up.
          </p>
          <ul className="mt-1 list-disc pl-5 text-xs text-muted">
            {skippedFiles.map((f) => (
              <li key={f.name}>
                <span className="text-text">{f.name}</span>: {f.reason}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-muted">
            To add it later, upload the same day again: only the missing files
            are sent.
          </p>
        </div>
      )}

      {resume && step === "pick" && (
        <div className="card mt-6 flex flex-wrap items-center gap-3 p-4">
          <p className="min-w-0 flex-1 text-sm">
            <span className="font-semibold">An upload didn&apos;t finish</span>
            <span className="block text-xs text-muted">
              {resume.days.map(dayLabel).join(", ")} · {resume.files} files (
              {formatBytes(resume.bytes)}). Files that already arrived
              won&apos;t be sent again.
            </span>
          </p>
          <button className="btn btn-primary" onClick={carryOn}>
            Carry on
          </button>
          <button
            className="btn"
            onClick={() => {
              saveResume(null);
              setResume(null);
            }}
          >
            Start over
          </button>
        </div>
      )}

      {step === "scanning" && (
        <div className="mt-8" role="status">
          <p className="text-sm font-semibold">Scanning files...</p>
          <div className="mt-2 h-2 overflow-hidden bg-panel-2">
            <div className="h-full w-1/3 animate-[scan_1.2s_ease-in-out_infinite] bg-accent" />
          </div>
          <p className="mt-1 text-xs text-muted">
            {scan.checked
              ? `${scan.checked.toLocaleString()} files checked, ${scan.found} match ${scan.found === 1 ? "file" : "files"} found. Game pictures are skipped.`
              : "Opening the folder..."}
          </p>
          {!canOpenFolder() && (
            <>
              <p className="mt-2 text-xs text-muted">
                This browser lists every file in the folder first, so the whole
                game folder can take a minute. Chrome or Edge on a computer is
                much faster.
              </p>
              <button className="btn mt-3" onClick={() => setStep("pick")}>
                Cancel
              </button>
            </>
          )}
        </div>
      )}

      {step === "pick" && (
        <div className="mt-6 space-y-6">
          <p className="text-sm text-muted">
            Choose the game&apos;s{" "}
            <span className="text-text">Free Fire_64_Data</span> folder, or pick
            the files yourself. Only match files (MatchResult, ReplayInfo .json
            and .bin, SafeZone, MatchId) and debugger logs are sent, and only
            for the dates you tick.
          </p>
          <div className="flex flex-wrap gap-2">
            {canOpenFolder() ? (
              <button
                className="btn btn-primary"
                onClick={() => chooseFolder(resume?.days)}
              >
                Choose folder
              </button>
            ) : (
              <label className="btn btn-primary cursor-pointer">
                Choose folder
                <input
                  type="file"
                  className="hidden"
                  multiple
                  {...({
                    webkitdirectory: "",
                    onCancel: () => setStep("pick"),
                  } as Record<string, unknown>)}
                  onClick={() => {
                    setScan({ checked: 0, found: 0 });
                    setStep("scanning");
                  }}
                  onChange={(e) => chooseList(e.target.files)}
                />
              </label>
            )}
            <label className="btn cursor-pointer">
              Choose files
              <input
                type="file"
                className="hidden"
                multiple
                onChange={(e) => chooseList(e.target.files)}
              />
            </label>
          </div>

          {items.length === 0 && scan.checked > 0 && (
            <p className="text-sm text-bad">
              No match logs in that folder. Pick Free Fire_64_Data.
            </p>
          )}
          {perDay.size > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-muted uppercase">
                Which days?
              </h2>
              <p className="mt-1 text-xs text-muted">
                Files are dated by when the game wrote them. If the match day
                went past midnight, tick both dates.
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {[...perDay.entries()].map(([d, n]) => (
                  <label
                    key={d}
                    className="flex items-center gap-2 border border-line px-3 py-1.5 text-sm"
                  >
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
                    {dayLabel(d)}
                    <span className="text-xs text-muted">
                      {n.files} {n.files === 1 ? "file" : "files"} ·{" "}
                      {formatBytes(n.bytes)}
                    </span>
                  </label>
                ))}
              </div>
              <button
                className="btn btn-primary mt-4"
                disabled={!files.length}
                onClick={() => upload()}
              >
                Upload {files.length} files ({formatBytes(totalBytes)})
              </button>
            </div>
          )}
        </div>
      )}

      {(step === "uploading" || step === "reading") && p && (
        <div className="mt-8" role="status">
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
            <span className="font-semibold">
              {step === "reading"
                ? "Reading the matches..."
                : `${p.send.done} of ${p.total} files`}
            </span>
            <span className="text-muted">
              {formatBytes(sentNow)} of {formatBytes(p.bytes)}
              {step === "uploading" &&
                ` · ${p.send.done === p.total ? "finishing" : timeLeft(left)}`}
            </span>
          </div>
          <div className="relative mt-2 h-3 overflow-hidden bg-panel-2">
            <div
              className="h-full bg-accent transition-[width] duration-500"
              style={{ width: `${step === "reading" ? 100 : pct}%` }}
            />
            <div className="absolute inset-0 animate-[shimmer_1.6s_linear_infinite] bg-[linear-gradient(100deg,transparent_30%,rgb(255_255_255/0.18)_50%,transparent_70%)] bg-[length:200%_100%]" />
          </div>
          <p className="mt-2 text-xs text-muted">
            {step === "reading"
              ? "All files are in. The server is reading them; the preview appears next."
              : p.send.active.length
                ? `Sending ${p.send.active.join(", ")}`
                : (p.send.note ?? "Starting...")}
            {rate ? ` · ${formatBytes(rate)}/s` : ""} · {elapsed} s
          </p>
          {step === "uploading" && p.send.note && p.send.active.length > 0 && (
            <p className="mt-1 text-xs text-accent-2">{p.send.note}</p>
          )}
          {p.already > 0 && (
            <p className="mt-1 text-xs text-muted">
              {p.already} {p.already === 1 ? "file was" : "files were"} already
              on the server, so {p.already === 1 ? "it wasn't" : "they weren't"}{" "}
              sent again.
            </p>
          )}
          {p.send.skipped.length > 0 && (
            <p className="mt-1 text-xs text-accent-2">
              Skipped so far: {p.send.skipped.map((f) => f.name).join(", ")}
            </p>
          )}
          <p className="mt-3 text-xs text-muted">
            You can leave this page open in the background. If it gets closed or
            the internet drops, come back and click Carry on.
          </p>
        </div>
      )}

      {(step === "preview" || step === "building") && batch && (
        <div className="mt-6 space-y-6">
          <p className="text-sm text-muted">
            Found {matches.length} {matches.length === 1 ? "match" : "matches"},
            grouped by room and session, in the order they were played. TDL
            sessions are ticked; other rooms are not. Check the names and
            numbers, then confirm.
            {skipped > 0 &&
              ` ${skipped} other ${skipped === 1 ? "game" : "games"} in the debugger log had no result file and ${skipped === 1 ? "was" : "were"} left out.`}
          </p>

          {sessions.map((session, i) => {
            const plan = plans[session.key];
            if (!plan) return null;
            const setPlan = (patch: Partial<Plan>) =>
              setPlans((p) => ({ ...p, [session.key]: { ...plan, ...patch } }));
            const firstOther =
              !session.league && (i === 0 || sessions[i - 1].league);
            const ids = session.matches.map((m) => m.game_match_id);
            const allOn = ids.every((id) => rows[id]?.include);
            return (
              <Fragment key={session.key}>
                {i === 0 && session.league && (
                  <h2 className="section-title">TDL sessions</h2>
                )}
                {firstOther && (
                  <div className="border-t border-line pt-6">
                    <h2 className="section-title">Other rooms</h2>
                    <p className="mt-1 text-sm text-muted">
                      Not TDL, so these are left unticked and won&apos;t be
                      added. Tick a session only if it belongs on the site.
                    </p>
                  </div>
                )}
                <div
                  className={`space-y-3 ${session.league ? "" : "opacity-80"}`}
                >
                  <div
                    className={`card p-4 ${session.league ? "border-accent/40" : ""}`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h2 className="font-display text-2xl leading-none uppercase">
                        {session.name || "Session"}
                        <span
                          className={`chip ml-2 align-middle ${session.league ? "" : "opacity-70"}`}
                        >
                          {session.league ? "TDL" : "Not TDL"} ·{" "}
                          {session.matches.length}{" "}
                          {session.matches.length === 1 ? "match" : "matches"}
                        </span>
                      </h2>
                      <label className="flex items-center gap-2 text-xs text-muted">
                        <input
                          type="checkbox"
                          checked={allOn}
                          disabled={step === "building"}
                          onChange={(e) =>
                            setRows((r) => ({
                              ...r,
                              ...Object.fromEntries(
                                ids.map((id) => [
                                  id,
                                  { ...r[id], include: e.target.checked },
                                ]),
                              ),
                            }))
                          }
                        />
                        Add this session
                      </label>
                    </div>
                    <h3 className="mt-3 text-sm font-semibold text-muted uppercase">
                      Match day
                    </h3>
                    <select
                      className="input mt-2"
                      value={plan.choice}
                      disabled={step === "building"}
                      onChange={(e) => {
                        setPlan({ choice: e.target.value });
                        const numbers = numberFor(
                          session.matches,
                          e.target.value === "new"
                            ? null
                            : Number(e.target.value),
                        );
                        setRows((r) => ({
                          ...r,
                          ...Object.fromEntries(
                            session.matches.map((m) => [
                              m.game_match_id,
                              {
                                ...r[m.game_match_id],
                                number: numbers[m.game_match_id],
                              },
                            ]),
                          ),
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
                          <span className="text-muted">
                            Name (from the room name)
                          </span>
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
                            <select
                              className="input mt-1"
                              value={plan.stage}
                              onChange={(e) =>
                                setPlan({ stage: e.target.value })
                              }
                            >
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
                            onChange={(e) =>
                              setPlan({ number: e.target.value })
                            }
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
                      const row = rows[m.game_match_id] ?? {
                        include: false,
                        number: 1,
                      };
                      const set = (patch: Partial<Row>) =>
                        setRows((r) => ({
                          ...r,
                          [m.game_match_id]: { ...row, ...patch },
                        }));
                      return (
                        <li
                          key={m.game_match_id}
                          className="flex flex-wrap items-start gap-3 px-4 py-3 text-sm"
                        >
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
                                {clockTime(m.started_at)} ·{" "}
                                {m.map?.name ?? "Map unknown"} ·{" "}
                                {m.teams.length} teams
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
                              {m.existing_match
                                ? ` · Already on the site: it will be updated and filed under this match day`
                                : ""}
                            </p>
                            {m.warnings.map((w) => (
                              <p
                                key={w}
                                className="mt-0.5 text-xs text-accent-2"
                              >
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
                              onChange={(e) =>
                                set({ number: Number(e.target.value) })
                              }
                            />
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </Fragment>
            );
          })}

          {matches.length === 0 && (
            <p className="text-sm text-bad">
              None of these games has a MatchResult file, so nothing can be
              built. Include the MatchResult logs and upload again.
            </p>
          )}
          <button
            className="btn btn-primary"
            disabled={step === "building" || !ticked}
            onClick={confirm}
          >
            {step === "building"
              ? "Building the matches..."
              : `Confirm and build ${ticked} ${ticked === 1 ? "match" : "matches"}`}
          </button>
          {step === "building" && (
            <p className="text-xs text-muted">
              Results, standings, rotations and the live replay are being built.
              This can take a few minutes.
            </p>
          )}
        </div>
      )}

      {step === "done" && batch && (
        <div className="mt-6 space-y-4">
          <ul className="divide-y divide-line card">
            {(batch.preview.results ?? []).map((r) => {
              const m = matches.find(
                (x) => x.game_match_id === r.game_match_id,
              );
              const ok = r.status !== "FAILED";
              return (
                <li
                  key={r.game_match_id}
                  className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm"
                >
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${ok ? "bg-ok" : "bg-bad"}`}
                  />
                  <span className="flex-1">
                    {m?.room_name || r.game_match_id}
                    {!ok && (
                      <span className="block text-xs text-bad">{r.error}</span>
                    )}
                    {ok && r.status === "WARNINGS" && (
                      <span className="block text-xs text-muted">
                        Built with warnings
                      </span>
                    )}
                  </span>
                  {ok && r.match_id && (
                    <Link
                      href={`/staff/matches/${r.match_id}/replay`}
                      className="text-accent"
                    >
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
                setItems([]);
                setSkippedFiles([]);
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
