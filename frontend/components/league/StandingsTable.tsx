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
  const cell = "px-2 py-2.5 text-right tabular-nums";
  const wide = compact ? "hidden" : "hidden sm:table-cell";
  return (
    <div className="card overflow-x-auto">
      <table className="table">
        <thead>
          <tr>
            <th className="w-12 text-left">#</th>
            <th className="text-left">Team</th>
            <th className={`${cell} ${wide}`} title="Matches played">MP</th>
            <th className={cell} title="Booyahs">Booyah</th>
            <th className={cell}>Kills</th>
            <th className={`${cell} ${wide}`} title="Placement points">Place pts</th>
            <th className={`${cell} ${wide}`} title="Kill points">Kill pts</th>
            <th className={`${cell} pr-4`}>Pts</th>
            <th className={`${cell} ${compact ? "hidden" : "hidden md:table-cell"}`} title="Placements in the last five matches">
              Form
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.team.id} className={r.rank === 1 ? "bg-[linear-gradient(90deg,rgb(246_197_68/0.08),transparent_60%)]" : ""}>
              <td className="px-2 py-2.5">
                <RankBadge rank={r.rank} />
              </td>
              <td className="max-w-[10.5rem] px-2 py-2.5 sm:max-w-none">
                <TeamBadge team={r.team} wrap />
              </td>
              <td className={`${cell} ${wide} text-muted`}>{r.matches_played}</td>
              <td className={`${cell} font-semibold ${r.booyahs ? "text-accent-2" : "text-muted"}`}>{r.booyahs}</td>
              <td className={`${cell} font-semibold`}>{r.kills}</td>
              <td className={`${cell} ${wide} text-muted`}>{r.placement_points}</td>
              <td className={`${cell} ${wide} text-muted`}>{r.kill_points}</td>
              <td className={`${cell} pr-4 font-display text-xl text-white`}>{r.total_points}</td>
              <td className={`${cell} ${compact ? "hidden" : "hidden md:table-cell"}`}>
                <Form placements={r.form} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
