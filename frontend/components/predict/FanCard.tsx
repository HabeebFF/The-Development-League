import { CARD_SHAPE } from "@/components/league/PlayerCard";
import { TdlMark } from "@/components/ui/TdlLogo";
import { copyText, designColors, PATTERNS } from "@/lib/cardDesigns";
import type { FanCardData } from "@/lib/shop";

// The default fan card: the site's dark broadcast look with a molten gold line.
const DEFAULT = { top: "#1a1d29", bottom: "#07080c", ink: "#f2f3f7", line: "#f5a524", glow: "245 165 36" };

/** A predictor's card (anyone with DC): favourite team, wins and net DC, in their design. */
export default function FanCard({ fan, size = 1 }: { fan: FanCardData; size?: number }) {
  const look = designColors(fan.design) ?? DEFAULT;
  const parts = fan.design && designColors(fan.design) ? fan.design.parts : null;
  const pattern = parts ? PATTERNS[parts.pattern] : undefined;
  const effect = parts?.effect ?? "none";
  const copy = copyText(fan.design);
  const s = fan.stats;
  const acc = s.accuracy == null ? "–" : `${Math.round(s.accuracy * 100)}`;
  const team = fan.favourite_team;
  return (
    <div
      className="holo-host relative aspect-[5/7] w-[15em] select-none"
      style={{
        fontSize: `${size * 16}px`,
        color: look.ink,
        ["--design-glow" as string]: look.glow,
        filter: `drop-shadow(0 0 0.8em rgb(${look.glow} / 0.4))`,
      }}
      aria-label={`${fan.name}'s fan card`}
    >
      <div
        className="absolute inset-0"
        style={{
          clipPath: CARD_SHAPE,
          background: `linear-gradient(160deg, ${look.top}, ${look.bottom})`,
          boxShadow: "inset 0 0 0 0.12em rgb(255 255 255 / 0.25)",
        }}
      >
        <span className="absolute inset-0 bg-[linear-gradient(115deg,transparent_30%,rgb(255_255_255/0.2)_45%,transparent_60%)]" />
        {pattern && pattern !== "none" && <span className="absolute inset-0" style={{ background: pattern }} />}
        {effect === "glow" && <span aria-hidden className="design-glow absolute inset-0" />}
        {effect === "shine" && <span aria-hidden className="design-shine absolute inset-0" />}
        {effect === "flame" && <span aria-hidden className="design-flame absolute inset-0" />}
        {effect === "sparkle" && <span aria-hidden className="design-sparkle absolute inset-0" />}
        <span aria-hidden className="holo absolute inset-0" />
        <span className="absolute inset-[0.35em]" style={{ clipPath: CARD_SHAPE, boxShadow: `inset 0 0 0 0.08em ${look.line}` }} />

        <div className="absolute top-[1.4em] left-[1.5em] flex w-[3.2em] flex-col items-center">
          <span className="font-display text-[3em] leading-[0.85]">{s.won}</span>
          <span className="mt-[0.15em] font-display text-[1.05em] tracking-wider uppercase">Wins</span>
          <span className="mt-[0.35em] h-px w-[2.4em]" style={{ background: look.ink, opacity: 0.35 }} />
          <span className="mt-[0.45em] font-display text-[0.8em] tracking-widest uppercase opacity-80">Fan</span>
        </div>
        <div className="absolute top-[1.4em] right-[1.4em] flex h-[6.8em] w-[7em] items-center justify-center">
          {team?.logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={team.logo} alt={team.name} className="h-full w-full object-contain" />
          ) : team ? (
            <span
              className="flex h-[4.5em] min-w-[4.5em] items-center justify-center px-[0.3em] font-display text-[1.4em] text-white"
              style={{ background: team.primary_color || "#181b26", clipPath: "polygon(0 0, 100% 0, 100% 78%, 78% 100%, 0 100%)" }}
            >
              {(team.tag || team.name).slice(0, 4).toUpperCase()}
            </span>
          ) : (
            <TdlMark className="h-[5em] w-auto opacity-90" />
          )}
        </div>

        <div className="absolute inset-x-[0.8em] top-[8.75em]">
          <p className="truncate text-center font-display text-[1.45em] leading-none tracking-wide uppercase">{fan.name}</p>
        </div>
        <span className="absolute inset-x-[2em] top-[10.5em] h-px" style={{ background: look.ink, opacity: 0.35 }} />
        <div className="absolute inset-x-[1.6em] top-[11em] grid grid-cols-2 gap-x-[1em] gap-y-[0.2em]">
          <FanStat value={compact(s.net)} label="DC" />
          <FanStat value={acc} label="ACC" />
          <FanStat value={String(s.won)} label="WON" />
          <FanStat value={String(s.lost)} label="LOST" />
        </div>
        <div className="absolute inset-x-0 bottom-[1.3em]">
          <p className="text-center text-[0.5em] font-bold tracking-[0.25em] uppercase opacity-70">
            {team ? `${team.tag || team.name} fan` : "TDL predictor"}
            {copy && <span className="ml-[0.6em]">{copy}</span>}
          </p>
        </div>
      </div>
    </div>
  );
}

function FanStat({ value, label }: { value: string; label: string }) {
  return (
    <span className="flex items-baseline gap-[0.3em]">
      <span className="min-w-[1.4em] text-right font-display text-[1.15em] leading-tight">{value}</span>
      <span className="font-display text-[0.95em] tracking-wide uppercase">{label}</span>
    </span>
  );
}

function compact(n: number): string {
  return n >= 10000 ? `${Math.round(n / 1000)}K` : n.toLocaleString("en-GB");
}
