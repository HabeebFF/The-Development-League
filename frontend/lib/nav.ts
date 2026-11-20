// The site's sections, in plain words: used by the top bar, the phone bar, the footer, the home page and /players.

export type NavLink = {
  href: string;
  label: string;
  /** One short line saying what the page is for. */
  blurb: string;
  icon: string;
  /** Only shown when the server has this switch on. */
  flag?: "predictions";
};

const ICON = {
  home: "M3 11 12 4l9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  standings: "M4 20V10h4v10zm6 0V4h4v16zm6 0v-7h4v7z",
  results: "M7 4h10v3a5 5 0 0 1-10 0zM5 5H3v2a4 4 0 0 0 4 4M19 5h2v2a4 4 0 0 1-4 4M10 14h4v3h3v3H7v-3h3z",
  kills:
    "M12 2a1 1 0 0 1 1 1v1.06A8 8 0 0 1 19.94 11H21a1 1 0 1 1 0 2h-1.06A8 8 0 0 1 13 19.94V21a1 1 0 1 1-2 0v-1.06A8 8 0 0 1 4.06 13H3a1 1 0 1 1 0-2h1.06A8 8 0 0 1 11 4.06V3a1 1 0 0 1 1-1m0 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12m0 3a3 3 0 1 1 0 6 3 3 0 0 1 0-6",
  ratings: "M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 14.3l-4.8 2.6.9-5.4-3.9-3.8 5.4-.8zM4 20h16v2H4z",
  awards: "M7 2h10v3h3v3a5 5 0 0 1-4.6 5A5 5 0 0 1 13 15.9V18h3v4H8v-4h3v-2.1A5 5 0 0 1 8.6 13 5 5 0 0 1 4 8V5h3zm0 5H6v1a3 3 0 0 0 1.4 2.5A7 7 0 0 1 7 8zm10 0v1a7 7 0 0 1-.4 2.5A3 3 0 0 0 18 8V7z",
  cards: "M7 2h10l3 3v12l-8 5-8-5V5zm5 5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5m-4 9h8c0-2-1.8-3-4-3s-4 1-4 3",
  map: "M9 3 3 5.5v15.5l6-2.5 6 2.5 6-2.5V3l-6 2.5zm0 2.2 6 2.5v11.6l-6-2.5z",
  players: "M12 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8m-7 17c0-3.9 3.1-7 7-7s7 3.1 7 7z",
  teams: "M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z",
  pp: "M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5zm-1 6h2v3h3v2h-3v3h-2v-3H8v-2h3z",
  predict: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 3a7 7 0 1 1 0 14 7 7 0 0 1 0-14m-1 2v5.4l4.3 2.6 1-1.7-3.3-2V7z",
  shop: "M4 7h16l-1.2 12.2A2 2 0 0 1 16.8 21H7.2a2 2 0 0 1-2-1.8zm4 0V6a4 4 0 0 1 8 0v1h-2V6a2 2 0 0 0-4 0v1z",
  menu: "M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z",
  league: "M5 3h14v2h-1v4a6 6 0 0 1-5 5.9V18h3v3H8v-3h3v-3.1A6 6 0 0 1 6 9V5H5zm3 2v4a4 4 0 0 0 8 0V5z",
  me: "M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20m0 4a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7m0 9c-2.6 0-4.8 1.3-5.9 3.2A8 8 0 0 0 12 20a8 8 0 0 0 5.9-1.8C16.8 16.3 14.6 15 12 15",
  wallet: "M3 7a3 3 0 0 1 3-3h12v3h1a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a3 3 0 0 1-3-3zm3-1a1 1 0 0 0 0 2h10V6zm11 6a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3",
  list: "M4 5h2v2H4zm4 0h12v2H8zM4 11h2v2H4zm4 0h12v2H8zm-4 6h2v2H4zm4 0h12v2H8z",
  staff: "M12 1 3 5v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V5zm0 5a3 3 0 1 1 0 6 3 3 0 0 1 0-6m-5 11c.6-2 2.6-3.5 5-3.5s4.4 1.5 5 3.5a8.7 8.7 0 0 1-5 3.6A8.7 8.7 0 0 1 7 17",
};

export const HOME: NavLink = { href: "/", label: "Home", blurb: "", icon: ICON.home };

export const ME_ICON = ICON.me;

// -- The simpler layout: three sections and "Me" ------------------------------------------
// Every public page sits in exactly one section. The phone's bottom bar is
// Home · League · Players · Predict · Me, the desktop bar is the same four, and each
// section shows its own row of tabs under the header so people always see where they are.

export type SectionKey = "league" | "players" | "predict";

export type Section = {
  key: SectionKey;
  label: string;
  blurb: string;
  icon: string;
  /** Where the bottom-bar tab goes: the section's first page. */
  href: string;
  links: (NavLink & { playersOnly?: boolean })[];
  flag?: "predictions";
};

