"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type Invite, type Member, type Paged, type Role } from "@/lib/api";

const ROLE: Record<Role, string> = { MANAGER: "Manager", PLAYER: "Player" };

function rows<T>(data: Paged<T> | T[]): T[] {
  return Array.isArray(data) ? data : data.results;
}

/**
 * A team's members and invites. Managers invite players; league staff can also invite
 * managers. Every open invite shows its link, so it can be sent on WhatsApp as well.
 */
export default function TeamPeople({
  slug,
  canManage,
  canInviteManagers,
}: {
  slug: string;
  canManage: boolean;
  canInviteManagers: boolean;
}) {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);

  const [version, setVersion] = useState(0); // bumped to reload after a change

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const people = rows(await api<Paged<Member> | Member[]>(`/teams/${slug}/members?page_size=100`));
        const sent = canManage
          ? rows(await api<Paged<Invite> | Invite[]>(`/teams/${slug}/invites?page_size=100`))
          : [];
        if (live) {
          setMembers(people);
          setInvites(sent);
        }
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : "Couldn't load the team.");
      }
    })();
    return () => {
      live = false;
    };
  }, [slug, canManage, version]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function invite(form: FormData) {
    await run(async () => {
      const created = await api<Invite>(`/teams/${slug}/invites`, {
        method: "POST",
        body: { email: form.get("email"), role: form.get("role") ?? "PLAYER" },
      });
      if (created.link) await copy(created);
    });
  }

  async function copy(inv: Invite) {
    if (!inv.link) return;
    try {
      await navigator.clipboard.writeText(inv.link);
      setCopied(inv.id);
    } catch {
      setCopied(null);
    }
  }

  const open = invites.filter((i) => i.is_open);
  const active = (members ?? []).filter((m) => m.is_active);

  return (
    <div className="space-y-8">
      {error && <p className="text-sm text-bad">{error}</p>}

      <div>
        <h2 className="font-display text-2xl uppercase">Members</h2>
        {!members && !error && <p className="mt-2 text-muted">Loading...</p>}
        {members && active.length === 0 && <p className="mt-2 text-sm text-muted">Nobody has joined yet.</p>}
        <ul className="mt-3 divide-y divide-line rounded-lg border border-line bg-panel">
          {active.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-2 px-4 py-3 text-sm">
              <span className="flex-1">
                <span className="block font-medium">{m.display_name || m.email}</span>
                <span className="text-xs text-muted">
                  {m.email}
                  {m.game_uid ? ` · UID ${m.game_uid}` : ""}
                </span>
              </span>
              <span className="text-xs text-muted uppercase">{ROLE[m.role]}</span>
              {canManage && (m.role === "PLAYER" || canInviteManagers) && (
                <button
                  className="btn px-2 py-1 text-xs"
                  disabled={busy}
                  onClick={() => {
                    if (confirm(`Remove ${m.display_name || m.email} from the team?`)) {
                      run(() => api(`/teams/${slug}/members/${m.id}`, { method: "DELETE" }));
                    }
                  }}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>

      {canManage && (
        <div>
          <h2 className="font-display text-2xl uppercase">Invite someone</h2>
          <p className="mt-1 text-sm text-muted">
            They get an email with a link. The link is also copied for you, so you can send it on
            WhatsApp or Discord. It works for 7 days.
          </p>
          <form action={invite} className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input name="email" type="email" required placeholder="player@email.com" className="input flex-1" />
            {canInviteManagers && (
              <select name="role" defaultValue="MANAGER" className="input sm:w-40">
                <option value="MANAGER">Manager</option>
                <option value="PLAYER">Player</option>
              </select>
            )}
            <button type="submit" disabled={busy} className="btn btn-primary">
              {busy ? "Sending..." : "Send invite"}
            </button>
          </form>

          {open.length > 0 && (
            <>
              <h3 className="mt-6 text-sm font-semibold text-muted uppercase">Waiting to join</h3>
              <ul className="mt-2 divide-y divide-line rounded-lg border border-line bg-panel">
                {open.map((inv) => (
                  <li key={inv.id} className="flex flex-wrap items-center gap-2 px-4 py-3 text-sm">
                    <span className="flex-1">
                      <span className="block">{inv.email}</span>
                      <span className="text-xs text-muted">
                        {ROLE[inv.role]} · expires {new Date(inv.expires_at).toLocaleDateString()}
                      </span>
                    </span>
                    <button className="btn px-2 py-1 text-xs" onClick={() => copy(inv)}>
                      {copied === inv.id ? "Link copied" : "Copy link"}
                    </button>
                    <button
                      className="btn px-2 py-1 text-xs"
                      disabled={busy}
                      onClick={() => run(() => api(`/teams/${slug}/invites/${inv.id}`, { method: "DELETE" }))}
                    >
                      Withdraw
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
