"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useStaff } from "@/app/staff/StaffGate";
import { api, ApiError, type Paged, type TeamRef } from "@/lib/api";
import {
  CATEGORIES,
  coins,
  defaultTitle,
  MARKET_STATUS,
  newKey,
  oddsProblem,
  outcomeCodes,
  signedCoins,
  teamsProblem,
  toLocalInput,
  type Category,
  type Entry,
  type Fixture,
  type Market,
} from "@/lib/predictions";

type Season = { id: number; name: string; slug: string; is_active: boolean };
type StaffFixture = Fixture & {
  season: number;
  display_title: string;
  match_day: number | null;
};
type StaffOutcome = Market["outcomes"][number] & {
  bets: number;
  staked: number;
};
type StaffMarket = Omit<Market, "outcomes"> & {
  stored_status: string;
  params: Record<string, unknown>;
  bets: number;
  outcomes: StaffOutcome[];
};
type Candidate = {
  id: number;
  title: string;
  number: number;
  map: string | null;
  status: string;
  started_at: string | null;
  likely: boolean;
};
type Suggestion = {
  kind: "SETTLE" | "VOID";
  winners: number[];
  voids: number[];
  note: string;
  evidence: Record<string, unknown>;
};
type SettlementRow = {
  id: number;
  version: number;
  kind: string;
  winners: { id: number; label: string }[];
  voids: { id: number; label: string }[];
  reference: string;
  reason: string;
  summary: Record<string, number>;
  by: string;
  created_at: string;
};
type StaffBet = {
  id: string;
  user: { email: string; name: string };
  outcome: string;
  stake: number;
  odds_accepted: string;
  payout: number | null;
  status: string;
  placed_at: string;
};
type History = {
  type: string;
  at: string;
  from: string;
  to: string;
  by: string;
  reason?: string;
  outcome?: string;
}[];
type StaffWallet = {
  id: number;
  email: string;
  display_name: string;
  balance: number;
  entry_count: number;
};

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

