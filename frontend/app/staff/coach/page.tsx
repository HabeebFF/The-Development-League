"use client";

import { useEffect, useState } from "react";

import CounterPlanView from "@/components/coach/CounterPlanView";
import RotateView from "@/components/coach/RotateView";
import AreaEditor from "@/components/staff/coach/AreaEditor";
import KnowledgeEditor from "@/components/staff/coach/KnowledgeEditor";
import ReportsAdmin from "@/components/staff/coach/ReportsAdmin";
import WeaponTable from "@/components/staff/coach/WeaponTable";
import { api, type GameMap, type Paged, type TeamRef } from "@/lib/api";

type Tab = "reports" | "counter" | "rotate" | "knowledge" | "areas" | "weapons";
const TABS: { key: Tab; label: string }[] = [
  { key: "reports", label: "Weekly reports" },
  { key: "counter", label: "Counter plans" },
  { key: "rotate", label: "When to rotate" },
  { key: "knowledge", label: "Knowledge" },
  { key: "areas", label: "Map areas" },
  { key: "weapons", label: "Weapons" },
];

export default function StaffCoach() {
  const [tab, setTab] = useState<Tab>("reports");
  const [maps, setMaps] = useState<GameMap[] | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api<Paged<GameMap> | GameMap[]>("/maps?page_size=50")
      .then((d) => setMaps(Array.isArray(d) ? d : d.results))
      .catch(() => setMaps([]));
  }, [version]);

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Coach</h1>
      <p className="mt-2 max-w-3xl text-sm text-muted">
        Weekly reports for every team, worked out from its own matches, and the general Free Fire knowledge the coach may add to them.
      </p>
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
      <div className="mt-6">
        {!maps && <p className="text-muted">Loading...</p>}
        {maps && tab === "knowledge" && <KnowledgeEditor maps={maps} />}
        {maps && tab === "areas" && <AreaEditor maps={maps} onChanged={() => setVersion((v) => v + 1)} />}
        {tab === "weapons" && <WeaponTable />}
        {tab === "reports" && <ReportsAdmin />}
        {tab === "counter" && <StaffCounter />}
        {tab === "rotate" && <RotateView matchHref={(id) => `/matches/${id}/rotations`} />}
      </div>
    </section>
  );
}

/** Staff see any team's counter plan: pick the team asking, then its opponent. */
function StaffCounter() {
  const [teams, setTeams] = useState<TeamRef[] | null>(null);
  const [team, setTeam] = useState("");
  useEffect(() => {
    api<Paged<TeamRef> | TeamRef[]>("/teams?page_size=100")
      .then((d) => setTeams(Array.isArray(d) ? d : d.results))
      .catch(() => setTeams([]));
  }, []);
  return (
    <div>
      <label className="block max-w-xs text-sm">
        <span className="text-muted">Team</span>
        <select className="input mt-1 w-full" value={team} onChange={(e) => setTeam(e.target.value)} disabled={!teams}>
          <option value="">{teams ? "Pick a team" : "Loading teams..."}</option>
          {teams?.map((t) => (
            <option key={t.slug} value={t.slug}>
              {t.name}
            </option>
          ))}
        </select>
      </label>
      {team && (
        <div className="mt-4">
          <CounterPlanView key={team} teamSlug={team} matchHref={(id) => `/matches/${id}/rotations`} />
        </div>
      )}
    </div>
  );
}
