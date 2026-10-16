import Link from "next/link";

import type { NavLink } from "@/lib/nav";

/** Big tiles that say what each page is for, so first-time visitors know where to go. */
export default function ExploreGrid({ links, className = "" }: { links: NavLink[]; className?: string }) {
  return (
    <div className={`grid grid-cols-2 gap-3 lg:grid-cols-4 ${className}`}>
      {links.map((l) => (
        <Link key={l.href} href={l.href} className="card card-hover group flex flex-col gap-2 p-4">
          <span className="flex h-10 w-10 items-center justify-center bg-accent/15 text-accent transition-colors group-hover:bg-accent group-hover:text-white">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden>
              <path d={l.icon} />
            </svg>
          </span>
          <span className="font-display text-xl leading-tight uppercase sm:text-2xl">{l.label}</span>
          <span className="text-xs leading-snug text-muted sm:text-sm">{l.blurb}</span>
        </Link>
      ))}
    </div>
  );
}
