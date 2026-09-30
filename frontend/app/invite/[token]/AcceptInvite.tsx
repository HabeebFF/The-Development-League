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

  if (me || info.account_exists) {
    return (
      <>
        {heading}
        <p className="mt-6 text-sm">
          {me
            ? `You're signed in as ${me.email}. Sign in as ${info.email} to accept.`
            : `There's already an account for ${info.email}. Sign in, then come back to this link.`}
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
      <form action={accept} className="mt-8 space-y-4">
        <label className="block text-sm">
          <span className="text-muted">Your name (as your team knows you)</span>
          <input name="display_name" maxLength={80} autoComplete="nickname" className="input mt-1" />
        </label>
        <label className="block text-sm">
          <span className="text-muted">Choose a password</span>
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
