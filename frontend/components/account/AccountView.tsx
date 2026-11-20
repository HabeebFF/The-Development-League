"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

import { api, ApiError, type UidClaim, type UidPreview } from "@/lib/api";
import { useApi } from "@/lib/useApi";

import { useAuth } from "../Auth";
import { SkeletonRows } from "../league/Loading";

import MatchEarnings from "../dc/MatchEarnings";

import JoinTeam from "./JoinTeam";
import NewTeam from "./NewTeam";

const dc = (n: number) => `${n.toLocaleString("en-GB")} DC`;
const ROLE: Record<string, string> = { RUSHER: "Rusher", GRENADER: "Grenader", SNIPER: "Sniper", ALL_ROUNDER: "All-rounder" };

function day(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(`${iso.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

/** My account: who you are, your DC, and for fans a way to switch to a player account by
 * linking their Free Fire UID (with an "Is this you?" check first). */
export default function AccountView() {
  const { me, status, site, refresh } = useAuth();
  const [done, setDone] = useState<{ claim: UidClaim; refund: number } | null>(null);
  // Asked again after linking, since refunds change the balance.
  const wallet = useApi<{ balance: number }>(status === "in" && site.predictions ? `/predictions/wallet${done ? `?after=${done.claim.id}` : ""}` : null);

  // Once a manager accepts, the menu's My team needs the new membership.
  const onJoined = useCallback(() => void refresh(), [refresh]);

  if (status !== "in" || !me) return <SkeletonRows count={4} />;
  const isStaff = !!me.staff_role;
  const player = me.player;

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-display text-2xl uppercase">{me.display_name || me.email}</h2>
          {isStaff ? (
            <span className="chip">League staff</span>
          ) : player ? (
            <span className="chip border-ok/60 text-ok">Player · {player.display_name}</span>
          ) : me.pending_uid_claim ? (
            <span className="chip">Player · waiting for staff</span>
          ) : (
            <span className="chip">Fan</span>
          )}
        </div>
        <p className="mt-1 text-sm text-muted">
          {me.email}
          {player ? ` · UID ${player.game_uid}` : ""}
        </p>
        {wallet.data && (
          <p className="mt-3 text-sm">
            <span className="font-display text-xl text-accent">{dc(wallet.data.balance)}</span> <Link href="/predict/wallet" className="text-muted underline">history</Link>
          </p>
        )}
        {done && done.claim.status === "APPROVED" && (
          <p className="mt-3 border-l-[3px] border-accent bg-panel-2 px-3 py-2 text-sm">
            Linked to <b>{done.claim.player_name}</b>.{" "}
            {done.claim.voided_bets > 0
              ? `${done.claim.voided_bets} open prediction${done.claim.voided_bets === 1 ? " was" : "s were"} on you or your team, so ${done.claim.voided_bets === 1 ? "it was" : "they were"} cancelled: +${dc(done.refund)} back.`
              : "Your DC and designs are all still here."}
          </p>
        )}
        {player && (
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href="/cards" className="btn btn-primary px-4 py-1.5 text-xs">See my cards</Link>
            <Link href="/player-shop" className="btn px-4 py-1.5 text-xs">Player shop</Link>
          </div>
        )}
      </div>

      {player && !isStaff && <MatchEarnings />}

      <DisplayName current={me.display_name} nextChange={me.display_name_next_change} onSaved={refresh} />

      {player && !isStaff && <JoinTeam onJoined={onJoined} />}

      {!isStaff && <NewTeam compact />}

      {player ? (
        <div className="card p-4 text-sm">
          <p className="font-display text-lg uppercase">Wrong UID?</p>
          <p className="mt-1 text-muted">Ask league staff to change it. Your DC stays either way.</p>
        </div>
      ) : me.pending_uid_claim ? (
        <div className="card p-4 text-sm">
          <p className="font-display text-lg uppercase">Waiting for staff</p>
          <p className="mt-1 text-muted">
            Another account already has UID {me.pending_uid_claim}. League staff will check who it belongs to. Until then you can still look around and use the fan
            shop, but you can&apos;t predict, because we don&apos;t know your team yet. Typed it wrong? Enter the right one below.
          </p>
          <LinkUid
            onLinked={async (claim, refund) => {
              setDone({ claim, refund });
              await refresh();
            }}
          />
        </div>
      ) : isStaff ? null : (
        <div className="card border-accent/40 p-4 text-sm">
          <p className="font-display text-xl uppercase">Do you play in the league?</p>
          <p className="mt-1 text-muted">
            Picked &quot;fan&quot; by mistake? Link your Free Fire UID to switch to a player account. You keep everything: your DC, predictions and card designs.
          </p>
          <LinkUid
            onLinked={async (claim, refund) => {
              setDone({ claim, refund });
              await refresh();
            }}
          />
        </div>
      )}
    </div>
  );
}

/** Your name on the DC leaderboard, fan zone and shop. Card names still come from the match
 * logs (by UID), so this never changes results or cards. */
function DisplayName({ current, nextChange, onSaved }: { current: string; nextChange: string | null; onSaved: () => unknown }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(current);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const waitUntil = day(nextChange);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api("/me", { method: "PATCH", body: { display_name: name } });
      await onSaved();
      setEditing(false);
      setSaved(true);
    } catch (err) {
      const field = err instanceof ApiError ? (err.data as { display_name?: string[] } | null)?.display_name?.[0] : null;
      setError(field ?? (err instanceof Error ? err.message : "Couldn't change your name."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-display text-lg uppercase">Display name</p>
        {!editing && (
          <button
            type="button"
            className="btn px-4 py-1.5 text-xs"
            disabled={!!waitUntil}
            onClick={() => {
              setName(current);
              setSaved(false);
              setEditing(true);
            }}
          >
            Change
          </button>
        )}
      </div>
      <p className="mt-1 text-muted">
        Shown on the DC leaderboard, fan zone and shop. Your player card keeps your in-game name, and your stats stay linked to your UID.
      </p>
      {saved && !editing && <p className="mt-2 text-ok">Saved. You&apos;re now {current}.</p>}
      {waitUntil && !editing && <p className="mt-2 text-muted">You can change it again on {waitUntil}.</p>}
      {editing && (
        <form onSubmit={save} className="mt-3">
          <label className="block">
            <span className="text-muted">New name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={30} className="input mt-1" autoFocus />
          </label>
          <p className="mt-1 text-xs text-muted">2 to 30 characters. You can change it once a week.</p>
          {error && <p className="mt-2 text-xs text-bad">{error}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="submit" className="btn btn-primary px-4 py-1.5 text-xs" disabled={busy || name.trim().length < 2 || name.trim() === current}>
              {busy ? "Saving…" : "Save name"}
            </button>
            <button type="button" className="btn px-4 py-1.5 text-xs" disabled={busy} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function LinkUid({ onLinked }: { onLinked: (claim: UidClaim, refund: number) => void | Promise<void> }) {
  const start = useSearchParams().get("uid") ?? "";
  const [uid, setUid] = useState(start);
  const [preview, setPreview] = useState<UidPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function find(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      setPreview(await api<UidPreview>(`/me/link-uid?uid=${encodeURIComponent(uid.trim())}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't check that UID.");
    } finally {
      setBusy(false);
    }
  }

  async function link() {
    if (!preview) return;
    setError(null);
    setBusy(true);
    try {
      const claim = await api<UidClaim>("/me/link-uid", { method: "POST", body: { game_uid: preview.game_uid } });
      await onLinked(claim, claim.status === "APPROVED" ? preview.refund : 0);
      setPreview(null);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Couldn't link that UID.");
    } finally {
      setBusy(false);
    }
  }

  if (preview) {
    const p = preview.player;
    return (
      <div className="mt-4 border-t border-line pt-4">
        <p className="eyebrow">Is this you?</p>
        <p className="mt-1 font-display text-lg">UID {preview.game_uid}</p>
        {p ? (
          <div className="mt-2 flex items-center gap-3 bg-panel-2 p-3">
            {p.overall != null && (
              <span className="flex h-14 w-11 shrink-0 items-center justify-center bg-[linear-gradient(160deg,var(--gold-hi),var(--lion-deep))] font-display text-lg text-[var(--lion-ink)] [clip-path:polygon(0_0,100%_0,100%_85%,50%_100%,0_85%)]">
                {p.overall}
              </span>
            )}
            <div>
              <p className="font-display text-xl uppercase">{p.name}</p>
              <p className="text-xs text-muted">
                {[p.team?.name ?? "No team yet", p.role ? ROLE[p.role] ?? p.role : null, `${p.matches} match${p.matches === 1 ? "" : "es"}`, p.last_played ? `last played ${day(p.last_played)}` : null]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
          </div>
        ) : (
          <p className="mt-2 bg-panel-2 p-3 text-muted">New player: nobody with this UID has played yet. You&apos;ll show up after your first match.</p>
        )}
        {preview.taken ? (
          <p className="mt-3 text-muted">
            Another account already has this UID. If it&apos;s yours, send it to staff: they&apos;ll check and link the right account. Until they decide you can&apos;t predict.
          </p>
        ) : (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-muted">
            <li>
              Your account becomes <b className="text-text">{p?.name ?? "this player"}</b>: your cards and the player shop open up.
            </li>
            <li>Your DC, prediction history and card designs stay as they are.</li>
            <li>From now on you can&apos;t predict on yourself, {p?.team?.name ?? "your team"} or your team-mates.</li>
            {preview.voids.length > 0 && (
              <li>
                <b className="text-text">
                  {preview.voids.length} open prediction{preview.voids.length === 1 ? "" : "s"}
                </b>{" "}
                on you or your team {preview.voids.length === 1 ? "gets" : "get"} cancelled and {dc(preview.refund)} comes back:
                <ul className="mt-1 list-none space-y-0.5 pl-0 text-xs">
                  {preview.voids.map((v) => (
                    <li key={v.id}>
                      {v.title} · {dc(v.stake)}
                    </li>
                  ))}
                </ul>
              </li>
            )}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted">Only link your own UID. Staff see every link and undo ones that aren&apos;t yours. After linking, only staff can change it.</p>
        {error && <p className="mt-2 text-xs text-bad">{error}</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" className="btn btn-primary px-4 py-1.5 text-xs" disabled={busy} onClick={link}>
            {preview.taken ? "Send to staff" : "Yes, link me"}
          </button>
          <button type="button" className="btn px-4 py-1.5 text-xs" disabled={busy} onClick={() => setPreview(null)}>
            Not me
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={find} className="mt-4">
      <label className="block">
        <span className="text-muted">Your Free Fire UID</span>
        <input
          value={uid}
          onChange={(e) => setUid(e.target.value.replace(/\D/g, ""))}
          required
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={20}
          className="input mt-1"
          placeholder="e.g. 2847193650"
        />
      </label>
      {error && <p className="mt-2 text-xs text-bad">{error}</p>}
      <button type="submit" className="btn btn-primary mt-3 px-4 py-1.5 text-xs" disabled={busy || !uid}>
        {busy ? "Checking…" : "Find my player"}
      </button>
    </form>
  );
}
