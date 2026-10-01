// Upload page helpers: pure functions, so they can be tested without a browser.

export type FileKind = "MATCH_ID" | "SAFE_ZONE" | "MATCH_RESULT" | "REPLAY_JSON" | "REPLAY_BIN" | "DEBUGGER";

export type Classified = { kind: FileKind; matchId: string | null; day: string | null };

// Same names the server reads (backend/apps/ingest/parsers/filenames.py).
const MATCH_FILE = /^(MatchId|SafeZone|MatchResult|ReplayInfo)_(\d+)_(\d{4}-\d{2}-\d{2})(?:-\d{2}){3}\.(log|json|bin)$/i;
const DEBUGGER_FILE = /^debugger-(\d{4}-\d{2}-\d{2})\S*\.log$/i;

const KINDS: Record<string, FileKind> = {
  "matchid.log": "MATCH_ID",
  "safezone.log": "SAFE_ZONE",
  "matchresult.log": "MATCH_RESULT",
  "replayinfo.json": "REPLAY_JSON",
  "replayinfo.bin": "REPLAY_BIN",
};

/** What a log file is, from its name (a bare name or a folder path). Null if not a match file. */
export function classify(path: string): Classified | null {
  const name = path.split(/[\\/]/).pop()?.trim() ?? "";
  const m = MATCH_FILE.exec(name);
  if (m) {
    const kind = KINDS[`${m[1].toLowerCase()}.${m[4].toLowerCase()}`];
    return kind ? { kind, matchId: m[2], day: m[3] } : null;
  }
  const d = DEBUGGER_FILE.exec(name);
  return d ? { kind: "DEBUGGER", matchId: null, day: d[1] } : null;
}

/**
 * The files worth uploading from a pick (often the whole game folder): match files and
 * debugger logs, optionally only those written on ``days`` (YYYY-MM-DD, local file names).
 */
export function pickMatchFiles<F extends { name: string }>(files: F[], days?: Set<string>): F[] {
  return files.filter((f) => {
    const info = classify(f.name);
    return info !== null && (!days || days.size === 0 || (info.day !== null && days.has(info.day)));
  });
}

/** Every day that appears in the files' names, newest first. */
export function daysIn(files: { name: string }[]): string[] {
  const days = new Set<string>();
  for (const f of files) {
    const day = classify(f.name)?.day;
    if (day) days.add(day);
  }
  return [...days].sort().reverse();
}

/** Split files into upload requests of at most ``limit`` bytes (a bigger file goes alone). */
export function chunk<F extends { size: number }>(files: F[], limit: number): F[][] {
  const out: F[][] = [];
  let current: F[] = [];
  let bytes = 0;
  for (const f of files) {
    if (current.length && bytes + f.size > limit) {
      out.push(current);
      current = [];
      bytes = 0;
    }
    current.push(f);
    bytes += f.size;
  }
  if (current.length) out.push(current);
  return out;
}

export type PreviewMatch = {
  game_match_id: string;
  room_name: string;
  started_at: string | null;
  map: { id: number; name: string } | null;
  teams: { in_game_name: string; team: { id: number; name: string } | null }[];
  has_match_result: boolean;
  has_replay_info: boolean;
  has_debugger: boolean;
  match_day_hint: number | null;
  existing_match: { id: number; match_day: number; number: number; status: string } | null;
  ready: boolean;
  warnings: string[];
};

/** Matches in the order they were played (unknown start times last, by id). */
export function inPlayOrder(matches: PreviewMatch[]): PreviewMatch[] {
  return [...matches].sort((a, b) => {
    if (a.started_at && b.started_at) return a.started_at.localeCompare(b.started_at);
    if (a.started_at || b.started_at) return a.started_at ? -1 : 1;
    return a.game_match_id.localeCompare(b.game_match_id);
  });
}

/** The match day hinted by most room names ("TDL DAY 12" -> 12), if any. */
export function dayHint(matches: PreviewMatch[]): number | null {
  const counts = new Map<number, number>();
  for (const m of matches) {
    if (m.match_day_hint != null) counts.set(m.match_day_hint, (counts.get(m.match_day_hint) ?? 0) + 1);
  }
  let best: number | null = null;
  for (const [day, n] of counts) if (best === null || n > (counts.get(best) ?? 0)) best = day;
  return best;
}

export function formatBytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(n / 1024))} KB`;
}
