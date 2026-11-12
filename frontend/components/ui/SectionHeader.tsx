import Link from "next/link";
import type { ReactNode } from "react";

/** A section title with the slanted gold bar, and an optional link or controls on the right. */
export default function SectionHeader({
  title,
  href,
  link,
  as: H = "h2",
  children,
}: {
  title: string;
  href?: string;
  link?: string;
  as?: "h1" | "h2" | "h3";
  /** Extra controls (tabs, filters) shown on the right. */
  children?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
      <H className="section-title">{title}</H>
      {children}
      {href && link && (
        <Link
          href={href}
          className="inline-flex min-h-11 items-center font-display text-sm font-bold tracking-[0.14em] text-accent uppercase transition-colors hover:text-accent-hot"
        >
          {link} <span aria-hidden className="ml-1">&rsaquo;</span>
        </Link>
      )}
    </div>
  );
}
