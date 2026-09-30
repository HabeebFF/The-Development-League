"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, ApiError, type Me } from "@/lib/api";
import { homeFor } from "@/lib/home";

export default function LoginForm({ next }: { next: string | null }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(form: FormData) {
    setBusy(true);
    setError(null);
    try {
      const me = await api<Me>("/auth/login", {
        method: "POST",
        body: { email: form.get("email"), password: form.get("password") },
      });
      router.replace(next ?? homeFor(me));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  return (
    <form action={submit} className="mt-8 space-y-4">
      <label className="block text-sm">
        <span className="text-muted">Email</span>
        <input name="email" type="email" autoComplete="email" required className="input mt-1" />
      </label>
      <label className="block text-sm">
        <span className="text-muted">Password</span>
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="input mt-1"
        />
      </label>
      {error && <p className="text-sm text-bad">{error}</p>}
      <button type="submit" disabled={busy} className="btn btn-primary w-full">
        {busy ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}
