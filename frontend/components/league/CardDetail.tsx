"use client";

import Link from "next/link";
import { useState } from "react";

import { cardFileName, changeText, TIER_LABELS, totwText, weekLabel, type CardDetail as Detail } from "@/lib/cards";
import { useApi } from "@/lib/useApi";

import { cardImage } from "./cardImage";
import Loading from "./Loading";
import PlayerCard from "./PlayerCard";

/** One player's card, big, with what each stat is made of and their rating week by week. */
export default function CardDetail({ id, week }: { id: string; week?: string }) {
  const data = useApi<Detail>(`/cards/${id}${week ? `?week=${week}` : ""}`);
  const [saving, setSaving] = useState(false);
  const card = data.data;

  async function save() {
    if (!card) return;
    setSaving(true);
    try {
      const blob = await cardImage(card);
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = cardFileName(card);
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } finally {
      setSaving(false);
    }
  }

  if (!card) return <Loading error={data.error} count={4} />;
  return (
    <div className="grid gap-8 md:grid-cols-[auto_1fr]">
      <div className="flex flex-col items-center gap-4">
        <PlayerCard card={card} size={1.25} />
        <button className="btn btn-primary px-4" onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save as image"}
        </button>
      </div>
      <div className="min-w-0">
        <p className="eyebrow">
          {TIER_LABELS[card.tier]} · week of {weekLabel(card.week)}
        </p>
        <h2 className="mt-1 font-display text-4xl uppercase">{card.name}</h2>
        <p className="mt-1 text-sm text-muted">
          {card.role_label}
          {card.role_suggested ? " (suggested from how they play)" : ""}
          {card.team && (
            <>
              {" · "}
              <Link href={`/teams/${card.team.slug}`} className="hover:text-accent">
                {card.team.name}
              </Link>
            </>
          )}
          {` · ${card.matches} matches in the last four weeks, ${card.week_matches} this week`}
        </p>
        {card.totw.length > 0 && <p className="mt-2 text-sm font-semibold text-accent">{totwText(card.totw)}</p>}
        {card.special === "rising_star" && card.rise ? (
          <p className="mt-2 text-sm font-semibold text-ok">Rising Star: up {card.rise} since their last card</p>
        ) : null}
        {card.special === "icon" && (
          <p className="mt-2 text-sm font-semibold text-accent-2">Icon: {card.streak} weeks in a row at the top</p>
        )}
        {card.stale && (
          <p className="mt-2 text-sm text-muted">Not enough matches this week, so these are the numbers from their last card.</p>
        )}

        <ul className="mt-6 divide-y divide-line border-y border-line">
          {card.stats.map((s) => (
            <li key={s.key} className={`flex items-center gap-3 py-2.5 ${s.stale ? "opacity-60" : ""}`}>
              <span className="w-10 text-right font-display text-3xl leading-none">{s.rating ?? "–"}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">
                  {s.label} <span className="text-muted">{s.key}</span>
                  {s.extra && <span className="ml-2 text-[10px] font-bold tracking-widest text-accent uppercase">Grenader extra</span>}
                </span>
                <span className="block text-xs text-muted">{s.detail}</span>
              </span>
              {s.change ? (
                <span className={`text-sm font-bold ${s.change > 0 ? "text-ok" : "text-bad"}`}>{changeText(s.change)}</span>
              ) : null}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted">
          Each stat ranks the player against everyone with at least four matches in the last four weeks: about 40 is the league&apos;s lowest, 99 the
          best. Players with few matches are pulled towards the average. The overall rating weighs the stats that matter most for the role.
        </p>

        {card.history.length > 1 && <History history={card.history} current={card.week} />}
      </div>
    </div>
  );
}

/** Overall rating week by week: one line, the latest value labelled, every week on hover. */
function History({ history, current }: { history: Detail["history"]; current: string }) {
  const w = 420;
  const h = 150;
  const pad = { l: 34, r: 40, t: 14, b: 26 };
  const values = history.map((p) => p.overall);
  const lo = Math.max(40, Math.floor((Math.min(...values) - 3) / 5) * 5);
  const hi = Math.min(99, Math.ceil((Math.max(...values) + 3) / 5) * 5);
  const x = (i: number) => pad.l + (i * (w - pad.l - pad.r)) / Math.max(1, history.length - 1);
  const y = (v: number) => pad.t + ((hi - v) * (h - pad.t - pad.b)) / Math.max(1, hi - lo);
  const last = history[history.length - 1];
  const ticks = [lo, Math.round((lo + hi) / 2), hi];
  return (
    <div className="mt-8">
      <h3 className="font-display text-xl uppercase">Overall rating, week by week</h3>
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-2 w-full" role="img" aria-label={`Overall rating from ${values[0]} to ${last.overall}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--muted)">
              {t}
            </text>
          </g>
        ))}
        <polyline
          points={history.map((p, i) => `${x(i)},${y(p.overall)}`).join(" ")}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={2}
          strokeLinejoin="round"
        />
        {history.map((p, i) => (
          <g key={p.week}>
            <circle cx={x(i)} cy={y(p.overall)} r={p.week === current ? 5 : 4} fill="var(--accent)" stroke="var(--panel)" strokeWidth={2} />
            {/* A bigger invisible target carries the hover text. */}
            <circle cx={x(i)} cy={y(p.overall)} r={14} fill="transparent">
              <title>{`${weekLabel(p.week)}: ${p.overall}`}</title>
            </circle>
          </g>
        ))}
        <text x={x(history.length - 1) + 9} y={y(last.overall) + 4} fontSize={12} fontWeight={700} fill="var(--text)">
          {last.overall}
        </text>
        <text x={pad.l} y={h - 6} fontSize={11} fill="var(--muted)">
          {weekLabel(history[0].week)}
        </text>
        <text x={w - pad.r} y={h - 6} fontSize={11} textAnchor="end" fill="var(--muted)">
          {weekLabel(last.week)}
        </text>
      </svg>
    </div>
  );
}
