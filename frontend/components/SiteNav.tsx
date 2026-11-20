"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type FocusEvent } from "react";

import { killsPath, type KillList } from "@/lib/kills";
import { HOME, ME_ICON, SECTIONS, activeLink, isActive as active, meLinks, sectionFor, type NavLink, type Section } from "@/lib/nav";
import { useApi } from "@/lib/useApi";

import { TeamMark } from "./league/TeamBadge";
import LionMark from "./ui/LionMark";
import TdlLogo from "./ui/TdlLogo";
import PlayerAvatar from "./ui/PlayerAvatar";

import { useAuth } from "./Auth";

function Icon({ d, className = "h-5 w-5" }: { d: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d={d} />
    </svg>
  );
}

/**
 * The site's navigation, the same idea on every screen: three sections (League, Players,
 * Predict) plus "Me". Desktop shows them across the top; phones get a bottom bar of
 * Home · League · Players · Predict · Me. Every page in a section shows that section's tabs
 * under the header, so people can always see where they are and hop sideways.
 */
export default function SiteNav() {
  const path = usePathname();
  const { me, status, publicSite, site, signOut } = useAuth();
  const sections = SECTIONS.filter((s) => !s.flag || site[s.flag]);
  const signedIn = status === "in";
  // Visitors see the league pages too while the site is public.
  const shown = signedIn || publicSite === true;
  const mine = meLinks(signedIn ? me : null);
  const section = sectionFor(path);
  const meOn = !section && path !== "/" && mine.some((l) => active(path, l.href));
  const [sheet, setSheet] = useState(false);
  // Close the phone sheet whenever the page changes.
  const [openedOn, setOpenedOn] = useState(path);
  if (openedOn !== path) {
    setOpenedOn(path);
    setSheet(false);
  }
  useEffect(() => {
    if (!sheet) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSheet(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sheet]);
  const login = `/auth/login?next=${encodeURIComponent(path)}`;

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
            <TdlLogo />
          </Link>
          <div className={`hidden h-full flex-1 items-center ${shown ? "md:flex" : ""}`}>
            <div className="mx-auto flex h-full items-center">
              {sections.map((s) => (
                <TopLink key={s.key} section={s} path={path} player={!!me?.player} />
              ))}
            </div>
            {signedIn ? (
              <MeMenu links={mine} on={meOn} name={me?.display_name ?? "Me"} photo={me?.player?.photo} onSignOut={signOut} />
            ) : (
              <span className="ml-2 flex items-center gap-2">
                <Link href={login} className={`btn ${site.signup ? "btn-ghost" : "btn-primary"}`}>
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
              <Link href={site.signup ? "/auth/signup" : login} className="btn btn-primary px-3">
                {site.signup ? "Sign up" : "Sign in"}
              </Link>
            </span>
          )}
        </nav>
      </header>

      {shown && section && <SectionTabs section={section} path={path} player={!!me?.player} />}

      {sheet && shown && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setSheet(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="page-enter absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto border-t-2 border-accent/60 bg-panel px-4 pt-4 pb-[calc(var(--bottom-nav-h)+env(safe-area-inset-bottom)+1rem)]"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Me"
          >
            <div className="flex items-center justify-between">
              <p className="flex min-w-0 items-center gap-3">
                {signedIn ? (
                  <>
                    <PlayerAvatar src={me?.player?.photo} name={me?.display_name ?? "?"} size="md" />
                    <span className="min-w-0">
                      <span className="block truncate font-display text-2xl leading-none font-black uppercase">{me?.display_name}</span>
                      <span className="block text-xs text-muted">{me?.player ? "League player" : me?.staff_role ? "Staff" : "Fan"}</span>
                    </span>
                  </>
                ) : (
                  <span className="eyebrow">Join the league</span>
                )}
              </p>
              <button type="button" className="flex h-11 w-11 items-center justify-center text-2xl leading-none text-muted" onClick={() => setSheet(false)} aria-label="Close">
                &times;
              </button>
            </div>
            {signedIn ? (
              <div className="mt-3">
                {mine.map((l) => (
                  <MenuRow key={l.href} link={l} on={active(path, l.href)} />
                ))}
                <button type="button" onClick={signOut} className="btn btn-ghost mt-4 w-full">
                  Sign out
                </button>
              </div>
            ) : (
              <div className="mt-3">
                <p className="text-sm text-muted">
                  A free account gets you 1,000 DC to predict matches, a fan card, and, if you play in the league, your own player card and team pages.
                </p>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  {site.signup && (
                    <Link href="/auth/signup" className="btn btn-primary">
                      Sign up
                    </Link>
                  )}
                  <Link href={login} className={`btn ${site.signup ? "" : "btn-primary col-span-2"}`}>
                    Sign in
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <nav
        className={`fixed inset-x-0 bottom-0 z-50 ${shown ? "" : "hidden"} border-t border-white/[0.06] bg-bg/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden`}
        aria-label="Main"
      >
        <div className="grid h-[var(--bottom-nav-h)]" style={{ gridTemplateColumns: `repeat(${sections.length + 2}, minmax(0, 1fr))` }}>
          {[{ key: "home", label: HOME.label, icon: HOME.icon, href: "/" }, ...sections].map((s) => {
            const on = !sheet && (s.key === "home" ? path === "/" : section?.key === s.key);
            return (
              <Link key={s.key} href={s.href} className={`${TAB} ${on ? "text-accent" : "text-muted"}`} aria-current={on ? "page" : undefined}>
                {on && <span className={TAB_ON} />}
                <Icon d={s.icon} />
                {s.label}
              </Link>
            );
          })}
          <button type="button" className={`${TAB} ${sheet || meOn ? "text-accent" : "text-muted"}`} onClick={() => setSheet((o) => !o)} aria-expanded={sheet}>
            {(sheet || meOn) && <span className={TAB_ON} />}
            <Icon d={ME_ICON} />
            Me
          </button>
        </div>
      </nav>
    </>
  );
}

const TAB = "relative flex min-h-11 flex-col items-center justify-center gap-0.5 font-display text-[11px] font-bold tracking-[0.08em] uppercase transition-colors";
const TAB_ON = "absolute inset-x-4 top-0 h-[3px] -skew-x-[18deg] bg-accent shadow-[0_0_12px_rgb(245_165_36)]";

/** The row of tabs under the header on every page of a section: where you are, and the pages next to it. */
function SectionTabs({ section: s, path, player }: { section: Section; path: string; player: boolean }) {
  const current = activeLink(path, s);
  const links = s.links.filter((l) => !l.playersOnly || player);
  const row = useRef<HTMLElement>(null);
  // On narrow phones the row scrolls: bring the current tab into view.
  useEffect(() => {
    const el = row.current?.querySelector<HTMLElement>('[aria-current="page"]');
    if (el && row.current) row.current.scrollLeft = el.offsetLeft - (row.current.clientWidth - el.offsetWidth) / 2;
  }, [current]);
  return (
    <div className="border-b border-line bg-panel/60">
      <nav
        ref={row}
        className="mx-auto flex max-w-6xl items-center gap-1 overflow-x-auto px-4 [mask-image:linear-gradient(90deg,#000_85%,transparent)] [scrollbar-width:none] sm:[mask-image:none]"
        aria-label={s.label}
      >
        <span className="mr-2 hidden shrink-0 items-center gap-1.5 text-[11px] font-bold tracking-[0.2em] text-muted uppercase sm:flex">
          <Icon d={s.icon} className="h-4 w-4 text-accent" />
          {s.label}
        </span>
        {links.map((l) => {
          const on = l.href === current;
          return (
            <Link
              key={l.href}
              href={l.href}
              aria-current={on ? "page" : undefined}
              className={`relative flex min-h-11 shrink-0 items-center px-3 font-display text-sm font-bold tracking-[0.08em] whitespace-nowrap uppercase transition-colors ${
                on ? "text-accent" : "text-muted hover:text-text"
              }`}
            >
              {l.label}
              {on && <span className="absolute inset-x-2 bottom-0 h-[3px] -skew-x-[18deg] bg-accent" aria-hidden />}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

/** Desktop: your name on the right, opening your own pages and Sign out. */
function MeMenu({ links, on, name, photo, onSignOut }: { links: NavLink[]; on: boolean; name: string; photo?: string | null; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const onBlur = (e: FocusEvent) => {
    if (!box.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
  };
  return (
    <div
      ref={box}
      className="relative flex h-full items-center"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onBlur={onBlur}
      onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        className={`flex min-h-11 items-center gap-2 px-2 font-display text-sm font-bold tracking-[0.08em] uppercase ${on ? "text-accent" : "text-muted hover:text-text"}`}
      >
        <PlayerAvatar src={photo} name={name} size="sm" />
        <span className="max-w-32 truncate">{name}</span>
        <svg viewBox="0 0 20 20" className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} fill="currentColor" aria-hidden>
          <path d="M5.5 7.5 10 12l4.5-4.5z" />
        </svg>
      </button>
      <div className="mega absolute top-full right-0 w-72 pt-2" data-open={open} style={{ transform: "none" }}>
        <div className="border border-line bg-panel/95 p-2 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.9)] backdrop-blur-xl">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="flex items-center gap-3 p-2 transition-colors hover:bg-accent/[0.07]">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center bg-panel-2 text-accent">
                <Icon d={l.icon} />
              </span>
              <span className="min-w-0">
                <span className="block font-display text-base leading-tight font-extrabold uppercase">{l.label}</span>
                <span className="block truncate text-xs text-muted">{l.blurb}</span>
              </span>
            </Link>
          ))}
          <button type="button" onClick={onSignOut} className="btn btn-ghost mt-2 w-full">
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}

/** A top-bar link; a group opens a wide panel of its pages (icon, name, one line each) and a featured card. */
function TopLink({ section, path, player }: { section: Section; path: string; player: boolean }) {
  const g = { ...section, items: section.links.filter((l) => !l.playersOnly || player) };
  const on = sectionFor(path)?.key === section.key;
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
          {g.key === "players" ? <TopFragger load={seen} /> : g.key === "league" ? <TableCard /> : <PredictCard />}
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

/** The Predict panel's featured card. */
function PredictCard() {
  return (
    <Link href="/predict" className={FEATURE} style={FEATURE_CLIP}>
      <LionMark className="absolute -top-5 -right-8 h-44 w-44 opacity-[0.12]" />
      <span className="chip chip-gold self-start">Free DC</span>
      <span className="mt-3 font-display text-3xl leading-none font-black uppercase">Call tonight&apos;s winners</span>
      <span className="mt-1 text-[13px] text-muted">1,000 DC free when you sign up. Coins only, never real money.</span>
    </Link>
  );
}
