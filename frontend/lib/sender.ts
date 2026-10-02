// Sends match files to an upload batch a few at a time. One file never fails the upload:
// each is retried (re-read first, so a log the game is still writing goes up as it is
// now), waits out a dropped connection, and is only skipped after the last try.

import { api, csrfToken } from "./api";
import type { Picked } from "./folder";
import { retryDelay } from "./upload";

export const PARALLEL = 3;
const TRIES = 4;

export type Skipped = { name: string; reason: string };

export type SendState = {
  done: number; // files finished (sent or skipped)
  sent: number; // bytes, including the parts of files still going up
  active: string[]; // files going up now
  note: string | null; // retry or connection notice
  skipped: Skipped[];
};

class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function online(): Promise<void> {
  if (typeof navigator === "undefined" || navigator.onLine)
    return Promise.resolve();
  return new Promise((resolve) =>
    window.addEventListener("online", () => resolve(), { once: true }),
  );
}

/** POSTs one file to the batch (stored only; the batch is read once everything is in). */
function post(
  batchId: number,
  file: File,
  token: string,
  onBytes: (n: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("files", file, file.name);
    form.append("defer", "1");
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/v1/uploads/batches/${batchId}/files`);
    xhr.setRequestHeader("X-CSRFToken", token);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => onBytes(e.loaded);
    xhr.onload = () => {
      if (xhr.status < 300) return resolve();
      let detail = `The server said no (${xhr.status})`;
      try {
        const data = JSON.parse(xhr.responseText);
        detail = data.detail ?? (data.files ? String(data.files) : detail);
      } catch {}
      reject(new HttpError(xhr.status, detail));
    };
    xhr.onerror = () => reject(new Error("connection dropped"));
    xhr.ontimeout = () => reject(new Error("connection timed out"));
    xhr.send(form);
  });
}

/** Reads a file's bytes now, so later changes by the game can't break the request. */
async function snapshot(item: Picked): Promise<File> {
  const file = await item.read();
  return new File([await file.arrayBuffer()], item.name, {
    lastModified: file.lastModified,
  });
}

/** Which of these files the server already has; it adds them to the batch itself. */
export async function alreadyThere(
  batchId: number,
  items: Picked[],
): Promise<Set<string>> {
  const have = new Set<string>();
  for (let i = 0; i < items.length; i += 500) {
    const files = items
      .slice(i, i + 500)
      .map((f) => ({ name: f.name, size: f.size }));
    const res = await api<{ have: string[] }>(
      `/uploads/batches/${batchId}/known`,
      { method: "POST", body: { files } },
    );
    for (const name of res.have) have.add(name);
  }
  return have;
}

/**
 * Sends ``items`` to the batch, ``PARALLEL`` at a time. ``onChange`` gets the running state
 * after every change; ``onSent`` each file that arrived. Resolves with the files skipped.
 */
export async function sendAll(
  batchId: number,
  items: Picked[],
  onChange: (s: SendState) => void,
  onSent: (name: string) => void = () => {},
): Promise<Skipped[]> {
  const state: SendState = {
    done: 0,
    sent: 0,
    active: [],
    note: null,
    skipped: [],
  };
  const inFlight = new Map<string, number>(); // bytes sent so far of each file going up
  let finished = 0; // bytes of files that are done
  const emit = () => {
    state.sent = finished + [...inFlight.values()].reduce((a, b) => a + b, 0);
    state.active = [...inFlight.keys()];
    onChange({ ...state, skipped: [...state.skipped] });
  };

  async function one(item: Picked) {
    inFlight.set(item.name, 0);
    emit();
    let lastError = "";
    for (let attempt = 1; attempt <= TRIES; attempt++) {
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        state.note =
          "Waiting for the internet to come back. The upload carries on by itself.";
        emit();
        await online();
        state.note = null;
      }
      try {
        const file = await snapshot(item);
        await post(batchId, file, await csrfToken(), (n) => {
          inFlight.set(item.name, Math.min(n, item.size));
          emit();
        });
        inFlight.delete(item.name);
        finished += item.size;
        state.done += 1;
        if (state.note?.includes(item.name)) state.note = null;
        onSent(item.name);
        emit();
        return;
      } catch (e) {
        inFlight.set(item.name, 0);
        if (e instanceof HttpError && (e.status === 401 || e.status === 403)) {
          await api("/me").catch(() => {}); // the sign-in ran out during a long upload: refresh it
        } else if (
          e instanceof HttpError &&
          e.status >= 400 &&
          e.status < 500 &&
          e.status !== 408 &&
          e.status !== 429
        ) {
          lastError = e.message; // the server refused this file; trying again won't help
          break;
        }
        lastError =
          e instanceof DOMException && e.name === "NotReadableError"
            ? "the game changed it while it was being read"
            : e instanceof Error
              ? e.message
              : String(e);
        if (attempt < TRIES) {
          const wait = retryDelay(attempt);
          state.note = `Trying ${item.name} again in ${Math.round(wait / 1000)} s (${lastError}).`;
          emit();
          await sleep(wait);
        }
      }
    }
    inFlight.delete(item.name);
    finished += item.size;
    state.done += 1;
    state.skipped.push({
      name: item.name,
      reason: lastError || "it could not be sent",
    });
    state.note = null;
    emit();
  }

  const queue = [...items];
  await Promise.all(
    Array.from({ length: Math.min(PARALLEL, queue.length) }, async () => {
      for (let item = queue.shift(); item; item = queue.shift())
        await one(item);
    }),
  );
  return state.skipped;
}
