"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, ApiError, type Paged, type TeamRef } from "@/lib/api";
import { dc, naira, regText, VIA_LABEL, type Entry, type Paid, type Preview, type Tournament } from "@/lib/tournaments";

type QualRow = { rank: number; team: { id: number; name: string; slug: string }; points: number; through: boolean };
type Staff = Tournament & {
  match_days: { id: number; title: string; date: string | null; number: number }[];
  qualifier_table: QualRow[];
};
type LeagueDay = { id: number; title: string; date: string | null; suggested: boolean };
type PrizeRow = { key: string; label: string; cash: number; dc: number };

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** Staff: make a tournament, invite teams, set prizes, move match days in, and pay out. */
export default function TournamentsManager() {
  const [list, setList] = useState<Tournament[] | null>(null);
  const [slug, setSlug] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const load = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    api<Tournament[]>("/admin/tournaments")
      .then((all) => {
        setList(all);
        setSlug((s) => s ?? all[0]?.slug ?? null);
      })
      .catch((e) => setNote(message(e)));
  }, [version]);

  if (!list) return note ? <p className="mt-6 text-bad">{note}</p> : null;
  return (
    <div className="mt-6 space-y-6">
      {list.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {list.map((t) => (
            <button key={t.slug} type="button" className={`btn px-3 py-1.5 text-sm ${t.slug === slug ? "btn-primary" : ""}`} onClick={() => setSlug(t.slug)}>
              {t.name}
            </button>
          ))}
        </div>
      )}
      {slug && <Manage key={slug} slug={slug} onChanged={load} />}
      <Create
        onMade={(t) => {
          setSlug(t.slug);
          void load();
        }}
      />
    </div>
  );
}

