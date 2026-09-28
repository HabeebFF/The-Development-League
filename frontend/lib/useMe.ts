"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type Me } from "./api";

type State = { me: Me | null; loading: boolean; signedOut: boolean };

export function useMe(): State {
  const [state, setState] = useState<State>({ me: null, loading: true, signedOut: false });
  useEffect(() => {
    let live = true;
    api<Me>("/me")
      .then((me) => live && setState({ me, loading: false, signedOut: false }))
      .catch((e) => {
        if (!live) return;
        const signedOut = e instanceof ApiError && (e.status === 401 || e.status === 403);
        setState({ me: null, loading: false, signedOut });
      });
    return () => {
      live = false;
    };
  }, []);
  return state;
}
