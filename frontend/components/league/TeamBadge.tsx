import Link from "next/link";

import type { TeamRef } from "@/lib/league";

/** A team's logo (or its tag in the team colour) and name, linking to its page. */
export default function TeamBadge({ team, link = true, size = "sm" }: { team: TeamRef; link?: boolean; size?: "sm" | "lg" }) {
  const box = size === "lg" ? "h-16 w-16 text-lg" : "h-7 w-7 text-[10px]";
  const mark = team.logo ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={team.logo} alt="" className={`${box} shrink-0 rounded object-contain`} />
  ) : (
    <span
      className={`${box} flex shrink-0 items-center justify-center rounded font-bold text-white`}
      style={{ background: team.primary_color || "var(--panel-2)" }}
    >
      {(team.tag || team.name).slice(0, 4).toUpperCase()}
    </span>
  );
  if (size === "lg") return mark;
  const body = (
    <span className="flex min-w-0 items-center gap-2">
      {mark}
      <span className="truncate">{team.name}</span>
    </span>
  );
  return link ? (
    <Link href={`/teams/${team.slug}`} className="min-w-0 hover:text-accent">
      {body}
    </Link>
  ) : (
    body
  );
}