function Create({ onMade }: { onMade: (t: Tournament) => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  if (!open)
    return (
      <button type="button" className="btn" onClick={() => setOpen(true)}>
        New tournament
      </button>
    );
  return (
    <form
      className="card space-y-3 p-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        try {
          const t = await api<Tournament>("/admin/tournaments", {
            method: "POST",
            body: {
              name: String(f.get("name")).trim(),
              starts_on: f.get("starts_on") || null,
              ends_on: f.get("ends_on") || null,
              keyword: String(f.get("keyword")).trim(),
              format_note: String(f.get("format_note")).trim(),
              planned_matches: Number(f.get("planned_matches")),
            },
          });
          setOpen(false);
          onMade(t);
        } catch (err) {
          setNote(message(err));
        }
      }}
    >
      <h2 className="section-title">New tournament</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">
          <span className="text-muted">Name</span>
          <input name="name" required className="input mt-1" placeholder="TDL Cup 2026" />
        </label>
        <label className="text-sm">
          <span className="text-muted">Room keyword (uploads with it go here)</span>
          <input name="keyword" className="input mt-1" placeholder="CUP" />
        </label>
        <label className="text-sm">
          <span className="text-muted">First day</span>
          <input name="starts_on" type="date" className="input mt-1" />
        </label>
        <label className="text-sm">
          <span className="text-muted">Last day</span>
          <input name="ends_on" type="date" className="input mt-1" />
        </label>
        <label className="text-sm">
          <span className="text-muted">Matches in all</span>
          <input name="planned_matches" type="number" min={1} defaultValue={12} className="input mt-1" />
        </label>
        <label className="text-sm">
          <span className="text-muted">Format (shown on the page)</span>
          <input name="format_note" className="input mt-1" placeholder="2 days · 6 maps a day · 10PM" />
        </label>
      </div>
      <p className="text-xs text-muted">It starts with the ₦100,000 + 1,000,000 DC prize table and the league&apos;s points; change them below.</p>
      {note && <p className="text-sm text-bad">{note}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn btn-primary">
          Make it
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function Manage({ slug, onChanged }: { slug: string; onChanged: () => void }) {
  const [t, setT] = useState<Staff | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const base = `/admin/tournaments/${encodeURIComponent(slug)}`;
  const [version, setVersion] = useState(0);
  useEffect(() => {
    api<Staff>(base)
      .then(setT)
      .catch((e) => setNote(message(e)));
  }, [base, version]);

  async function run(fn: () => Promise<unknown>) {
    setNote(null);
    try {
      await fn();
      setVersion((v) => v + 1);
      onChanged();
    } catch (e) {
      setNote(message(e));
    }
  }

  if (!t) return note ? <p className="text-bad">{note}</p> : null;
  const done = !!t.confirmed_at;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-display text-3xl font-extrabold uppercase">{t.name}</h2>
        <Link href={`/tournaments/${t.slug}`} className="chip chip-gold">
          Public page
        </Link>
        <span className="text-sm text-muted">
          {t.matches} of {t.planned_matches} matches · keyword {t.keyword ? `"${t.keyword}"` : "none"}
        </span>
      </div>
      {note && <p className="text-sm text-bad">{note}</p>}

      <section className="card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="section-title">
            {t.registration.qualifier ? `${t.registration.final.name} teams` : "Teams"} ({finalTeams(t).length})
          </h3>
          {!done && !t.registration.qualifier && (
            <>
              <button type="button" className="btn ml-auto px-3 py-1.5 text-sm" onClick={() => run(() => api(`${base}/invite-top`, { method: "POST", body: { n: 12 } }))}>
                Invite the top 12 now
              </button>
              <button
                type="button"
                className="btn px-3 py-1.5 text-sm"
                title="The top 11, plus the team outside them whose players earned the most DC from matches in the 30 days before the Cup"
                onClick={() => run(() => api(`${base}/invite-top`, { method: "POST", body: { n: 12, dc_wildcard: true } }))}
              >
                Top 11 + DC wildcard
              </button>
            </>
          )}
          {!done && t.registration.qualifier && (
            <>
              <button
                type="button"
                className="btn ml-auto px-3 py-1.5 text-sm"
                onClick={() => run(() => api(`${base}/invite-top`, { method: "POST", body: {} }))}
              >
                Invite the top {t.registration.invite_count} now
              </button>
              <button type="button" className="btn px-3 py-1.5 text-sm" onClick={() => run(() => api(`${base}/invite-next`, { method: "POST" }))}>
                Invite the next team
              </button>
            </>
          )}
        </div>
        <TeamEditor t={t} base={base} run={run} locked={done || !!t.cancelled_at} />
        <p className="mt-2 text-xs text-muted">
          {t.registration.qualifier
            ? `The top ${t.registration.invite_count} are invited when registration opens (the list is frozen then). If one declines, "Invite the next team" takes the best team in the standings that isn't in.`
            : "\"Invite the top 12\" fills the list from the league standings as they are now."}{" "}
          Add or remove teams by hand after that; to swap one, remove it and add the other.
        </p>
      </section>

      <RegistrationSettings t={t} base={base} run={run} />

      <PrizeTable t={t} base={base} run={run} />
      <Days t={t} base={base} run={run} />
      <Payout t={t} base={base} run={run} />
    </div>
  );
}

