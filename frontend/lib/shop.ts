// The card shop: card designs bought with DC (play coins with no money value) and equipped.

import type { TeamRef } from "./api";
import type { CardDesign, ShopDesign } from "./cardDesigns";

export type ShopList = { designs: ShopDesign[]; equipped: number | null; low_balance_warning: number };

export type FanStats = {
  balance: number;
  shop_spent: number;
  /** Balance plus DC spent in the shop: what the leaderboard ranks by. */
  net: number;
  won: number;
  lost: number;
  accuracy: number | null;
};

export type FanCardData = {
  name: string;
  favourite_team: TeamRef | null;
  design: CardDesign | null;
  stats: FanStats;
};

export type Me = FanCardData & {
  /** Set when this account is a league player: their weekly card wears the design too. */
  player_id: number | null;
  owned: { id: string; design: CardDesign; price_paid: number; gift: boolean; bought_at: string }[];
};

export type BuyResult = { owned: string; design: CardDesign; price_paid: number; balance: number; equipped: boolean };

// -- Player shop (league players only, paid with DC) ---------------------------------------

export type ItemKind = "FRAME" | "TITLE" | "NUMBER" | "GLOW";

export type PlayerItem = ShopDesign & {
  kind: ItemKind;
  kind_label: string;
  /** Milestone frames: earned by playing, never bought. */
  unlock: { stat: string; target: number; label: string; progress: number } | null;
};

export type PlayerShop = {
  signed_in: boolean;
  staff: boolean;
  /** The league player this account is linked to; null for fans and visitors. */
  player: { id: number; name: string; country: string } | null;
  can_buy: boolean;
  balance: number | null;
  items: PlayerItem[];
  number: number | null;
  flag: string | null;
  owns_number: boolean;
  progress: { kills: number; booyahs: number; totw: number } | null;
  low_balance_warning: number;
};
