"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, ApiError, type InviteInfo, type Me } from "@/lib/api";

/** Someone opened an invite link: join the team, creating an account if they need one. */
export default function AcceptInvite({ token }: { token: string }) {
  const router = useRouter();
  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const path = `/invite/${encodeURIComponent(token)}`;

  useEffect(() => {
    api<InviteInfo>(`/invites/${encodeURIComponent(token)}`)
      .then(setInfo)
      .catch((e) => setError(e instanceof ApiError && e.status === 404 ? "This invite link isn't valid." : e.message));
    api<Me>("/me")
      .then(setMe)
      .catch(() => setMe(null));
  }, [token]);

  async function accept(form?: FormData) {
    setBusy(true);
    setError(null);
    try {
      await api(`/invites/${encodeURIComponent(token)}`, {
        method: "POST",
        body: form ? { password: form.get("password"), display_name: form.get("display_name") } : {},
      });
      router.replace("/team");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError(null);
    try {
      await api("/auth/logout", { method: "POST" });
      setMe(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't sign out. Try again.");
    }
    setBusy(false);
  }

  if (!info) {
    return error ? <p className="text-bad">{error}</p> : <p className="text-muted">Loading...</p>;
  }

  const role = info.role === "MANAGER" ? "manager" : "player";
  const heading = (
    <>
      <p className="text-sm font-semibold tracking-[0.2em] text-accent uppercase">Team invite</p>
      <h1 className="mt-1 font-display text-3xl uppercase">Join {info.team.name}</h1>
      <p className="mt-2 text-sm text-muted">
        You&apos;re invited as a {role}. The invite is for {info.email}.
      </p>
    </>
  );

  if (!info.is_open) {
    return (
      <>
        {heading}
        <p className="mt-6 text-bad">This invite has expired or was already used. Ask for a new one.</p>
      </>
    );
  }

  // Already signed in with the invited email: one click.
  if (me && me.email.toLowerCase() === info.email.toLowerCase()) {
    return (
      <>
        {heading}
        {error && <p className="mt-6 text-sm text-bad">{error}</p>}
        <button className="btn btn-primary mt-6 w-full" disabled={busy} onClick={() => accept()}>
          {busy ? "Joining..." : `Join ${info.team.name}`}
        </button>
      </>
    );
  }

  // Someone else is signed in on this device (often the manager who made the link).
  if (me) {
    return (
      <>
        {heading}
        <p className="mt-6 text-sm">
          This device is signed in as {me.email}. Sign out, then this page lets {info.email} join
          {info.account_exists ? " by signing in" : " by creating an account"}.
        </p>
        {error && <p className="mt-4 text-sm text-bad">{error}</p>}
        <button className="btn btn-primary mt-4 w-full" disabled={busy} onClick={signOut}>
          {busy ? "Signing out..." : "Sign out"}
        </button>
      </>
    );
  }

  if (info.account_exists) {
    return (
      <>
        {heading}
        <p className="mt-6 text-sm">
          There&apos;s already an account for {info.email}. Sign in with it and you&apos;ll come back here
          to join.
        </p>
        <Link href={`/auth/login?next=${encodeURIComponent(path)}`} className="btn btn-primary mt-4 block text-center">
          Sign in
        </Link>
      </>
    );
  }

  return (
    <>
      {heading}
      <p className="mt-6 text-sm">
        You don&apos;t have an account yet, and you don&apos;t need one: create it here in one step.
      </p>
      <form action={accept} className="mt-6 space-y-4">
        <label className="block text-sm">
          <span className="text-muted">Email</span>
          <input value={info.email} readOnly className="input mt-1 opacity-70" />
        </label>
        <label className="block text-sm">
          <span className="text-muted">Your name (as your team knows you)</span>
          <input name="display_name" maxLength={80} autoComplete="nickname" className="input mt-1" />
        </label>
        <label className="block text-sm">
          <span className="text-muted">Create a password (8+ characters, you&apos;ll use it to sign in next time)</span>
          <input name="password" type="password" autoComplete="new-password" required minLength={8} className="input mt-1" />
        </label>
        {error && <p className="text-sm text-bad">{error}</p>}
        <button type="submit" disabled={busy} className="btn btn-primary w-full">
          {busy ? "Joining..." : "Create account and join"}
        </button>
      </form>
    </>
  );
}
