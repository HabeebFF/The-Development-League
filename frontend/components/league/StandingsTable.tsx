import Link from "next/link";

import type { StandingRow } from "@/lib/league";
import { signed } from "@/lib/pp";
import { Movement } from "@/components/ui/RankBadge";
import UiRankBadge from "@/components/ui/RankBadge";

import { TeamMark } from "./TeamBadge";

/** A rank number; the top three get gold, silver and bronze badges. */
export function RankBadge({ rank }: { rank: number }) {
  return <UiRankBadge rank={rank} />;
}

/** Placements in recent matches, Booyahs in gold. */
export function Form({ placements, className = "justify-end" }: { placements: number[]; className?: string }) {
  return (
    <span className={`flex gap-1 ${className}`}>
      {placements.map((p, i) => (
        <span
          key={i}
          className={`flex h-6 w-6 items-center justify-center font-display text-xs font-bold ${
            p === 1 ? "bg-accent-2 text-accent-ink shadow-[0_0_10px_rgb(255_204_77/0.5)]" : p <= 3 ? "bg-panel-2 text-text" : "bg-bg text-muted"
          }`}
          style={{ clipPath: "polygon(3px 0, 100% 0, calc(100% - 3px) 100%, 0 100%)" }}
          title={p === 1 ? "Booyah" : `Placed ${p}`}
        >
          {p}
        </span>
      ))}
    </span>
  );
}

/** Row tint for the podium: gold, silver, bronze fading into the panel. */
const PODIUM_ROW: Record<number, string> = {
  1: "bg-[linear-gradient(90deg,rgb(246_197_68/0.16),transparent_45%)]",
  2: "bg-[linear-gradient(90deg,rgb(200_208_220/0.12),transparent_45%)]",
  3: "bg-[linear-gradient(90deg,rgb(211_138_76/0.14),transparent_45%)]",
};

