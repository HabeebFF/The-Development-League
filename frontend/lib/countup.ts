// Count-up for stat numbers: where a number is, ``progress`` (0 to 1) of the way through its animation.

/** Ease-out cubic: fast start, gentle landing. */
export function easeOut(progress: number): number {
  const p = Math.min(1, Math.max(0, progress));
  return 1 - (1 - p) ** 3;
}

/** The number to show at ``progress``, rounded to ``decimals``; always exactly ``end`` once finished. */
export function countUpValue(end: number, progress: number, decimals = 0): string {
  if (progress >= 1) return end.toFixed(decimals);
  return (end * easeOut(progress)).toFixed(decimals);
}