export const SECTIONS: Section[] = [
  {
    key: "league",
    label: "League",
    blurb: "The table, every result, teams and cups",
    icon: ICON.league,
    href: "/standings",
    links: [
      { href: "/standings", label: "Standings", blurb: "Who is top of the table", icon: ICON.standings },
      { href: "/results", label: "Results", blurb: "Every match day, map by map, with replays", icon: ICON.results },
      { href: "/teams", label: "Teams", blurb: "Every team, its players and its rotations", icon: ICON.teams },
      { href: "/tournaments", label: "Cups", blurb: "Tournaments and finals, with prizes", icon: ICON.awards },
      { href: "/protection-points", label: "Protection Points", blurb: "Points teams win or lose from scrim tasks", icon: ICON.pp },
    ],
  },
  {
    key: "players",
    label: "Players",
    blurb: "Kills, ratings, cards and awards",
    icon: ICON.players,
    href: "/players",
    links: [
      { href: "/kills", label: "Kills", blurb: "Top fraggers for each session, week and month", icon: ICON.kills },
      { href: "/ratings", label: "Ratings", blurb: "Every player marked out of 10, like football", icon: ICON.ratings },
      { href: "/cards", label: "Cards", blurb: "FUT-style cards, new ones every Saturday", icon: ICON.cards },
      { href: "/awards", label: "Awards", blurb: "Best player, rusher, sniper and grenader", icon: ICON.awards },
      { href: "/maps", label: "Maps", blurb: "Top players, teams and weapons on each map", icon: ICON.map },
    ],
  },
  {
    key: "predict",
    label: "Predict",
    blurb: "Free DC coins: predict, climb, spend",
    icon: ICON.predict,
    href: "/predict",
    flag: "predictions",
    links: [
      { href: "/predict", label: "Matches", blurb: "Pick winners with free DC, no real money", icon: ICON.predict },
      { href: "/predict/mine", label: "My picks", blurb: "Your open and settled predictions", icon: ICON.list },
      { href: "/predict/leaderboard", label: "Leaderboard", blurb: "Who has the most DC", icon: ICON.ratings },
      { href: "/predict/wallet", label: "My DC", blurb: "Your balance and every coin in and out", icon: ICON.wallet },
      { href: "/shop", label: "Shop", blurb: "Spend DC on card designs", icon: ICON.shop },
      { href: "/player-shop", label: "Player shop", blurb: "Looks only league players can buy", icon: ICON.cards, playersOnly: true },
    ],
  },
];

/** Pages that live in a section without a tab of their own (a match, a team page, a card). */
const SECTION_EXTRA: [string, SectionKey][] = [
  ["/matches", "league"],
  ["/players", "players"],
];

/** The section a page belongs to, or null (home, account, team and staff pages). */
export function sectionFor(path: string): Section | null {
  for (const s of SECTIONS) if (s.links.some((l) => isActive(path, l.href))) return s;
  const extra = SECTION_EXTRA.find(([href]) => isActive(path, href));
  return extra ? (SECTIONS.find((s) => s.key === extra[1]) ?? null) : null;
}

/** The section tab that matches ``path`` best (the longest href wins, so /predict/mine beats /predict). */
export function activeLink(path: string, s: Section): string | null {
  const hits = s.links.filter((l) => isActive(path, l.href) || (l.href === "/predict" && path.startsWith("/predict/markets")));
  hits.sort((a, b) => b.href.length - a.href.length);
  return hits[0]?.href ?? null;
}

/** Pages under "Me", which depend on who is signed in. */
export function meLinks(me: { staff_role: string | null; memberships: unknown[]; player: unknown } | null): NavLink[] {
  if (!me) return [];
  const out: NavLink[] = [{ href: "/account", label: "My account", blurb: "Name, game UID, team requests", icon: ICON.me }];
  if (me.memberships.length > 0) out.push({ href: "/team", label: "My team", blurb: "Scrims, coach, replays and members", icon: ICON.teams });
  else if (!me.staff_role) out.push({ href: "/create-team", label: "Start a team", blurb: "Create a team or ask to join one", icon: ICON.teams });
  if (me.player) out.push({ href: "/player-shop", label: "Player shop", blurb: "Looks only league players can buy", icon: ICON.cards });
  if (me.staff_role) out.push({ href: "/staff", label: "Staff", blurb: "Uploads, teams, predictions and settings", icon: ICON.staff });
  return out;
}

/** True when ``path`` is ``href`` or a page under it. */
export function isActive(path: string, href: string): boolean {
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
}

/** The league's social accounts, shown in the footer. Add one here and its icon appears. */
export const SOCIALS: { label: "Instagram" | "TikTok" | "YouTube" | "X" | "Discord" | "WhatsApp"; href: string }[] = [];
