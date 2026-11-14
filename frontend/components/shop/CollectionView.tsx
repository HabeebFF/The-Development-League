"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import PlayerCard from "@/components/league/PlayerCard";
import TiltCard from "@/components/league/TiltCard";
import { designColors, RARITY_COLORS } from "@/lib/cardDesigns";
import type { PlayerCard as Card } from "@/lib/cards";
import { COLLECTION, shortDc, TIERS, type CollectionDesign } from "@/lib/playerDesigns";

// A stand-in player so every design can be seen on a real card layout.
const SAMPLE: Card = {
  player_id: 0,
  name: "Your name",
  photo: null,
  team: { id: 0, name: "Your team", tag: "TDL", slug: "", logo: null, primary_color: "#c81e3c" },
  week: "2026-11-14",
  role: "RUSHER",
  role_label: "Rusher",
  role_suggested: false,
  suggested_role: "RUSHER",
  overall: 88,
  overall_change: 3,
  tier: "gold",
  totw: [],
  stats: [
    ["ENT", 91],
    ["CQC", 89],
    ["FIN", 86],
    ["AIM", 84],
    ["TRD", 80],
    ["SUR", 77],
  ].map(([key, rating]) => ({ key: key as string, label: key as string, rating: rating as number, change: null, stale: false, value: null, detail: "" })),
  matches: 20,
  week_matches: 6,
  stale: false,
};

function cardFor(design: CollectionDesign): Card {
  return { ...SAMPLE, design };
}

/** The Player shop collection: every design by tier, a big tilting preview of the one
 *  you hover or tap, rarity colours and a Limited badge with copies left. */
export default function CollectionView() {
  const params = useSearchParams();
  const router = useRouter();
  const start = COLLECTION.find((d) => d.slug === params.get("d")) ?? null;
  const [picked, setPicked] = useState<CollectionDesign>(start ?? COLLECTION[COLLECTION.length - 1]);
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
        {TIERS.map((t) => (
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
              {COLLECTION.filter((d) => d.rarity === t.rarity).map((d) => (
                <Tile key={d.slug} design={d} active={picked.slug === d.slug} onHover={() => setPicked(d)} onOpen={() => open(d)} />
              ))}
            </ul>
          </section>
        ))}
      </div>

      {/* Desktop: a sticky preview that follows what you hover. */}
      <aside className="hidden lg:block">
        <div className="sticky top-24">
          <Preview key={picked.slug} design={picked} />
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
            <Preview key={picked.slug} design={picked} size={0.95} />
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
      Limited · {left} of {design.copies} left
    </span>
  );
}

function Tile({ design: d, active, onHover, onOpen }: { design: CollectionDesign; active: boolean; onHover: () => void; onOpen: () => void }) {
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
          <PlayerCard card={cardFor(d)} size={0.52} />
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

function Preview({ design: d, size = 1.12 }: { design: CollectionDesign; size?: number }) {
  const color = RARITY_COLORS[d.rarity];
  return (
    <div className="flex flex-col items-center gap-3">
      <TiltCard>
        <PlayerCard card={cardFor(d)} size={size} />
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
