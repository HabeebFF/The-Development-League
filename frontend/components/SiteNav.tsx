"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "./Auth";

const MAIN = [
  { href: "/", label: "Home", icon: "M3 11 12 4l9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" },
  { href: "/standings", label: "Standings", icon: "M4 20V10h4v10zm6 0V4h4v16zm6 0v-7h4v7z" },
  { href: "/results", label: "Results", icon: "M7 4h10v3a5 5 0 0 1-10 0zM5 5H3v2a4 4 0 0 0 4 4M19 5h2v2a4 4 0 0 1-4 4M10 14h4v3h3v3H7v-3h3z" },
  { href: "/teams", label: "Teams", icon: "M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z" },
];
const MORE = [
  { href: "/team", label: "My team" },
  { href: "/staff", label: "Staff" },
];

function active(path: string, href: string) {
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
}

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden>
      <path d={d} />
    </svg>
  );
}

/** The top bar (all links on desktop) and, on phones, a bottom tab bar plus a menu for the rest. */
export default function SiteNav() {
  const path = usePathname();
  const { status, publicSite, signOut } = useAuth();
  const signedIn = status === "in";
  // Visitors see the league pages too while the site is public.
  const shown = signedIn || publicSite === true;
  const more = signedIn ? MORE : [];
  const [open, setOpen] = useState(false);
  // Close the phone menu whenever the page changes.
  const [openedOn, setOpenedOn] = useState(path);
  if (openedOn !== path) {
    setOpenedOn(path);
    setOpen(false);
  }
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <header className="sticky top-0 z-30 h-[var(--header-h)] border-b border-line bg-bg/85 backdrop-blur-md">
        <nav className="mx-auto flex h-full max-w-6xl items-center gap-8 px-4">
          <Link href="/" className="flex items-center gap-2.5" aria-label="The Development League, home">
            <span
              className="flex h-8 w-9 items-center justify-center bg-gradient-to-br from-accent to-accent-hot font-display text-base text-white shadow-[0_0_18px_-2px_rgb(255_90_31/0.8)]"
              style={{ clipPath: "polygon(18% 0, 100% 0, 82% 100%, 0 100%)" }}
            >
              TDL
            </span>
            <span className="font-display text-xl leading-none tracking-wide uppercase">
              Development <span className="text-accent">League</span>
            </span>
          </Link>
          <div className={`hidden h-full flex-1 items-center gap-1 ${shown ? "md:flex" : ""}`}>
            {MAIN.slice(1).map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`relative flex h-full items-center px-3 text-sm font-semibold tracking-wide uppercase transition-colors ${
                  active(path, l.href) ? "text-white" : "text-muted hover:text-white"
                }`}
              >
                {l.label}
                {active(path, l.href) && <span className="absolute inset-x-3 bottom-0 h-0.5 bg-accent shadow-[0_0_10px_rgb(255_90_31)]" />}
              </Link>
            ))}
            <span className="flex-1" />
            {more.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`px-3 text-sm font-medium transition-colors ${active(path, l.href) ? "text-accent" : "text-muted hover:text-white"}`}
              >
                {l.label}
              </Link>
            ))}
            {signedIn ? (
              <button type="button" onClick={signOut} className="px-3 text-sm font-medium text-muted transition-colors hover:text-white">
                Sign out
              </button>
            ) : (
              <Link href={`/auth/login?next=${encodeURIComponent(path)}`} className="px-3 text-sm font-medium text-muted transition-colors hover:text-white">
                Sign in
              </Link>
            )}
          </div>
          <button
            type="button"
            className={`ml-auto h-10 w-10 items-center justify-center text-muted hover:text-white md:hidden ${shown ? "flex" : "hidden"}`}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              {open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h10" />}
            </svg>
          </button>
        </nav>
      </header>

      {open && shown && (
        <div className="fixed inset-0 z-20 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="page-enter absolute inset-x-0 top-[var(--header-h)] border-b border-line bg-panel p-4"
            onClick={(e) => e.stopPropagation()}
          >
            {[...MAIN, ...more].map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`flex items-center justify-between border-b border-line py-3.5 font-display text-2xl uppercase last:border-0 ${
                  active(path, l.href) ? "text-accent" : ""
                }`}
              >
                {l.label}
                <span className="text-muted">&rsaquo;</span>
              </Link>
            ))}
            {signedIn ? (
              <button
                type="button"
                onClick={signOut}
                className="flex w-full items-center justify-between pt-3.5 font-display text-2xl text-muted uppercase"
              >
                Sign out
              </button>
            ) : (
              <Link
                href={`/auth/login?next=${encodeURIComponent(path)}`}
                className="flex w-full items-center justify-between pt-3.5 font-display text-2xl text-muted uppercase"
              >
                Sign in
              </Link>
            )}
          </div>
        </div>
      )}

      <nav
        className={`fixed inset-x-0 bottom-0 z-30 ${shown ? "" : "hidden"} border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden`}
        aria-label="Main"
      >
        <div className="grid h-[var(--bottom-nav-h)] grid-cols-4">
          {MAIN.map((l) => {
            const on = active(path, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`relative flex flex-col items-center justify-center gap-0.5 text-[10px] font-semibold tracking-wider uppercase transition-colors ${
                  on ? "text-accent" : "text-muted"
                }`}
              >
                {on && <span className="absolute inset-x-6 top-0 h-0.5 bg-accent shadow-[0_0_10px_rgb(255_90_31)]" />}
                <Icon d={l.icon} />
                {l.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
