// Talks to the Django API through this site's own /api path (see next.config.ts), so
// the sign-in cookies stay first-party. Writes carry the CSRF token Django expects.

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
  ) {
    super(describe(data) ?? `Request failed (${status})`);
  }
}

const BASE = "/api/v1";

function cookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

export async function csrfToken(): Promise<string> {
  let token = cookie("csrftoken");
  if (!token) {
    await fetch(`${BASE}/auth/csrf`, { credentials: "same-origin" });
    token = cookie("csrftoken");
  }
  return token ?? "";
}

type Options = { method?: string; body?: unknown; retry?: boolean };

export async function api<T = unknown>(path: string, options: Options = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (method !== "GET") headers["X-CSRFToken"] = await csrfToken();

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body,
    credentials: "same-origin",
  });
  if (response.status === 401 && options.retry !== false && !path.startsWith("/auth/")) {
    // The access cookie is short-lived: refresh once, then try again.
    const refreshed = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "X-CSRFToken": await csrfToken() },
      credentials: "same-origin",
    });
    if (refreshed.ok) return api<T>(path, { ...options, retry: false });
  }
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

function describe(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  const first = Object.entries(record)[0];
  if (!first) return null;
  const [field, value] = first;
  const text = Array.isArray(value) ? value.join(" ") : String(value);
  return field === "non_field_errors" ? text : `${field}: ${text}`;
}

// -- API shapes ------------------------------------------------------------------------------

export type Paged<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type Me = {
  id: number;
  email: string;
  display_name: string;
  is_super_admin: boolean;
  staff_role: "SUPER_ADMIN" | "STAFF" | "ANALYST" | null;
  features: string[];
  memberships: Membership[];
};

export type Role = "MANAGER" | "PLAYER";

export type Membership = {
  id: number;
  team: { id: number; name: string; tag: string; slug: string };
  role: Role;
  is_active: boolean;
  created_at: string;
};

export type Member = {
  id: number;
  email: string;
  display_name: string;
  game_uid: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
};

export type Invite = {
  id: number;
  email: string;
  role: Role;
  link: string | null;
  invited_by: string | null;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  is_open: boolean;
  created_at: string;
};

export type InviteInfo = {
  team: { id: number; name: string; tag: string; slug: string };
  email: string;
  role: Role;
  expires_at: string;
  is_open: boolean;
  account_exists: boolean;
};

export type MatchSummary = {
  id: number;
  number: number;
  map: string | null;
  scheduled_at: string | null;
  started_at: string | null;
  played: boolean;
  booyah: { name: string } | null;
  vod_url: string | null;
};

export type MatchDay = {
  id: number;
  number: number;
  title: string;
  date: string | null;
  stage: string;
  group: string | null;
  matches: MatchSummary[];
};

export type TeamRef = {
  id: number;
  name: string;
  tag: string;
  slug: string;
  logo: string | null;
  primary_color: string;
};

export type MapArea = { id: number; name: string; polygon: [number, number][]; centre_x: number; centre_z: number };

export type GameMap = {
  id: number;
  name: string;
  slug: string;
  game_map_id: number | null;
  image: string | null;
  image_width: number | null;
  image_height: number | null;
  transform: import("./coordinates").Transform | null;
  is_calibrated: boolean;
  areas: MapArea[];
  calibration_error?: number | null;
  calibrated_at?: string | null;
  has_default_image?: boolean;
};

export type Zone = {
  stage_index: number;
  state: "STABLE" | "PRE_SHRINK" | "SHRINK";
  game_time_s: number | null;
  outer_x: number;
  outer_z: number;
  outer_radius: number | null;
  inner_x: number;
  inner_z: number;
  inner_radius: number;
};

export type TeamRotation = {
  team: TeamRef;
  placement: number | null;
  status: "AUTO" | "DRAFT" | "CONFIRMED";
  plotted_by: string | null;
  confirmed_at: string | null;
  updated_at: string;
  points: import("./rotation").RotationPoint[];
  /** The team's real route from the replay: pieces of [x, z] in world decimetres. */
  path?: number[][][];
};

export type AdminMatch = {
  id: number;
  label: string;
  match_day: number;
  number: number;
  map: string | null;
  scheduled_at: string | null;
  status: string;
  game_match_id: string | null;
  started_at: string | null;
  duration_s: number | null;
  has_results: boolean;
  rotations: { AUTO: number; DRAFT: number; CONFIRMED: number };
};