function PrizeTable({ t, base, run }: { t: Staff; base: string; run: (fn: () => Promise<unknown>) => void }) {
  const [rows, setRows] = useState<PrizeRow[]>(t.prizes.map(({ key, label, cash, dc: coins }) => ({ key, label, cash, dc: coins })));
  const done = !!t.confirmed_at;
  const set = (i: number, change: Partial<PrizeRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...change } : r)));
  const paid = new Set(t.prizes.filter((p) => p.cash_paid).map((p) => p.key));
  return (
    <section className="card p-4">
      <h3 className="section-title">Prizes</h3>
      <p className="mt-1 text-sm text-muted">
        {naira(t.total_cash)} cash (you pay it, the site only shows it) and {dc(t.total_dc)} paid to the winners&apos; wallets. Tick a cash prize once
        you&apos;ve paid it and the public page says so.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="text-left">Prize</th>
              <th className="text-right">Cash ₦</th>
              <th className="text-right">DC{rows.some((r) => r.key.includes("-")) ? " (each place)" : ""}</th>
              <th className="text-left">Cash paid</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.key} className="[&>td]:px-1 [&>td]:py-1">
                <td>
                  <input className="input py-1" value={r.label} disabled={done} onChange={(e) => set(i, { label: e.target.value })} aria-label="Prize name" />
                </td>
                <td>
                  <input className="input w-28 py-1 text-right" inputMode="numeric" value={r.cash} disabled={done} onChange={(e) => set(i, { cash: Number(e.target.value.replace(/\D/g, "")) || 0 })} aria-label="Cash" />
                </td>
                <td>
                  <input className="input w-32 py-1 text-right" inputMode="numeric" value={r.dc} disabled={done} onChange={(e) => set(i, { dc: Number(e.target.value.replace(/\D/g, "")) || 0 })} aria-label="DC" />
                </td>
                <td>
                  {r.cash > 0 && (
                    <input
                      type="checkbox"
                      checked={paid.has(r.key)}
                      aria-label="Cash paid"
                      onChange={(e) => {
                        const next = new Set(paid);
                        if (e.target.checked) next.add(r.key);
                        else next.delete(r.key);
                        run(() => api(base, { method: "PATCH", body: { cash_paid: [...next] } }));
                      }}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!done && (
        <button type="button" className="btn mt-3 px-3 py-1.5 text-sm" onClick={() => run(() => api(base, { method: "PATCH", body: { prizes: rows } }))}>
          Save prizes
        </button>
      )}
    </section>
  );
}

function Days({ t, base, run }: { t: Staff; base: string; run: (fn: () => Promise<unknown>) => void }) {
  const [league, setLeague] = useState<LeagueDay[] | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  useEffect(() => {
    api<LeagueDay[]>(`${base}/match-days`)
      .then((d) => {
        setLeague(d);
        setPicked(d.filter((x) => x.suggested).map((x) => x.id));
      })
      .catch(() => setLeague([]));
  }, [base, t.matches]);
  return (
    <section className="card p-4">
      <h3 className="section-title">Match days</h3>
      <p className="mt-1 text-sm text-muted">
        Upload as usual. On the upload page, pick <b>{t.name}</b> under &quot;Counts for&quot; (it&apos;s picked for you when the room name has
        the keyword). Cup nights still settle predictions when the match day name has 8PM or 10PM, like &quot;TDL CUP DAY 1 10PM&quot;.
      </p>
      <ul className="mt-2 text-sm">
        {t.match_days.length ? t.match_days.map((d) => <li key={d.id}>{d.title || `Day ${d.number}`} {d.date ? `(${d.date})` : ""}</li>) : <li className="text-muted">None yet.</li>}
      </ul>
      {!t.confirmed_at && league && league.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-accent">Uploaded into the league instead? Move match days in</summary>
          <ul className="mt-2 space-y-1 text-sm">
            {league.map((d) => (
              <li key={d.id}>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={picked.includes(d.id)} onChange={(e) => setPicked(e.target.checked ? [...picked, d.id] : picked.filter((x) => x !== d.id))} />
                  {d.title} {d.date ? <span className="text-muted">({d.date})</span> : null}
                </label>
              </li>
            ))}
          </ul>
          <button
            type="button"
            disabled={!picked.length}
            className="btn mt-2 px-3 py-1.5 text-sm"
            onClick={() => run(() => api(`${base}/match-days`, { method: "POST", body: { match_days: picked } }))}
          >
            Move {picked.length} into {t.name}
          </button>
          <p className="mt-1 text-xs text-muted">Their results leave the scrim standings and count for the tournament. Settled predictions stay as they are.</p>
        </details>
      )}
    </section>
  );
}

