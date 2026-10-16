"use client";

import { useState } from "react";

import { useAuth } from "@/components/Auth";
import { api, ApiError, type Me } from "@/lib/api";
import { homeFor } from "@/lib/home";

import GoogleButton from "./GoogleButton";
import PlaysFields from "./PlaysFields";

type Answer = (Me & { code?: undefined }) | { code: "needs_profile"; email: string; name: string };

/** "Continue with Google" with an "or" line. A new Google account then gives a name (and
 * the game UID if they play) before the account is made. Hidden until the site has a
 * Google client ID. */
export default function GoogleSignIn({
  next,
  text = "continue_with",
  first = false,
}: {
  next?: string | null;
  text?: "signin_with" | "signup_with" | "continue_with";
  /** Shown above the email form: the "or" line goes under the button. */
  first?: boolean;
}) {
  const { site } = useAuth();
  const [pending, setPending] = useState<{ credential: string; email: string; name: string } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  if (!site.google_client_id) return null;
  const or = (
    <p className="flex items-center gap-3 text-xs text-muted uppercase before:h-px before:flex-1 before:bg-line after:h-px after:flex-1 after:bg-line">or</p>
  );

  function done(me: Me | null) {
    // A full load so the whole site knows who is signed in.
    window.location.assign(next ?? (me ? homeFor(me) : site.predictions ? "/predict" : "/"));
  }

  function fail(e: unknown) {
    if (e instanceof ApiError && e.data && typeof e.data === "object") {
      const out: Record<string, string> = {};
      for (const [k, v] of Object.entries(e.data as Record<string, unknown>)) out[k] = Array.isArray(v) ? String(v[0]) : String(v);
      setErrors(out);
    } else {
      setErrors({ detail: "Something went wrong. Try again." });
    }
    setBusy(false);
  }

  async function withGoogle(credential: string) {
    setBusy(true);
    setErrors({});
    try {
      const answer = await api<Answer>("/auth/google", { method: "POST", body: { credential } });
      if (answer.code === "needs_profile") {
        setPending({ credential, email: answer.email, name: answer.name });
        setBusy(false);
      } else {
        done(answer);
      }
    } catch (e) {
      fail(e);
    }
  }

  async function finish(form: FormData) {
    if (!pending) return;
    setBusy(true);
    setErrors({});
    try {
      await api("/auth/google", {
        method: "POST",
        body: { credential: pending.credential, display_name: form.get("display_name"), game_uid: form.get("game_uid") ?? "" },
      });
      done(null);
    } catch (e) {
      fail(e);
    }
  }

  if (pending) {
    return (
      <form action={finish} className="mt-8 space-y-4 border border-line bg-panel-2 p-4">
        <p className="text-sm">
          New account for <span className="font-semibold">{pending.email}</span> with Google.
        </p>
        <label className="block text-sm">
          <span className="text-muted">Name on the leaderboard</span>
          <input name="display_name" required minLength={2} maxLength={30} defaultValue={pending.name} autoComplete="nickname" className="input mt-1" />
          {errors.display_name && <span className="mt-1 block text-xs text-bad">{errors.display_name}</span>}
        </label>
        <PlaysFields error={errors.game_uid} />
        {(errors.detail || errors.email) && <p className="text-sm text-bad">{errors.detail || errors.email}</p>}
        <button type="submit" disabled={busy} className="btn btn-primary w-full">
          {busy ? "Creating account..." : "Create account"}
        </button>
        <button type="button" className="w-full text-xs text-muted hover:text-accent" onClick={() => setPending(null)}>
          Cancel
        </button>
      </form>
    );
  }

  return (
    <div className="mt-6 space-y-3">
      {!first && or}
      <GoogleButton clientId={site.google_client_id} text={text} onCredential={withGoogle} />
      {busy && <p className="text-center text-xs text-muted">Signing in with Google...</p>}
      {errors.detail && <p className="text-sm text-bad">{errors.detail}</p>}
      {first && or}
    </div>
  );
}
