import Link from "next/link";

import { PLAYER_PAGES, SOCIALS, TEAM_PAGES } from "@/lib/nav";

import TdlLogo from "./ui/TdlLogo";

const SOCIAL_ICON: Record<(typeof SOCIALS)[number]["label"], string> = {
  Instagram:
    "M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5m5 5a5 5 0 1 0 0 10 5 5 0 0 0 0-10m0 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6m5.5-3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3",
  TikTok: "M14 2h3a5 5 0 0 0 5 5v3a8 8 0 0 1-5-1.7V15a7 7 0 1 1-7-7v3a4 4 0 1 0 4 4z",
  YouTube:
    "M22 8.2a3 3 0 0 0-2.1-2.1C18 5.6 12 5.6 12 5.6s-6 0-7.9.5A3 3 0 0 0 2 8.2 31 31 0 0 0 1.6 12 31 31 0 0 0 2 15.8a3 3 0 0 0 2.1 2.1c1.9.5 7.9.5 7.9.5s6 0 7.9-.5a3 3 0 0 0 2.1-2.1c.4-1.2.4-3.8.4-3.8s0-2.6-.4-3.8M10 15V9l5.2 3z",
  X: "M17.8 3h3.3l-7.2 8.2L22.4 21h-6.6l-5.2-6.8L4.6 21H1.3l7.7-8.8L.9 3h6.8l4.7 6.2zm-1.2 16h1.8L6.6 4.9H4.6z",
  Discord:
    "M19.6 5.3A17 17 0 0 0 15.4 4l-.5 1a15 15 0 0 0-5.8 0L8.6 4a17 17 0 0 0-4.2 1.3C1.7 9.3 1 13.2 1.3 17a17 17 0 0 0 5.1 2.6l1.1-1.8-1.7-.8.4-.3a12 12 0 0 0 11.6 0l.4.3-1.7.8 1.1 1.8a17 17 0 0 0 5.1-2.6c.4-4.4-.7-8.3-3.1-11.7M8.9 14.7c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2m6.2 0c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2",
  WhatsApp:
    "M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2m5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.6-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.9s.7-2 1-2.3.6-.3.8-.3h.6c.2 0 .4 0 .6.5l.9 2.1c.1.2.1.4 0 .5l-.4.6-.4.4c-.1.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.4 2.4 1.5.3.2.5.1.6 0l.9-1c.2-.3.4-.2.6-.1l2 1c.3.1.5.2.5.3.1.1.1.6-.1 1.2",
};

const LEAGUE = [
  { href: "/standings", label: "Standings" },
  { href: "/results", label: "Results" },
  ...TEAM_PAGES,
];

/** The foot of every page: lion mark, the site's links, the league's socials and the copyright line. */
export default function SiteFooter() {
  return (
    <footer className="relative mt-12 border-t border-line bg-gradient-to-b from-panel to-bg">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-4 pt-9 pb-11 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="col-span-2 md:col-span-1">
          <Link href="/" className="inline-flex min-h-11 items-center gap-2.5" aria-label="The Development League, home">
            <TdlLogo size="lg" tagline />
          </Link>
          <p className="mt-2 max-w-xs text-sm text-muted">The home of The Development League. Free Fire esports: every scrim, every stat.</p>
          {SOCIALS.length > 0 && (
            <ul className="mt-4 flex gap-2">
              {SOCIALS.map((s) => (
                <li key={s.label}>
                  <a
                    href={s.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={s.label}
                    className="flex h-11 w-11 items-center justify-center bg-panel-2 text-text transition-colors hover:bg-accent hover:text-accent-ink"
                    style={{ clipPath: "polygon(20% 0, 100% 0, 80% 100%, 0 100%)" }}
                  >
                    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="currentColor" aria-hidden>
                      <path d={SOCIAL_ICON[s.label]} />
                    </svg>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
        <FooterLinks title="League" links={LEAGUE} />
        <FooterLinks title="Players" links={[...PLAYER_PAGES, { href: "/staff", label: "Staff" }, { href: "/privacy", label: "Privacy" }]} />
        <p className="col-span-2 border-t border-line pt-4 text-xs text-muted md:col-span-3">&copy; The Development League</p>
      </div>
    </footer>
  );
}

function FooterLinks({ title, links }: { title: string; links: { href: string; label: string }[] }) {
  return (
    <nav aria-label={title}>
      <h2 className="mb-2 font-display text-sm font-extrabold tracking-[0.18em] text-muted uppercase">{title}</h2>
      <ul>
        {links.map((l) => (
          <li key={l.href}>
            <Link href={l.href} className="inline-flex min-h-9 items-center text-sm text-text/85 transition-colors hover:text-accent-hot">
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
