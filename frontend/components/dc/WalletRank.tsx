"use client";

import { rankFor } from "@/lib/dc";
import { useDcBoard } from "@/lib/dcBoard";

import RankIcon from "./RankIcon";

/** A DC rank badge from a wallet's net DC (coins now plus shop spend): fans and players alike. */
export default function WalletRank({ net }: { net: number | null | undefined }) {
  const board = useDcBoard();
  if (!board || net == null) return null;
  const earned = Math.max(net - board.initial, 0);
  const step = rankFor(earned, board.steps);
  return step ? (
    <span className="ml-1.5">
      <RankIcon step={step} earned={earned} />
    </span>
  ) : null;
}
