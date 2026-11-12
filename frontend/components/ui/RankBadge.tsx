/** A rank in a slanted plate; 1, 2 and 3 get gold, silver and bronze. */
export default function RankBadge({ rank, className = "" }: { rank: number; className?: string }) {
  return (
    <span className={`rank ${rank >= 1 && rank <= 3 ? `rank-${rank}` : ""} ${className}`.trim()} aria-label={`Rank ${rank}`}>
      {rank}
    </span>
  );
}

/** Up, down or no change since last time, as a coloured arrow and the number of places. */
export function Movement({ by }: { by: number | null | undefined }) {
  if (by == null) return <span className="inline-block w-7" aria-hidden />;
  const dir = by > 0 ? "up" : by < 0 ? "down" : "same";
  const label = dir === "same" ? "No change" : `${dir === "up" ? "Up" : "Down"} ${Math.abs(by)}`;
  return (
    <span
      className={`inline-flex w-7 items-center gap-0.5 font-display text-[13px] font-extrabold tabular-nums ${
        dir === "up" ? "text-up" : dir === "down" ? "text-down" : "text-same"
      }`}
      title={label}
    >
      <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" fill="currentColor" aria-hidden>
        <path d={dir === "up" ? "M5 1 10 9H0z" : dir === "down" ? "M5 9 0 1h10z" : "M0 4h10v2H0z"} />
      </svg>
      {dir !== "same" && Math.abs(by)}
      <span className="sr-only">{label}</span>
    </span>
  );
}
