"use client";

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
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function signInAndAccept(form: FormData) {
    if (!info) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/login", { method: "POST", body: { email: info.email, password: form.get("password") } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
      setBusy(false);
      return;
    }
    await accept();
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

  // Signed in as someone else (often the manager testing the link on their own phone).
  if (me) {
    return (
      <>
        {heading}
        <p className="mt-6 text-sm">
          You&apos;re signed in as {me.email}, but this invite is for {info.email}. Sign out to
          continue as {info.email}.
        </p>
        {error && <p className="mt-4 text-sm text-bad">{error}</p>}
        <button className="btn btn-primary mt-4 w-full" disabled={busy} onClick={signOut}>
          {busy ? "Signing out..." : "Sign out"}
        </button>
      </>
    );
  }

  // The invited email already has an account: sign in right here, then join.
  if (info.account_exists) {
    return (
      <>
        {heading}
        <p className="mt-6 text-sm">
          {info.email} already has an account on this site. Enter its password to join.
        </p>
        <p className="mt-2 text-xs text-muted">
          Never made an account? Then this link was already used by someone else. Ask your
          manager for a new invite with your own email.
        </p>
        <form action={signInAndAccept} className="mt-4 space-y-4">
          <label className="block text-sm">
            <span className="text-muted">Password</span>
            <input name="password" type="password" autoComplete="current-password" required className="input mt-1" />
          </label>
          {error && <p className="text-sm text-bad">{error}</p>}
          <button type="submit" disabled={busy} className="btn btn-primary w-full">
            {busy ? "Joining..." : `Sign in and join ${info.team.name}`}
          </button>
        </form>
      </>
    );
  }

  // First time here: the invite creates the account.
  return (
    <>
      {heading}
      <div className="mt-6 rounded-lg border border-line bg-panel p-3 text-sm">
        <p className="font-medium">New here? No account needed yet.</p>
        <p className="mt-1 text-muted">
          This creates your account. Pick a new password now. Next time, sign in with{" "}
          {info.email} and this password.
        </p>
      </div>
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
          <span className="text-muted">Create a password (at least 8 characters)</span>
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
