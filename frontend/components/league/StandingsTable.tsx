import type { StandingRow } from "@/lib/league";

import TeamBadge from "./TeamBadge";

function Form({ placements }: { placements: number[] }) {
  return (
    <span className="flex justify-end gap-1">
      {placements.map((p, i) => (
        <span
          key={i}
          className={`flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold ${
            p === 1 ? "bg-accent-2 text-black" : p <= 3 ? "bg-panel-2 text-text" : "bg-panel text-muted"
          }`}
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
  const cell = "px-2 py-2 text-right tabular-nums";
  const wide = compact ? "hidden" : "hidden sm:table-cell";
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-panel">
      <table className="w-full text-sm">
        <thead className="text-xs text-muted uppercase">
          <tr className="border-b border-line">
            <th className="px-2 py-2 text-left">#</th>
            <th className="px-2 py-2 text-left">Team</th>
            <th className={`${cell} ${wide}`} title="Matches played">MP</th>
            <th className={cell} title="Booyahs">Booyah</th>
            <th className={cell}>Kills</th>
            <th className={`${cell} ${wide}`} title="Placement points">Place pts</th>
            <th className={`${cell} ${wide}`} title="Kill points">Kill pts</th>
            <th className={cell}>Total</th>
            <th className={`${cell} ${compact ? "hidden" : "hidden md:table-cell"}`} title="Placements in the last five matches">
              Form
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.team.id} className="border-b border-line last:border-0">
              <td className={`px-2 py-2 font-display text-lg ${r.rank <= 3 ? "text-accent" : "text-muted"}`}>{r.rank}</td>
              <td className="max-w-[8rem] px-2 py-2 sm:max-w-none">
                <TeamBadge team={r.team} />
              </td>
              <td className={`${cell} ${wide}`}>{r.matches_played}</td>
              <td className={cell}>{r.booyahs}</td>
              <td className={cell}>{r.kills}</td>
              <td className={`${cell} ${wide}`}>{r.placement_points}</td>
              <td className={`${cell} ${wide}`}>{r.kill_points}</td>
              <td className={`${cell} font-bold`}>{r.total_points}</td>
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
