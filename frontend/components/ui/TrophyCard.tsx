import Link from "next/link";

import { headline, unit, type Award } from "@/lib/awards";

import { TeamMark } from "../league/TeamBadge";

/** Role icons for the award slots (24px paths). */
export const AWARD_ICON: Record<string, string> = {
  player: "M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 14.3l-4.8 2.6.9-5.4-3.9-3.8 5.4-.8z",
  mvp: "M5 16 3 6l5.5 4L12 4l3.5 6L21 6l-2 10zm0 2h14v2H5z",
  rusher: "M13 2 4 14h6l-1 8 9-12h-6z",
  sniper:
    "M12 2a1 1 0 0 1 1 1v1.06A8 8 0 0 1 19.94 11H21a1 1 0 1 1 0 2h-1.06A8 8 0 0 1 13 19.94V21a1 1 0 1 1-2 0v-1.06A8 8 0 0 1 4.06 13H3a1 1 0 1 1 0-2h1.06A8 8 0 0 1 11 4.06V3a1 1 0 0 1 1-1m0 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12m0 3a3 3 0 1 1 0 6 3 3 0 0 1 0-6",
  grenader: "M10 2h4v2h-4zm2 3a8 8 0 1 1 0 16 8 8 0 0 1 0-16m-1 4v5h2V9zM17 3l3 3-1.4 1.4-3-3z",
  team: "M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z",
  kill_team: "M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6zm-1 5h2v3h3v2h-3v3h-2v-3H8v-2h3z",
  igl: "M4 4h16v12H8l-4 4zm4 4v2h8V8zm0 4v2h5v-2z",
};

/** One award in the trophy case: a role icon, the title, the winner and the headline number. */
export default function TrophyCard({ award, href = "/awards" }: { award: Award; href?: string }) {
  const winner = award.top[0];
  const icon = AWARD_ICON[award.key] ?? AWARD_ICON.player;
  return (
    <Link href={href} className="card card-hover flex flex-col gap-3 overflow-hidden p-4 sm:p-5">
      <span className="pointer-events-none absolute inset-0 bg-[radial-gradient(80%_60%_at_100%_0%,rgb(245_165_36/0.16),transparent_70%)]" />
      <span className="relative flex items-start justify-between gap-3">
        <span className="eyebrow">{award.title}</span>
        <span
          className="flex h-12 w-12 shrink-0 items-center justify-center bg-accent/[0.12] text-accent"
          style={{ clipPath: "polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%)" }}
        >
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor" aria-hidden>
            <path d={icon} />
          </svg>
        </span>
      </span>
      {winner && !award.blocked ? (
        <>
          <span className="relative flex min-w-0 items-center gap-3">
            <TeamMark
              team={{ id: 0, name: winner.team ?? "", tag: winner.team_tag, slug: winner.team_slug ?? "", logo: winner.logo, primary_color: winner.team_color }}
              size="md"
            />
            <span className="min-w-0">
              <span className="block truncate font-display text-2xl leading-tight font-black uppercase">{winner.player ?? winner.team}</span>
              {winner.player && winner.team && <span className="block truncate text-xs text-muted">{winner.team}</span>}
            </span>
          </span>
          <span className="num relative text-4xl leading-none text-accent-hot">
            {headline(award.key, winner.value)}
            <span className="ml-1.5 text-sm tracking-[0.12em] text-muted uppercase">{unit(award.key, winner.value)}</span>
          </span>
        </>
      ) : (
        <span className="relative text-sm text-muted">{award.blocked ?? "No winner yet."}</span>
      )}
    </Link>
  );
}
