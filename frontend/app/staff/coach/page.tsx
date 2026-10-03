"use client";

import { useEffect, useState } from "react";

import AreaEditor from "@/components/staff/coach/AreaEditor";
import KnowledgeEditor from "@/components/staff/coach/KnowledgeEditor";
import WeaponTable from "@/components/staff/coach/WeaponTable";
import { api, type GameMap, type Paged } from "@/lib/api";

type Tab = "knowledge" | "areas" | "weapons";
const TABS: { key: Tab; label: string }[] = [
  { key: "knowledge", label: "Knowledge" },
  { key: "areas", label: "Map areas" },
  { key: "weapons", label: "Weapons" },
];

export default function StaffCoach() {
  const [tab, setTab] = useState<Tab>("knowledge");
  const [maps, setMaps] = useState<GameMap[] | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api<Paged<GameMap> | GameMap[]>("/maps?page_size=50")
      .then((d) => setMaps(Array.isArray(d) ? d : d.results))
      .catch(() => setMaps([]));
  }, [version]);

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Coach knowledge</h1>
      <p className="mt-2 max-w-3xl text-sm text-muted">
        What the AI Coach knows about Free Fire beyond our match data: utility, weapons, characters and pets, the zone, and the named drop spots and
        routes on each map. Coaching about a team always comes from its matches; this is the general knowledge the coach may add.
      </p>
      <div className="mt-6 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${tab === t.key ? "border-accent text-white" : "border-transparent text-muted hover:text-white"}`}
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
      </div>
    </section>
  );
}
