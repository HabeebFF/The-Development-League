"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { dc, entryText, placesLeft, regText, type MyEntry, type Registration } from "@/lib/tournaments";

function message(e: unknown) {
  return e instanceof ApiError ? e.message : "That didn't work. Try again.";
}

/** "Register for <tournament>": the fee, places left and closing time, and the buttons for a
 * team's manager or linked players (pay from your wallet or the team pot). Also shows an
 * invited team its place, with a way to decline. Used on the tournament page and Team page. */
export default function TournamentRegister({
  slug,
  name,
  team,
  onChanged,
}: {
  slug: string;
  name: string;
  /** The team to show (Team page); else the signed-in person's own team. */
  team?: string;
  onChanged?: () => void;
}) {
  const [me, setMe] = useState<MyEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [payFrom, setPayFrom] = useState<"WALLET" | "POT">("WALLET");
  const path = `/tournaments/${encodeURIComponent(slug)}`;
  const query = team ? `?team=${encodeURIComponent(team)}` : "";

  const load = useCallback(() => {
    api<MyEntry>(`${path}/me${query}`)
      .then((d) => {
        setMe(d);
        if (d.can_use_pot && !d.pays) setPayFrom("POT");
      })
      .catch((e) => setError(message(e)));
  }, [path, query]);
  useEffect(load, [load]);

  async function press(what: "register" | "withdraw") {
    if (what === "withdraw" && !window.confirm(me?.entry?.via === "INVITED" ? `Decline the invite to ${name}?` : `Withdraw from ${name}? The fee is refunded.`)) return;
    setBusy(true);
    setError(null);
    try {
      setMe(
        await api<MyEntry>(`${path}/${what}`, {
          method: "POST",
          body: { pay_from: payFrom, ...(team ? { team } : {}) },
        }),
      );
      onChanged?.();
    } catch (e) {
      setError(message(e));
      load();
    } finally {
      setBusy(false);
    }
  }

  if (!me) return error ? <p className="text-sm text-bad">{error}</p> : null;
  const r = me.registration;
  if (r.state === "off" && !me.entry) return null;
  const left = placesLeft(r);
  const entry = me.entry;
  const canRegister = r.state === "open" && !entry && me.can_register;
  const canLeave = !!entry && me.can_register && entry.via !== "QUALIFIED" && (entry.via === "INVITED" || r.state === "open");
  const wallet = me.wallet ?? null;
  const short = payFrom === "POT" ? (me.pot ?? 0) < r.fee : wallet !== null && wallet < r.fee;

  return (
    <div className="card border-l-4 border-accent p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="eyebrow">{team ? name : "Register your team"}</p>
          <h3 className="font-display text-2xl leading-none font-black uppercase">
            {entry ? entryText(entry) : r.fee > 0 ? `${dc(r.fee)} entry` : "Free entry"}
          </h3>
        </div>
        {r.qualifier && (
          <span className="num text-2xl leading-none">
            {r.taken}/{r.places}
            <span className="ml-1 text-xs tracking-[0.14em] text-muted">PLACES</span>
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-muted">{regText(r)}</p>
      <Rules r={r} />
      {me.team && <p className="mt-2 text-sm">Team: <b>{me.team.name}</b></p>}
      {entry?.status === "WAITLIST" && (
        <p className="mt-1 text-xs text-muted">No DC is taken yet. If a place frees up, the fee is taken then and your team moves in.</p>
      )}
      {canRegister && (
        <div className="mt-3 space-y-2">
          {r.fee > 0 && (me.pays || me.can_use_pot) && (
            <fieldset className="flex flex-wrap gap-3 text-sm">
              <legend className="sr-only">Pay from</legend>
              {me.pays && (
                <label className="flex items-center gap-1.5">
                  <input type="radio" name={`pay-${slug}`} checked={payFrom === "WALLET"} onChange={() => setPayFrom("WALLET")} />
                  My wallet {wallet !== null && <span className="text-muted">({dc(wallet)})</span>}
                </label>
              )}
              {me.can_use_pot && (
                <label className="flex items-center gap-1.5">
                  <input type="radio" name={`pay-${slug}`} checked={payFrom === "POT"} onChange={() => setPayFrom("POT")} />
                  Team pot <span className="text-muted">({dc(me.pot ?? 0)})</span>
                </label>
              )}
            </fieldset>
          )}
          <button type="button" className="btn btn-primary w-full sm:w-auto" disabled={busy || (short && left > 0)} onClick={() => press("register")}>
            {busy ? "Saving..." : left > 0 ? `Register ${me.team?.name ?? "my team"}${r.fee > 0 ? ` · ${dc(r.fee)}` : ""}` : "Join the waitlist (no DC yet)"}
          </button>
          {short && left > 0 && (
            <p className="text-xs text-bad">
              Not enough DC {payFrom === "POT" ? "in the team pot" : "in your wallet"}.{" "}
              {payFrom === "WALLET" ? "Team-mates can chip in to the team pot in the Player shop." : "Team-mates can chip in from the Player shop."}
            </p>
          )}
        </div>
      )}
      {r.state === "open" && !entry && !me.can_register && (
        <p className="mt-3 text-sm text-muted">
          {me.team ? (
            "Your team's manager or a player with a linked game UID registers the team."
          ) : (
            <>
              <Link href="/account" className="text-accent underline">
                Sign in and link your game UID
              </Link>{" "}
              to register your team.
            </>
          )}
        </p>
      )}
      {canLeave && (
        <button type="button" className="btn btn-ghost mt-3 text-sm" disabled={busy} onClick={() => press("withdraw")}>
          {entry?.via === "INVITED" ? "Decline the invite" : entry?.status === "WAITLIST" ? "Leave the waitlist" : "Withdraw (fee refunded)"}
        </button>
      )}
      {error && <p className="mt-2 text-sm text-bad">{error}</p>}
    </div>
  );
}

function Rules({ r }: { r: Registration }) {
  if (!r.qualifier) return null;
  return (
    <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-muted">
      {r.invite_count > 0 && (
        <li>
          The top {r.invite_count} teams in the scrim standings are invited straight into the {r.final.name}, free.
        </li>
      )}
      <li>
        Every other team plays the {r.qualifier.name}: {r.places} places, then a waitlist. The top {r.qualify_count} go through to the {r.final.name}.
      </li>
      <li>Withdraw before registration closes and the fee comes back. Teams that play, get knocked out or don&apos;t show keep no refund.</li>
    </ul>
  );
}
