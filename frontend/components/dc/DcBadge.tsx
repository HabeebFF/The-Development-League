"use client";

import { kingMonth, rankFor } from "@/lib/dc";
import { useDcBoard } from "@/lib/dcBoard";

import RankIcon from "./RankIcon";

/** Beside a player's name: their DC rank, and "DC KING · NOVEMBER" for the month's DC King. */
export default function DcBadge({ playerId, king = true, size }: { playerId: number | null | undefined; king?: boolean; size?: number }) {
  const board = useDcBoard();
  if (!board || playerId == null) return null;
  const earned = board.players[String(playerId)] ?? 0;
  const step = rankFor(earned, board.steps);
  const isKing = king && board.king?.player_id === playerId;
  if (!step && !isKing) return null;
  return (
    <span className="ml-1.5 inline-flex items-center gap-1 align-middle">
      {step && <RankIcon step={step} earned={earned} size={size} />}
      {isKing && board.king && (
        <span className="rounded-sm bg-[var(--gold)] px-1 font-display text-[10px] leading-4 font-extrabold tracking-wide text-black">
          DC KING · {kingMonth(board.king.month)}
        </span>
      )}
    </span>
  );
}
