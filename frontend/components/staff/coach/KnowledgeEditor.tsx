"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type GameMap } from "@/lib/api";
import {
  dataText,
  KINDS,
  matchesReview,
  parseData,
  sourceLine,
  type KnowledgeEntry,
  type KnowledgeKind,
  type KnowledgeStatus,
  type ReviewFilter,
} from "@/lib/coach";

type Draft = {
  id: number | null;
  kind: KnowledgeKind;
  title: string;
  body: string;
  data: string;
  map: string;
  area: string;
  patch: string;
  conflicts: string;
  status: KnowledgeStatus;
  entry: KnowledgeEntry | null;
};

const REVIEW: { key: ReviewFilter; label: string }[] = [
  { key: "DRAFT", label: "Drafts to review" },
  { key: "WEAK", label: "Weak sources" },
  { key: "WRITE", label: "Needs writing" },
  { key: "APPROVED", label: "Approved" },
  { key: "REJECTED", label: "Rejected" },
  { key: "ALL", label: "All" },
];

const STATUS_BADGE: Record<KnowledgeStatus, string> = {
  DRAFT: "border-accent-2/40 text-accent-2",
  APPROVED: "border-ok/40 text-ok",
  REJECTED: "border-bad/40 text-bad",
};

const BLANK: Draft = {
  id: null,
  kind: "UTILITY",
  title: "",
  body: "",
  data: "",
  map: "",
  area: "",
  patch: "",
  conflicts: "",
  status: "APPROVED",
  entry: null,
};

function draftOf(e: KnowledgeEntry): Draft {
  return {
    id: e.id,
    kind: e.kind,
    title: e.title,
    body: e.body,
    data: dataText(e.data),
    map: e.map ?? "",
    area: e.area ? String(e.area) : "",
    patch: e.patch,
    conflicts: e.conflicts,
    status: e.status,
    entry: e,
  };
}

