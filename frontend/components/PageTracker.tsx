"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { type Act, describeChange, describeClick, hitFor, onApiWrite } from "@/lib/analytics";
import { api } from "@/lib/api";

// Counts each page opened, how long it stays open and what is done on it, for the staff
// analytics pages (see /privacy). No cookies; anything that fails is simply not counted.

const BASE = "/api/v1/analytics";

let lastPath: string | null = null; // so a re-render (or React's dev double run) never counts twice
let key: string | null = null; // the current page view, once the server has answered
let pending: Act[] = []; // actions before the key arrived
let activeMs = 0; // time the current page has been visible
let shownAt: number | null = null;

function send(url: string, body: object) {
  // keepalive: still delivered when the page is closing. No sign-in: the key is the proof.
  fetch(`${BASE}/${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "omit",
    keepalive: true,
  }).catch(() => {});
}

function seconds(): number {
  return Math.round((activeMs + (shownAt === null ? 0 : performance.now() - shownAt)) / 1000);
}

function reportTime() {
  if (key) send("time", { key, seconds: seconds() });
}

function track(act: Act | null) {
  if (!act) return;
  if (key) send("action", { key, ...act });
  else if (pending.length < 50) pending.push(act);
}

function labelOf(el: Element): string {
  return el.getAttribute("aria-label") || el.getAttribute("title") || (el as HTMLElement).innerText || el.textContent || "";
}

/** A form control's label: aria-label, a <label> around or for it, or its name. */
function controlLabel(el: HTMLInputElement | HTMLSelectElement): string {
  const own = el.getAttribute("aria-label") || el.labels?.[0]?.innerText || el.getAttribute("title") || el.name;
  return (own || "").split("\n")[0];
}

function onClick(e: MouseEvent) {
  const el = (e.target as Element | null)?.closest?.("[data-track], button, a, [role=tab], [role=button]");
  if (!el || el.closest("[data-no-track]")) return;
  const tag = el.tagName.toLowerCase();
  track(
    describeClick({
      tag,
      label: labelOf(el),
      href: tag === "a" ? el.getAttribute("href") : null,
      origin: window.location.origin,
      track: el.getAttribute("data-track"),
      trackDetail: el.getAttribute("data-track-detail"),
    }),
  );
}

function onChange(e: Event) {
  const el = e.target as HTMLInputElement | HTMLSelectElement | null;
  if (!el || !("tagName" in el) || el.closest("[data-no-track]")) return;
  const tag = el.tagName.toLowerCase();
  if (tag !== "select" && tag !== "input") return;
  const input = el as HTMLInputElement;
  track(
    describeChange({
      tag,
      type: tag === "input" ? input.type : undefined,
      label: controlLabel(el),
      value: tag === "select" ? (el as HTMLSelectElement).selectedOptions[0]?.text : input.type === "password" ? "" : input.value,
      checked: input.checked,
      files: input.files?.length,
    }),
  );
}

function onVisibility() {
  if (document.visibilityState === "hidden") {
    if (shownAt !== null) activeMs += performance.now() - shownAt;
    shownAt = null;
    reportTime();
  } else if (shownAt === null) {
    shownAt = performance.now();
  }
}

/** Counts pages, time on page and actions for the staff analytics page. */
export default function PageTracker() {
  const path = usePathname();

  useEffect(() => {
    document.addEventListener("click", onClick, true);
    document.addEventListener("change", onChange, true);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", reportTime);
    onApiWrite((method, apiPath, ok) => track({ name: "api", api: { method, path: apiPath, ok } }));
    return () => {
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("change", onChange, true);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", reportTime);
      onApiWrite(null);
    };
  }, []);

  useEffect(() => {
    if (!path || path === lastPath) return;
    const first = lastPath === null;
    reportTime(); // the page being left
    lastPath = path;
    key = null;
    pending = [];
    activeMs = 0;
    shownAt = document.visibilityState === "hidden" ? null : performance.now();
    api<{ key: string } | null>("/analytics/hit", { method: "POST", body: hitFor(path, window.location.search, document.referrer, first), retry: false })
      .then((answer) => {
        if (!answer?.key || lastPath !== path) return;
        key = answer.key;
        const queued = pending;
        pending = [];
        queued.forEach(track);
      })
      .catch(() => {});
  }, [path]);

  return null;
}
