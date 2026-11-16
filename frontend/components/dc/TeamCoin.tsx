"use client";

import { dc, teamCoin } from "@/lib/dc";
import { useDcBoard } from "@/lib/dcBoard";

const COIN = { 1: "var(--gold)", 2: "#c9d1dc", 3: "#c98a4b" } as const;
const PLACE = { 1: "Most", 2: "2nd most", 3: "3rd most" } as const;

/** On the standings: a gold, silver or bronze coin for the three teams whose players earned the
 * most DC from matches this month. */
export default function TeamCoin({ teamId }: { teamId: number | null | undefined }) {
  const board = useDcBoard();
  if (!board) return null;
  const place = teamCoin(board.teams, teamId);
  if (!place) return null;
  const row = board.teams[place - 1];
  const label = `${PLACE[place]} DC earned this month: ${dc(row.dc)}`;
  return (
    <span role="img" aria-label={label} title={label} className="ml-1.5 inline-flex shrink-0 align-middle">
      <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="7" fill={COIN[place]} stroke="rgba(0,0,0,.35)" />
        <text x="8" y="11.2" textAnchor="middle" fontSize="8.5" fontWeight="800" fill="rgba(0,0,0,.7)">
          {place}
        </text>
      </svg>
    </span>
  );
}
