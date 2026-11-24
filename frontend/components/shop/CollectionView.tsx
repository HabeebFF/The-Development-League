"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import PlayerCard from "@/components/league/PlayerCard";
import TiltCard from "@/components/league/TiltCard";
import { designColors, RARITY_COLORS } from "@/lib/cardDesigns";
import type { PlayerCard as Card } from "@/lib/cards";
import { COLLECTION, SAMPLE_CARD as SAMPLE, shortDc, TIERS, type CollectionDesign } from "@/lib/playerDesigns";

function cardFor(design: CollectionDesign, photo?: string | null): Card {
  return { ...SAMPLE, design, ...(photo ? { photo } : {}) };
}

/** The Player shop collection: every design by tier, a big tilting preview of the one
 *  you hover or tap, rarity colours and a Limited badge with copies left. */
export default function CollectionView({ designs = COLLECTION, tiers = TIERS, photo }: { designs?: CollectionDesign[]; tiers?: typeof TIERS; photo?: string } = {}) {
  const params = useSearchParams();
  const router = useRouter();
  const start = designs.find((d) => d.slug === params.get("d")) ?? null;
  const [picked, setPicked] = useState<CollectionDesign>(start ?? designs[designs.length - 1]);
  const [sheet, setSheet] = useState<boolean>(!!start);

  useEffect(() => {
    if (!sheet) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && setSheet(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [sheet]);

  function open(d: CollectionDesign) {
    setPicked(d);
    setSheet(true);
    router.replace(`?d=${d.slug}`, { scroll: false });
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_22rem]">
      <div className="space-y-10">
        {tiers.map((t) => (
          <section key={t.rarity} aria-labelledby={`tier-${t.rarity}`}>
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b pb-2" style={{ borderColor: `color-mix(in srgb, ${RARITY_COLORS[t.rarity]} 50%, transparent)` }}>
              <h2 id={`tier-${t.rarity}`} className="font-display text-3xl uppercase" style={{ color: RARITY_COLORS[t.rarity] }}>
                {t.label}
              </h2>
              <p className="text-xs text-muted">
                <span className="font-bold text-white">{t.range}</span> · {t.perks}
              </p>
            </div>
            <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {designs.filter((d) => d.rarity === t.rarity).map((d) => (
                <Tile key={d.slug} design={d} photo={photo} active={picked.slug === d.slug} onHover={() => setPicked(d)} onOpen={() => open(d)} />
              ))}
            </ul>
          </section>
        ))}
      </div>

      {/* Desktop: a sticky preview that follows what you hover. */}
      <aside className="hidden lg:block">
        <div className="sticky top-24">
          <Preview key={picked.slug} design={picked} photo={photo} />
        </div>
      </aside>

      {/* Phone (and a click on desktop): a full preview sheet. */}
      {sheet &&
        typeof document !== "undefined" &&
        createPortal(
        <div
          className="fixed inset-0 z-[60] flex items-end justify-center bg-black/80 p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] backdrop-blur-sm sm:items-center lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label={`Preview ${picked.name}`}
          onClick={() => setSheet(false)}
        >
          <div className="card max-h-full w-full max-w-sm overflow-y-auto p-4" onClick={(e) => e.stopPropagation()}>
            <Preview key={picked.slug} design={picked} photo={photo} size={0.95} />
            <button type="button" className="btn mt-3 w-full" onClick={() => setSheet(false)}>
              Close
            </button>
          </div>
        </div>,
          document.body,
        )}
    </div>
  );
}

function Limited({ design }: { design: CollectionDesign }) {
  if (!design.copies) return null;
  const left = design.copies - (design.copy_number ?? 0);
  return (
    <span className="inline-flex items-center gap-1 border border-bad/60 bg-bad/15 px-1.5 py-0.5 text-[10px] font-bold tracking-wider text-bad uppercase">
      {design.copies === 1 ? "Limited · one of one" : `Limited · ${left} of ${design.copies} left`}
    </span>
  );
}

function Tile({ design: d, photo, active, onHover, onOpen }: { design: CollectionDesign; photo?: string; active: boolean; onHover: () => void; onOpen: () => void }) {
  const color = RARITY_COLORS[d.rarity];
  return (
    <li>
      <button
        type="button"
        onMouseEnter={onHover}
        onFocus={onHover}
        onClick={onOpen}
        className={`card group flex w-full flex-col items-center gap-2 p-3 text-left transition ${active ? "ring-2" : ""}`}
        style={{ borderColor: `color-mix(in srgb, ${color} 45%, transparent)`, ["--tw-ring-color" as string]: color }}
        aria-label={`${d.name}, ${d.rarity.toLowerCase()}, ${d.price.toLocaleString("en-GB")} DC`}
      >
        <span className={`fx-mini ${active ? "" : "fx-paused"}`}>
          <PlayerCard card={cardFor(d, photo)} size={0.52} />
        </span>
        <span className="w-full">
          <span className="block truncate font-display text-lg leading-tight uppercase">{d.name}</span>
          <span className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-bold tracking-wider uppercase" style={{ color }}>
              {d.rarity.toLowerCase()}
              {d.ff && <span className="ml-1 text-accent">· FF</span>}
            </span>
            <span className="num text-sm text-accent-hot">{shortDc(d.price)} DC</span>
          </span>
          {d.copies && (
            <span className="mt-1 block">
              <Limited design={d} />
            </span>
          )}
        </span>
      </button>
    </li>
  );
}

function Preview({ design: d, photo, size = 1.12 }: { design: CollectionDesign; photo?: string; size?: number }) {
  const color = RARITY_COLORS[d.rarity];
  return (
    <div className="flex flex-col items-center gap-3">
      <TiltCard>
        <PlayerCard card={cardFor(d, photo)} size={size} />
      </TiltCard>
      <div className="w-full text-center">
        <p className="text-[11px] font-bold tracking-[0.25em] uppercase" style={{ color }}>
          {d.rarity.toLowerCase()}
          {d.ff && " · Free Fire"}
        </p>
        <h3 className="font-display text-3xl leading-none uppercase">{d.name}</h3>
        <p className="mt-1 text-sm text-muted">{d.blurb}</p>
        <p className="num mt-2 text-2xl text-accent-hot">{d.price.toLocaleString("en-GB")} DC</p>
        {d.copies && (
          <p className="mt-1">
            <Limited design={d} />
          </p>
        )}
        {d.rarity === "MYTHIC" && (
          <p className="mt-3 text-sm">
            Name aura: <span className="fx-aura font-display text-lg uppercase" style={{ ["--aura" as string]: designColors(d)?.glow }}>Your name</span>{" "}
            <span className="text-muted">on kill lists, ratings and standings</span>
          </p>
        )}
      </div>
    </div>
  );
}
