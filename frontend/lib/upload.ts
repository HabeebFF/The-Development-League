// Upload page helpers: pure functions, so they can be tested without a browser.

export type FileKind =
  | "MATCH_ID"
  | "SAFE_ZONE"
  | "MATCH_RESULT"
  | "REPLAY_JSON"
  | "REPLAY_BIN"
  | "DEBUGGER";

export type Classified = {
  kind: FileKind;
  matchId: string | null;
  day: string | null;
};

// Same names the server reads (backend/apps/ingest/parsers/filenames.py).
const MATCH_FILE =
  /^(MatchId|SafeZone|MatchResult|ReplayInfo)_(\d+)_(\d{4}-\d{2}-\d{2})(?:-\d{2}){3}\.(log|json|bin)$/i;
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
export function pickMatchFiles<F extends { name: string }>(
  files: F[],
  days?: Set<string>,
): F[] {
  return files.filter((f) => {
    const info = classify(f.name);
    return (
      info !== null &&
      (!days || days.size === 0 || (info.day !== null && days.has(info.day)))
    );
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
export function chunk<F extends { size: number }>(
  files: F[],
  limit: number,
): F[][] {
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
  existing_match: {
    id: number;
    match_day: number;
    number: number;
    status: string;
  } | null;
  ready: boolean;
  warnings: string[];
};

/** Matches in the order they were played (unknown start times last, by id). */
export function inPlayOrder(matches: PreviewMatch[]): PreviewMatch[] {
  return [...matches].sort((a, b) => {
    if (a.started_at && b.started_at)
      return a.started_at.localeCompare(b.started_at);
    if (a.started_at || b.started_at) return a.started_at ? -1 : 1;
    return a.game_match_id.localeCompare(b.game_match_id);
  });
}

/** The match day hinted by most room names ("TDL DAY 12" -> 12), if any. */
export function dayHint(matches: PreviewMatch[]): number | null {
  const counts = new Map<number, number>();
  for (const m of matches) {
    if (m.match_day_hint != null)
      counts.set(m.match_day_hint, (counts.get(m.match_day_hint) ?? 0) + 1);
  }
  let best: number | null = null;
  for (const [day, n] of counts)
    if (best === null || n > (counts.get(best) ?? 0)) best = day;
  return best;
}

/** The room name most of the matches were played in ("TDL DAY 12"), tidied, if any. */
export function roomName(
  matches: Pick<PreviewMatch, "room_name">[],
): string | null {
  const counts = new Map<string, number>();
  for (const m of matches) {
    const name = (m.room_name ?? "").replace(/\s+/g, " ").trim();
    if (name) counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  let best: string | null = null;
  for (const [name, n] of counts)
    if (best === null || n > (counts.get(best) ?? 0)) best = name;
  return best;
}

/** One sitting in one room: its matches, a name for its match day, and whether it is TDL's. */
export type Session = {
  key: string;
  name: string;
  room: string;
  league: boolean;
  matches: PreviewMatch[];
};

/** "8PM" for a start time, to the nearest hour, in the viewer's time zone. */
export function hourLabel(iso: string): string {
  const d = new Date(iso);
  const h = (d.getHours() + (d.getMinutes() >= 30 ? 1 : 0)) % 24;
  return `${h % 12 || 12}${h < 12 ? "AM" : "PM"}`;
}

const tidy = (room: string | null | undefined) =>
  (room ?? "").replace(/\s+/g, " ").trim();

/** League rooms are named "TDL ..."; anything else (HYDRA SCRIMS, ...) is another organiser's. */
export function isLeagueRoom(room: string): boolean {
  return tidy(room) === "" || /^TDL\b/i.test(tidy(room));
}

/** Splits one room's matches (in play order) into sittings, by breaks and slot length. */
function splitByTime(
  ordered: PreviewMatch[],
  breakMinutes: number,
  sessionMinutes: number,
): PreviewMatch[][] {
  const groups: PreviewMatch[][] = [];
  let first: number | null = null;
  let last: number | null = null;
  for (const m of ordered) {
    const at = m.started_at ? Date.parse(m.started_at) : null;
    const fresh =
      !groups.length ||
      (at != null && last != null && (at - last) / 60000 >= breakMinutes) ||
      (at != null && first != null && (at - first) / 60000 >= sessionMinutes);
    if (fresh) {
      groups.push([]);
      first = at;
    }
    groups[groups.length - 1].push(m);
    if (at != null) {
      last = at;
      first ??= at;
    }
  }
  return groups;
}

/**
 * Splits matches (in play order) into sessions: first by room, so another organiser's scrims
 * (HYDRA SCRIMS) never mix with TDL's, then by time, such as the 8pm and 10pm scrims of one
 * day. A new session starts after a break of ``breakMinutes`` between two starts, or once
 * ``sessionMinutes`` have passed since the session's first match (TDL plays 5 matches in a
 * 2-hour slot, starting about every 24 minutes). Each session is named after its room and,
 * when that room has more than one, its start hour ("TDL DAY 12 8PM"). TDL sessions come
 * first, then the others, each in play order.
 */
export function sessionsOf(
  ordered: PreviewMatch[],
  breakMinutes = 40,
  sessionMinutes = 110,
): Session[] {
  const rooms = new Map<string, PreviewMatch[]>();
  for (const m of ordered) {
    const key = tidy(m.room_name).toLowerCase();
    rooms.set(key, [...(rooms.get(key) ?? []), m]);
  }
  const out: Session[] = [];
  for (const matches of rooms.values()) {
    const groups = splitByTime(matches, breakMinutes, sessionMinutes);
    for (const group of groups) {
      const room = roomName(group) ?? "";
      const start = group.find((m) => m.started_at)?.started_at;
      const name =
        groups.length > 1 && start
          ? `${room} ${hourLabel(start)}`.trim()
          : room;
      out.push({
        key: group[0].game_match_id,
        name,
        room,
        league: isLeagueRoom(room),
        matches: group,
      });
    }
  }
  const startOf = (s: Session) =>
    s.matches.find((m) => m.started_at)?.started_at ?? "\uffff";
  return out.sort(
    (a, b) =>
      Number(b.league) - Number(a.league) ||
      startOf(a).localeCompare(startOf(b)),
  );
}

/** Match days are told apart by their name: same words, any case or spacing. */
export function sameDayName(a: string, b: string): boolean {
  const norm = (s: string) => s.replace(/\s+/g, " ").trim().toLowerCase();
  return norm(a) !== "" && norm(a) === norm(b);
}

/**
 * Match numbers for a chosen match day: a match already in that day keeps its number,
 * the rest are numbered in play order after the highest number taken.
 */
export function numberFor(
  ordered: PreviewMatch[],
  dayId: number | null,
): Record<string, number> {
  const kept = ordered.filter(
    (m) => dayId != null && m.existing_match?.match_day === dayId,
  );
  let next = Math.max(0, ...kept.map((m) => m.existing_match!.number));
  return Object.fromEntries(
    ordered.map((m) => [
      m.game_match_id,
      kept.includes(m) ? m.existing_match!.number : ++next,
    ]),
  );
}

/** "about 3 min left": rounded so it doesn't jump around. */
export function timeLeft(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "working out time left";
  if (seconds < 10) return "a few seconds left";
  if (seconds < 60) return `about ${Math.ceil(seconds / 10) * 10} s left`;
  const min = Math.round(seconds / 60);
  if (min < 60) return `about ${min} min left`;
  return `about ${Math.floor(min / 60)} h ${min % 60} min left`;
}

/** Wait before retry ``attempt`` (1, 2, 3...): 2 s, 5 s, 10 s, then 20 s. */
export function retryDelay(attempt: number): number {
  return [2000, 5000, 10000][attempt - 1] ?? 20000;
}

/**
 * Upload speed in bytes per second over the last ``windowMs`` of ``samples`` ([time, total
 * bytes sent], oldest first), so the time left follows the connection as it is now.
 */
export function speed(
  samples: [number, number][],
  windowMs = 15000,
): number | null {
  if (samples.length < 2) return null;
  const end = samples[samples.length - 1];
  const start = samples.find(([t]) => t >= end[0] - windowMs) ?? samples[0];
  const secs = (end[0] - start[0]) / 1000;
  return secs >= 1 ? (end[1] - start[1]) / secs : null;
}

export function formatBytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(n / 1024))} KB`;
}
