// Distinct team colours for maps (up to 16 teams), readable on the dark background.
export const TEAM_COLORS = [
  "#ff2e63",
  "#22d3ee",
  "#facc15",
  "#a3e635",
  "#c084fc",
  "#fb923c",
  "#38bdf8",
  "#f472b6",
  "#4ade80",
  "#e879f9",
  "#fbbf24",
  "#2dd4bf",
  "#f87171",
  "#818cf8",
  "#bef264",
  "#fda4af",
];

export function teamColor(index: number, preferred?: string | null): string {
  return preferred || TEAM_COLORS[index % TEAM_COLORS.length];
}