function Payout({ t, base, run }: { t: Staff; base: string; run: (fn: () => Promise<unknown>) => void }) {
  const [view, setView] = useState<Preview | Paid | null>(null);
  const [igl, setIgl] = useState("");
  useEffect(() => {
    api<Preview | Paid>(`${base}/payout`)
      .then(setView)
      .catch(() => setView(null));
  }, [base, t.matches, t.confirmed_at]);
  if (!view) return null;
  if (view.confirmed)
    return (
      <section className="card p-4">
        <h3 className="section-title">Paid out</h3>
        <ul className="mt-2 space-y-1 text-sm">
          {view.payouts.map((p, i) => (
            <li key={i}>
              {p.label}: <b>{p.player}</b> {dc(p.amount)} {p.paid ? "" : <span className="chip chip-gold">Waiting for their account</span>}
            </li>
          ))}
        </ul>
      </section>
    );
  const igLRow = view.prizes.find((p) => p.key === "best_igl");
  return (
    <section className="card p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="section-title">Pay out</h3>
        <span className={view.ready ? "chip chip-gold" : "chip"}>{view.ready ? "Ready to confirm" : `${view.matches} of ${view.planned_matches} matches in`}</span>
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="text-left">Prize</th>
              <th className="text-left">Winner</th>
              <th className="text-right">Cash</th>
              <th className="text-right">DC</th>
              <th className="text-left">Each player</th>
            </tr>
          </thead>
          <tbody>
            {view.prizes.flatMap((p) =>
              (p.winners.length ? p.winners : [null]).map((w, i) => (
                <tr key={`${p.key}-${i}`} className="[&>td]:px-2 [&>td]:py-2">
                  <td className="font-display font-extrabold uppercase">{w?.place ? `#${w.place}` : p.label}</td>
                  <td className="text-sm">
                    {w ? (w.player ?? w.team?.name) : <span className="text-muted">–</span>} {w?.detail && <span className="text-xs text-muted">· {w.detail}</span>}
                  </td>
                  <td className="num text-right">{p.cash ? naira(p.cash) : "–"}</td>
                  <td className="num text-right text-accent-2">{p.dc.toLocaleString("en-GB")}</td>
                  <td className="text-xs text-muted">{w?.shares.map((s) => `${s.player} ${s.amount.toLocaleString("en-GB")}${s.has_account ? "" : " (held)"}`).join(", ")}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
      {igLRow && (
        <label className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Best IGL</span>
          <select className="input w-auto py-1" value={igl} onChange={(e) => setIgl(e.target.value)}>
            <option value="">{igLRow.winners[0]?.player ? `${igLRow.winners[0].player} (as shown)` : "Pick a player"}</option>
            {view.igl_choices.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {view.no_account > 0 && (
        <p className="mt-3 border-l-[3px] border-accent bg-accent/5 px-3 py-2 text-sm">
          {view.no_account} winner{view.no_account === 1 ? " has" : "s have"} no site account yet. Their DC is held and lands when they sign up with their
          game UID.
        </p>
      )}
      <button
        type="button"
        disabled={!view.ready}
        className="btn btn-primary mt-4"
        onClick={() => run(() => api(`${base}/payout`, { method: "POST", body: igl ? { best_igl: Number(igl) } : {} }))}
      >
        Confirm &amp; pay {dc(view.total_dc)}
      </button>
      <p className="mt-1 text-xs text-muted">Pays once and can&apos;t be undone. Check the table first.</p>
    </section>
  );
}

function TeamEditor({ t, base, run, locked }: { t: Staff; base: string; run: (fn: () => Promise<unknown>) => void; locked: boolean }) {
  const [all, setAll] = useState<TeamRef[]>([]);
  const [pick, setPick] = useState("");
  useEffect(() => {
    if (locked) return;
    api<Paged<TeamRef>>("/teams?page_size=100")
      .then((p) => setAll(p.results))
      .catch(() => setAll([]));
  }, [locked]);
  const shown = finalTeams(t);
  const ids = shown.map((x) => x.id);
  const save = (next: number[]) => run(() => api(base, { method: "PATCH", body: { teams: next } }));
  const others = all.filter((x) => !ids.includes(x.id)).sort((a, b) => a.name.localeCompare(b.name));
  return (
    <>
      {shown.length ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {shown.map((x) => (
            <li key={x.id} className="chip gap-1.5">
              {x.name}
              {!locked && (
                <button
                  type="button"
                  aria-label={`Remove ${x.name}`}
                  className="-mr-1 rounded px-1 text-muted hover:text-bad"
                  onClick={() => {
                    if (window.confirm(`Remove ${x.name} from ${t.name}?`)) save(ids.filter((id) => id !== x.id));
                  }}
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted">No teams yet.</p>
      )}
      {!locked && (
        <form
          className="mt-3 flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!pick) return;
            save([...ids, Number(pick)]);
            setPick("");
          }}
        >
          <select className="input max-w-xs" value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Team to add">
            <option value="">Pick a team to add…</option>
            {others.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
          <button type="submit" className="btn px-3 py-1.5 text-sm" disabled={!pick}>
            Add team
          </button>
        </form>
      )}
    </>
  );
}

/** The teams in the final stage (all the teams, for a tournament without a qualifier). */
function finalTeams(t: Staff) {
  if (!t.registration.qualifier) return t.teams;
  return t.entries.filter((e) => e.stage === t.registration.final.id && e.status === "IN").map((e) => e.team);
}

function local(iso: string | null): string {
  // A <input type="datetime-local"> value in the browser's time.
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Registration: a qualifier stage, the fee, places, dates, who registered (and their fees),
 * sending the qualifier's top teams to the final, and cancelling with refunds. */
function RegistrationSettings({ t, base, run }: { t: Staff; base: string; run: (fn: () => Promise<unknown>) => void }) {
  const r = t.registration;
  const done = !!t.confirmed_at || !!t.cancelled_at;
  if (!r.qualifier)
    return (
      <section className="card p-4">
        <h3 className="section-title">Registration with DC</h3>
        <p className="mt-1 text-sm text-muted">
          Add a qualifier to let teams register: the top teams are invited straight into the {r.final.name}, every other team pays DC to play the
          qualifier, and its top teams go through.
        </p>
        {!done && (
          <button type="button" className="btn mt-3 px-3 py-1.5 text-sm" onClick={() => run(() => api(`${base}/qualifier`, { method: "POST", body: {} }))}>
            Add a qualifier
          </button>
        )}
      </section>
    );
  const q = r.qualifier;
  const inQ = t.entries.filter((e) => e.stage === q.id && (e.status === "IN" || e.status === "WAITLIST"));
  const gone = t.entries.filter((e) => e.status === "WITHDRAWN" || e.status === "REMOVED");
  const held = t.entries.reduce((n, e) => n + (e.fee_paid ?? 0), 0);
  return (
    <section className="card p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="section-title">Registration · {q.name}</h3>
        <span className={`chip ${r.state === "open" ? "chip-hot" : ""}`}>{r.state === "off" ? "Set the dates" : r.state}</span>
        <span className="text-sm text-muted">
          {r.taken}/{r.places} places · {r.waitlist} waiting · {dc(held)} in fees
        </span>
      </div>
      {r.state !== "off" && <p className="mt-1 text-sm text-muted">{regText(r)}</p>}
      <form
        className="mt-3 grid gap-3 sm:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const at = (k: string) => (f.get(k) ? new Date(String(f.get(k))).toISOString() : null);
          run(() =>
            api(base, {
              method: "PATCH",
              body: {
                reg_opens_at: at("reg_opens_at"),
                reg_closes_at: at("reg_closes_at"),
                entry_fee: Number(f.get("entry_fee")),
                places: Number(f.get("places")),
                invite_count: Number(f.get("invite_count")),
                qualify_count: Number(f.get("qualify_count")),
              },
            }),
          );
        }}
      >
        <label className="text-sm">
          <span className="text-muted">Opens</span>
          <input name="reg_opens_at" type="datetime-local" defaultValue={local(r.opens_at)} className="input mt-1" disabled={done} />
        </label>
        <label className="text-sm">
          <span className="text-muted">Closes</span>
          <input name="reg_closes_at" type="datetime-local" defaultValue={local(r.closes_at)} className="input mt-1" disabled={done} />
        </label>
        <label className="text-sm">
          <span className="text-muted">Entry fee (DC per team)</span>
          <input name="entry_fee" type="number" min={0} defaultValue={r.fee} className="input mt-1" disabled={done} />
        </label>
        <label className="text-sm">
          <span className="text-muted">{q.name} places</span>
          <input name="places" type="number" min={2} defaultValue={r.places} className="input mt-1" disabled={done} />
        </label>
        <label className="text-sm">
          <span className="text-muted">Top teams invited to the {r.final.name}</span>
          <input name="invite_count" type="number" min={0} defaultValue={r.invite_count} className="input mt-1" disabled={done} />
        </label>
        <label className="text-sm">
          <span className="text-muted">Go through from the {q.name}</span>
          <input name="qualify_count" type="number" min={1} defaultValue={r.qualify_count} className="input mt-1" disabled={done} />
        </label>
        {!done && (
          <div className="sm:col-span-3">
            <button type="submit" className="btn px-3 py-1.5 text-sm">
              Save registration
            </button>
            <span className="ml-3 text-xs text-muted">Times are in your browser&apos;s time zone. Fees are spent (they leave the game).</span>
          </div>
        )}
      </form>

      <h4 className="mt-5 font-display text-lg uppercase">{q.name} teams</h4>
      <EntryRows rows={inQ} base={base} run={run} locked={done} />
      {!done && <AddToStage t={t} stage={q.id} base={base} run={run} />}

      <Advance t={t} base={base} run={run} locked={done} />

      {gone.length > 0 && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer text-muted">Withdrew or removed ({gone.length})</summary>
          <EntryRows rows={gone} base={base} run={run} locked />
        </details>
      )}

      {!done && (
        <button
          type="button"
          className="btn btn-ghost mt-5 text-sm text-bad"
          onClick={() => {
            if (window.confirm(`Cancel ${t.name}? Every entry fee goes back to whoever paid it. This can't be undone.`))
              run(() => api(`${base}/cancel`, { method: "POST" }));
          }}
        >
          Cancel the tournament (refund every fee)
        </button>
      )}
      {t.cancelled_at && <p className="mt-4 text-sm text-bad">Cancelled. Every entry fee was refunded.</p>}
    </section>
  );
}

function EntryRows({ rows, base, run, locked }: { rows: Entry[]; base: string; run: (fn: () => Promise<unknown>) => void; locked: boolean }) {
  if (!rows.length) return <p className="mt-2 text-sm text-muted">None yet.</p>;
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="table">
        <thead>
          <tr>
            <th className="text-left">Team</th>
            <th className="text-left">How</th>
            <th className="text-right">Fee held</th>
            <th className="text-left">Paid by</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.id} className="[&>td]:px-2 [&>td]:py-1.5">
              <td>
                {e.team.name} {e.status === "WAITLIST" && <span className="chip ml-1">Waitlist</span>}
                {e.note && <span className="block text-xs text-muted">{e.note}</span>}
              </td>
              <td className="text-sm">{VIA_LABEL[e.via]}</td>
              <td className="num text-right">
                {e.fee_paid ? dc(e.fee_paid) : "–"}
                {e.refunded ? <span className="block text-xs text-muted">{dc(e.refunded)} refunded</span> : null}
              </td>
              <td className="text-sm">
                {e.paid_from === "POT" ? "Team pot" : e.paid_by ?? <span className="text-muted">–</span>}
                {e.paid_from === "POT" && e.paid_by && <span className="text-xs text-muted"> ({e.paid_by})</span>}
              </td>
              <td className="text-right whitespace-nowrap">
                {!locked && (
                  <>
                    <button
                      type="button"
                      className="btn btn-ghost px-2 py-1 text-xs"
                      onClick={() => {
                        if (window.confirm(`Take ${e.team.name} out and refund its fee?`)) run(() => api(`${base}/entries/${e.id}/remove`, { method: "POST", body: {} }));
                      }}
                    >
                      Remove
                    </button>
                    {!!e.fee_paid && (
                      <button
                        type="button"
                        className="btn btn-ghost px-2 py-1 text-xs text-bad"
                        title="For a rule break: the team is out and the fee is not refunded"
                        onClick={() => {
                          if (window.confirm(`Take ${e.team.name} out and KEEP its ${dc(e.fee_paid ?? 0)} fee?`))
                            run(() => api(`${base}/entries/${e.id}/remove`, { method: "POST", body: { keep_fee: true } }));
                        }}
                      >
                        Remove, keep fee
                      </button>
                    )}
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AddToStage({ t, stage, base, run }: { t: Staff; stage: number; base: string; run: (fn: () => Promise<unknown>) => void }) {
  const [all, setAll] = useState<TeamRef[]>([]);
  const [pick, setPick] = useState("");
  useEffect(() => {
    api<Paged<TeamRef>>("/teams?page_size=100")
      .then((p) => setAll(p.results))
      .catch(() => setAll([]));
  }, []);
  const busy = new Set(t.entries.filter((e) => e.status === "IN" || e.status === "WAITLIST").map((e) => e.team.id));
  const others = all.filter((x) => !busy.has(x.id)).sort((a, b) => a.name.localeCompare(b.name));
  return (
    <form
      className="mt-2 flex flex-wrap gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!pick) return;
        run(() => api(`${base}/entries`, { method: "POST", body: { team: Number(pick), stage } }));
        setPick("");
      }}
    >
      <select className="input max-w-xs" value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Team to add for free">
        <option value="">Add a team for free…</option>
        {others.map((x) => (
          <option key={x.id} value={x.id}>
            {x.name}
          </option>
        ))}
      </select>
      <button type="submit" className="btn px-3 py-1.5 text-sm" disabled={!pick}>
        Add
      </button>
    </form>
  );
}

function Advance({ t, base, run, locked }: { t: Staff; base: string; run: (fn: () => Promise<unknown>) => void; locked: boolean }) {
  const r = t.registration;
  const through = t.qualifier_table.filter((x) => x.through);
  return (
    <div className="mt-5 border-t border-line pt-4">
      <h4 className="font-display text-lg uppercase">Send to the {r.final.name}</h4>
      {t.qualifier_table.length ? (
        <ol className="mt-2 space-y-1 text-sm">
          {t.qualifier_table.map((x) => (
            <li key={x.team.id} className={x.through ? "font-semibold" : "text-muted"}>
              #{x.rank} {x.team.name} · {x.points} pts {x.through && <span className="chip chip-gold ml-1">Through</span>}
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-1 text-sm text-muted">The {r.qualifier?.name} table fills in as its matches are uploaded.</p>
      )}
      {r.advanced_at && <p className="mt-2 text-sm text-ok">Sent. New uploads now go to the {r.final.name}.</p>}
      {!locked && through.length > 0 && (
        <button
          type="button"
          className="btn btn-primary mt-3 px-3 py-1.5 text-sm"
          onClick={() => {
            if (window.confirm(`Send ${through.map((x) => x.team.name).join(", ")} to the ${r.final.name}?`)) run(() => api(`${base}/advance`, { method: "POST", body: {} }));
          }}
        >
          {r.advanced_at ? "Send again" : `Send the top ${r.qualify_count} through`}
        </button>
      )}
      <p className="mt-1 text-xs text-muted">Until you do, uploads for {t.name} go to the {r.qualifier?.name}.</p>
    </div>
  );
}
