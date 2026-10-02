import Link from "next/link";

import type { TeamRef } from "@/lib/league";

const BOX = { sm: "h-7 w-7 text-[10px]", md: "h-10 w-10 text-xs", lg: "h-16 w-16 text-lg", xl: "h-24 w-24 text-2xl sm:h-28 sm:w-28" };

/** A team's mark: its logo, or its tag on the team colour. */
export function TeamMark({ team, size = "sm" }: { team: TeamRef; size?: keyof typeof BOX }) {
  const box = BOX[size];
  return team.logo ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={team.logo} alt="" className={`${box} shrink-0 object-contain`} loading="lazy" />
  ) : (
    <span
      className={`${box} flex shrink-0 items-center justify-center font-display text-white`}
      style={{
        background: `linear-gradient(135deg, ${team.primary_color || "var(--panel-2)"}, color-mix(in srgb, ${team.primary_color || "#181b26"} 55%, black))`,
        clipPath: "polygon(0 0, 100% 0, 100% 78%, 78% 100%, 0 100%)",
      }}
    >
      {(team.tag || team.name).slice(0, 4).toUpperCase()}
    </span>
  );
}

/** A team's mark and name, linking to its page. */
export default function TeamBadge({
  team,
  link = true,
  size = "sm",
  wrap = false,
}: {
  team: TeamRef;
  link?: boolean;
  size?: "sm" | "lg";
  /** Let a long name run onto a second line instead of cutting it off. */
  wrap?: boolean;
}) {
  if (size === "lg") return <TeamMark team={team} size="lg" />;
  const body = (
    <span className="flex min-w-0 items-center gap-2.5">
      <TeamMark team={team} />
      <span className={`font-semibold ${wrap ? "line-clamp-2 text-[13px] leading-tight sm:text-sm" : "truncate"}`}>{team.name}</span>
    </span>
  );
  return link ? (
    <Link href={`/teams/${team.slug}`} className="min-w-0 transition-colors hover:text-accent">
      {body}
    </Link>
  ) : (
    body
  );
}
