"use client";

// Name auras: players wearing a Mythic Player shop design get a glowing name across the site.

import { useEffect, useState } from "react";

import { api } from "./api";
import { PALETTES } from "./cardDesigns";

let cache: Promise<Record<string, string>> | null = null;

function load(): Promise<Record<string, string>> {
  cache ??= api<{ auras: Record<string, string> }>("/shop/auras")
    .then((r) => r.auras ?? {})
    .catch(() => ({}));
  return cache;
}

/** ``{player_id: palette}`` for glowing names (loaded once per page visit). */
export function useAuras(): Record<string, string> {
  const [auras, setAuras] = useState<Record<string, string>>({});
  useEffect(() => {
    let live = true;
    load().then((a) => live && setAuras(a));
    return () => {
      live = false;
    };
  }, []);
  return auras;
}

/** Class and style that make a player's name glow, or nothing. */
export function aura(auras: Record<string, string>, playerId: number | null | undefined) {
  const palette = playerId == null ? undefined : auras[String(playerId)];
  const glow = palette ? PALETTES[palette]?.[4] : undefined;
  if (!glow) return { className: "", style: undefined };
  return { className: "fx-aura", style: { ["--aura" as string]: glow } };
}
