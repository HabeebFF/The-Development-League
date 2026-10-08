"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError, type Paged, type TeamRef } from "@/lib/api";
import { aiWritten, headToHeadText, type CounterPlan, type ReportMatch } from "@/lib/coach";
import Advice from "./Advice";

const title = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Pick an opponent and see how to play them: plays from their own matches, each with its evidence. */
export default function CounterPlanView({ teamSlug, matchHref }: { teamSlug: string; matchHref: (id: number) => string }) {
  const [teams, setTeams] = useState<TeamRef[] | null>(null);
  const [opponent, setOpponent] = useState("");
  const [plan, setPlan] = useState<CounterPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Paged<TeamRef> | TeamRef[]>("/teams?page_size=100")
      .then((d) => setTeams((Array.isArray(d) ? d : d.results).filter((t) => t.slug !== teamSlug)))
      .catch(() => setTeams([]));
  }, [teamSlug]);

  function pick(slug: string) {
    setOpponent(slug);
    setPlan(null);
    setError(null);
    if (!slug) return;
    setLoading(true);
    api<CounterPlan>(`/coach/teams/${teamSlug}/counter/${slug}`)
      .then(setPlan)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't make the plan."))
      .finally(() => setLoading(false));
  }

  const byId = new Map<number, ReportMatch>((plan?.matches ?? []).map((m) => [m.id, m]));
  const chips = (ids: number[]) => (
    <span className="mt-2 flex flex-wrap gap-1">
      {ids.map((id) => (
        <Link
          key={id}
          href={matchHref(id)}
          className="rounded border border-line px-1.5 py-0.5 text-xs text-muted hover:border-accent hover:text-white"
        >
          {byId.get(id)?.label ?? `Match ${id}`}
          {byId.get(id)?.map ? ` · ${title(byId.get(id)!.map)}` : ""}
        </Link>
      ))}
    </span>
  );

  return (
    <div>
      <label className="block max-w-xs text-sm">
        <span className="text-muted">Plan against</span>
        <select className="input mt-1 w-full" value={opponent} onChange={(e) => pick(e.target.value)} disabled={!teams}>
          <option value="">{teams ? "Pick a team" : "Loading teams..."}</option>
          {teams?.map((t) => (
            <option key={t.slug} value={t.slug}>
              {t.name}
            </option>
          ))}
        </select>
      </label>
      {loading && <p className="mt-4 text-muted">Working it out from their matches...</p>}
      {error && <p className="mt-4 text-bad">{error}</p>}
      {plan && (
        <div className="mt-6">
          <p className="text-sm text-muted">
            From {plan.matches.length} of {plan.opponent}&apos;s matches. {headToHeadText(plan.head_to_head, plan.opponent)}
          </p>
          {plan.head_to_head.matches.length > 0 && chips(plan.head_to_head.matches)}
          <h2 className="mt-6 font-display text-2xl uppercase">How to play them</h2>
          {plan.plays.length === 0 ? (
            <p className="mt-2 text-sm text-muted">
              Nothing about {plan.opponent} stands out yet. A play needs the same pattern in at least 3 of their matches.
            </p>
          ) : (
            <ol className="mt-3 space-y-3">
              {plan.plays.map((p, i) => (
                <li key={p.title} className="card p-4">
                  <p className="flex gap-3 font-medium">
                    <span className="font-display text-xl leading-none text-accent">{i + 1}</span>
                    <span>{p.title}</span>
                  </p>
                  <Advice task={p} />
                  <ul className="mt-2 space-y-1 pl-7 text-sm text-muted">
                    {p.why.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                  <div className="pl-7">{chips(p.matches)}</div>
                </li>
              ))}
            </ol>
          )}
          <p className="mt-8 text-xs text-muted">
            Every play comes from {plan.opponent}&apos;s recorded matches and links to them.
            {aiWritten(plan.writer) ? " The advice is written by AI and checked against those matches." : ""}
          </p>
        </div>
      )}
    </div>
  );
}
