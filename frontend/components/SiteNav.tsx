"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { GROUPS, HOME, MENU_ICON, groupActive, isActive as active, type NavGroup } from "@/lib/nav";

import { useAuth } from "./Auth";

const MORE = [
  { href: "/team", label: "My team" },
  { href: "/staff", label: "Staff" },
];

function Icon({ d, className = "h-5 w-5" }: { d: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d={d} />
    </svg>
  );
}

/** The top bar (grouped links on desktop) and, on phones, a bottom tab bar whose Menu opens every page with a line on each. */
export default function SiteNav() {
  const path = usePathname();
  const { status, publicSite, site, signOut } = useAuth();
  // Links behind a switch (e.g. Predict) only show once the server has it on.
  const groups = GROUPS.filter((g) => !g.flag || site[g.flag]);
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
            {groups.map((g) => (
              <TopLink key={g.href} group={g} path={path} />
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
              <Link
                href={`/auth/login?next=${encodeURIComponent(path)}`}
                className="btn btn-primary ml-2 px-4 py-1.5 text-sm"
              >
                Sign in
              </Link>
            )}
          </div>
        </nav>
      </header>

      {open && shown && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="page-enter absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto border-t border-line bg-panel px-4 pt-4 pb-[calc(var(--bottom-nav-h)+env(safe-area-inset-bottom)+1rem)]"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Menu"
          >
            <div className="flex items-center justify-between">
              <p className="eyebrow">Menu</p>
              <button type="button" className="px-2 text-2xl leading-none text-muted" onClick={() => setOpen(false)} aria-label="Close menu">
                &times;
              </button>
            </div>
            {groups.map((g) => (
              <div key={g.href} className="mt-4">
                {g.items ? (
                  <>
                    <p className="mb-1 text-[11px] font-bold tracking-widest text-muted uppercase">{g.label}</p>
                    {g.items.map((l) => (
                      <MenuRow key={l.href} link={l} on={active(path, l.href)} />
                    ))}
                  </>
                ) : (
                  <MenuRow link={g} on={active(path, g.href)} />
                )}
              </div>
            ))}
            <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
              {more.map((l) => (
                <Link key={l.href} href={l.href} className="btn px-4 py-2 text-sm">
                  {l.label}
                </Link>
              ))}
              {signedIn ? (
                <button type="button" onClick={signOut} className="btn px-4 py-2 text-sm">
                  Sign out
                </button>
              ) : (
                <Link href={`/auth/login?next=${encodeURIComponent(path)}`} className="btn btn-primary px-4 py-2 text-sm">
                  Sign in
                </Link>
              )}
            </div>
          </div>
        </div>
      )}

      <nav
        className={`fixed inset-x-0 bottom-0 z-50 ${shown ? "" : "hidden"} border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden`}
        aria-label="Main"
      >
        <div className="grid h-[var(--bottom-nav-h)] grid-cols-5">
          {[HOME, ...GROUPS.slice(0, 3)].map((l) => {
            const on = !open && groupActive(path, l);
            return (
              <Link key={l.href} href={l.href} className={`${TAB} ${on ? "text-accent" : "text-muted"}`} onClick={() => setOpen(false)}>
                {on && <span className={TAB_ON} />}
                <Icon d={l.icon} />
                {l.label}
              </Link>
            );
          })}
          <button type="button" className={`${TAB} ${open ? "text-accent" : "text-muted"}`} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
            {open && <span className={TAB_ON} />}
            <Icon d={MENU_ICON} />
            Menu
          </button>
        </div>
      </nav>
    </>
  );
}

const TAB = "relative flex flex-col items-center justify-center gap-0.5 text-[10px] font-semibold tracking-wide uppercase transition-colors";
const TAB_ON = "absolute inset-x-4 top-0 h-0.5 bg-accent shadow-[0_0_10px_rgb(255_90_31)]";

/** A top-bar link; a group opens a panel of its pages, each with a line on what it is. */
function TopLink({ group: g, path }: { group: NavGroup; path: string }) {
  const on = groupActive(path, g);
  const cls = `relative flex h-full items-center gap-1 px-3 text-sm font-semibold tracking-wide uppercase transition-colors ${
    on ? "text-white" : "text-muted hover:text-white"
  }`;
  const bar = on && <span className="absolute inset-x-3 bottom-0 h-0.5 bg-accent shadow-[0_0_10px_rgb(255_90_31)]" />;
  if (!g.items) {
    return (
      <Link href={g.href} className={cls}>
        {g.label}
        {bar}
      </Link>
    );
  }
  return (
    <div className="group relative h-full">
      <Link href={g.href} className={cls} aria-haspopup="true">
        {g.label}
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 transition-transform group-hover:rotate-180" fill="currentColor" aria-hidden>
          <path d="M5.5 7.5 10 12l4.5-4.5z" />
        </svg>
        {bar}
      </Link>
      <div className="invisible absolute top-full left-0 w-80 pt-1 opacity-0 transition group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
        <div className="border border-line bg-panel p-2 shadow-[0_18px_40px_-12px_rgb(0_0_0/0.8)]">
          {g.items.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`flex items-start gap-3 px-3 py-2.5 transition-colors hover:bg-panel-2 ${active(path, l.href) ? "text-accent" : ""}`}
            >
              <Icon d={l.icon} className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
              <span>
                <span className="block text-sm font-semibold">{l.label}</span>
                <span className="block text-xs text-muted">{l.blurb}</span>
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

/** A row in the phone menu: icon, name and what the page is for. */
function MenuRow({ link: l, on }: { link: { href: string; label: string; blurb: string; icon: string }; on: boolean }) {
  return (
    <Link href={l.href} className={`flex items-center gap-3 border-b border-line/60 py-3 last:border-0 ${on ? "text-accent" : ""}`}>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center bg-panel-2 text-accent">
        <Icon d={l.icon} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-display text-xl leading-tight uppercase">{l.label}</span>
        <span className="block truncate text-xs text-muted">{l.blurb}</span>
      </span>
      <span className="text-muted">&rsaquo;</span>
    </Link>
  );
}
