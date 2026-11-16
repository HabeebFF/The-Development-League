import { dc, type RankStep } from "@/lib/dc";

const COLOURS: Record<string, string> = {
  bronze: "#c98a4b",
  silver: "#c9d1dc",
  gold: "var(--gold)",
  elite: "var(--gold)",
  legend: "var(--gold)",
};

/** A small rank badge: a chevron (bronze, silver, gold), a sparked chevron (Elite) or a crown
 * (Legend). Ranks staff add later get a plain gold chevron. */
export default function RankIcon({ step, earned, size = 14 }: { step: RankStep; earned?: number; size?: number }) {
  const colour = COLOURS[step.key] ?? "var(--gold)";
  const label = earned != null ? `${step.name} · ${dc(earned)} earned` : step.name;
  return (
    <span role="img" aria-label={label} title={label} className="inline-flex shrink-0 items-center align-middle">
      <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
        {step.key === "legend" ? (
          <path d="M2 12 L3 5 L6 8 L8 3 L10 8 L13 5 L14 12 Z" fill={colour} stroke="rgba(0,0,0,.35)" strokeWidth="0.8">
            <animate attributeName="opacity" values="1;.7;1" dur="2.4s" repeatCount="indefinite" />
          </path>
        ) : (
          <>
            <path d="M2 4 L8 8 L14 4 L14 7.5 L8 11.5 L2 7.5 Z" fill={colour} stroke="rgba(0,0,0,.35)" strokeWidth="0.8" />
            {step.key === "elite" && <path d="M8 12.2 L9 14 L8 15.8 L7 14 Z" fill={colour} />}
          </>
        )}
      </svg>
    </span>
  );
}
