// The match MVP banner (``/matches/<id>/mvp``).

import type { TeamRef } from "./api";

export type MatchMvp = {
  player_id: number;
  name: string;
  photo: string | null;
  team: TeamRef;
  /** Match rating out of 10; null when the match has no ratings yet. */
  rating: number | null;
  kills: number;
  knocks: number | null;
  headshots: number | null;
  hs_pct: number | null;
  damage: number | null;
  weapons: { id: number; name: string; kills: number; knocks: number; uses: number; share: number }[];
  /** Abilities the replay file shows them using (Bolt Maker, Dinoculars, UAV). */
  skills: { kind: string; label: string; count: number }[];
};
