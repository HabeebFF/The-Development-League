"use client";

// The DC ranks board (rank steps, earned DC per player, team table, DC King), loaded once per page.

import { useEffect, useState } from "react";

import { api } from "./api";
import type { DcBoard } from "./dc";

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
