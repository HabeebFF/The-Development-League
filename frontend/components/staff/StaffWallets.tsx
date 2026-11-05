"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useStaff } from "@/app/staff/StaffGate";
import { api, ApiError, type Paged } from "@/lib/api";
import { BET_STATUS, coins, newKey, signedCoins, type Bet, type Entry, type Multiple } from "@/lib/predictions";

type StaffWallet = {
  id: number;
  email: string;
  display_name: string;
  balance: number;
  entry_count: number;
  created_at: string;
  won: number;
  lost: number;
  pending: number;
  last_active: string | null;
};
type StaffEntry = Entry & { idempotency_key: string; actor: string | null };
type Summary = { wallets: number; held: number; riding: number };

const SORTS = [
  { key: "balance", label: "Most DC" },
  { key: "recent", label: "Predicted most recently" },
  { key: "active", label: "Most active" },
  { key: "new", label: "Newest" },
  { key: "name", label: "Name A to Z" },
];
const PAGE = 25;

function when(iso: string) {
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function ago(iso: string | null): string {
  if (!iso) return "never predicted";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `predicted ${Math.max(mins, 1)}m ago`;
  if (mins < 60 * 24) return `predicted ${Math.round(mins / 60)}h ago`;
  return `predicted ${Math.round(mins / 1440)}d ago`;
}

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** Staff: everyone's DC. Totals at the top, search and sort, then one row per person; open a row
 * for their predictions, their DC history and (Super Admin) an adjustment. */
export default function StaffWallets() {
  const me = useStaff();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("balance");
  const [pages, setPages] = useState(1);
  const [data, setData] = useState<{ rows: StaffWallet[]; count: number } | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [version, setVersion] = useState(0);
  const refresh = () => setVersion((v) => v + 1);

  // Search after a short pause in typing, not on every key.
  useEffect(() => {
    const id = setTimeout(() => {
      setQuery(search.trim());
      setPages(1);
    }, 300);
    return () => clearTimeout(id);
  }, [search]);

  useEffect(() => {
    let live = true;
    api<Paged<StaffWallet>>(`/admin/predictions/wallets?page_size=${PAGE * pages}&sort=${sort}&search=${encodeURIComponent(query)}`)
      .then((p) => live && setData({ rows: p.results, count: p.count }))
      .catch(() => live && setData({ rows: [], count: 0 }));
    api<Summary>("/admin/predictions/wallets/summary")
      .then((s) => live && setSummary(s))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [query, sort, pages, version]);

  return (
    <div className="mt-6">
      {summary && (
        <div className="grid grid-cols-3 gap-2">
          <Tile label="People" value={summary.wallets.toLocaleString("en-GB")} />
          <Tile label="DC held" value={coins(summary.held)} />
          <Tile label="On open bets" value={coins(summary.riding)} />
        </div>
      )}
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <input
          className="input flex-1"
          type="search"
          placeholder="Search by name or email"
          aria-label="Search wallets"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="input sm:w-64"
          aria-label="Sort by"
          value={sort}
          onChange={(e) => {
            setSort(e.target.value);
            setPages(1);
          }}
        >
          {SORTS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {!data ? (
        <p className="mt-4 text-muted">Loading...</p>
      ) : data.rows.length === 0 ? (
        <p className="mt-4 text-muted">{query ? `Nobody matches "${query}".` : "No wallets yet."}</p>
      ) : (
        <>
          <p className="mt-3 text-xs text-muted">
            Showing {data.rows.length} of {data.count}
          </p>
          <ul className="mt-2 space-y-2">
            {data.rows.map((w) => (
              <li key={w.id} className={`card text-sm ${open === w.id ? "border-accent" : ""}`}>
                <button
                  type="button"
                  aria-expanded={open === w.id}
                  className="flex w-full items-center gap-3 p-3 text-left"
                  onClick={() => setOpen(open === w.id ? null : w.id)}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{w.display_name || "No name"}</span>
                    <span className="block truncate text-xs text-muted">{w.email}</span>
                    <span className="mt-1 block text-xs text-muted">
                      <span className="text-ok">{w.won} won</span> · <span className="text-bad">{w.lost} lost</span>
                      {w.pending > 0 && <span className="text-accent-2"> · {w.pending} open</span>} · {ago(w.last_active)}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="block font-display text-xl text-accent-2">{coins(w.balance)}</span>
                    <span className="text-xs text-muted">{open === w.id ? "Close" : "Open"}</span>
                  </span>
                </button>
                {open === w.id && <WalletDetail wallet={w} canAdjust={me.is_super_admin} onAdjusted={refresh} />}
              </li>
            ))}
          </ul>
          {data.rows.length < data.count && (
            <button type="button" className="btn mt-3 w-full" onClick={() => setPages(pages + 1)}>
              Show more
            </button>
          )}
        </>
      )}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-3">
      <p className="text-[11px] font-bold tracking-widest text-muted uppercase">{label}</p>
      <p className="mt-1 font-display text-xl leading-tight sm:text-2xl">{value}</p>
    </div>
  );
}

type Tab = "bets" | "history" | "adjust";

function WalletDetail({ wallet, canAdjust, onAdjusted }: { wallet: StaffWallet; canAdjust: boolean; onAdjusted: () => void }) {
  const [tab, setTab] = useState<Tab>("bets");
  const tabs: { key: Tab; label: string }[] = [
    { key: "bets", label: "Predictions" },
    { key: "history", label: "DC history" },
    ...(canAdjust ? [{ key: "adjust" as Tab, label: "Adjust DC" }] : []),
  ];
  return (
    <div className="border-t border-line px-3 pt-2 pb-3">
      <div className="flex gap-1 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            aria-pressed={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`shrink-0 border px-3 py-1 text-sm font-semibold ${tab === t.key ? "border-accent bg-accent/15 text-white" : "border-line text-muted hover:text-white"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "bets" && <WalletBets wallet={wallet} />}
      {tab === "history" && <WalletHistory wallet={wallet} />}
      {tab === "adjust" && <Adjust wallet={wallet} onAdjusted={onAdjusted} />}
    </div>
  );
}

type Row = { kind: "single"; bet: Bet } | { kind: "multiple"; bet: Multiple };

function WalletBets({ wallet }: { wallet: StaffWallet }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  useEffect(() => {
    let live = true;
    api<{ singles: Bet[]; multiples: Multiple[] }>(`/admin/predictions/wallets/${wallet.id}/bets`)
      .then((d) => {
        if (!live) return;
        const all: Row[] = [...d.singles.map((bet) => ({ kind: "single" as const, bet })), ...d.multiples.map((bet) => ({ kind: "multiple" as const, bet }))];
        all.sort((a, b) => b.bet.placed_at.localeCompare(a.bet.placed_at));
        setRows(all);
      })
      .catch(() => live && setRows([]));
    return () => {
      live = false;
    };
  }, [wallet.id]);
  if (!rows) return <p className="mt-3 text-muted">Loading...</p>;
  if (rows.length === 0) return <p className="mt-3 text-muted">No predictions yet.</p>;
  return (
    <ul className="mt-3 divide-y divide-line/60">
      {rows.map((r) => {
        const s = BET_STATUS[r.bet.status];
        const paid = r.bet.payout ?? 0;
        return (
          <li key={r.bet.id} className="flex items-start gap-3 py-2">
            <div className="min-w-0 flex-1">
              {r.kind === "single" ? (
                <>
                  <Link href={`/predict/markets/${r.bet.market.id}`} className="font-semibold hover:text-accent">
                    {r.bet.outcome.label}
                  </Link>
                  <p className="text-xs text-muted">
                    {r.bet.market.title}
                    {r.bet.market.fixture ? ` · ${r.bet.market.fixture.title}` : ""}
                  </p>
                </>
              ) : (
                <>
                  <p className="font-semibold">Multiple · {r.bet.picks.length} picks</p>
                  <p className="text-xs text-muted">{r.bet.picks.map((p) => p.outcome.label).join(" + ")}</p>
                </>
              )}
              <p className="mt-0.5 text-xs text-muted">
                {when(r.bet.placed_at)} · {r.bet.stake} DC at {r.kind === "single" ? r.bet.odds_accepted : r.bet.odds}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <span className={`chip ${s.tone}`}>{s.label}</span>
              <p className="mt-1 text-xs text-muted">
                {r.bet.status === "PENDING"
                  ? `could return ${r.bet.potential_return}`
                  : r.bet.status === "LOST"
                    ? `lost ${r.bet.stake}`
                    : r.bet.status === "VOID"
                      ? `${paid} back`
                      : `paid ${paid}`}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function WalletHistory({ wallet }: { wallet: StaffWallet }) {
  const [entries, setEntries] = useState<StaffEntry[] | null>(null);
  useEffect(() => {
    let live = true;
    api<Paged<StaffEntry>>(`/admin/predictions/wallets/${wallet.id}/entries?page_size=100`)
      .then((p) => live && setEntries(p.results))
      .catch(() => live && setEntries([]));
    return () => {
      live = false;
    };
  }, [wallet.id, wallet.balance]);
  if (!entries) return <p className="mt-3 text-muted">Loading...</p>;
  return (
    <ul className="mt-3 divide-y divide-line/60">
      {entries.map((e) => (
        <li key={e.id} className="flex items-start gap-3 py-2">
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{e.kind_label}</p>
            <p className="text-xs text-muted">
              {when(e.created_at)}
              {e.actor ? ` · by ${e.actor}` : ""}
              {e.reason ? ` · ${e.reason}` : ""}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className={e.amount > 0 ? "text-ok" : "text-bad"}>{signedCoins(e.amount)}</p>
            <p className="text-xs text-muted">now {e.balance_after}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function Adjust({ wallet, onAdjusted }: { wallet: StaffWallet; onAdjusted: () => void }) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [key, setKey] = useState(newKey);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);

  async function adjust() {
    setNote(null);
    try {
      await api(`/admin/predictions/wallets/${wallet.id}/adjust`, { method: "POST", body: { amount: Number(amount), reason, key } });
      setNote({ ok: true, text: `Done: ${signedCoins(Number(amount))} DC.` });
      setAmount("");
      setReason("");
      setKey(newKey());
      onAdjusted();
    } catch (e) {
      setNote({ ok: false, text: message(e) });
    }
  }

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <input
        className="input w-28"
        inputMode="numeric"
        placeholder="+50 or -50"
        aria-label="Amount"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <input className="input min-w-40 flex-1" placeholder="Reason (required)" aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      <button type="button" className="btn btn-primary" disabled={!/^-?\d+$/.test(amount) || Number(amount) === 0 || reason.trim().length < 5} onClick={adjust}>
        Adjust DC
      </button>
      {note && <p className={`w-full text-sm ${note.ok ? "text-ok" : "text-bad"}`}>{note.text}</p>}
    </div>
  );
}
