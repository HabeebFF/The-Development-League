"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import Loading from "@/components/league/Loading";
import PlayerCard from "@/components/league/PlayerCard";
import { api, ApiError, type Paged, type TeamRef } from "@/lib/api";
import { PALETTES, PATTERNS, RARITY_COLORS, type CardDesign, type ShopDesign } from "@/lib/cardDesigns";
import type { CardDetail } from "@/lib/cards";
import { coins } from "@/lib/predictions";
import type { BuyResult, FanCardData, Me, ShopList } from "@/lib/shop";
import { useApi } from "@/lib/useApi";

import FanCard from "./FanCard";
import PredictNav, { NOTE, NotOpen } from "./PredictNav";
import { useWallet } from "./useWallet";

type Tab = "shop" | "mine";

/** Card designs bought with DC: browse them on your own card, buy, and equip one. */
export default function ShopView() {
  const { state, setBalance } = useWallet();
  const [tick, setTick] = useState(0);
  const [tab, setTab] = useState<Tab>("shop");
  const [picked, setPicked] = useState<number | null>(null);
  const [buying, setBuying] = useState<ShopDesign | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const list = useApi<ShopList>(`/shop/designs?v=${tick}`);
  const me = useApi<Me>(state.kind === "ok" ? `/shop/me?v=${tick}` : null);
  const card = useApi<CardDetail>(me.data?.player_id ? `/cards/${me.data.player_id}` : null);

  const designs = useMemo(() => list.data?.designs ?? [], [list.data]);
  const equipped = designs.find((d) => d.equipped) ?? null;
  const preview: CardDesign | null = picked === 0 ? null : (designs.find((d) => d.id === picked) ?? equipped);
  const balance = state.kind === "ok" ? state.wallet.balance : null;
  const signedIn = state.kind === "ok";

  if (list.error === "Not found.") return <NotOpen />;

  const fan: FanCardData = me.data
    ? { ...me.data, design: preview }
    : {
        name: "You",
        favourite_team: null,
        design: preview,
        stats: { balance: 1000, shop_spent: 0, net: 1000, won: 0, lost: 0, accuracy: null },
      };
  const plainCard =
    card.data && (card.data.tier === "gold" || card.data.tier === "silver" || card.data.tier === "bronze")
      ? { ...card.data, design: preview }
      : null;

  async function equip(design: number | null) {
    setBusy(true);
    setError(null);
    try {
      await api("/shop/equip", { method: "POST", body: { design } });
      setMessage(design ? "Equipped. It's on your card now." : "Back to the Default look.");
      setTick((t) => t + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't equip it.");
    } finally {
      setBusy(false);
    }
  }

  async function buy(design: ShopDesign, equipNow: boolean) {
    setBusy(true);
    setError(null);
    try {
      const made = await api<BuyResult>(`/shop/designs/${design.id}/buy`, { method: "POST", body: { equip: equipNow } });
      setBalance(made.balance);
      setBuying(null);
      setMessage(`${design.name} is yours${equipNow ? " and on your card" : ""}.`);
      setTick((t) => t + 1);
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Couldn't buy it.");
    } finally {
      setBusy(false);
    }
  }

  const shown = tab === "shop" ? designs.filter((d) => d.available || d.owned) : designs.filter((d) => d.owned);

  return (
    <>
      <PredictNav wallet={state} />
      <p className="mt-4 text-xs text-muted">
        Designs change how your card looks, never its numbers. Players see the design on their weekly card; everyone gets a fan card. {NOTE}
      </p>

      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,20rem)_1fr]">
        {/* Your card, wearing the design you're looking at. */}
        <aside className="flex flex-col items-center gap-4 lg:sticky lg:top-24 lg:self-start">
          <div className="flex flex-wrap items-end justify-center gap-4">
            {plainCard && <PlayerCard card={plainCard} size={0.95} />}
            <FanCard fan={fan} size={plainCard ? 0.7 : 0.95} />
          </div>
          <p className="text-center text-sm text-muted">
            {preview ? (
              <>
                Showing <b className="text-white">{preview.name}</b>
                {preview.id !== equipped?.id && " (preview)"}
              </>
            ) : (
              "Default look"
            )}
          </p>
          {card.data && !plainCard && (
            <p className="text-center text-xs text-muted">Your weekly card is a special card right now, so it keeps its own look.</p>
          )}
          {signedIn && me.data && <FavouriteTeam me={me.data} onSaved={() => setTick((t) => t + 1)} />}
        </aside>

        <div>
          <div className="flex flex-wrap items-center gap-1" role="tablist">
            {(
              [
                ["shop", "Shop"],
                ["mine", "My designs"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={tab === key}
                className={`btn px-3 py-1 text-xs uppercase ${tab === key ? "border-accent text-white" : "text-muted"}`}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
            {signedIn && equipped && (
              <button type="button" className="btn btn-ghost ml-auto px-3 py-1 text-xs" disabled={busy} onClick={() => equip(null)}>
                Use Default look
              </button>
            )}
          </div>
          {message && <p className="mt-3 text-sm text-ok">{message}</p>}
          {error && !buying && <p className="mt-3 text-sm text-bad">{error}</p>}
          {state.kind === "out" && (
            <p className="mt-3 text-sm text-muted">
              <Link href="/auth/login?next=/predict/shop" className="text-accent underline">
                Sign in
              </Link>{" "}
              to buy designs with your DC.
            </p>
          )}
          {state.kind === "staff" && <p className="mt-3 text-sm text-muted">League staff can&apos;t buy designs.</p>}

          <div className="mt-4">
            {!list.data ? (
              <Loading error={list.error} count={6} />
            ) : shown.length === 0 ? (
              <p className="text-muted">{tab === "mine" ? "You don't own any designs yet." : "Nothing on sale right now."}</p>
            ) : (
              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {shown.map((d) => (
                  <DesignTile
                    key={d.id}
                    design={d}
                    active={preview?.id === d.id}
                    signedIn={signedIn}
                    busy={busy}
                    onPreview={() => setPicked(d.id)}
                    onBuy={() => {
                      setPicked(d.id);
                      setError(null);
                      setBuying(d);
                    }}
                    onEquip={() => equip(d.id)}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {buying && (
        <BuySheet
          design={buying}
          balance={balance}
          warnBelow={list.data?.low_balance_warning ?? 100}
          busy={busy}
          error={error}
          onCancel={() => {
            setBuying(null);
            setError(null);
          }}
          onConfirm={(equipNow) => buy(buying, equipNow)}
        />
      )}
    </>
  );
}

function DesignTile({
  design: d,
  active,
  signedIn,
  busy,
  onPreview,
  onBuy,
  onEquip,
}: {
  design: ShopDesign;
  active: boolean;
  signedIn: boolean;
  busy: boolean;
  onPreview: () => void;
  onBuy: () => void;
  onEquip: () => void;
}) {
  const color = RARITY_COLORS[d.rarity];
  const soldOut = d.left === 0 && !d.owned;
  return (
    <li
      className={`card flex flex-col gap-2 p-3 transition ${active ? "ring-2 ring-accent" : ""}`}
      style={{ borderColor: `color-mix(in srgb, ${color} 45%, transparent)` }}
    >
      <button type="button" className="flex items-center gap-3 text-left" onClick={onPreview} aria-label={`Preview ${d.name}`}>
        <Swatch design={d} />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-display text-lg uppercase">{d.name}</span>
          <span className="text-xs font-bold tracking-wider uppercase" style={{ color }}>
            {d.rarity_label}
          </span>
          {d.copies !== null && (
            <span className="block text-xs text-muted">
              {d.owned && d.copy_number ? `Your copy #${d.copy_number} of ${d.copies}` : `${d.left} of ${d.copies} left`}
            </span>
          )}
        </span>
        <span className="num text-right text-lg text-accent-hot">{coins(d.price)}</span>
      </button>
      <div className="flex gap-2">
        <button type="button" className="btn btn-ghost flex-1 py-1.5 text-xs" onClick={onPreview}>
          Preview
        </button>
        {d.equipped ? (
          <span className="btn flex-1 cursor-default border-ok py-1.5 text-xs text-ok">Equipped</span>
        ) : d.owned ? (
          <button type="button" className="btn btn-primary flex-1 py-1.5 text-xs" disabled={busy || !signedIn} onClick={onEquip}>
            Equip
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary flex-1 py-1.5 text-xs"
            disabled={busy || !signedIn || soldOut || !d.available}
            onClick={onBuy}
          >
            {soldOut ? "Sold out" : "Buy"}
          </button>
        )}
      </div>
    </li>
  );
}

/** A small chip of a design's colours (used in the shop and next to names). */
export function Swatch({ design, size = "md" }: { design: CardDesign; size?: "sm" | "md" }) {
  return <DesignChip design={design} className={size === "sm" ? "h-4 w-3" : "h-12 w-9"} />;
}

function DesignChip({ design, className }: { design: CardDesign; className: string }) {
  const p = PALETTES[design.parts.palette];
  if (!p) return null;
  const pattern = PATTERNS[design.parts.pattern];
  return (
    <span
      aria-hidden
      className={`relative inline-block shrink-0 overflow-hidden ${className}`}
      style={{
        clipPath: "polygon(12% 0, 88% 0, 100% 7%, 100% 90%, 50% 100%, 0 90%, 0 7%)",
        background: `${pattern && pattern !== "none" ? `${pattern}, ` : ""}linear-gradient(160deg, ${p[0]}, ${p[1]})`,
        boxShadow: `inset 0 0 0 2px ${p[3]}`,
      }}
    />
  );
}

function BuySheet({
  design,
  balance,
  warnBelow,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  design: ShopDesign;
  balance: number | null;
  warnBelow: number;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (equipNow: boolean) => void;
}) {
  const [equipNow, setEquipNow] = useState(true);
  const after = balance === null ? null : balance - design.price;
  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-black/70 p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label={`Buy ${design.name}`}
    >
      <div className="card page-enter w-full max-w-sm p-5">
        <h3 className="font-display text-2xl uppercase">Buy {design.name}</h3>
        <dl className="mt-4 grid grid-cols-2 gap-y-1.5 text-sm">
          <dt className="text-muted">Rarity</dt>
          <dd className="text-right" style={{ color: RARITY_COLORS[design.rarity] }}>
            {design.rarity_label}
          </dd>
          <dt className="text-muted">Price</dt>
          <dd className="text-right font-semibold">{coins(design.price)}</dd>
          <dt className="text-muted">DC after</dt>
          <dd className={`text-right ${after !== null && after < 0 ? "text-bad" : ""}`}>{after === null ? "–" : coins(Math.max(after, 0))}</dd>
        </dl>
        {after !== null && after < 0 && <p className="mt-3 text-sm text-bad">You don&apos;t have enough DC for this one.</p>}
        {after !== null && after >= 0 && after < warnBelow && (
          <p className="mt-3 text-sm text-accent">This leaves you under {coins(warnBelow)} for predictions. The daily bonus tops you up a little each day.</p>
        )}
        <label className="mt-4 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={equipNow} onChange={(e) => setEquipNow(e.target.checked)} />
          Put it on my card now
        </label>
        <p className="mt-3 text-xs text-muted">You keep it for good. Spending DC here doesn&apos;t cost you a place on the leaderboard.</p>
        {error && <p className="mt-2 text-sm text-bad">{error}</p>}
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button type="button" className="btn" onClick={onCancel} disabled={busy}>
            Back
          </button>
          <button type="button" className="btn btn-primary" onClick={() => onConfirm(equipNow)} disabled={busy || (after !== null && after < 0)}>
            {busy ? "Buying..." : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}

function FavouriteTeam({ me, onSaved }: { me: Me; onSaved: () => void }) {
  const teams = useApi<Paged<TeamRef>>("/teams?page_size=100");
  const [saving, setSaving] = useState(false);
  async function save(slug: string) {
    setSaving(true);
    try {
      await api("/shop/me", { method: "PATCH", body: { favourite_team: slug || null } });
      onSaved();
    } finally {
      setSaving(false);
    }
  }
  return (
    <label className="flex w-full max-w-xs flex-col gap-1 text-sm">
      <span className="text-muted">Favourite team (on your fan card)</span>
      <select
        className="input"
        value={me.favourite_team?.slug ?? ""}
        disabled={saving || !teams.data}
        onChange={(e) => save(e.target.value)}
      >
        <option value="">None</option>
        {teams.data?.results.map((t) => (
          <option key={t.slug} value={t.slug}>
            {t.name}
          </option>
        ))}
      </select>
    </label>
  );
}
