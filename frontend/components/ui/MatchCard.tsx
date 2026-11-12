import Image from "next/image";
import Link from "next/link";

import { mapName } from "@/lib/league";

/** Maps with bundled art in /public/maps (the same images the map tools use, shrunk for cards). */
const MAP_ART = new Set(["bermuda", "purgatory", "kalahari", "nexterra", "solara"]);

/** The bundled art for a map, or null for a map we have no picture of. */
export function mapArt(slug: string | null): string | null {
  return slug && MAP_ART.has(slug) ? `/maps/${slug}.webp` : null;
}

export type MatchCardTeam = { name: string; points?: number | null };

/**
 * One match as a broadcast card: the map's art behind its name, a label (day, session, match number),
 * the Booyah winner and, when known, each team's points.
 */
export default function MatchCard({
  href,
  map,
  label,
  booyah,
  teams,
  footer,
  className = "",
}: {
  href: string;
  map: string | null;
  label: string;
  booyah?: string | null;
  /** Teams in finishing order; the first is the Booyah. */
  teams?: MatchCardTeam[];
  footer?: string;
  className?: string;
}) {
  const art = mapArt(map);
  return (
    <Link href={href} className={`card card-hover group block overflow-hidden ${className}`}>
      <span className="relative block h-24 overflow-hidden bg-panel-2">
        {art && (
          <Image
            src={art}
            alt=""
            fill
            unoptimized
            sizes="320px"
            className="object-cover opacity-80 transition-transform duration-500 group-hover:scale-105"
          />
        )}
        <span className="absolute inset-0 bg-[linear-gradient(180deg,rgb(7_8_12/0.15),var(--panel)_96%),linear-gradient(90deg,rgb(7_8_12/0.75),transparent_70%)]" />
        <span className="chip absolute top-2.5 right-2.5 bg-bg/80">{label}</span>
        <span className="absolute bottom-2 left-3.5 font-display text-[28px] leading-none font-black tracking-[0.02em] uppercase">
          {mapName(map)}
        </span>
      </span>
      <span className="block px-3.5 pt-1 pb-3.5">
        {teams && teams.length > 0 ? (
          <ol className="space-y-1.5">
            {teams.map((t, i) => (
              <li key={t.name} className="flex items-center gap-2.5 font-display text-base font-bold uppercase">
                <span className="w-5 text-muted tabular-nums">{i + 1}</span>
                <span className={`min-w-0 flex-1 truncate ${i === 0 ? "text-accent-hot" : ""}`}>{t.name}</span>
                {i === 0 && <BooyahBadge />}
                {t.points != null && <span className="font-extrabold tabular-nums">{t.points}</span>}
              </li>
            ))}
          </ol>
        ) : booyah ? (
          <span className="flex items-center gap-2.5 font-display text-lg font-bold uppercase">
            <BooyahBadge />
            <span className="min-w-0 flex-1 truncate text-accent-hot">{booyah}</span>
          </span>
        ) : (
          <span className="text-sm text-muted">No Booyah recorded</span>
        )}
        {footer && <span className="mt-2 block text-[11px] font-bold tracking-[0.16em] text-accent uppercase">{footer}</span>}
      </span>
    </Link>
  );
}

/** The gold "Booyah" tag for a match winner. */
export function BooyahBadge() {
  return (
    <span
      className="inline-flex shrink-0 items-center bg-gradient-to-br from-lion-hot to-lion px-1.5 py-0.5 font-display text-[11px] font-black tracking-[0.12em] text-accent-ink uppercase"
      style={{ clipPath: "polygon(4px 0, 100% 0, calc(100% - 4px) 100%, 0 100%)" }}
    >
      Booyah
    </span>
  );
}
