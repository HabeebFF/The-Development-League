"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import PlayerCard from "@/components/league/PlayerCard";
import { api, ApiError } from "@/lib/api";
import { BLANK_PHOTO } from "@/lib/cards";
import {
  photoProblem,
  PHOTO_TYPES,
  requestLine,
  type MyCard,
} from "@/lib/photos";
import { useApi } from "@/lib/useApi";

/** On My account: a linked player picks a new photo for their own FUT card. It waits for
 * league staff to approve it, then goes on the card with the background cut out. */
export default function CardPhoto() {
  // Bumped after a send or take-back so the card and request load again.
  const [version, setVersion] = useState(0);
  const { data, error } = useApi<MyCard>(
    `/me/card${version ? `?v=${version}` : ""}`,
  );
  const [file, setFile] = useState<File | null>(null);
  const preview = useMemo(
    () => (file ? URL.createObjectURL(file) : null),
    [file],
  );
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  // Free the local preview of the picked picture when it changes.
  useEffect(
    () => () => void (preview && URL.revokeObjectURL(preview)),
    [preview],
  );

  if (error) return null;
  if (!data?.player) return null;
  const player = data.player;
  const req = data.request ?? null;
  const waiting = req?.status === "PENDING";
  const line = requestLine(req);

  function pick(f: File) {
    const problem = photoProblem(f);
    setNote(problem);
    setFile(problem ? null : f);
  }

  async function send() {
    if (!file) return;
    setBusy(true);
    setNote(null);
    try {
      const body = new FormData();
      body.set("photo", file);
      await api("/me/card/photo", { method: "POST", body });
      setFile(null);
      setNote("Sent. League staff will check it before it goes on your card.");
      setVersion((v) => v + 1);
    } catch (e) {
      setNote(
        e instanceof ApiError ? e.message : "Couldn't send it. Try again.",
      );
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
      setVersion((v) => v + 1);
    } catch (e) {
      setNote(
        e instanceof ApiError ? e.message : "Couldn't take it back. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card p-4" id="card-photo">
      <p className="font-display text-xl uppercase">Card photo</p>
      <div className="mt-3 grid items-start gap-5 sm:grid-cols-[auto_1fr]">
        <div className="flex justify-center">
          {data.card ? (
            <PlayerCard card={data.card} size={0.7} />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={player.photo || BLANK_PHOTO}
              alt="Your current card photo"
              className="h-36 w-36 bg-panel-2 object-cover object-top"
            />
          )}
        </div>
        <div className="text-sm">
          <p className="text-muted">
            Send a clear photo of your face and shoulders. League staff check
            every photo before it goes on your card, and the background is cut
            out for you. Your card name still comes from the game.
          </p>
          {!data.card && (
            <p className="mt-2 text-muted">
              You don&apos;t have a card yet. Cards come out every Saturday for
              players who played that week.
            </p>
          )}
          {player.card_hidden && (
            <p className="mt-2 text-muted">
              League staff have taken your card off the cards pages for now.
            </p>
          )}
          {line && (
            <p
              className={`mt-3 ${req?.status === "REJECTED" ? "text-bad" : ""}`}
              role="status"
            >
              {line}
            </p>
          )}
          {waiting && req.image && !preview && (
            <div className="mt-3 flex items-center gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={req.image}
                alt="Your photo waiting for approval"
                className="h-20 w-20 bg-panel-2 object-cover object-top"
              />
              <span className="text-xs text-muted">Waiting for approval</span>
            </div>
          )}
          {preview && (
            <div className="mt-3 flex items-center gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview}
                alt="The photo you picked"
                className="h-20 w-20 bg-panel-2 object-cover object-top"
              />
              <span className="text-xs text-muted">Not sent yet</span>
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {preview ? (
              <>
                <button
                  type="button"
                  className="btn btn-primary px-4 py-1.5 text-xs"
                  disabled={busy}
                  onClick={send}
                >
                  {busy ? "Sending..." : "Send for approval"}
                </button>
                <button
                  type="button"
                  className="btn px-4 py-1.5 text-xs"
                  disabled={busy}
                  onClick={() => setFile(null)}
                >
                  Cancel
                </button>
              </>
            ) : (
              <label
                className={`btn btn-primary cursor-pointer px-4 py-1.5 text-xs ${busy ? "opacity-60" : ""}`}
              >
                {waiting
                  ? "Pick a different photo"
                  : player.photo
                    ? "Change my card photo"
                    : "Add my card photo"}
                <input
                  type="file"
                  accept={PHOTO_TYPES.join(",")}
                  className="sr-only"
                  disabled={busy}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    e.target.value = "";
                    if (f) pick(f);
                  }}
                />
              </label>
            )}
            {waiting && !preview && (
              <button
                type="button"
                className="btn px-4 py-1.5 text-xs"
                disabled={busy}
                onClick={withdraw}
              >
                Take it back
              </button>
            )}
          </div>
          <p className="mt-2 text-xs text-muted">
            JPEG, PNG or WebP, up to 5 MB.
          </p>
          {note && (
            <p className="mt-2" role="status">
              {note}
            </p>
          )}
          {data.card && !player.card_hidden && (
            <Link
              href={`/cards/${player.id}`}
              className="mt-3 inline-block text-xs text-accent"
            >
              See your card&apos;s full page
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
