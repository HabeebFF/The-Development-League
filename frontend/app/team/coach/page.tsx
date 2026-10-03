"use client";

import { useEffect, useState } from "react";

import ReportView from "@/components/coach/ReportView";
import { api, ApiError } from "@/lib/api";
import { weekLabel, type CoachReport } from "@/lib/coach";

import { useTeam } from "../TeamGate";

export default function TeamCoach() {
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
  return (
    <section className="mx-auto max-w-3xl px-4 py-10">
      <p className="text-sm font-semibold tracking-[0.2em] text-accent uppercase">Coach</p>
      <h1 className="mt-1 font-display text-5xl leading-none font-extrabold uppercase">{membership?.team.name ?? "Coach"}</h1>
      {!membership && <p className="mt-4 text-muted">League staff see every team&apos;s reports under Staff, Coach knowledge.</p>}
      {membership && !allowed && <p className="mt-4 text-muted">The coach isn&apos;t part of your team&apos;s plan yet. Ask league staff.</p>}
      {error && <p className="mt-4 text-bad">{error}</p>}
      {membership && allowed && !reports && !error && <p className="mt-4 text-muted">Loading...</p>}
      {reports && reports.length === 0 && (
        <p className="mt-4 text-muted">Your first weekly report appears after the league&apos;s next report day.</p>
      )}
      {reports && reports.length > 1 && (
        <select className="input mt-4 max-w-xs" value={pick} onChange={(e) => setPick(Number(e.target.value))} aria-label="Week">
          {reports.map((r, i) => (
            <option key={r.id} value={i}>
              {weekLabel(r.week_start)}
            </option>
          ))}
        </select>
      )}
      {report && (
        <div className="mt-4">
          <ReportView report={report} matchHref={(id) => `/team/matches/${id}/rotations`} />
        </div>
      )}
    </section>
  );
}