function when(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Staff: fixtures and their markets (odds, status, settle, void, correct) and wallets. */
export default function PredictionsManager() {
  const [tab, setTab] = useState<"markets" | "wallets">("markets");
  return (
    <div className="mt-6">
      <div className="flex gap-1" role="tablist">
        {(["markets", "wallets"] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={`btn px-4 py-1.5 text-sm uppercase ${tab === t ? "btn-primary" : "text-muted"}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
        <Link href="/predict" className="btn ml-auto px-3 py-1.5 text-sm">
          See the public page
        </Link>
      </div>
      {tab === "markets" ? <Markets /> : <Wallets />}
    </div>
  );
}

// -- fixtures and markets ------------------------------------------------------------------------

function Markets() {
  const [seasons, setSeasons] = useState<Season[] | null>(null);
  const [teams, setTeams] = useState<TeamRef[]>([]);
  const [fixtures, setFixtures] = useState<StaffFixture[]>([]);
  const [fixtureId, setFixtureId] = useState<number | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const loadFixtures = useCallback(
    () =>
      api<Paged<StaffFixture>>("/admin/predictions/fixtures?page_size=100").then((page) => {
        setFixtures(page.results);
        setFixtureId((cur) => cur ?? page.results[0]?.id ?? null);
      }),
    [],
  );

  useEffect(() => {
    Promise.all([
      api<Paged<Season>>("/admin/seasons?page_size=100").then((p) => setSeasons(p.results)),
      api<Paged<TeamRef>>("/teams?page_size=100").then((p) => setTeams(p.results)),
      api<Paged<StaffFixture>>("/admin/predictions/fixtures?page_size=100").then((page) => {
        setFixtures(page.results);
        setFixtureId(page.results[0]?.id ?? null);
      }),
    ]).catch((e) => setNote(message(e)));
  }, []);

  if (!seasons) return note ? <p className="mt-6 text-bad">{note}</p> : <p className="mt-6 text-muted">Loading...</p>;
  const fixture = fixtures.find((f) => f.id === fixtureId) ?? null;

  return (
    <div className="mt-6 space-y-8">
      <section>
        <h2 className="section-title">Fixtures</h2>
        <p className="mt-1 text-sm text-muted">
          A fixture is a planned match (or a whole session). Markets hang off it; once the logs are uploaded, link it to the real match to settle.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {fixtures.length > 0 && (
            <select className="input w-auto" value={fixtureId ?? ""} onChange={(e) => setFixtureId(Number(e.target.value))} aria-label="Fixture">
              {fixtures.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.display_title}
                  {f.match ? " (linked)" : ""}
                </option>
              ))}
            </select>
          )}
        </div>
        <NewFixture
          seasons={seasons}
          onMade={async (f) => {
            await loadFixtures();
            setFixtureId(f.id);
          }}
        />
      </section>
      {fixture && <FixturePanel key={fixture.id} fixture={fixture} teams={teams} onChanged={loadFixtures} />}
    </div>
  );
}

function NewFixture({ seasons, onMade }: { seasons: Season[]; onMade: (f: StaffFixture) => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const active = seasons.find((s) => s.is_active) ?? seasons[0];
  if (!open)
    return (
      <button type="button" className="btn mt-3" onClick={() => setOpen(true)}>
        New fixture
      </button>
    );

  async function submit(form: FormData) {
    setNote(null);
    const date = String(form.get("date"));
    const time = String(form.get("time"));
    try {
      const made = await api<StaffFixture>("/admin/predictions/fixtures", {
        method: "POST",
        body: {
          season: Number(form.get("season")),
          date,
          session: form.get("session"),
          match_number: form.get("match_number") ? Number(form.get("match_number")) : null,
          title: form.get("title"),
          scheduled_at: new Date(`${date}T${time}`).toISOString(),
        },
      });
      setOpen(false);
      onMade(made);
    } catch (e) {
      setNote(message(e));
    }
  }

  return (
    <form action={submit} className="card mt-3 grid gap-3 p-4 sm:grid-cols-3">
      <label className="text-sm">
        <span className="text-muted">Season</span>
        <select name="season" className="input mt-1" defaultValue={active?.id}>
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm">
        <span className="text-muted">Date</span>
        <input name="date" type="date" required className="input mt-1" />
      </label>
      <label className="text-sm">
        <span className="text-muted">Planned start (your time)</span>
        <input name="time" type="time" required defaultValue="20:00" className="input mt-1" />
      </label>
      <label className="text-sm">
        <span className="text-muted">Session</span>
        <select name="session" className="input mt-1">
          <option>8PM</option>
          <option>10PM</option>
        </select>
      </label>
      <label className="text-sm">
        <span className="text-muted">Match number (empty = whole session)</span>
        <input name="match_number" type="number" min={1} max={10} defaultValue={1} className="input mt-1" />
      </label>
      <label className="text-sm">
        <span className="text-muted">Title (optional)</span>
        <input name="title" placeholder="TDL DAY 23 8PM · Match 1" className="input mt-1" />
      </label>
      {note && <p className="text-sm text-bad sm:col-span-3">{note}</p>}
      <div className="flex gap-2 sm:col-span-3">
        <button type="submit" className="btn btn-primary">
          Create fixture
        </button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function FixturePanel({ fixture, teams, onChanged }: { fixture: StaffFixture; teams: TeamRef[]; onChanged: () => void }) {
  const [markets, setMarkets] = useState<StaffMarket[] | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Paged<StaffMarket>>(`/admin/predictions/markets?fixture=${fixture.id}&page_size=100`)
      .then((p) => setMarkets(p.results))
      .catch((e) => setNote(message(e)));
  }, [fixture.id]);
  useEffect(load, [load]);

  return (
    <section className="space-y-6">
      <div>
        <h2 className="section-title">{fixture.display_title}</h2>
        <p className="mt-1 text-sm text-muted">
          Planned start {when(fixture.scheduled_at)} · {fixture.match ? `linked to match ${fixture.match}` : "not linked to a match yet"}
        </p>
        <LinkMatch fixture={fixture} onLinked={onChanged} />
      </div>
      <NewMarket fixture={fixture} teams={teams} onMade={load} />
      {note && <p className="text-bad">{note}</p>}
      {markets?.length === 0 && <p className="text-muted">No markets on this fixture yet.</p>}
      {markets?.map((m) => (
        <MarketPanel key={m.id} market={m} onChanged={load} />
      ))}
    </section>
  );
}

function LinkMatch({ fixture, onLinked }: { fixture: StaffFixture; onLinked: () => void }) {
  const [rows, setRows] = useState<Candidate[] | null>(null);
  const [pick, setPick] = useState<string>(fixture.match ? String(fixture.match) : "");
  const [note, setNote] = useState<string | null>(null);

  async function look() {
    setNote(null);
    try {
      const found = await api<Candidate[]>(`/admin/predictions/fixtures/${fixture.id}/candidate-matches`);
      setRows(found);
      if (!pick && found[0]?.likely) setPick(String(found[0].id));
    } catch (e) {
      setNote(message(e));
    }
  }

  async function save() {
    setNote(null);
    try {
      await api(`/admin/predictions/fixtures/${fixture.id}`, {
        method: "PATCH",
        body: { match: pick ? Number(pick) : null },
      });
      setNote("Saved.");
      onLinked();
    } catch (e) {
      setNote(message(e));
    }
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
      {rows === null ? (
        <button type="button" className="btn px-3 py-1.5 text-sm" onClick={look}>
          Link to uploaded match
        </button>
      ) : rows.length === 0 ? (
        <span className="text-muted">No uploaded matches on this date yet.</span>
      ) : (
        <>
          <select className="input w-auto py-1.5" value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Match">
            <option value="">Not linked</option>
            {rows.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
                {r.map ? ` · ${r.map}` : ""} · {r.status.toLowerCase()}
                {r.likely ? " (likely)" : ""}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-primary px-3 py-1.5 text-sm" onClick={save}>
            Save link
          </button>
        </>
      )}
      {note && <span className={note === "Saved." ? "text-ok" : "text-bad"}>{note}</span>}
    </div>
  );
}

function NewMarket({ fixture, teams, onMade }: { fixture: StaffFixture; teams: TeamRef[]; onMade: () => void }) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<Category>("BOOYAH");
  const [picked, setPicked] = useState<number[]>([]);
  const [n, setN] = useState(3);
  const [odds, setOdds] = useState<Record<string, string>>({});
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [opens, setOpens] = useState(toLocalInput(new Date().toISOString()));
  const [closes, setCloses] = useState(toLocalInput(fixture.scheduled_at));
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!open)
    return (
      <button type="button" className="btn btn-primary" onClick={() => setOpen(true)}>
        New market
      </button>
    );

  const chosen = picked.map((id) => teams.find((t) => t.id === id)!).filter(Boolean);
  const codes = outcomeCodes(category, chosen, n);
  const teamNote = teamsProblem(category, chosen.length);
  const oddsNote = codes.map((c) => oddsProblem(odds[c.code] ?? "")).find(Boolean) ?? null;

  async function create(openNow: boolean) {
    setBusy(true);
    setNote(null);
    try {
      const params = category === "TOP_N" ? { team: picked[0], n } : { teams: picked };
      const made = await api<StaffMarket>("/admin/predictions/markets", {
        method: "POST",
        body: {
          title: title.trim() || defaultTitle(category, chosen, n, fixture.match_number),
          description,
          category,
          season: fixture.season,
          fixture: fixture.id,
          params,
          odds: Object.fromEntries(codes.map((c) => [c.code, odds[c.code]])),
          opens_at: new Date(opens).toISOString(),
          closes_at: new Date(closes).toISOString(),
        },
      });
      if (openNow)
        await api(`/admin/predictions/markets/${made.id}/transition`, {
          method: "POST",
          body: { to: "OPEN" },
        });
      setOpen(false);
      setPicked([]);
      setOdds({});
      setTitle("");
      setDescription("");
      onMade();
    } catch (e) {
      setNote(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card space-y-3 p-4">
      <h3 className="font-display text-xl uppercase">New market</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          <span className="text-muted">Type</span>
          <select
            className="input mt-1"
            value={category}
            onChange={(e) => {
              setCategory(e.target.value as Category);
              setPicked([]);
              setOdds({});
            }}
          >
            {CATEGORIES.map((c) => (
              <option key={c.key} value={c.key}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        {category === "TOP_N" && (
          <label className="text-sm">
            <span className="text-muted">Top</span>
            <select className="input mt-1" value={n} onChange={(e) => setN(Number(e.target.value))}>
              {[3, 5, 10].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div>
        <p className="text-sm text-muted">Teams {teamNote && <span className="text-bad">· {teamNote}</span>}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {teams.map((t) => {
            const on = picked.includes(t.id);
            return (
              <button
                key={t.id}
                type="button"
                className={`btn px-2 py-1 text-xs ${on ? "btn-primary" : "text-muted"}`}
                onClick={() => setPicked(on ? picked.filter((x) => x !== t.id) : [...picked, t.id])}
              >
                {t.name}
              </button>
            );
          })}
          {category === "BOOYAH" && (
            <button type="button" className="btn px-2 py-1 text-xs" onClick={() => setPicked(teams.map((t) => t.id))}>
              All teams
            </button>
          )}
        </div>
      </div>
      {codes.length > 0 && (
        <div>
          <p className="text-sm text-muted">Decimal odds {oddsNote && <span className="text-bad">· {oddsNote}</span>}</p>
          <div className="mt-1 grid gap-2 sm:grid-cols-3">
            {codes.map((c) => (
              <label key={c.code} className="block text-sm">
                <span className="block truncate text-muted">{c.label}</span>
                <input
                  className="input mt-1 py-1"
                  inputMode="decimal"
                  placeholder="2.50"
                  value={odds[c.code] ?? ""}
                  onChange={(e) => setOdds({ ...odds, [c.code]: e.target.value })}
                />
              </label>
            ))}
          </div>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          <span className="text-muted">Title</span>
          <input
            className="input mt-1"
            value={title}
            placeholder={defaultTitle(category, chosen, n, fixture.match_number)}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="text-sm">
          <span className="text-muted">Description (rules in plain words)</span>
          <input className="input mt-1" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label className="text-sm">
          <span className="text-muted">Opens</span>
          <input type="datetime-local" className="input mt-1" value={opens} onChange={(e) => setOpens(e.target.value)} />
        </label>
        <label className="text-sm">
          <span className="text-muted">Closes (no bets after this)</span>
          <input type="datetime-local" className="input mt-1" value={closes} onChange={(e) => setCloses(e.target.value)} />
        </label>
      </div>
      {note && <p className="text-sm text-bad">{note}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn btn-primary" disabled={busy || !!teamNote || !!oddsNote} onClick={() => create(true)}>
          Create and open
        </button>
        <button type="button" className="btn" disabled={busy || !!teamNote || !!oddsNote} onClick={() => create(false)}>
          Save as draft
        </button>
        <button type="button" className="btn" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  );
}

const MOVES: Record<string, { to: string; label: string }[]> = {
  DRAFT: [{ to: "OPEN", label: "Open" }],
  OPEN: [
    { to: "SUSPENDED", label: "Pause" },
    { to: "CLOSED", label: "Close now" },
  ],
  SUSPENDED: [
    { to: "OPEN", label: "Re-open" },
    { to: "CLOSED", label: "Close" },
  ],
  CLOSED: [],
  SETTLED: [],
  VOID: [],
};

function MarketPanel({ market, onChanged }: { market: StaffMarket; onChanged: () => void }) {
  const [note, setNote] = useState<string | null>(null);
  const [show, setShow] = useState<"bets" | "history" | null>(null);
  const status = market.stored_status;

  async function run(fn: () => Promise<unknown>, done?: string) {
    setNote(null);
    try {
      await fn();
      onChanged();
      if (done) setNote(done);
    } catch (e) {
      setNote(message(e));
    }
  }

  return (
    <article className="card p-4">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="eyebrow">{market.category_label}</p>
          <h3 className="font-display text-2xl leading-tight uppercase">{market.title}</h3>
          <p className="text-xs text-muted">
            {when(market.opens_at)} → {when(market.closes_at)} · {market.bets} bets
          </p>
        </div>
        <span className="chip">{MARKET_STATUS[status as keyof typeof MARKET_STATUS] ?? status}</span>
      </div>

      <table className="table mt-3 w-full text-sm">
        <thead>
          <tr>
            <th className="text-left">Choice</th>
            <th className="text-right">Bets</th>
            <th className="text-right">Staked</th>
            <th className="text-right">Odds</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {market.outcomes.map((o) => (
            <OutcomeRow key={o.id} outcome={o} editable={["DRAFT", "OPEN", "SUSPENDED"].includes(status)} won={market.winners.includes(o.id)} run={run} />
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex flex-wrap gap-2">
        {MOVES[status]?.map((m) => (
          <button
            key={m.to}
            type="button"
            className="btn px-3 py-1.5 text-sm"
            onClick={() =>
              run(() =>
                api(`/admin/predictions/markets/${market.id}/transition`, {
                  method: "POST",
                  body: { to: m.to },
                }),
              )
            }
          >
            {m.label}
          </button>
        ))}
        <button type="button" className="btn px-3 py-1.5 text-sm" onClick={() => setShow(show === "bets" ? null : "bets")}>
          Bets
        </button>
        <button type="button" className="btn px-3 py-1.5 text-sm" onClick={() => setShow(show === "history" ? null : "history")}>
          History
        </button>
      </div>
      {note && <p className="mt-2 text-sm text-bad">{note}</p>}

      {status === "CLOSED" && <SettleForm market={market} onDone={onChanged} />}
      {["DRAFT", "OPEN", "SUSPENDED", "CLOSED"].includes(status) && <VoidForm market={market} onDone={onChanged} />}
      {["SETTLED", "VOID"].includes(status) && <CorrectForm market={market} onDone={onChanged} />}
      {show === "bets" && <MarketBets id={market.id} />}
      {show === "history" && <MarketHistory id={market.id} />}
    </article>
  );
}

function OutcomeRow({ outcome, editable, won, run }: { outcome: StaffOutcome; editable: boolean; won: boolean; run: (fn: () => Promise<unknown>) => void }) {
  const [odds, setOdds] = useState(outcome.odds);
  const problem = oddsProblem(odds);
  const url = `/admin/predictions/outcomes/${outcome.id}`;
  return (
    <tr className={outcome.is_active ? "" : "opacity-50"}>
      <td>
        {outcome.label} {won && <span className="chip text-ok">Won</span>}
      </td>
      <td className="text-right">{outcome.bets}</td>
      <td className="text-right">{outcome.staked}</td>
      <td className="text-right">
        {editable ? (
          <input
            className="input ml-auto w-20 py-1 text-right"
            value={odds}
            onChange={(e) => setOdds(e.target.value)}
            aria-label={`Odds for ${outcome.label}`}
          />
        ) : (
          outcome.odds
        )}
      </td>
      <td className="whitespace-nowrap text-right">
        {editable && odds !== outcome.odds && (
          <button type="button" className="btn px-2 py-1 text-xs" disabled={!!problem} onClick={() => run(() => api(url, { method: "PATCH", body: { odds } }))}>
            Save
          </button>
        )}
        {editable && (
          <button
            type="button"
            className="btn ml-1 px-2 py-1 text-xs"
            onClick={() =>
              run(() =>
                api(url, {
                  method: "PATCH",
                  body: { is_active: !outcome.is_active },
                }),
              )
            }
          >
            {outcome.is_active ? "Switch off" : "Switch on"}
          </button>
        )}
      </td>
    </tr>
  );
}

function Picks({
  market,
  winners,
  voids,
  setWinners,
  setVoids,
}: {
  market: StaffMarket;
  winners: number[];
  voids: number[];
  setWinners: (v: number[]) => void;
  setVoids: (v: number[]) => void;
}) {
  const toggle = (list: number[], id: number) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  return (
    <div className="max-w-md space-y-1 text-sm">
      {market.outcomes.map((o) => (
        <div key={o.id} className="flex items-center gap-3">
          <span className="min-w-0 flex-1 truncate">{o.label}</span>
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={winners.includes(o.id)} onChange={() => setWinners(toggle(winners, o.id))} /> wins
          </label>
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={voids.includes(o.id)} onChange={() => setVoids(toggle(voids, o.id))} /> refund
          </label>
        </div>
      ))}
    </div>
  );
}

function SettleForm({ market, onDone }: { market: StaffMarket; onDone: () => void }) {
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [waiting, setWaiting] = useState<string | null>(null);
  const [winners, setWinners] = useState<number[]>([]);
  const [voids, setVoids] = useState<number[]>([]);
  const [reference, setReference] = useState("");
  const [override, setOverride] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Suggestion>(`/admin/predictions/markets/${market.id}/suggested-result`)
      .then((s) => {
        setSuggestion(s);
        setWinners(s.winners);
        setVoids(s.voids);
      })
      .catch((e) => setWaiting(message(e)));
  }, [market.id]);

  const same =
    suggestion?.kind === "SETTLE" &&
    [...winners].sort().join() === [...suggestion.winners].sort().join() &&
    [...voids].sort().join() === [...suggestion.voids].sort().join();

  async function settle() {
    setBusy(true);
    setNote(null);
    try {
      await api(`/admin/predictions/markets/${market.id}/settle`, {
        method: "POST",
        body: {
          winners,
          voids,
          reference,
          override_reason: same ? "" : override,
        },
      });
      onDone();
    } catch (e) {
      setNote(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 border-t border-line pt-4">
      <h4 className="font-display text-lg uppercase">Settle</h4>
      {waiting ? (
        <p className="text-sm text-muted">{waiting}</p>
      ) : !suggestion ? (
        <p className="text-sm text-muted">Checking the match...</p>
      ) : (
        <div className="mt-2 space-y-3">
          <p className="text-sm">
            <span className="text-muted">The match says:</span>{" "}
            {suggestion.kind === "VOID"
              ? `void. ${suggestion.note}`
              : market.outcomes
                  .filter((o) => suggestion.winners.includes(o.id))
                  .map((o) => o.label)
                  .join(", ") || "no listed choice won"}
            {suggestion.kind === "SETTLE" && suggestion.note && <span className="text-muted"> · {suggestion.note}</span>}
          </p>
          <Picks market={market} winners={winners} voids={voids} setWinners={setWinners} setVoids={setVoids} />
          <input className="input" placeholder="Reference (e.g. Day 23 8PM logs)" value={reference} onChange={(e) => setReference(e.target.value)} />
          {!same && (
            <input
              className="input"
              placeholder="Why this differs from the match result (required)"
              value={override}
              onChange={(e) => setOverride(e.target.value)}
            />
          )}
          {note && <p className="text-sm text-bad">{note}</p>}
          <button type="button" className="btn btn-primary" disabled={busy || (!same && !override.trim())} onClick={settle}>
            {busy ? "Settling..." : "Settle and pay out"}
          </button>
        </div>
      )}
    </div>
  );
}

function VoidForm({ market, onDone }: { market: StaffMarket; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState<string | null>(null);
  if (!open)
    return (
      <button type="button" className="btn mt-3 px-3 py-1.5 text-sm text-bad" onClick={() => setOpen(true)}>
        Void and refund everyone
      </button>
    );
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <input className="input flex-1" placeholder="Reason (shown in the history)" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button
        type="button"
        className="btn btn-primary"
        disabled={!reason.trim()}
        onClick={async () => {
          try {
            await api(`/admin/predictions/markets/${market.id}/void`, {
              method: "POST",
              body: { reason },
            });
            onDone();
          } catch (e) {
            setNote(message(e));
          }
        }}
      >
        Void
      </button>
      <button type="button" className="btn" onClick={() => setOpen(false)}>
        Cancel
      </button>
      {note && <p className="w-full text-sm text-bad">{note}</p>}
    </div>
  );
}

function CorrectForm({ market, onDone }: { market: StaffMarket; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"SETTLE" | "VOID">("SETTLE");
  const [winners, setWinners] = useState<number[]>(market.winners);
  const [voids, setVoids] = useState<number[]>([]);
  const [reason, setReason] = useState("");
  const [key] = useState(newKey);
  const [note, setNote] = useState<string | null>(null);
  const [rows, setRows] = useState<SettlementRow[] | null>(null);

  useEffect(() => {
    api<SettlementRow[]>(`/admin/predictions/markets/${market.id}/settlements`)
      .then(setRows)
      .catch(() => setRows([]));
  }, [market.id]);

  return (
    <div className="mt-4 border-t border-line pt-4">
      <h4 className="font-display text-lg uppercase">Settlement history</h4>
      <ul className="mt-2 space-y-1 text-sm">
        {rows?.map((r) => (
          <li key={r.id}>
            <b>v{r.version}</b> {r.kind === "VOID" ? "voided" : `won: ${r.winners.map((w) => w.label).join(", ") || "none"}`}
            {r.voids.length > 0 && `, refunded: ${r.voids.map((w) => w.label).join(", ")}`} · {r.by} · {when(r.created_at)}
            {r.reason && <span className="text-muted"> · {r.reason}</span>}
            {r.summary.coins_unrecovered ? <span className="text-bad"> · {r.summary.coins_unrecovered} coins could not be taken back</span> : null}
          </li>
        ))}
      </ul>
      {!open ? (
        <button type="button" className="btn mt-3 px-3 py-1.5 text-sm" onClick={() => setOpen(true)}>
          Correct the result
        </button>
      ) : (
        <div className="mt-3 space-y-3">
          <p className="text-xs text-muted">
            A correction adds a new version. Each bet gets the difference; if a player has spent the coins, their balance stops at 0 and the rest is recorded.
          </p>
          <select className="input w-auto" value={kind} onChange={(e) => setKind(e.target.value as "SETTLE" | "VOID")}>
            <option value="SETTLE">New result</option>
            <option value="VOID">Void (refund everyone)</option>
          </select>
          {kind === "SETTLE" && <Picks market={market} winners={winners} voids={voids} setWinners={setWinners} setVoids={setVoids} />}
          <input className="input" placeholder="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} />
          {note && <p className="text-sm text-bad">{note}</p>}
          <button
            type="button"
            className="btn btn-primary"
            disabled={!reason.trim()}
            onClick={async () => {
              try {
                await api(`/admin/predictions/markets/${market.id}/correct`, {
                  method: "POST",
                  body: { kind, winners, voids, reason, key },
                });
                onDone();
              } catch (e) {
                setNote(message(e));
              }
            }}
          >
            Apply correction
          </button>
        </div>
      )}
    </div>
  );
}

function MarketBets({ id }: { id: number }) {
  const [rows, setRows] = useState<StaffBet[] | null>(null);
  useEffect(() => {
    api<Paged<StaffBet>>(`/admin/predictions/markets/${id}/bets?page_size=100`)
      .then((p) => setRows(p.results))
      .catch(() => setRows([]));
  }, [id]);
  if (!rows) return <p className="mt-3 text-sm text-muted">Loading...</p>;
  if (rows.length === 0) return <p className="mt-3 text-sm text-muted">No bets yet.</p>;
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="table w-full text-sm">
        <thead>
          <tr>
            <th className="text-left">Player</th>
            <th className="text-left">Choice</th>
            <th className="text-right">Stake</th>
            <th className="text-right">Odds</th>
            <th className="text-right">Paid</th>
            <th className="text-left">Status</th>
            <th className="text-left">Placed</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => (
            <tr key={b.id}>
              <td>
                {b.user.name || b.user.email}
                <span className="block text-xs text-muted">{b.user.email}</span>
              </td>
              <td>{b.outcome}</td>
              <td className="text-right">{b.stake}</td>
              <td className="text-right">{b.odds_accepted}</td>
              <td className="text-right">{b.payout ?? "–"}</td>
              <td>{b.status}</td>
              <td className="whitespace-nowrap text-muted">{when(b.placed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MarketHistory({ id }: { id: number }) {
  const [rows, setRows] = useState<History | null>(null);
  useEffect(() => {
    api<History>(`/admin/predictions/markets/${id}/history`)
      .then(setRows)
      .catch(() => setRows([]));
  }, [id]);
  if (!rows) return <p className="mt-3 text-sm text-muted">Loading...</p>;
  return (
    <ul className="mt-3 space-y-1 text-sm">
      {rows.map((h, i) => (
        <li key={i}>
          <span className="text-muted">{when(h.at)}</span>{" "}
          {h.type === "odds" ? `${h.outcome}: odds ${h.from} → ${h.to}` : h.from === h.to ? h.reason : `${h.from || "created"} → ${h.to}`} · {h.by}
          {h.type === "status" && h.reason && h.from !== h.to && <span className="text-muted"> · {h.reason}</span>}
        </li>
      ))}
    </ul>
  );
}

// -- wallets -------------------------------------------------------------------------------------

function Wallets() {
  const me = useStaff();
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<StaffWallet[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);

  const load = useCallback(() => {
    api<Paged<StaffWallet>>(`/admin/predictions/wallets?page_size=100&search=${encodeURIComponent(search)}`)
      .then((p) => setRows(p.results))
      .catch(() => setRows([]));
  }, [search]);
  useEffect(load, [load]);

  return (
    <div className="mt-6">
      <input className="input max-w-sm" placeholder="Search by email or name" value={search} onChange={(e) => setSearch(e.target.value)} />
      {!rows ? (
        <p className="mt-4 text-muted">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="mt-4 text-muted">No wallets yet.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {rows.map((w) => (
            <li key={w.id} className="card p-3 text-sm">
              <button type="button" className="flex w-full items-center gap-3 text-left" onClick={() => setOpen(open === w.id ? null : w.id)}>
                <span className="min-w-0 flex-1">
                  <b>{w.display_name || "No name"}</b> <span className="text-muted">{w.email}</span>
                </span>
                <span className="font-display text-lg text-accent-2">{coins(w.balance)}</span>
              </button>
              {open === w.id && <WalletDetail wallet={w} canAdjust={me.is_super_admin} onAdjusted={load} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type StaffEntry = Entry & { idempotency_key: string; actor: string | null };

function WalletDetail({ wallet, canAdjust, onAdjusted }: { wallet: StaffWallet; canAdjust: boolean; onAdjusted: () => void }) {
  const [entries, setEntries] = useState<StaffEntry[] | null>(null);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [key, setKey] = useState(newKey);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Paged<StaffEntry>>(`/admin/predictions/wallets/${wallet.id}/entries?page_size=100`)
      .then((p) => setEntries(p.results))
      .catch(() => setEntries([]));
  }, [wallet.id]);
  useEffect(load, [load]);

  async function adjust() {
    setNote(null);
    try {
      await api(`/admin/predictions/wallets/${wallet.id}/adjust`, {
        method: "POST",
        body: { amount: Number(amount), reason, key },
      });
      setAmount("");
      setReason("");
      setKey(newKey());
      load();
      onAdjusted();
    } catch (e) {
      setNote(message(e));
    }
  }

  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="overflow-x-auto">
        <table className="table w-full min-w-[34rem] text-xs">
          <thead>
            <tr>
              <th className="text-left">#</th>
              <th className="text-left">When</th>
              <th className="text-left">What</th>
              <th className="text-right">Coins</th>
              <th className="text-right">Before → after</th>
            </tr>
          </thead>
          <tbody>
            {entries?.map((e) => (
              <tr key={e.id}>
                <td>{e.seq}</td>
                <td className="whitespace-nowrap">{when(e.created_at)}</td>
                <td>
                  {e.kind_label}
                  <span className="block break-all text-muted">
                    {e.idempotency_key}
                    {e.actor ? ` · by ${e.actor}` : ""}
                    {e.reason ? ` · ${e.reason}` : ""}
                  </span>
                </td>
                <td className={`text-right ${e.amount > 0 ? "text-ok" : "text-bad"}`}>{signedCoins(e.amount)}</td>
                <td className="whitespace-nowrap text-right">
                  {e.balance_before} → {e.balance_after}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canAdjust && (
        <div className="mt-3 flex flex-wrap gap-2">
          <input className="input w-28" inputMode="numeric" placeholder="+50 or -50" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <input className="input flex-1" placeholder="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <button
            type="button"
            className="btn btn-primary"
            disabled={!/^-?\d+$/.test(amount) || Number(amount) === 0 || reason.trim().length < 5}
            onClick={adjust}
          >
            Adjust coins
          </button>
          {note && <p className="w-full text-bad">{note}</p>}
        </div>
      )}
    </div>
  );
}
