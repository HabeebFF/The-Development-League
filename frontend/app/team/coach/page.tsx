"use client";

import { useEffect, useState } from "react";

import CounterPlanView from "@/components/coach/CounterPlanView";
import ReportView from "@/components/coach/ReportView";
import RotateView from "@/components/coach/RotateView";
import { api, ApiError } from "@/lib/api";
import { weekLabel, type CoachReport } from "@/lib/coach";

import { useTeam } from "../TeamGate";

type Tab = "report" | "counter" | "rotate";
const TABS: { key: Tab; label: string }[] = [
  { key: "report", label: "Weekly report" },
  { key: "counter", label: "Counter plan" },
  { key: "rotate", label: "When to rotate" },
];

export default function TeamCoach() {
  const [tab, setTab] = useState<Tab>("report");
  const { me, membership } = useTeam();
  const [reports, setReports] = useState<CoachReport[] | null>(null);
  const [pick, setPick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const slug = membership?.team.slug;
  const allowed = me.features.includes("assistant");

  useEffect(() => {
    if (!slug || !allowed) return;
    api<CoachReport[]>(`/coach/teams/${slug}/reports`)
      .then(setReports)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load your reports."));
  }, [slug, allowed]);

  const report = reports?.[pick];
  const matchHref = (id: number) => `/team/matches/${id}/rotations`;
  return (
    <section className={`mx-auto px-4 py-10 ${tab === "rotate" ? "max-w-6xl" : "max-w-3xl"}`}>
      <p className="text-sm font-semibold tracking-[0.2em] text-accent uppercase">Coach</p>
      <h1 className="mt-1 font-display text-5xl leading-none font-extrabold uppercase">{membership?.team.name ?? "Coach"}</h1>
      {!membership && <p className="mt-4 text-muted">League staff see every team&apos;s reports under Staff, Coach knowledge.</p>}
      {membership && !allowed && <p className="mt-4 text-muted">The coach isn&apos;t part of your team&apos;s plan yet. Ask league staff.</p>}
      {membership && allowed && (
        <div className="mt-6 flex gap-1 overflow-x-auto border-b border-line">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm font-medium ${tab === t.key ? "border-accent text-white" : "border-transparent text-muted hover:text-white"}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
      {slug && allowed && tab === "counter" && (
        <div className="mt-6">
          <CounterPlanView teamSlug={slug} matchHref={matchHref} />
        </div>
      )}
      {slug && allowed && tab === "rotate" && (
        <div className="mt-6">
          <RotateView matchHref={matchHref} />
        </div>
      )}
      {tab === "report" && error && <p className="mt-4 text-bad">{error}</p>}
      {tab === "report" && membership && allowed && !reports && !error && <p className="mt-4 text-muted">Loading...</p>}
      {tab === "report" && reports && reports.length === 0 && (
        <p className="mt-4 text-muted">Your first weekly report appears after the league&apos;s next report day.</p>
      )}
      {tab === "report" && reports && reports.length > 1 && (
        <select className="input mt-4 max-w-xs" value={pick} onChange={(e) => setPick(Number(e.target.value))} aria-label="Week">
          {reports.map((r, i) => (
            <option key={r.id} value={i}>
              {weekLabel(r.week_start)}
            </option>
          ))}
        </select>
      )}
      {tab === "report" && report && (
        <div className="mt-4">
          <ReportView report={report} matchHref={matchHref} />
        </div>
      )}
    </section>
  );
}