function message(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/**
 * The coach's general Free Fire knowledge. Researched entries arrive as drafts with their
 * sources; staff approve, edit or reject them, and the coach only uses approved ones.
 */
export default function KnowledgeEditor({ maps }: { maps: GameMap[] }) {
  const [entries, setEntries] = useState<KnowledgeEntry[] | null>(null);
  const [kind, setKind] = useState<KnowledgeKind | "ALL">("ALL");
  const [review, setReview] = useState<ReviewFilter | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api<KnowledgeEntry[]>("/coach/knowledge")
      .then((list) => {
        setEntries(list);
        // Open on the drafts while there are any.
        setReview((r) => r ?? (list.some((e) => e.status === "DRAFT") ? "DRAFT" : "ALL"));
      })
      .catch((e) => setError(message(e)));
  }, [version]);

  const filter = review ?? "ALL";
  const ofKind = (entries ?? []).filter((e) => kind === "ALL" || e.kind === kind);
  const shown = ofKind.filter((e) => matchesReview(e, filter));
  const count = (f: ReviewFilter) => ofKind.filter((e) => matchesReview(e, f)).length;
  const areas = maps.find((m) => m.slug === draft?.map)?.areas ?? [];
  const mapName = (slug: string | null) => maps.find((m) => m.slug === slug)?.name;

  async function save(status?: KnowledgeStatus) {
    if (!draft) return;
    const data = parseData(draft.data);
    if (data === null) {
      setError('Numbers must be written like {"duration_s": 30}, or left empty.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = {
        kind: draft.kind,
        title: draft.title.trim(),
        body: draft.body.trim(),
        data,
        map: draft.map || null,
        area: draft.area ? Number(draft.area) : null,
        patch: draft.patch.trim(),
        conflicts: draft.conflicts.trim(),
        status: status ?? draft.status,
      };
      if (draft.id) await api(`/coach/knowledge/${draft.id}`, { method: "PUT", body });
      else await api("/coach/knowledge", { method: "POST", body });
      setDraft(null);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!draft?.id || !confirm(`Delete "${draft.title}"?`)) return;
    setBusy(true);
    try {
      await api(`/coach/knowledge/${draft.id}`, { method: "DELETE" });
      setDraft(null);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1" role="tablist" aria-label="Review">
        {REVIEW.map((r) => (
          <button
            key={r.key}
            role="tab"
            aria-selected={filter === r.key}
            className={`rounded border px-2 py-1 text-xs ${filter === r.key ? "border-accent text-white" : "border-line text-muted hover:text-white"}`}
            onClick={() => setReview(r.key)}
          >
            {r.label} <span className="text-muted">{entries ? count(r.key) : ""}</span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select className="input max-w-xs" value={kind} onChange={(e) => setKind(e.target.value as KnowledgeKind | "ALL")} aria-label="Show">
          <option value="ALL">Everything</option>
          {KINDS.map((k) => (
            <option key={k.key} value={k.key}>
              {k.label}
            </option>
          ))}
        </select>
        <button className="btn btn-primary" onClick={() => setDraft({ ...BLANK, kind: kind === "ALL" ? "UTILITY" : kind })}>
          New entry
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-bad">{error}</p>}

      {draft && (
        <div className="card mt-4 space-y-3 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block text-muted">Kind</span>
              <select className="input" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as KnowledgeKind })}>
                {KINDS.map((k) => (
                  <option key={k.key} value={k.key}>
                    {k.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted">Title</span>
              <input
                className="input"
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                placeholder="Gloo Wall, Clock Tower drop..."
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted">Map (optional)</span>
              <select className="input" value={draft.map} onChange={(e) => setDraft({ ...draft, map: e.target.value, area: "" })}>
                <option value="">Any map</option>
                {maps.map((m) => (
                  <option key={m.slug} value={m.slug}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted">Named area (optional)</span>
              <select className="input" value={draft.area} disabled={!draft.map} onChange={(e) => setDraft({ ...draft, area: e.target.value })}>
                <option value="">{draft.map ? (areas.length ? "None" : "No areas drawn on this map yet") : "Pick a map first"}</option>
                {areas.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="block text-sm">
            <span className="mb-1 block text-muted">What the coach should know</span>
            <textarea className="input min-h-32" value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-muted">Numbers (optional), e.g. {'{"duration_s": 30}'}</span>
            <textarea
              className="input min-h-16 font-mono text-xs"
              value={draft.data}
              onChange={(e) => setDraft({ ...draft, data: e.target.value })}
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-[8rem_1fr]">
            <label className="text-sm">
              <span className="mb-1 block text-muted">Patch</span>
              <input className="input" value={draft.patch} onChange={(e) => setDraft({ ...draft, patch: e.target.value })} placeholder="OB55" />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-muted">Where sources disagree</span>
              <textarea
                className="input min-h-10 text-xs"
                value={draft.conflicts}
                onChange={(e) => setDraft({ ...draft, conflicts: e.target.value })}
              />
            </label>
          </div>
          {draft.entry && <Sources entry={draft.entry} />}
          <div className="flex flex-wrap gap-2">
            {draft.status !== "APPROVED" && (
              <button className="btn btn-primary" disabled={busy || !draft.title.trim() || !draft.body.trim()} onClick={() => save("APPROVED")}>
                Approve
              </button>
            )}
            <button
              className={`btn ${draft.status === "APPROVED" ? "btn-primary" : ""}`}
              disabled={busy || !draft.title.trim()}
              onClick={() => save()}
            >
              {draft.status === "DRAFT" ? "Save draft" : "Save"}
            </button>
            {draft.id && draft.status !== "REJECTED" && (
              <button className="btn text-bad" disabled={busy} onClick={() => save("REJECTED")}>
                Reject
              </button>
            )}
            {draft.status === "REJECTED" && (
              <button className="btn" disabled={busy} onClick={() => save("DRAFT")}>
                Back to drafts
              </button>
            )}
            <button className="btn" disabled={busy} onClick={() => setDraft(null)}>
              Cancel
            </button>
            {draft.id && (
              <button className="btn ml-auto text-bad" disabled={busy} onClick={remove}>
                Delete
              </button>
            )}
          </div>
        </div>
      )}

      {!entries && !error && <p className="mt-4 text-muted">Loading...</p>}
      {entries && !shown.length && <p className="mt-4 text-sm text-muted">Nothing here yet.</p>}
      <ul className="mt-4 space-y-2">
        {shown.map((e) => (
          <li key={e.id}>
            <button className="card card-hover block w-full p-3 text-left" onClick={() => setDraft(draftOf(e))}>
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{e.title}</span>
                <span className="text-xs text-muted">{KINDS.find((k) => k.key === e.kind)?.label}</span>
                {e.map && (
                  <span className="text-xs text-muted">
                    · {mapName(e.map)}
                    {e.area_name ? `, ${e.area_name}` : ""}
                  </span>
                )}
                <span className="ml-auto flex flex-wrap gap-1">
                  {e.patch && <span className="rounded border border-line px-1.5 text-xs text-muted">{e.patch}</span>}
                  {e.weak_sources && <span className="rounded border border-accent-2/40 px-1.5 text-xs text-accent-2">Weak sources</span>}
                  {e.conflicts && <span className="rounded border border-accent-2/40 px-1.5 text-xs text-accent-2">Sources disagree</span>}
                  {!e.body && <span className="rounded border border-accent-2/40 px-1.5 text-xs text-accent-2">Needs writing</span>}
                  {e.body && (
                    <span className={`rounded border px-1.5 text-xs ${STATUS_BADGE[e.status]}`}>
                      {e.status === "DRAFT" ? "Draft" : e.status === "APPROVED" ? "Approved" : "Rejected"}
                    </span>
                  )}
                </span>
              </span>
              {e.body && <span className="mt-1 line-clamp-2 block text-sm text-muted">{e.body}</span>}
              {Object.keys(e.data).length > 0 && <span className="mt-1 block font-mono text-xs text-muted">{JSON.stringify(e.data)}</span>}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Where a researched entry came from, with links and dates. */
function Sources({ entry }: { entry: KnowledgeEntry }) {
  if (!entry.sources.length && !entry.weak_sources && entry.origin === "STAFF") return null;
  return (
    <div className="rounded border border-line p-3 text-sm">
      <p className="text-muted">
        {entry.origin === "RESEARCH" ? "Researched online" : "Written by staff"}
        {entry.reviewed_by ? ` · reviewed by ${entry.reviewed_by}` : ""}
      </p>
      {entry.weak_sources && <p className="mt-1 text-xs text-accent-2">Weak sources: {entry.weak_reason || "check before approving"}</p>}
      {entry.area_status === "SUGGESTED" && (
        <p className="mt-1 text-xs text-accent-2">Its place outline is only suggested: confirm or move it on the Map areas tab.</p>
      )}
      <ul className="mt-2 space-y-1">
        {entry.sources.map((s) => (
          <li key={s.url} className="text-xs">
            <a href={s.url} target="_blank" rel="noreferrer noopener" className="text-accent hover:underline">
              {s.title || s.url}
            </a>
            <span className="text-muted"> · {sourceLine(s)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
