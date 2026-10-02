import type { StandingRow } from "@/lib/league";

import TeamBadge from "./TeamBadge";

/** A rank number; the top three get gold, silver and bronze badges. */
export function RankBadge({ rank }: { rank: number }) {
  return <span className={`rank ${rank <= 3 ? `rank-${rank}` : ""}`}>{rank}</span>;
}

/** Placements in recent matches, Booyahs in gold. */
export function Form({ placements, className = "justify-end" }: { placements: number[]; className?: string }) {
  return (
    <span className={`flex gap-1 ${className}`}>
      {placements.map((p, i) => (
        <span
          key={i}
          className={`flex h-6 w-6 items-center justify-center font-display text-xs ${
            p === 1 ? "bg-accent-2 text-black shadow-[0_0_10px_rgb(255_194_61/0.5)]" : p <= 3 ? "bg-panel-2 text-text" : "bg-bg text-muted"
          }`}
          title={p === 1 ? "Booyah" : `Placed ${p}`}
        >
          {p}
        </span>
      ))}
    </span>
  );
}

/** The league table. ``compact`` keeps rank, team, Booyahs, kills and points only. */
export default function StandingsTable({ rows, compact = false }: { rows: StandingRow[]; compact?: boolean }) {
  if (!rows.length) return <p className="text-sm text-muted">No results yet.</p>;
  const cell = "px-1.5 py-2.5 text-right tabular-nums sm:px-2";
  // Matches played and placement points show on phones too; kill points only on wider screens.
  const full = compact ? "hidden" : "";
  const wide = compact ? "hidden" : "hidden sm:table-cell";
  return (
    <div className="card overflow-x-auto">
      <table className="table">
        <thead>
          <tr>
            <th className="w-10 text-left sm:w-12">#</th>
            <th className="text-left">Team</th>
            <th className={`${cell} ${full}`} title="Matches played">MP</th>
            <th className={cell} title="Booyahs">
              <span className="sm:hidden">BY</span>
              <span className="hidden sm:inline">Booyah</span>
            </th>
            <th className={cell}>Kills</th>
            <th className={`${cell} ${full}`} title="Placement points">
              <span className="sm:hidden">PL</span>
              <span className="hidden sm:inline">Place pts</span>
            </th>
            <th className={`${cell} ${wide}`} title="Kill points">Kill pts</th>
            <th className={`${cell} pr-3 sm:pr-4`}>Pts</th>
            <th className={`${cell} ${compact ? "hidden" : "hidden md:table-cell"}`} title="Placements in the last five matches">
              Form
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.team.id} className={r.rank === 1 ? "bg-[linear-gradient(90deg,rgb(246_197_68/0.08),transparent_60%)]" : ""}>
              <td className="px-1.5 py-2.5 sm:px-2">
                <RankBadge rank={r.rank} />
              </td>
              <td className="max-w-[8.5rem] px-1.5 py-2.5 sm:max-w-none sm:px-2">
                <TeamBadge team={r.team} wrap />
              </td>
              <td className={`${cell} ${full} text-muted`}>{r.matches_played}</td>
              <td className={`${cell} font-semibold ${r.booyahs ? "text-accent-2" : "text-muted"}`}>{r.booyahs}</td>
              <td className={`${cell} font-semibold`}>{r.kills}</td>
              <td className={`${cell} ${full} text-muted`}>{r.placement_points}</td>
              <td className={`${cell} ${wide} text-muted`}>{r.kill_points}</td>
              <td className={`${cell} pr-3 font-display sm:pr-4 text-xl text-white`}>{r.total_points}</td>
              <td className={`${cell} ${compact ? "hidden" : "hidden md:table-cell"}`}>
                <Form placements={r.form} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!compact && (
        <p className="border-t border-line px-3 py-2 text-[11px] text-muted sm:hidden">
          MP matches played · BY Booyahs · PL placement points
        </p>
      )}
    </div>
  );
}
