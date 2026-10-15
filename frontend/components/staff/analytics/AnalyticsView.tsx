"use client";

import { useState } from "react";

import { leagueToday, type Who } from "@/lib/analytics";

import ActionsView from "./ActionsView";
import DayView from "./DayView";
import Overview from "./Overview";
import PeopleView from "./PeopleView";
import { Tabs, WhoPicker } from "./parts";

type Tab = "overview" | "day" | "people" | "actions";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "day", label: "Day by day" },
  { key: "people", label: "People" },
  { key: "actions", label: "Actions" },
];

/** Staff only: who visits the website and everything they do there (see /privacy). */
export default function AnalyticsView() {
  const [tab, setTab] = useState<Tab>("overview");
  const [who, setWho] = useState<Who>("everyone");
  const [date, setDate] = useState(leagueToday);
  const [person, setPerson] = useState<string | null>(null);

  const openDay = (d: string) => {
    setDate(d);
    setPerson(null);
    setTab("day");
  };

  return (
    // data-no-track: staff reading these numbers are not themselves recorded as actions.
    <section className="mx-auto max-w-6xl px-4 py-10" data-no-track>
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Analytics</h1>
      <p className="mt-2 max-w-3xl text-sm text-muted">
        Who visits the website and what they do. Signed-in people are shown by name. Visitors without an account stay anonymous and get a new code each day. Bots are left out.
      </p>
      <div className="mt-6">
        <Tabs tabs={TABS} value={tab} onChange={(t) => (setTab(t), setPerson(null))} />
      </div>
      {tab !== "people" && (
        <div className="mt-4">
          <WhoPicker value={who} onChange={setWho} />
        </div>
      )}
      <div className="mt-4">
        {tab === "overview" && <Overview who={who} onDay={openDay} />}
        {tab === "day" && <DayView who={who} date={date} onDate={(d) => (setDate(d), setPerson(null))} person={person} onPerson={setPerson} />}
        {tab === "people" && (
          <PeopleView
            onOpen={(p, d) => {
              setDate(d);
              setPerson(p);
              setTab("day");
            }}
          />
        )}
        {tab === "actions" && <ActionsView who={who} />}
      </div>
    </section>
  );
}
