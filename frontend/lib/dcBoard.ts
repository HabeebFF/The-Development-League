"use client";

// The DC ranks board (rank steps, earned DC per player, team table, DC King), loaded once per page.

import { useEffect, useState } from "react";

import { api } from "./api";
import { PALETTES } from "./cardDesigns";
import type { DcBoard, LivePerks } from "./dc";

let cache: Promise<DcBoard | null> | null = null;

function load(): Promise<DcBoard | null> {
  cache ??= api<DcBoard>("/dc/ranks").catch(() => null);
  return cache;
}

export function useDcBoard(): DcBoard | null {
  const [board, setBoard] = useState<DcBoard | null>(null);
  useEffect(() => {
    let live = true;
    load().then((b) => live && setBoard(b));
    return () => {
      live = false;
    };
  }, []);
  return board;
}

let live: Promise<LivePerks | null> | null = null;

/** Shoutouts, name colours, team banners and pinned moments on now (loaded once per page). */
export function useLivePerks(): LivePerks | null {
  const [data, setData] = useState<LivePerks | null>(null);
  useEffect(() => {
    let on = true;
    live ??= api<LivePerks>("/dc/perks/live").catch(() => null);
    live.then((d) => on && setData(d));
    return () => {
      on = false;
    };
  }, []);
  return data;
}

/** Text colour for a player who bought a name colour (a Mythic name aura wins over it). */
export function nameColour(
  live: LivePerks | null,
  playerId: number | null | undefined,
): React.CSSProperties | undefined {
  const key =
    playerId == null ? undefined : live?.name_colours[String(playerId)];
  const colour = key ? PALETTES[key]?.[3] : undefined;
  return colour ? { color: colour } : undefined;
}
