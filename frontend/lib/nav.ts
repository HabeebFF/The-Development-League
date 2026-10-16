// The site's sections, in plain words: used by the top bar, the phone menu, the home page and /players.

export type NavLink = {
  href: string;
  label: string;
  /** One short line saying what the page is for. */
  blurb: string;
  icon: string;
  /** Only shown when the server has this switch on. */
  flag?: "predictions";
};

export type NavGroup = NavLink & {
  /** Pages inside the group; the group's own href is its first stop. */
  items?: NavLink[];
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
  players: "M12 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8m-7 17c0-3.9 3.1-7 7-7s7 3.1 7 7z",
  teams: "M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z",
  pp: "M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5zm-1 6h2v3h3v2h-3v3h-2v-3H8v-2h3z",
  predict: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 3a7 7 0 1 1 0 14 7 7 0 0 1 0-14m-1 2v5.4l4.3 2.6 1-1.7-3.3-2V7z",
  menu: "M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z",
};

export const HOME: NavLink = { href: "/", label: "Home", blurb: "", icon: ICON.home };

export const PLAYER_PAGES: NavLink[] = [
  { href: "/kills", label: "Kill list", blurb: "Top fraggers for each session, week and month", icon: ICON.kills },
  { href: "/ratings", label: "Player ratings", blurb: "Every player marked out of 10, like football", icon: ICON.ratings },
  { href: "/cards", label: "Player cards", blurb: "FUT-style cards, new ones every Saturday", icon: ICON.cards },
  { href: "/awards", label: "Awards", blurb: "Best player, rusher, sniper and grenader", icon: ICON.awards },
];

export const TEAM_PAGES: NavLink[] = [
  { href: "/teams", label: "All teams", blurb: "Every team, its players and its rotations", icon: ICON.teams },
  { href: "/protection-points", label: "Protection Points", blurb: "Points teams win or lose from scrim tasks", icon: ICON.pp },
];

export const GROUPS: NavGroup[] = [
  { href: "/standings", label: "Standings", blurb: "Who is top of the table", icon: ICON.standings },
  { href: "/results", label: "Results", blurb: "Every match day, map by map, with replays", icon: ICON.results },
  { href: "/players", label: "Players", blurb: "Kills, ratings, cards and awards", icon: ICON.players, items: PLAYER_PAGES },
  { href: "/teams", label: "Teams", blurb: "Teams and Protection Points", icon: ICON.teams, items: TEAM_PAGES },
  { href: "/predict", label: "Predict", blurb: "Bet free coins on matches, no real money", icon: ICON.predict, flag: "predictions" },
];

export const MENU_ICON = ICON.menu;

/** True when ``path`` is ``href`` or a page under it. */
export function isActive(path: string, href: string): boolean {
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
}

/** True when ``path`` is the group's page or any page inside it. */
export function groupActive(path: string, g: NavGroup): boolean {
  return isActive(path, g.href) || !!g.items?.some((i) => isActive(path, i.href));
}
