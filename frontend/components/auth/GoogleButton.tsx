"use client";

import { useEffect, useRef, useState } from "react";

type Gis = {
  accounts: {
    id: {
      initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string }) => void;
      renderButton: (el: HTMLElement, o: Record<string, string | number>) => void;
    };
  };
};

let loading: Promise<Gis> | null = null;

/** Google's own sign-in script, loaded once and only on the pages that show the button. */
function loadGis(): Promise<Gis> {
  loading ??= new Promise<Gis>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => {
      const g = (window as unknown as { google?: Gis }).google;
      if (g) resolve(g);
      else reject(new Error("no google"));
    };
    s.onerror = () => {
      loading = null;
      reject(new Error("blocked"));
    };
    document.head.appendChild(s);
  });
  return loading;
}

/** Google's "Continue with Google" button. It hands back Google's signed answer (an ID token),
 * which only the server checks. */
export default function GoogleButton({
  clientId,
  text,
  onCredential,
}: {
  clientId: string;
  text: "signin_with" | "signup_with" | "continue_with";
  onCredential: (credential: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    callback.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    let gone = false;
    loadGis()
      .then((g) => {
        if (gone || !box.current) return;
        g.accounts.id.initialize({ client_id: clientId, callback: (r) => callback.current(r.credential), ux_mode: "popup" });
        g.accounts.id.renderButton(box.current, {
          theme: "filled_black",
          size: "large",
          shape: "rectangular",
          text,
          width: Math.min(400, box.current.offsetWidth || 320),
        });
      })
      .catch(() => !gone && setFailed(true));
    return () => {
      gone = true;
    };
  }, [clientId, text]);

  if (failed) return <p className="text-xs text-muted">Google sign-in couldn&apos;t load here. Check your connection or use email instead.</p>;
  return <div ref={box} className="flex min-h-11 justify-center" />;
}
