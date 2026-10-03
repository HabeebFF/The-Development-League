"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type GameMap } from "@/lib/api";
import { dataText, KINDS, parseData, type KnowledgeEntry, type KnowledgeKind } from "@/lib/coach";

type Draft = {
  id: number | null;
  kind: KnowledgeKind;
  title: string;
  body: string;
  data: string;
  map: string;
  area: string;
};

const BLANK: Draft = {
  id: null,
  kind: "UTILITY",
  title: "",
  body: "",
  data: "",
  map: "",
  area: "",
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
  };
}

function message(e: unknown): string {
  return e instanceof ApiError ? e.message : "Something went wrong. Try again.";
}

/** The coach's general Free Fire knowledge, grouped by kind. Entries with no text are flagged. */
export default function KnowledgeEditor({ maps }: { maps: GameMap[] }) {
  const [entries, setEntries] = useState<KnowledgeEntry[] | null>(null);
  const [kind, setKind] = useState<KnowledgeKind | "ALL">("ALL");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api<KnowledgeEntry[]>("/coach/knowledge")
      .then(setEntries)
      .catch((e) => setError(message(e)));
  }, [version]);

  const shown = (entries ?? []).filter((e) => kind === "ALL" || e.kind === kind);
  const areas = maps.find((m) => m.slug === draft?.map)?.areas ?? [];
  const mapName = (slug: string | null) => maps.find((m) => m.slug === slug)?.name;

  async function save() {
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
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" disabled={busy || !draft.title.trim()} onClick={save}>
              Save
            </button>
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
                {!e.body && <span className="ml-auto rounded border border-accent-2/40 px-1.5 text-xs text-accent-2">Needs writing</span>}
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
