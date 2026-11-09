"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { aiWritten, type CoachAnswer } from "@/lib/coach";

const EXAMPLES = [
  "How do we beat Solar Flare on Purgatory?",
  "When should we rotate on Bermuda?",
  "What are we doing wrong?",
];

const title = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Ask the coach a question in your own words; every answer links to the matches behind it. */
export default function AskCoach({ teamSlug, matchHref }: { teamSlug: string; matchHref: (id: number) => string }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<CoachAnswer[] | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CoachAnswer[]>(`/coach/teams/${teamSlug}/ask`)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [teamSlug]);

  async function send(text: string) {
    const q = text.trim();
    if (q.length < 3 || asking) return;
    setAsking(true);
    setError(null);
    try {
      const answer = await api<CoachAnswer>(`/coach/teams/${teamSlug}/ask`, {
        method: "POST",
        body: { question: q },
      });
      setHistory((h) => [answer, ...(h ?? [])]);
      setQuestion("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The coach couldn't answer that. Try again.");
    } finally {
      setAsking(false);
    }
  }

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(question);
        }}
      >
        <label className="block text-sm">
          <span className="text-muted">Ask about your team, an opponent or a map</span>
          <textarea
            className="input mt-1 min-h-20 w-full"
            value={question}
            maxLength={300}
            placeholder={EXAMPLES[0]}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(question);
              }
            }}
          />
        </label>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button type="submit" className="btn btn-primary" disabled={asking || question.trim().length < 3}>
            {asking ? "Thinking..." : "Ask"}
          </button>
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" className="btn px-2 py-1 text-xs" disabled={asking} onClick={() => send(ex)}>
              {ex}
            </button>
          ))}
        </div>
      </form>
      {error && <p className="mt-4 text-bad">{error}</p>}
      {history === null && <p className="mt-6 text-muted">Loading...</p>}
      {history && history.length === 0 && !asking && (
        <p className="mt-6 text-sm text-muted">
          No questions yet. Name a team or a map in your question and the coach uses their recorded matches.
        </p>
      )}
      <ol className="mt-6 space-y-4">
        {history?.map((a) => (
          <AnswerCard key={a.id} answer={a} matchHref={matchHref} />
        ))}
      </ol>
      <p className="mt-8 text-xs text-muted">
        Answers only use the league&apos;s recorded matches, and every point links to them.
      </p>
    </div>
  );
}

function AnswerCard({ answer, matchHref }: { answer: CoachAnswer; matchHref: (id: number) => string }) {
  const byId = new Map(answer.matches.map((m) => [m.id, m]));
  const about = [
    ...answer.opponents.map((o) => o.name),
    ...(answer.map ? [answer.map.name] : []),
  ];
  return (
    <li className="card p-4">
      <p className="font-medium">{answer.question}</p>
      <p className="mt-1 text-xs text-muted">
        {answer.asked_by ? `${answer.asked_by} · ` : ""}
        {new Date(answer.asked_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
        {about.length > 0 ? ` · about ${about.join(", ")}` : ""}
      </p>
      {answer.points.length > 0 && (
        <ol className="mt-3 space-y-3">
          {answer.points.map((p, i) => (
            <li key={`${i}-${p.text}`}>
              <p className="flex gap-3">
                <span className="font-display text-xl leading-none text-accent">{i + 1}</span>
                <span>{p.text}</span>
              </p>
              {p.why.length > 0 && (p.why.length > 1 || p.why[0] !== p.text) && (
                <ul className="mt-1 space-y-1 pl-7 text-sm text-muted">
                  {p.why.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
              {p.knowledge && p.knowledge.length > 0 && (
                <p className="mt-1 pl-7 text-xs text-muted">
                  Also from the coach notes: {p.knowledge.map((k) => k.title).join(", ")}
                </p>
              )}
              {p.matches.length > 0 && (
                <span className="mt-2 flex flex-wrap gap-1 pl-7">
                  {p.matches.map((id) => (
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
              )}
            </li>
          ))}
        </ol>
      )}
      {answer.not_covered && <p className="mt-3 text-sm text-muted">{answer.not_covered}</p>}
      {aiWritten(answer.writer) && (
        <p className="mt-3 text-xs text-muted">Written by AI and checked against these matches.</p>
      )}
    </li>
  );
}
