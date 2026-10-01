"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "./api";

type Loaded<T> = { path: string; data: T | null; error: string | null };

/** GET a path from the API. A null path waits (for something it depends on). */
export function useApi<T>(path: string | null): { data: T | null; error: string | null; loading: boolean } {
  const [state, setState] = useState<Loaded<T> | null>(null);
  useEffect(() => {
    if (!path) return;
    let live = true;
    api<T>(path)
      .then((data) => live && setState({ path, data, error: null }))
      .catch((e) => {
        if (!live) return;
        const error = e instanceof ApiError && e.status === 404 ? "Not found." : e instanceof Error ? e.message : "Couldn't load this.";
        setState({ path, data: null, error });
      });
    return () => {
      live = false;
    };
  }, [path]);
  // A result for an older path is stale while the new one loads.
  const current = state && state.path === path ? state : null;
  return { data: current?.data ?? null, error: current?.error ?? null, loading: !!path && !current };
}
