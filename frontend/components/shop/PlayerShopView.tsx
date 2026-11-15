"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import Loading from "@/components/league/Loading";
import PlayerCard from "@/components/league/PlayerCard";
import TiltCard from "@/components/league/TiltCard";
import { Swatch } from "@/components/predict/ShopView";
import { api } from "@/lib/api";
import { PALETTES, RARITY_COLORS, RARITY_LABELS, type CardDesign } from "@/lib/cardDesigns";
import { flagEmoji, type CardDetail, type CardExtras, type PlayerCard as Card } from "@/lib/cards";
import { SAMPLE_CARD, shortDc, TIERS } from "@/lib/playerDesigns";
import type { BuyResult, ItemKind, PlayerItem, PlayerShop } from "@/lib/shop";
import { useApi } from "@/lib/useApi";

type Tab = "designs" | "extras" | "mine";

const KIND_ORDER: ItemKind[] = ["TITLE", "NUMBER", "GLOW"];
const KIND_HEAD: Record<ItemKind, string> = {
  FRAME: "Card designs",
  TITLE: "Card titles",
  NUMBER: "Number and flag",
  GLOW: "Rating glows",
};

/** The Player shop: card designs and extras only league players can buy, with DC. */
export default function PlayerShopView() {
  const [tick, setTick] = useState(0);
  const [tab, setTab] = useState<Tab>("designs");
  const [peek, setPeek] = useState<PlayerItem | null>(null);
  const [buying, setBuying] = useState<PlayerItem | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const shop = useApi<PlayerShop>(`/shop/player?v=${tick}`);
  const data = shop.data;
  const mine = useApi<CardDetail>(data?.player ? `/cards/${data.player.id}?v=${tick}` : null);
  const items = useMemo(() => data?.items ?? [], [data]);

  if (shop.error === "Not found.") return <p className="text-muted">The shop is closed right now.</p>;
  if (!data) return <Loading error={shop.error} count={6} />;

  const on = (kind: ItemKind) => items.find((i) => i.kind === kind && i.equipped) ?? null;
  const frame = peek?.kind === "FRAME" ? peek : on("FRAME");
  const title = peek?.kind === "TITLE" ? peek : on("TITLE");
  const glow = peek?.kind === "GLOW" ? peek : on("GLOW");
  const own = mine.data && ["gold", "silver", "bronze"].includes(mine.data.tier) ? mine.data : null;
  const base: Card = own ?? { ...SAMPLE_CARD, name: data.player?.name ?? SAMPLE_CARD.name };
  const showNumber = peek?.kind === "NUMBER" || data.owns_number;
  const extras: CardExtras = {
    title: title?.name ?? null,
    title_palette: title?.parts.palette ?? null,
    glow: glow?.parts.palette ?? null,
    glow_effect: glow?.parts.effect ?? null,
    number: showNumber ? (data.number ?? (peek?.kind === "NUMBER" ? 10 : null)) : null,
    flag: showNumber ? (data.flag ?? (peek?.kind === "NUMBER" ? data.player?.country || "NG" : null)) : null,
  };
  const preview: Card = { ...base, design: frame as CardDesign | null, extras };

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setMessage(done);
      setPeek(null);
      setTick((t) => t + 1);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const equip = (item: PlayerItem, off = false) =>
    run(
      () => api("/shop/player/equip", { method: "POST", body: { kind: item.kind, design: off ? null : item.id } }),
      off ? `${item.name} is off your card.` : `${item.name} is on your card.`,
    );

  async function buy(item: PlayerItem, equipNow: boolean) {
    const ok = await run(
      () => api<BuyResult>(`/shop/designs/${item.id}/buy`, { method: "POST", body: { equip: equipNow } }),
      `${item.name} is yours${equipNow && item.kind !== "NUMBER" ? " and on your card" : ""}.`,
    );
    if (ok) setBuying(null);
  }

  const frames = items.filter((i) => i.kind === "FRAME");
  const shown = (list: PlayerItem[]) => (tab === "mine" ? list.filter((i) => i.owned) : list);

  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        {data.can_buy ? (
          <span className="num border border-accent/50 bg-accent/10 px-3 py-1 text-accent-hot">{(data.balance ?? 0).toLocaleString("en-GB")} DC</span>
        ) : null}
        <Link href="/player-shop/collection" className="text-sm text-accent underline">
          See the whole collection
        </Link>
        <Link href="/shop" className="ml-auto text-sm text-muted underline">
          Fan card shop
        </Link>
      </div>
      <Gate shop={data} />

      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,21rem)_1fr]">
        <aside className="flex flex-col items-center gap-3 lg:sticky lg:top-24 lg:self-start">
          <TiltCard>
            <PlayerCard key={frame?.id ?? 0} card={preview} size={1.05} />
          </TiltCard>
          <p className="text-center text-sm text-muted">
            {peek ? (
              <>
                Previewing <b className="text-white">{peek.name}</b>
              </>
            ) : own ? (
              "Your card as it is now"
            ) : data.player ? (
              "Your weekly card is a special card right now, so this shows a stand-in"
            ) : (
              "A stand-in card: players see their own"
            )}
          </p>
          {data.owns_number && data.can_buy && <NumberForm shop={data} busy={busy} onSave={(n, f) => run(() => api("/shop/player/number", { method: "POST", body: { number: n, flag: f } }), "Number and flag saved.")} />}
          {data.progress && <Progress progress={data.progress} />}
        </aside>

        <div>
          <div className="flex flex-wrap items-center gap-1" role="tablist">
            {(
              [
                ["designs", "Designs"],
                ["extras", "Extras"],
                ["mine", "My items"],
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
          </div>
          {message && <p className="mt-3 text-sm text-ok">{message}</p>}
          {error && !buying && <p className="mt-3 text-sm text-bad">{error}</p>}

          {tab !== "extras" &&
            TIERS.map((t) => {
              const list = shown(frames.filter((i) => i.rarity === t.rarity && !i.unlock));
              if (!list.length) return null;
              return (
                <Group key={t.rarity} title={t.label} color={RARITY_COLORS[t.rarity]} note={`${t.range} · ${t.perks}`}>
                  {list.map((i) => (
                    <Tile key={i.id} item={i} shop={data} busy={busy} active={peek?.id === i.id} onPeek={() => setPeek(i)} onBuy={() => setBuying(i)} onEquip={equip} />
                  ))}
                </Group>
              );
            })}
          {tab !== "extras" && shown(frames.filter((i) => i.unlock)).length > 0 && (
            <Group title="Earned, not bought" color="#3ee6b0" note="Free frames you unlock by playing">
              {shown(frames.filter((i) => i.unlock)).map((i) => (
                <Tile key={i.id} item={i} shop={data} busy={busy} active={peek?.id === i.id} onPeek={() => setPeek(i)} onBuy={() => setBuying(i)} onEquip={equip} />
              ))}
            </Group>
          )}
          {tab !== "designs" &&
            KIND_ORDER.map((k) => {
              const list = shown(items.filter((i) => i.kind === k));
              if (!list.length) return null;
              return (
                <Group key={k} title={KIND_HEAD[k]} color="#f5b82e">
                  {list.map((i) => (
                    <Tile key={i.id} item={i} shop={data} busy={busy} active={peek?.id === i.id} onPeek={() => setPeek(i)} onBuy={() => setBuying(i)} onEquip={equip} />
                  ))}
                </Group>
              );
            })}
          {tab === "mine" && !items.some((i) => i.owned) && <p className="mt-6 text-muted">You don&apos;t own anything from the Player shop yet.</p>}
        </div>
      </div>

      {buying && (
        <BuySheet
          item={buying}
          balance={data.balance}
          warnBelow={data.low_balance_warning}
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

function Gate({ shop }: { shop: PlayerShop }) {
  if (shop.can_buy) return null;
  return (
    <div className="card mt-4 border-accent/40 p-4 text-sm">
      <p className="font-display text-xl uppercase">For league players only</p>
      <p className="mt-1 text-muted">
        {shop.staff
          ? "League staff can look around but can't buy."
          : !shop.signed_in
            ? "Players: sign in with the account linked to your in-game name to buy. Everyone can look."
            : "Your account isn't linked to a league player. Fans can buy designs in the fan card shop."}
      </p>
      {shop.signed_in && !shop.staff && (
        <>
          <p className="mt-3">Do you play in the league? Link your Free Fire UID to unlock your cards and this shop.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link href="/account" className="btn btn-primary px-4 py-1.5 text-xs">
              I&apos;m a player: link my UID
            </Link>
            <Link href="/shop" className="btn px-4 py-1.5 text-xs">
              Fan card shop
            </Link>
          </div>
        </>
      )}
      {!shop.signed_in && (
        <Link href="/auth/login?next=/player-shop" className="btn btn-primary mt-3 inline-block px-4 py-1.5 text-xs">
          Sign in
        </Link>
      )}
    </div>
  );
}

function Group({ title, color, note, children }: { title: string; color: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b pb-1.5" style={{ borderColor: `color-mix(in srgb, ${color} 50%, transparent)` }}>
        <h2 className="font-display text-2xl uppercase" style={{ color }}>
          {title}
        </h2>
        {note && <p className="text-xs text-muted">{note}</p>}
      </div>
      <ul className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">{children}</ul>
    </section>
  );
}

function Chip({ item }: { item: PlayerItem }) {
  const p = PALETTES[item.parts.palette];
  if (item.kind === "FRAME") return <Swatch design={item} />;
  if (item.kind === "GLOW")
    return <span aria-hidden className="h-12 w-9 shrink-0 rounded-full" style={{ background: `radial-gradient(circle, rgb(${p?.[4]}) , transparent 70%)` }} />;
  if (item.kind === "NUMBER") return <span aria-hidden className="flex h-12 w-9 shrink-0 items-center justify-center font-display text-lg">10{flagEmoji("NG")}</span>;
  return (
    <span aria-hidden className="flex h-12 w-9 shrink-0 items-center justify-center font-display text-[10px] leading-none tracking-wider uppercase" style={{ color: p?.[3] }}>
      Aa
    </span>
  );
}

function Tile({
  item: i,
  shop,
  busy,
  active,
  onPeek,
  onBuy,
  onEquip,
}: {
  item: PlayerItem;
  shop: PlayerShop;
  busy: boolean;
  active: boolean;
  onPeek: () => void;
  onBuy: () => void;
  onEquip: (item: PlayerItem, off?: boolean) => void;
}) {
  const color = RARITY_COLORS[i.rarity] ?? "#a0a6b4";
  const soldOut = i.left === 0 && !i.owned;
  return (
    <li
      className={`card flex flex-col gap-2 p-3 transition ${active ? "ring-2 ring-accent" : ""}`}
      style={{ borderColor: `color-mix(in srgb, ${color} 45%, transparent)` }}
      onMouseEnter={onPeek}
    >
      <button type="button" className="flex items-center gap-3 text-left" onClick={onPeek} aria-label={`Preview ${i.name}`}>
        <Chip item={i} />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-display text-lg leading-tight uppercase">{i.name}</span>
          <span className="text-[11px] font-bold tracking-wider uppercase" style={{ color }}>
            {RARITY_LABELS[i.rarity] ?? i.rarity_label}
          </span>
          {i.copies !== null && (
            <span className="mt-0.5 block">
              <span className="border border-bad/60 bg-bad/15 px-1.5 py-0.5 text-[10px] font-bold tracking-wider text-bad uppercase">
                {i.owned && i.copy_number ? `Your copy #${i.copy_number} of ${i.copies}` : `Limited · ${i.left} of ${i.copies} left`}
              </span>
            </span>
          )}
        </span>
        <span className="num text-right text-lg text-accent-hot">{i.unlock ? "Free" : `${shortDc(i.price)} DC`}</span>
      </button>
      {i.unlock && !i.owned && (
        <div>
          <div className="h-1.5 overflow-hidden bg-white/10">
            <div className="h-full bg-ok" style={{ width: `${Math.min(100, (i.unlock.progress / i.unlock.target) * 100)}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted">
            {i.unlock.label}: {i.unlock.progress.toLocaleString("en-GB")} / {i.unlock.target.toLocaleString("en-GB")}
          </p>
        </div>
      )}
      <div className="flex gap-2">
        <button type="button" className="btn btn-ghost flex-1 py-1.5 text-xs" onClick={onPeek}>
          Preview
        </button>
        {i.kind === "NUMBER" && i.owned ? (
          <span className="btn flex-1 cursor-default border-ok py-1.5 text-xs text-ok">Owned</span>
        ) : i.equipped ? (
          <button type="button" className="btn flex-1 border-ok py-1.5 text-xs text-ok" disabled={busy} onClick={() => onEquip(i, true)}>
            Take off
          </button>
        ) : i.owned ? (
          <button type="button" className="btn btn-primary flex-1 py-1.5 text-xs" disabled={busy || !shop.can_buy} onClick={() => onEquip(i)}>
            Equip
          </button>
        ) : i.unlock ? (
          <span className="btn flex-1 cursor-default py-1.5 text-xs text-muted">Locked</span>
        ) : (
          <button type="button" className="btn btn-primary flex-1 py-1.5 text-xs" disabled={busy || !shop.can_buy || soldOut || !i.available} onClick={onBuy}>
            {soldOut ? "Sold out" : "Buy"}
          </button>
        )}
      </div>
    </li>
  );
}

function BuySheet({
  item,
  balance,
  warnBelow,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  item: PlayerItem;
  balance: number | null;
  warnBelow: number;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (equipNow: boolean) => void;
}) {
  const [equipNow, setEquipNow] = useState(true);
  const after = balance === null ? null : balance - item.price;
  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-black/70 p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label={`Buy ${item.name}`}
    >
      <div className="card w-full max-w-sm p-5">
        <h3 className="font-display text-2xl uppercase">Buy {item.name}</h3>
        <dl className="mt-4 grid grid-cols-2 gap-y-1.5 text-sm">
          <dt className="text-muted">Type</dt>
          <dd className="text-right">{item.kind_label}</dd>
          <dt className="text-muted">Rarity</dt>
          <dd className="text-right" style={{ color: RARITY_COLORS[item.rarity] }}>
            {RARITY_LABELS[item.rarity] ?? item.rarity_label}
          </dd>
          <dt className="text-muted">Price</dt>
          <dd className="text-right font-semibold">{item.price.toLocaleString("en-GB")} DC</dd>
          <dt className="text-muted">DC after</dt>
          <dd className={`text-right ${after !== null && after < 0 ? "text-bad" : ""}`}>{after === null ? "–" : `${Math.max(after, 0).toLocaleString("en-GB")} DC`}</dd>
        </dl>
        {after !== null && after < 0 && <p className="mt-3 text-sm text-bad">You don&apos;t have enough DC for this one.</p>}
        {after !== null && after >= 0 && after < warnBelow && <p className="mt-3 text-sm text-accent">This leaves you under {warnBelow} DC for predictions.</p>}
        {item.kind !== "NUMBER" && (
          <label className="mt-4 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={equipNow} onChange={(e) => setEquipNow(e.target.checked)} />
            Put it on my card now
          </label>
        )}
        <p className="mt-3 text-xs text-muted">Looks only: your numbers never change. You keep it for good.</p>
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

function NumberForm({ shop, busy, onSave }: { shop: PlayerShop; busy: boolean; onSave: (n: number | null, flag: string) => void }) {
  const [num, setNum] = useState(shop.number === null ? "" : String(shop.number));
  const [flag, setFlag] = useState(shop.flag ?? shop.player?.country ?? "");
  return (
    <form
      className="flex w-full max-w-xs items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(num === "" ? null : Number(num), flag);
      }}
    >
      <label className="flex flex-1 flex-col gap-1 text-xs text-muted">
        Number
        <input className="input" inputMode="numeric" maxLength={2} value={num} onChange={(e) => setNum(e.target.value.replace(/\D/g, ""))} />
      </label>
      <label className="flex flex-1 flex-col gap-1 text-xs text-muted">
        Flag (e.g. NG)
        <input className="input uppercase" maxLength={2} value={flag} onChange={(e) => setFlag(e.target.value.replace(/[^a-z]/gi, ""))} />
      </label>
      <button type="submit" className="btn btn-primary px-3 py-2 text-xs" disabled={busy}>
        Save
      </button>
    </form>
  );
}

function Progress({ progress }: { progress: NonNullable<PlayerShop["progress"]> }) {
  return (
    <p className="text-center text-xs text-muted">
      Your career: <b className="text-white">{progress.kills.toLocaleString("en-GB")}</b> kills ·{" "}
      <b className="text-white">{progress.booyahs}</b> booyahs · <b className="text-white">{progress.totw}</b> TOTW
    </p>
  );
}
