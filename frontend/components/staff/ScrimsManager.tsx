"use client";

import { useCallback, useEffect, useState } from "react";

import TeamBadge from "@/components/league/TeamBadge";
import { api } from "@/lib/api";
import {
  clock,
  nightName,
  places,
  stageText,
  WEEKDAYS,
  weekdayList,
  type Entry,
  type LogRow,
  type ScrimSession,
  type ScrimSettings,
  type StaffNight,
  type StaffTeam,
} from "@/lib/scrims";

function when(iso?: string): string {
  return iso ? `${new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Africa/Lagos" })} ${clock(iso)}` : "";
}

/** Staff > Scrims: who's playing each session, suspensions, sign-up settings and the log. */
export default function ScrimsManager() {
  const [date, setDate] = useState<string | null>(null);
  const [night, setNight] = useState<StaffNight | null>(null);
  const [teams, setTeams] = useState<StaffTeam[]>([]);
  const [log, setLog] = useState<LogRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const n = await api<StaffNight>(`/admin/scrims/night${date ? `?date=${date}` : ""}`);
      setNight(n);
      if (!date && n.date) setDate(n.date);
      setTeams(await api<StaffTeam[]>("/admin/scrims/teams"));
      setLog(await api<LogRow[]>(`/admin/scrims/log?date=${n.date}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load scrims.");
    }
  }, [date]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loads from the server
    load();
  }, [load]);

  async function run(job: () => Promise<unknown>, done: string) {
    setError(null);
    setNotice(null);
    try {
      await job();
      setNotice(done);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
    }
  }

  return (
    <div className="mt-8 space-y-10">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Night
          <input type="date" className="input mt-1 w-auto" value={date ?? ""} onChange={(e) => setDate(e.target.value || null)} />
        </label>
        {night?.date && (
          <p className="pb-2 text-sm text-muted">
            {nightName(night.date)}
            {night.scrim_night ? "" : " · not a scrim night (teams can't sign up, staff can still add teams)"}
          </p>
        )}
      </div>
      {error && <p className="text-bad">{error}</p>}
      {notice && <p className="text-ok">{notice}</p>}

      <div className="grid gap-6 lg:grid-cols-2">
        {night?.sessions.map((s) => (
          <SessionPanel key={s.session} s={s} teams={teams} run={run} />
        ))}
      </div>

      <Suspensions teams={teams} run={run} />
      <Settings run={run} />

      <section>
        <h2 className="font-display text-2xl uppercase">Log{night?.date ? ` · ${nightName(night.date)}` : ""}</h2>
        {log.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Nothing yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line card text-sm">
            {log.map((r, i) => (
              <li key={i} className="flex flex-wrap gap-x-3 px-4 py-2">
                <span className="text-muted">{when(r.at)}</span>
                <span className="font-semibold">{r.team}</span>
                <span>{r.label}</span>
                {r.session && <span className="text-muted">{r.session.split(" ")[1]}</span>}
                {r.by && <span className="text-muted">by {r.by}</span>}
                {r.note && <span className="text-muted">· {r.note}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

type Run = (job: () => Promise<unknown>, done: string) => Promise<void>;

function SessionPanel({ s, teams, run }: { s: ScrimSession; teams: StaffTeam[]; run: Run }) {
  const [pick, setPick] = useState("");
  const [note, setNote] = useState("");
  const [max, setMax] = useState(String(s.max_teams));
  const base = `/admin/scrims/${s.date}/${s.session}`;
  const inSession = new Set([...s.playing, ...s.waitlist].map((e) => e.team.id));
  const free = teams.filter((t) => !inSession.has(t.id));
  const { taken } = places(s);

  const add = (team: number, n = "") =>
    run(() => api(`${base}/add`, { method: "POST", body: { team, note: n } }), "Team added.");
  const remove = (e: Entry) =>
    run(() => api(`${base}/remove`, { method: "POST", body: { team: e.team.id } }), `${e.team.name} removed.`);

  const row = (e: Entry, waiting: boolean, i: number) => (
    <li key={e.team.id} className="flex flex-wrap items-center gap-2 px-3 py-2">
      <span className="num w-5 text-right text-sm text-muted">{i + 1}</span>
      <span className="min-w-0 flex-1">
        <TeamBadge team={e.team} />
        <span className="block text-xs text-muted">
          {e.by_staff ? "Added by staff" : "Signed up"}
          {e.registered_by ? ` · ${e.registered_by}` : ""} · {when(e.at)}
        </span>
      </span>
      {waiting && (
        <button type="button" className="btn px-3 py-1 text-sm" onClick={() => add(e.team.id)}>
          Put in
        </button>
      )}
      <button type="button" className="btn btn-ghost px-3 py-1 text-sm text-bad" onClick={() => remove(e)}>
        Remove
      </button>
    </li>
  );

  return (
    <section className="card p-4 sm:p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-3xl leading-none font-black uppercase">{s.session}</h2>
        <span className="num text-2xl leading-none">{taken}</span>
      </div>
      <p className="mt-1 text-sm text-muted">{stageText(s)}</p>

      <h3 className="mt-4 text-sm font-semibold text-muted uppercase">Playing</h3>
      {s.playing.length === 0 ? (
        <p className="mt-1 text-sm text-muted">No teams.</p>
      ) : (
        <ol className="mt-2 divide-y divide-line border border-line">{s.playing.map((e, i) => row(e, false, i))}</ol>
      )}
      {s.waitlist.length > 0 && (
        <>
          <h3 className="mt-4 text-sm font-semibold text-muted uppercase">Waitlist</h3>
          <ol className="mt-2 divide-y divide-line border border-line">{s.waitlist.map((e, i) => row(e, true, i))}</ol>
        </>
      )}

      <form
        className="mt-4 flex flex-wrap items-end gap-2"
        onSubmit={(ev) => {
          ev.preventDefault();
          if (pick) add(Number(pick), note).then(() => (setPick(""), setNote("")));
        }}
      >
        <label className="min-w-40 flex-1 text-sm">
          Add a team
          <select className="input mt-1" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">Pick a team</option>
            {free.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
                {t.suspended ? " (suspended)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-32 flex-1 text-sm">
          Note
          <input className="input mt-1" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional" maxLength={300} />
        </label>
        <button type="submit" className="btn btn-primary" disabled={!pick}>
          Add
        </button>
      </form>

      <form
        className="mt-3 flex items-end gap-2"
        onSubmit={(ev) => {
          ev.preventDefault();
          run(() => api(base, { method: "PATCH", body: { max_teams: Number(max) } }), `${s.session} now has ${max} places.`);
        }}
      >
        <label className="text-sm">
          Places
          <input type="number" min={2} max={50} className="input mt-1 w-24" value={max} onChange={(e) => setMax(e.target.value)} />
        </label>
        <button type="submit" className="btn" disabled={Number(max) === s.max_teams}>
          Save
        </button>
      </form>
    </section>
  );
}

function Suspensions({ teams, run }: { teams: StaffTeam[]; run: Run }) {
  const [pick, setPick] = useState("");
  const [reason, setReason] = useState("");
  const [until, setUntil] = useState("");
  const held = teams.filter((t) => t.suspended);
  const others = teams.filter((t) => !t.suspended);
  return (
    <section>
      <h2 className="font-display text-2xl uppercase">Suspended teams</h2>
      <p className="mt-1 text-sm text-muted">
        A suspended team can&apos;t sign up, and is taken out of any session that hasn&apos;t started. You can still add it to a session yourself.
      </p>
      {held.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No team is suspended.</p>
      ) : (
        <ul className="mt-3 divide-y divide-line card">
          {held.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="min-w-0 flex-1">
                <TeamBadge team={t} />
                <span className="block text-xs text-muted">
                  Since {when(t.suspended!.since)} · {t.suspended!.until ? `until ${t.suspended!.until}` : "until lifted"}
                  {t.suspended!.reason ? ` · ${t.suspended!.reason}` : ""}
                </span>
              </span>
              <button
                type="button"
                className="btn px-3 py-1 text-sm"
                onClick={() => run(() => api(`/admin/scrims/teams/${t.slug}/unsuspend`, { method: "POST" }), `${t.name} can sign up again.`)}
              >
                Unsuspend
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="mt-4 card flex flex-wrap items-end gap-3 p-4"
        onSubmit={(ev) => {
          ev.preventDefault();
          const team = teams.find((t) => String(t.id) === pick);
          if (!team) return;
          run(
            () => api(`/admin/scrims/teams/${team.slug}/suspend`, { method: "POST", body: { reason, until: until || null } }),
            `${team.name} is suspended.`,
          ).then(() => (setPick(""), setReason(""), setUntil("")));
        }}
      >
        <label className="min-w-40 flex-1 text-sm">
          Team
          <select className="input mt-1" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">Pick a team</option>
            {others.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-40 flex-[2] text-sm">
          Reason (the team sees it)
          <input className="input mt-1" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="Optional" />
        </label>
        <label className="text-sm">
          Last day (optional)
          <input type="date" className="input mt-1 w-auto" value={until} onChange={(e) => setUntil(e.target.value)} />
        </label>
        <button type="submit" className="btn btn-hot" disabled={!pick}>
          Suspend
        </button>
      </form>
    </section>
  );
}

function Settings({ run }: { run: Run }) {
  const [conf, setConf] = useState<ScrimSettings | null>(null);
  const [skips, setSkips] = useState("");

  useEffect(() => {
    api<ScrimSettings>("/admin/scrims/settings")
      .then((c) => {
        setConf(c);
        setSkips(c.skip_dates.join(", "));
      })
      .catch(() => setConf(null));
  }, []);

  if (!conf) return null;
  const toggle = (d: number) =>
    setConf({ ...conf, weekdays: conf.weekdays.includes(d) ? conf.weekdays.filter((x) => x !== d) : [...conf.weekdays, d] });
  const time = (session: string, value: string) => setConf({ ...conf, closes_at: { ...conf.closes_at, [session]: value } });

  return (
    <section>
      <h2 className="font-display text-2xl uppercase">Sign-up settings</h2>
      <p className="mt-1 text-sm text-muted">
        Scrims on {weekdayList(conf.weekdays)}. Sign-up opens {conf.opens_at.slice(0, 5)} Lagos time.
      </p>
      <form
        className="mt-4 card space-y-4 p-4"
        onSubmit={(ev) => {
          ev.preventDefault();
          const skip_dates = skips
            .split(/[\s,]+/)
            .map((s) => s.trim())
            .filter(Boolean);
          run(
            () =>
              api("/admin/scrims/settings", {
                method: "PATCH",
                body: { weekdays: conf.weekdays, closes_at: conf.closes_at, max_teams: conf.max_teams, opens_at: conf.opens_at, skip_dates },
              }),
            "Settings saved.",
          );
        }}
      >
        <fieldset>
          <legend className="text-sm">Scrim days</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {WEEKDAYS.map((name, d) => (
              <label key={name} className={`chip cursor-pointer ${conf.weekdays.includes(d) ? "chip-gold" : ""}`}>
                <input type="checkbox" className="sr-only" checked={conf.weekdays.includes(d)} onChange={() => toggle(d)} />
                {name.slice(0, 3)}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm">
            Sign-up opens
            <input type="time" className="input mt-1 w-auto" value={conf.opens_at.slice(0, 5)} onChange={(e) => setConf({ ...conf, opens_at: e.target.value })} />
          </label>
          {["8PM", "10PM"].map((s) => (
            <label key={s} className="text-sm">
              {s} sign-up closes
              <input type="time" className="input mt-1 w-auto" value={conf.closes_at[s] ?? ""} onChange={(e) => time(s, e.target.value)} />
            </label>
          ))}
          <label className="text-sm">
            Places per session
            <input
              type="number"
              min={2}
              max={50}
              className="input mt-1 w-24"
              value={conf.max_teams}
              onChange={(e) => setConf({ ...conf, max_teams: Number(e.target.value) })}
            />
          </label>
        </div>
        <label className="block text-sm">
          Nights off (dates, comma separated)
          <input className="input mt-1" value={skips} onChange={(e) => setSkips(e.target.value)} placeholder="2026-12-25, 2026-12-26" />
        </label>
        <button type="submit" className="btn btn-primary">
          Save settings
        </button>
      </form>
    </section>
  );
}
