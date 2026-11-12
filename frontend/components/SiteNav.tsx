"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type FocusEvent } from "react";

import { killsPath, type KillList } from "@/lib/kills";
import { GROUPS, HOME, MENU_ICON, groupActive, isActive as active, type NavGroup } from "@/lib/nav";
import { useApi } from "@/lib/useApi";

import { TeamMark } from "./league/TeamBadge";
import LionMark from "./ui/LionMark";
import PlayerAvatar from "./ui/PlayerAvatar";

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
      <header className="sticky top-0 z-30 h-[var(--header-h)] border-b border-white/[0.06] bg-bg/75 backdrop-blur-xl backdrop-saturate-150">
        {/* A thin gold-to-red broadcast rule along the bottom edge. */}
        <span
          className="pointer-events-none absolute inset-x-0 -bottom-px h-px bg-[linear-gradient(90deg,transparent,var(--lion)_30%,var(--hot)_70%,transparent)] opacity-60"
          aria-hidden
        />
        <nav className="mx-auto flex h-full max-w-6xl items-center gap-4 px-4 lg:gap-6" aria-label="Site">
          <Link href="/" className="flex min-h-11 shrink-0 items-center gap-2.5" aria-label="The Development League, home">
            <LionMark className="h-10 w-10 drop-shadow-[0_0_10px_rgb(245_165_36/0.45)]" />
            <span className="flex flex-col leading-none">
              <span className="font-display text-[26px] font-black tracking-wide">
                T<span className="text-accent">D</span>L
              </span>
              <span className="hidden text-[9px] font-bold tracking-[0.28em] text-muted uppercase lg:block">The Development League</span>
            </span>
          </Link>
          <div className={`hidden h-full flex-1 items-center ${shown ? "md:flex" : ""}`}>
            <div className="mx-auto flex h-full items-center">
              {groups.map((g) => (
                <TopLink key={g.href} group={g} path={path} />
              ))}
            </div>
            {more.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`flex min-h-11 items-center px-2.5 font-display text-sm font-bold tracking-[0.08em] uppercase transition-colors ${
                  active(path, l.href) ? "text-accent" : "text-muted hover:text-text"
                }`}
              >
                {l.label}
              </Link>
            ))}
            {signedIn ? (
              <button type="button" onClick={signOut} className="btn btn-ghost ml-1">
                Sign out
              </button>
            ) : (
              <span className="ml-2 flex items-center gap-2">
                <Link href={`/auth/login?next=${encodeURIComponent(path)}`} className={`btn ${site.signup ? "btn-ghost" : "btn-primary"}`}>
                  Sign in
                </Link>
                {site.signup && (
                  <Link href="/auth/signup" className="btn btn-primary">
                    Sign up
                  </Link>
                )}
              </span>
            )}
          </div>
          {status === "out" && (
            <span className="ml-auto flex shrink-0 items-center gap-2 md:hidden">
              {site.signup ? (
                <Link href="/auth/signup" className="btn btn-primary px-3">
                  Sign up
                </Link>
              ) : (
                <Link href={`/auth/login?next=${encodeURIComponent(path)}`} className="btn btn-primary px-3">
                  Sign in
                </Link>
              )}
            </span>
          )}
        </nav>
      </header>

      {open && shown && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="page-enter absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto border-t-2 border-accent/60 bg-panel px-4 pt-4 pb-[calc(var(--bottom-nav-h)+env(safe-area-inset-bottom)+1rem)]"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Menu"
          >
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-2">
                <LionMark className="h-6 w-6" />
                <span className="eyebrow">Menu</span>
              </p>
              <button type="button" className="flex h-11 w-11 items-center justify-center text-2xl leading-none text-muted" onClick={() => setOpen(false)} aria-label="Close menu">
                &times;
              </button>
            </div>
            {groups.map((g) => (
              <div key={g.href} className="mt-4">
                {g.items ? (
                  <>
                    <p className="mb-1 text-[11px] font-bold tracking-[0.2em] text-muted uppercase">{g.label}</p>
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
                <Link key={l.href} href={l.href} className="btn">
                  {l.label}
                </Link>
              ))}
              {signedIn ? (
                <button type="button" onClick={signOut} className="btn">
                  Sign out
                </button>
              ) : (
                <>
                  {site.signup && (
                    <Link href="/auth/signup" className="btn btn-primary">
                      Sign up
                    </Link>
                  )}
                  <Link href={`/auth/login?next=${encodeURIComponent(path)}`} className={`btn ${site.signup ? "" : "btn-primary"}`}>
                    Sign in
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <nav
        className={`fixed inset-x-0 bottom-0 z-50 ${shown ? "" : "hidden"} border-t border-white/[0.06] bg-bg/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden`}
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

const TAB = "relative flex min-h-11 flex-col items-center justify-center gap-0.5 font-display text-[11px] font-bold tracking-[0.08em] uppercase transition-colors";
const TAB_ON = "absolute inset-x-4 top-0 h-[3px] -skew-x-[18deg] bg-accent shadow-[0_0_12px_rgb(245_165_36)]";

/** A top-bar link; a group opens a wide panel of its pages (icon, name, one line each) and a featured card. */
function TopLink({ group: g, path }: { group: NavGroup; path: string }) {
  const on = groupActive(path, g);
  const [open, setOpen] = useState(false);
  // The featured card loads its data the first time the panel opens, not on every page.
  const [seen, setSeen] = useState(false);
  const show = (v: boolean) => {
    setOpen(v);
    if (v) setSeen(true);
  };
  // Close the panel when the page changes.
  const [openedOn, setOpenedOn] = useState(path);
  if (openedOn !== path) {
    setOpenedOn(path);
    setOpen(false);
  }
  const box = useRef<HTMLDivElement>(null);
  const cls = `relative flex h-full min-h-11 items-center gap-1 px-3 font-display text-[15px] font-bold tracking-[0.1em] uppercase transition-colors lg:px-4 ${
    on ? "text-text" : "text-muted hover:text-text"
  }`;
  const bar = on && (
    <span className="absolute inset-x-3 bottom-0 h-[3px] -skew-x-[18deg] bg-accent shadow-[0_0_12px_rgb(245_165_36)]" aria-hidden />
  );
  if (!g.items) {
    return (
      <Link href={g.href} className={cls} aria-current={on ? "page" : undefined}>
        {g.label}
        {bar}
      </Link>
    );
  }
  const onBlur = (e: FocusEvent) => {
    if (!box.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
  };
  return (
    <div
      ref={box}
      className="relative h-full"
      onMouseEnter={() => show(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => show(true)}
      onBlur={onBlur}
      onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
    >
      <Link href={g.href} className={cls} aria-haspopup="true" aria-expanded={open}>
        {g.label}
        <svg viewBox="0 0 20 20" className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} fill="currentColor" aria-hidden>
          <path d="M5.5 7.5 10 12l4.5-4.5z" />
        </svg>
        {bar}
      </Link>
      <div className="mega absolute top-full left-1/2 w-[min(46rem,calc(100vw-2rem))] pt-2" data-open={open}>
        <div
          className="grid grid-cols-[1.4fr_1fr] gap-4 border border-line bg-panel/95 p-4 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.9)] backdrop-blur-xl"
          style={{ clipPath: "polygon(0 0, calc(100% - var(--cut)) 0, 100% var(--cut), 100% 100%, var(--cut) 100%, 0 calc(100% - var(--cut)))" }}
        >
          <div>
            {g.items.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`flex items-start gap-3 p-2.5 transition-colors hover:bg-accent/[0.07] ${active(path, l.href) ? "bg-accent/[0.07]" : ""}`}
              >
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center bg-panel-2 text-accent"
                  style={{ clipPath: "polygon(20% 0, 100% 0, 80% 100%, 0 100%)" }}
                >
                  <Icon d={l.icon} />
                </span>
                <span>
                  <span className={`block font-display text-lg leading-tight font-extrabold tracking-[0.04em] uppercase ${active(path, l.href) ? "text-accent" : ""}`}>
                    {l.label}
                  </span>
                  <span className="block text-[13px] text-muted">{l.blurb}</span>
                </span>
              </Link>
            ))}
          </div>
          {g.href === "/players" ? <TopFragger load={seen} /> : <TableCard />}
        </div>
      </div>
    </div>
  );
}

const FEATURE =
  "relative flex min-h-48 flex-col justify-end overflow-hidden bg-panel-2 bg-[radial-gradient(120%_80%_at_100%_0%,rgb(245_165_36/0.28),transparent_60%)] p-4 transition hover:brightness-110";
const FEATURE_CLIP = { clipPath: "polygon(0 0, 100% 0, 100% calc(100% - var(--cut)), calc(100% - var(--cut)) 100%, 0 100%)" };

/** The Players panel's featured card: this week's top fragger. */
function TopFragger({ load }: { load: boolean }) {
  const { data, error } = useApi<KillList>(load ? killsPath("week", null) : null);
  const top = data?.players[0] ?? null;
  return (
    <Link href="/kills" className={FEATURE} style={FEATURE_CLIP}>
      <LionMark className="absolute -top-5 -right-8 h-44 w-44 opacity-[0.12]" />
      <span className="chip chip-hot self-start">Top fragger this week</span>
      {top ? (
        <>
          <span className="mt-3 flex items-end gap-3">
            <PlayerAvatar name={top.player} colour={top.team?.primary_color} size="lg" />
            <span className="num text-6xl leading-[0.85]">
              {top.kills}
              <span className="ml-1 text-sm tracking-[0.12em] text-muted">KILLS</span>
            </span>
          </span>
          <span className="mt-2 truncate font-display text-2xl font-black uppercase">{top.player}</span>
          <span className="flex items-center gap-2 text-[13px] text-muted">
            {top.team && <TeamMark team={top.team} />}
            {top.team?.name ?? "No team"} · {top.matches} {top.matches === 1 ? "match" : "matches"}
          </span>
        </>
      ) : (
        <>
          <span className="mt-3 font-display text-2xl font-black uppercase">{data ? "No kills yet this week" : "Kill list"}</span>
          <span className="text-[13px] text-muted">{data ? "The first scrim of the week fills this in." : error ? "See who leads the kill list." : "Loading this week's leader…"}</span>
        </>
      )}
    </Link>
  );
}

/** The Teams panel's featured card: straight to the table. */
function TableCard() {
  return (
    <Link href="/standings" className={FEATURE} style={FEATURE_CLIP}>
      <LionMark className="absolute -top-5 -right-8 h-44 w-44 opacity-[0.12]" />
      <span className="chip chip-gold self-start">Standings</span>
      <span className="mt-3 font-display text-3xl leading-none font-black uppercase">Who&apos;s top of the table?</span>
      <span className="mt-1 text-[13px] text-muted">Points, Booyahs and kills for every team, updated after every upload.</span>
    </Link>
  );
}

/** A row in the phone menu: icon, name and what the page is for. */
function MenuRow({ link: l, on }: { link: { href: string; label: string; blurb: string; icon: string }; on: boolean }) {
  return (
    <Link href={l.href} className={`flex items-center gap-3 border-b border-line/60 py-3 last:border-0 ${on ? "text-accent" : ""}`}>
      <span className="flex h-10 w-10 shrink-0 items-center justify-center bg-panel-2 text-accent" style={{ clipPath: "polygon(20% 0, 100% 0, 80% 100%, 0 100%)" }}>
        <Icon d={l.icon} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-display text-xl leading-tight font-extrabold uppercase">{l.label}</span>
        <span className="block truncate text-xs text-muted">{l.blurb}</span>
      </span>
      <span className="text-muted">&rsaquo;</span>
    </Link>
  );
}
