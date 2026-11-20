// New teams signing themselves up (NEW-TEAMS.md): the form's shapes and small helpers.

export type RosterRow = { uid: string; name: string; role: string; igl: boolean };

export type CheckedRow = RosterRow & {
  /** Can't be used: the manager must fix it. */
  error: string | null;
  /** Allowed, but staff will look (e.g. the UID last played for another team). */
  flag: string | null;
  /** What the logs know about this UID. */
  known: { name: string; last: { team: { name: string; slug: string }; date: string | null } | null } | null;
};

export type NewTeam = {
  id: number;
  name: string;
  tag: string;
  slug: string;
  logo: string | null;
  country: string;
  lobby_name: string;
  contact: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  review_note: string;
  reviewed_at: string | null;
  created_at: string;
  players: CheckedRow[];
  manager?: { name: string; email: string } | null;
  reviewed_by?: string | null;
};

export type MyNewTeam = {
  team: NewTeam | null;
  can_create: boolean;
  on_team: { name: string; slug: string } | null;
  min_players: number;
  max_players: number;
  roles: Record<string, string>;
};

export type TeamCheck = {
  errors: Partial<Record<"name" | "tag" | "lobby_name" | "country" | "contact", string>>;
  players: CheckedRow[];
  roster: string | null;
};

export type TeamForm = {
  name: string;
  tag: string;
  country: string;
  lobby_name: string;
  contact: string;
  roster: RosterRow[];
};

export type Squad = {
  season: string | null;
  max: number;
  players: { id: number; name: string; game_uid: string; role: string; joined_on: string | null }[];
  from_logs: { id: number; name: string; game_uid: string }[];
};

/** Sub-Saharan Africa first (TDL's region), by name. */
export const COUNTRIES: [string, string][] = [
  ["AO", "Angola"],
  ["BJ", "Benin"],
  ["BW", "Botswana"],
  ["BF", "Burkina Faso"],
  ["BI", "Burundi"],
  ["CM", "Cameroon"],
  ["CV", "Cape Verde"],
  ["CF", "Central African Republic"],
  ["TD", "Chad"],
  ["KM", "Comoros"],
  ["CG", "Congo"],
  ["CD", "DR Congo"],
  ["CI", "Côte d'Ivoire"],
  ["DJ", "Djibouti"],
  ["GQ", "Equatorial Guinea"],
  ["ER", "Eritrea"],
  ["SZ", "Eswatini"],
  ["ET", "Ethiopia"],
  ["GA", "Gabon"],
  ["GM", "Gambia"],
  ["GH", "Ghana"],
  ["GN", "Guinea"],
  ["GW", "Guinea-Bissau"],
  ["KE", "Kenya"],
  ["LS", "Lesotho"],
  ["LR", "Liberia"],
  ["MG", "Madagascar"],
  ["MW", "Malawi"],
  ["ML", "Mali"],
  ["MR", "Mauritania"],
  ["MU", "Mauritius"],
  ["MZ", "Mozambique"],
  ["NA", "Namibia"],
  ["NE", "Niger"],
  ["NG", "Nigeria"],
  ["RW", "Rwanda"],
  ["ST", "São Tomé and Príncipe"],
  ["SN", "Senegal"],
  ["SC", "Seychelles"],
  ["SL", "Sierra Leone"],
  ["SO", "Somalia"],
  ["ZA", "South Africa"],
  ["SS", "South Sudan"],
  ["SD", "Sudan"],
  ["TZ", "Tanzania"],
  ["TG", "Togo"],
  ["UG", "Uganda"],
  ["ZM", "Zambia"],
  ["ZW", "Zimbabwe"],
];

export const countryName = (code: string) => COUNTRIES.find(([c]) => c === code)?.[1] ?? code;

export const blankRow = (): RosterRow => ({ uid: "", name: "", role: "", igl: false });

export function blankForm(min = 4): TeamForm {
  return { name: "", tag: "", country: "NG", lobby_name: "", contact: "", roster: Array.from({ length: min }, blankRow) };
}

/** The form from a team that's waiting or was rejected, to edit and send again. */
export function formFrom(team: NewTeam): TeamForm {
  return {
    name: team.name,
    tag: team.tag,
    country: team.country,
    lobby_name: team.lobby_name,
    contact: team.contact,
    roster: team.players.map(({ uid, name, role, igl }) => ({ uid, name, role, igl })),
  };
}

/** Only one IGL: ticking one unticks the rest. */
export function setIgl(rows: RosterRow[], index: number, on: boolean): RosterRow[] {
  return rows.map((r, i) => ({ ...r, igl: i === index ? on : on ? false : r.igl }));
}

/** UIDs are digits: keep what was typed or pasted, minus spaces and other characters. */
export const cleanUid = (value: string) => value.replace(/\D/g, "").slice(0, 20);

/** Rows the manager has started to fill in (blank rows are ignored when sending). */
export const filledRows = (rows: RosterRow[]) => rows.filter((r) => r.uid.trim() || r.name.trim());

export function formData(form: TeamForm, logo: File | null): FormData {
  const data = new FormData();
  data.set("name", form.name.trim());
  data.set("tag", form.tag.trim().toUpperCase());
  data.set("country", form.country);
  data.set("lobby_name", form.lobby_name.trim());
  data.set("contact", form.contact.trim());
  data.set("roster", JSON.stringify(filledRows(form.roster)));
  if (logo) data.set("logo", logo);
  return data;
}

/** What the manager sees as the team's state. */
export function statusText(team: Pick<NewTeam, "status" | "review_note">): { title: string; body: string } {
  if (team.status === "REJECTED") {
    return {
      title: "Not approved yet",
      body: team.review_note ? `TDL staff said: "${team.review_note}". Fix it below and send it again.` : "Fix your team below and send it again.",
    };
  }
  if (team.status === "PENDING") {
    return {
      title: "Waiting for TDL staff",
      body: "TDL staff check every new team, usually by DM on the contact you gave. Once approved you can sign up for scrims, and your players are recognised in every match.",
    };
  }
  return { title: "Approved", body: "Your team is in TDL." };
}
