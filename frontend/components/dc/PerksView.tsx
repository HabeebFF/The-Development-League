"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { PALETTES } from "@/lib/cardDesigns";
import {
  clockTime,
  dc,
  PERK_TEXT,
  parseClock,
  type MyEarnings,
  type Perk,
  type PerkPurchase,
  type PerksPage,
} from "@/lib/dc";
import { newKey } from "@/lib/predictions";
import { useApi } from "@/lib/useApi";

import { useAuth } from "../Auth";
import { SkeletonRows } from "../league/Loading";

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

function until(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Player shop > Perks: spend DC on things people see (never on how you play), and chip in to
 * the team pot that pays for team perks. */
export default function PerksView() {
  const { status } = useAuth();
  const [page, setPage] = useState<PerksPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(() => {
    api<PerksPage>("/dc/perks")
      .then(setPage)
      .catch((e) => setError(message(e)));
  }, []);
  useEffect(() => {
    if (status !== "loading") load();
  }, [status, load]);

  async function buy(perk: Perk, data: Record<string, unknown>, image?: File) {
    setError(null);
    setDone(null);
    try {
      let body: FormData | Record<string, unknown>;
      if (image) {
        body = new FormData();
        body.append("key", perk.key);
        body.append("once", newKey());
        body.append("data", JSON.stringify(data));
        body.append("image", image);
      } else {
        body = { key: perk.key, once: newKey(), data };
      }
      const row = await api<PerkPurchase>("/dc/perks/buy", {
        method: "POST",
        body,
      });
      setDone(
        row.status === "PENDING"
          ? `${perk.name} sent to staff. If they turn it down you get the DC back.`
          : `${perk.name} is on.`,
      );
      load();
    } catch (e) {
      setError(message(e));
    }
  }

  async function chipIn(amount: number) {
    setError(null);
    setDone(null);
    try {
      await api("/dc/pot", {
        method: "POST",
        body: { amount, once: newKey() },
      });
      setDone(`${dc(amount)} into the team pot.`);
      load();
    } catch (e) {
      setError(message(e));
    }
  }

  if (!page)
    return error ? (
      <p className="text-bad">{error}</p>
    ) : (
      <SkeletonRows count={4} />
    );
  const me = page.me;

  return (
    <div className="space-y-6">
      {!me ? (
        <div className="card p-4 text-sm">
          Perks are for league players.{" "}
          {status === "in" ? (
            <Link href="/account" className="underline">
              Link your Free Fire UID
            </Link>
          ) : (
            <Link href="/auth/login" className="underline">
              Sign in
            </Link>
          )}{" "}
          to buy them with the DC you earn from your matches.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="card p-4">
            <p className="eyebrow">Your DC</p>
            <p className="mt-1 font-display text-3xl text-accent">
              {dc(me.balance)}
            </p>
            <p className="mt-1 text-xs text-muted">For your own perks below.</p>
          </div>
          <TeamPot me={me} onChip={chipIn} />
        </div>
      )}

      {done && (
        <p className="border-l-[3px] border-ok bg-panel-2 px-3 py-2 text-sm">
          {done}
        </p>
      )}
      {error && (
        <p className="border-l-[3px] border-bad bg-panel-2 px-3 py-2 text-sm text-bad">
          {error}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {page.perks.map((p) => (
          <PerkCard key={p.key} perk={p} page={page} onBuy={buy} />
        ))}
      </div>

      {me && me.purchases.length > 0 && (
        <div className="card p-4">
          <h2 className="font-display text-2xl uppercase">Your perks</h2>
          <ul className="mt-2 divide-y divide-line text-sm">
            {me.purchases.map((r) => (
              <li
                key={r.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2"
              >
                <b>{r.name}</b>
                <span
                  className={
                    r.status === "ACTIVE"
                      ? "text-ok"
                      : r.status === "PENDING"
                        ? "text-accent"
                        : "text-muted"
                  }
                >
                  {r.status_label}
                </span>
                {r.ends_at && r.status === "ACTIVE" && (
                  <span className="text-muted">until {until(r.ends_at)}</span>
                )}
                {r.review_note && (
                  <span className="text-muted">
                    &ldquo;{r.review_note}&rdquo;
                  </span>
                )}
                <span className="ml-auto text-muted">
                  {dc(r.price)}
                  {r.from_pot ? " from the pot" : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted">
        Perks only change what people see. Nothing in DC buys a scrim place, a
        map, or a Cup spot: the team that earns the most DC from matches in a
        week gets the scrim waitlist tie-break the week after, and the Cup can
        give its last place to the month&apos;s top DC team.
      </p>
    </div>
  );
}

function TeamPot({
  me,
  onChip,
}: {
  me: NonNullable<PerksPage["me"]>;
  onChip: (n: number) => void;
}) {
  const [amount, setAmount] = useState(1000);
  if (!me.team)
    return (
      <div className="card p-4 text-sm text-muted">
        Join a team to chip in to its pot for team perks.
      </div>
    );
  return (
    <div className="card p-4">
      <p className="eyebrow">{me.team.name} pot</p>
      <p className="mt-1 font-display text-3xl text-accent">{dc(me.pot)}</p>
      <p className="mt-1 text-xs text-muted">
        {me.can_spend_pot
          ? "You can spend it on team perks."
          : "Your manager spends it on team perks."}{" "}
        DC in the pot can&apos;t come back out.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          type="number"
          min={100}
          step={100}
          className="input py-1"
          style={{ width: "8rem" }}
          value={amount}
          onChange={(e) => setAmount(Number(e.target.value))}
          aria-label="DC to chip in"
        />
        <button
          className="btn px-3 py-1.5 text-sm"
          onClick={() => onChip(amount)}
          disabled={amount < 100 || amount > me.balance}
        >
          Chip in
        </button>
      </div>
      {me.pot_entries.length > 0 && (
        <ul className="mt-3 space-y-0.5 text-xs text-muted">
          {me.pot_entries.slice(0, 5).map((e, i) => (
            <li key={i}>
              {e.amount > 0 ? "+" : ""}
              {e.amount.toLocaleString("en-GB")} · {e.note}
              {e.by ? ` · ${e.by}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PerkCard({
  perk,
  page,
  onBuy,
}: {
  perk: Perk;
  page: PerksPage;
  onBuy: (
    p: Perk,
    data: Record<string, unknown>,
    image?: File,
  ) => Promise<void>;
}) {
  const me = page.me;
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [colour, setColour] = useState(page.name_colours[0]);
  const [primary, setPrimary] = useState("#f5a524");
  const [secondary, setSecondary] = useState("#0b0c10");
  const [file, setFile] = useState<File | null>(null);
  const [matchId, setMatchId] = useState<number | "">("");
  const [at, setAt] = useState("");
  const [note, setNote] = useState("");
  const earnings = useApi<MyEarnings>(
    perk.key === "PIN" && me ? "/dc/me" : null,
  );
  const matches =
    earnings.data && earnings.data.linked ? earnings.data.latest : [];

  const canAfford = me
    ? perk.for_team
      ? me.pot >= perk.price && me.can_spend_pot
      : me.balance >= perk.price
    : false;
  const ready =
    perk.key === "SHOUTOUT"
      ? text.trim().length >= 3
      : perk.key === "BANNER"
        ? !!file
        : perk.key === "PIN"
          ? matchId !== "" && (at.trim() === "" || parseClock(at) != null)
          : true;

  async function go() {
    setBusy(true);
    const data =
      perk.key === "SHOUTOUT"
        ? { text }
        : perk.key === "NAME_COLOUR"
          ? { colour }
          : perk.key === "THEME"
            ? { primary, secondary }
            : perk.key === "PIN"
              ? { match_id: matchId, at_s: parseClock(at), note }
              : {};
    await onBuy(perk, data, file ?? undefined);
    setBusy(false);
  }

  return (
    <div className="card flex flex-col p-4">
      <div className="flex items-baseline gap-2">
        <h2 className="font-display text-2xl uppercase">{perk.name}</h2>
        <span className="ml-auto font-display text-lg text-accent">
          {dc(perk.price)}
        </span>
      </div>
      <p className="mt-1 text-sm text-muted">
        {PERK_TEXT[perk.key]}
        {perk.days
          ? ` Lasts ${perk.days === 1 ? "a day" : `${perk.days} days`}.`
          : ""}
        {perk.for_team ? " Paid from the team pot." : ""}
      </p>

      {me && (
        <div className="mt-3 flex-1 space-y-2 text-sm">
          {perk.key === "SHOUTOUT" && (
            <input
              className="input"
              maxLength={120}
              placeholder="GG to everyone in the 10PM lobby!"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          )}
          {perk.key === "NAME_COLOUR" && (
            <div className="flex flex-wrap gap-2">
              {page.name_colours.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColour(c)}
                  aria-label={c}
                  aria-pressed={colour === c}
                  className={`h-8 w-8 rounded-full border-2 ${colour === c ? "border-white" : "border-transparent"}`}
                  style={{ background: PALETTES[c]?.[3] }}
                />
              ))}
              <span
                className="self-center font-display text-lg uppercase"
                style={{ color: PALETTES[colour]?.[3] }}
              >
                Your name
              </span>
            </div>
          )}
          {perk.key === "THEME" && (
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="color"
                  value={primary}
                  onChange={(e) => setPrimary(e.target.value)}
                />{" "}
                Main
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="color"
                  value={secondary}
                  onChange={(e) => setSecondary(e.target.value)}
                />{" "}
                Second
              </label>
            </div>
          )}
          {perk.key === "BANNER" && (
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-xs"
            />
          )}
          {perk.key === "PIN" && (
            <>
              <select
                className="input"
                value={matchId}
                onChange={(e) =>
                  setMatchId(e.target.value ? Number(e.target.value) : "")
                }
              >
                <option value="">Pick one of your recent matches</option>
                {matches.map((m) => (
                  <option key={m.match_id} value={m.match_id}>
                    {m.day} · Match {m.number} · {m.kills} kills
                    {m.booyah ? " · Booyah" : ""}
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                <input
                  className="input"
                  style={{ width: "7rem" }}
                  placeholder="12:05"
                  value={at}
                  onChange={(e) => setAt(e.target.value)}
                  aria-label="Time in the match"
                />
                <input
                  className="input"
                  maxLength={80}
                  placeholder="What happened (optional)"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
              {at && parseClock(at) != null && (
                <p className="text-xs text-muted">
                  At {clockTime(parseClock(at))} in the match.
                </p>
              )}
            </>
          )}
        </div>
      )}

      {me && (
        <button
          className="btn btn-primary mt-3 self-start px-4"
          onClick={go}
          disabled={busy || !canAfford || !ready}
        >
          {busy
            ? "Buying..."
            : perk.for_team && !me.can_spend_pot
              ? "Manager only"
              : canAfford
                ? `Buy for ${dc(perk.price)}`
                : perk.for_team
                  ? "Not enough in the pot"
                  : "Not enough DC"}
        </button>
      )}
    </div>
  );
}
