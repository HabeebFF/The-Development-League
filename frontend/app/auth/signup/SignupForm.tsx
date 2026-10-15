"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/Auth";
import { api, ApiError } from "@/lib/api";

/** A fan account: no team, no staff access. Only shown while the league has sign-up open. */
export default function SignupForm() {
  const { site, publicSite } = useAuth();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  if (publicSite !== null && !site.signup) {
    return (
      <p className="mt-6 text-muted">
        Sign-up isn&apos;t open right now. Team players join with the invite link from their manager.{" "}
        <Link href="/auth/login" className="text-accent hover:underline">
          Sign in
        </Link>
      </p>
    );
  }

  async function submit(form: FormData) {
    setBusy(true);
    setErrors({});
    try {
      await api("/auth/signup", {
        method: "POST",
        body: { email: form.get("email"), password: form.get("password"), display_name: form.get("display_name") },
      });
      // A full load so the whole site knows who is signed in.
      window.location.assign(site.predictions ? "/predict" : "/");
    } catch (e) {
      if (e instanceof ApiError && e.data && typeof e.data === "object") {
        const out: Record<string, string> = {};
        for (const [k, v] of Object.entries(e.data as Record<string, unknown>)) out[k] = Array.isArray(v) ? String(v[0]) : String(v);
        setErrors(out);
      } else {
        setErrors({ detail: "Something went wrong. Try again." });
      }
      setBusy(false);
    }
  }

  const err = (k: string) => errors[k] && <span className="mt-1 block text-xs text-bad">{errors[k]}</span>;

  return (
    <form action={submit} className="mt-8 space-y-4">
      <label className="block text-sm">
        <span className="text-muted">Name on the leaderboard</span>
        <input name="display_name" required minLength={2} maxLength={30} autoComplete="nickname" className="input mt-1" />
        {err("display_name")}
      </label>
      <label className="block text-sm">
        <span className="text-muted">Email</span>
        <input name="email" type="email" autoComplete="email" required className="input mt-1" />
        {err("email")}
      </label>
      <label className="block text-sm">
        <span className="text-muted">Password</span>
        <input name="password" type="password" autoComplete="new-password" required minLength={8} className="input mt-1" />
        {err("password")}
      </label>
      {(errors.detail || errors.non_field_errors) && <p className="text-sm text-bad">{errors.detail || errors.non_field_errors}</p>}
      <button type="submit" disabled={busy} className="btn btn-primary w-full">
        {busy ? "Creating account..." : "Create account"}
      </button>
      <p className="text-sm text-muted">
        Already have one?{" "}
        <Link href="/auth/login" className="text-accent hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