function PP({ value }: { value: number | undefined }) {
  if (value === undefined) return <span className="text-muted">–</span>;
  return <span className={value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted"}>{signed(value)}</span>;
}

/**
 * The league table, broadcast style: big rank plates, movement arrows, metal rows for the top three
 * and a sticky header. Below tablet width every row becomes a card with its numbers underneath.
 * ``compact`` keeps rank, team, Booyahs, kills and points only.
 */
export default function StandingsTable({
  rows,
  compact = false,
  movement,
  pp,
}: {
  rows: StandingRow[];
  compact?: boolean;
  /** Places moved since the last match day, by team id (overall table only). */
  movement?: Map<number, number | null>;
  /** Protection Points this period, by team id. */
  pp?: Map<number, number>;
}) {
  if (!rows.length) return <p className="text-sm text-muted">No results yet.</p>;
  const th = "sticky top-[var(--header-h)] z-10 bg-bg/90 px-2 py-3 font-semibold backdrop-blur-md";
  const thn = `${th} text-right`;
  const td = "px-2 py-2.5 text-right font-display text-xl font-bold tabular-nums";
  return (
    <>
      {/* Tablet and up: the table. */}
      <table className="hidden w-full border-separate border-spacing-y-1 text-sm tabular-nums md:table">
        <thead className="text-[11px] tracking-[0.16em] text-muted uppercase">
          <tr>
            <th className={`${th} w-24 text-left`}>#</th>
            <th className={`${th} text-left`}>Team</th>
            {!compact && <th className={thn} title="Matches played">Played</th>}
            <th className={thn}>Booyahs</th>
            <th className={thn}>Kills</th>
            {!compact && <th className={thn} title="Placement points">Place pts</th>}
            {!compact && <th className={`${thn} hidden xl:table-cell`} title="Kill points">Kill pts</th>}
            {pp && <th className={thn} title="Protection Points this period">PP</th>}
            <th className={`${thn} pr-4`}>Total</th>
            {!compact && (
              <th className={`${thn} hidden lg:table-cell`} title="Placements in the last five matches">
                Form
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.team.id} className={`group bg-panel transition-colors hover:bg-panel-2 ${PODIUM_ROW[r.rank] ?? ""}`}>
              <td className="px-2 py-2 group-hover:shadow-[inset_3px_0_0_var(--accent)]">
                <span className="flex items-center gap-2">
                  <UiRankBadge rank={r.rank} />
                  {movement && <Movement by={movement.get(r.team.id)} />}
                </span>
              </td>
              <td className="px-2 py-2">
                <Link href={`/teams/${r.team.slug}`} className="flex min-w-0 items-center gap-3 hover:text-accent-hot">
                  <TeamMark team={r.team} size="md" />
                  <span className="min-w-0">
                    <span className="block truncate font-display text-lg leading-tight font-extrabold uppercase">{r.team.name}</span>
                    {r.last_match_points != null && <span className="block text-xs text-muted">Last match +{r.last_match_points}</span>}
                  </span>
                </Link>
              </td>
              {!compact && <td className={`${td} text-muted`}>{r.matches_played}</td>}
              <td className={`${td} ${r.booyahs ? "text-accent-2" : "text-muted"}`}>{r.booyahs}</td>
              <td className={td}>{r.kills}</td>
              {!compact && <td className={`${td} text-muted`}>{r.placement_points}</td>}
              {!compact && <td className={`${td} hidden text-muted xl:table-cell`}>{r.kill_points}</td>}
              {pp && (
                <td className={td}>
                  <PP value={pp.get(r.team.id)} />
                </td>
              )}
              <td className={`${td} pr-4 text-3xl font-black text-accent-hot`}>{r.total_points}</td>
              {!compact && (
                <td className="hidden px-2 py-2 lg:table-cell">
                  <Form placements={r.form} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Phones: one card per team. */}
      <ol className="space-y-2 md:hidden">
        {rows.map((r) => {
          const stats: [string, React.ReactNode][] = [
            ...(!compact ? ([["Played", r.matches_played]] as [string, React.ReactNode][]) : []),
            ["Booyahs", <span key="b" className={r.booyahs ? "text-accent-2" : ""}>{r.booyahs}</span>],
            ["Kills", r.kills],
            ...(!compact ? ([["Place", r.placement_points]] as [string, React.ReactNode][]) : []),
            ...(pp ? ([["PP", <PP key="pp" value={pp.get(r.team.id)} />]] as [string, React.ReactNode][]) : []),
          ];
          return (
            <li key={r.team.id} className={`card p-3 ${PODIUM_ROW[r.rank] ?? ""}`}>
              <div className="flex items-center gap-3">
                <span className="flex flex-col items-center gap-1">
                  <UiRankBadge rank={r.rank} />
                  {movement && <Movement by={movement.get(r.team.id)} />}
                </span>
                <Link href={`/teams/${r.team.slug}`} className="flex min-w-0 flex-1 items-center gap-2.5">
                  <TeamMark team={r.team} size="md" />
                  <span className="min-w-0">
                    <span className="block truncate font-display text-lg leading-tight font-extrabold uppercase">{r.team.name}</span>
                    {r.last_match_points != null && <span className="block text-xs text-muted">Last match +{r.last_match_points}</span>}
                  </span>
                </Link>
                <span className="text-right">
                  <span className="num block text-3xl leading-none text-accent-hot">{r.total_points}</span>
                  <span className="text-[10px] font-bold tracking-[0.16em] text-muted uppercase">pts</span>
                </span>
              </div>
              <dl className="mt-3 grid border-t border-line pt-2.5" style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}>
                {stats.map(([label, value]) => (
                  <div key={label} className="text-center">
                    <dt className="text-[10px] font-bold tracking-[0.14em] text-muted uppercase">{label}</dt>
                    <dd className="num text-lg">{value}</dd>
                  </div>
                ))}
              </dl>
            </li>
          );
        })}
      </ol>
    </>
  );
}
