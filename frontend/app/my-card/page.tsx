"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import PlayerCard from "@/components/league/PlayerCard";
import { api, ApiError } from "@/lib/api";
import { BLANK_PHOTO } from "@/lib/cards";
import { photoProblem, PHOTO_TYPES, requestLine, type MyCard } from "@/lib/photos";

/** A signed-in player's own card: send a new photo for staff to approve. */
export default function MyCardPage() {
  const router = useRouter();
  const path = usePathname();
  const [data, setData] = useState<MyCard | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<MyCard>("/me/card")
      .then(setData)
      .catch((e) => {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          router.replace(`/auth/login?next=${encodeURIComponent(path)}`);
        } else setError(e.message);
      });
  }, [router, path]);
  useEffect(load, [load]);

  return (
    <section className="mx-auto max-w-4xl px-4 py-10">
      <p className="text-sm font-semibold tracking-[0.2em] text-accent uppercase">My card</p>
      <h1 className="mt-1 font-display text-5xl leading-none font-extrabold uppercase">
        {data?.player?.name ?? "Your player card"}
      </h1>
      {error && <p className="mt-4 text-bad">{error}</p>}
      {!data && !error && <p className="mt-4 text-muted">Loading...</p>}
      {data && !data.player && <NotLinked pending={data.pending_uid_claim ?? null} />}
      {data?.player && <Linked data={data} onChange={load} />}
    </section>
  );
}

function NotLinked({ pending }: { pending: string | null }) {
  return (
    <div className="card mt-6 p-5">
      {pending ? (
        <p>
          You asked to link game UID <b>{pending}</b> to this account. League staff will check it soon, then your card
          shows here.
        </p>
      ) : (
        <p>
          This account isn&apos;t linked to a league player yet. When you sign up, give your game UID under &ldquo;Do you
          play in the league?&rdquo;, or ask league staff to link it for you.
        </p>
      )}
      <Link href="/cards" className="btn mt-4 inline-block">
        See all player cards
      </Link>
    </div>
  );
}

function Linked({ data, onChange }: { data: MyCard; onChange: () => void }) {
  const player = data.player!;
  const req = data.request ?? null;
  const waiting = req?.status === "PENDING";
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function send(file: File) {
    const problem = photoProblem(file);
    if (problem) {
      setNote(problem);
      return;
    }
    setBusy(true);
    setNote(null);
    try {
      const body = new FormData();
      body.set("photo", file);
      await api("/me/card/photo", { method: "POST", body });
      setNote("Sent. League staff will check it before it goes on your card.");
      onChange();
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Couldn't send it. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function withdraw() {
    setBusy(true);
    setNote(null);
    try {
      await api("/me/card/photo", { method: "DELETE" });
      setNote("Taken back. Your card keeps its current photo.");
      onChange();
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Couldn't take it back. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const line = requestLine(req);
  return (
    <>
      <p className="mt-2 text-sm text-muted">
        UID {player.game_uid}
        {player.team ? ` · ${player.team.name}` : ""}
      </p>
      <div className="mt-8 grid items-start gap-8 sm:grid-cols-[auto_1fr]">
        <div className="flex justify-center">
          {data.card ? (
            <PlayerCard card={data.card} size={1} />
          ) : (
            <div className="card w-[15rem] p-5 text-center text-sm text-muted">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={player.photo || BLANK_PHOTO} alt="" className="mx-auto mb-3 h-40 w-40 bg-panel-2 object-cover object-top" />
              You don&apos;t have a card yet. Cards come out every Saturday at midnight for players who played that week.
            </div>
          )}
        </div>

        <div>
          <h2 className="section-title">Change your photo</h2>
          <p className="mt-2 text-sm text-muted">
            Send a clear photo of your face and shoulders. League staff check every photo before it goes on your
            card, and the background is cut out for you. Your name comes from the game, so change it in Free Fire
            and it updates here after your next match.
          </p>
          {player.card_hidden && (
            <p className="mt-2 text-sm text-muted">League staff have taken your card off the cards pages for now.</p>
          )}
          {line && (
            <p className={`mt-4 text-sm ${req?.status === "REJECTED" ? "text-bad" : ""}`} role="status">
              {line}
            </p>
          )}
          {waiting && req.image && (
            <div className="mt-3 flex items-center gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={req.image} alt="Your photo waiting for approval" className="h-24 w-24 bg-panel-2 object-cover object-top" />
              <span className="text-xs text-muted">Waiting for approval</span>
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <label className={`btn btn-primary cursor-pointer ${busy ? "opacity-60" : ""}`}>
              {waiting ? "Send a different photo" : "Send a new photo"}
              <input
                type="file"
                accept={PHOTO_TYPES.join(",")}
                className="sr-only"
                disabled={busy}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (file) send(file);
                }}
              />
            </label>
            {waiting && (
              <button type="button" className="btn" disabled={busy} onClick={withdraw}>
                Take it back
              </button>
            )}
          </div>
          <p className="mt-2 text-xs text-muted">JPEG, PNG or WebP, up to 5 MB.</p>
          {note && (
            <p className="mt-3 text-sm" role="status">
              {note}
            </p>
          )}
          {data.card && !player.card_hidden && (
            <Link href={`/cards/${player.id}`} className="mt-6 inline-block text-sm text-accent">
              See your card&apos;s full page
            </Link>
          )}
        </div>
      </div>
    </>
  );
}
