"use client";

import SectionHeader from "@/components/ui/SectionHeader";
import TeamBadge from "@/components/league/TeamBadge";
import { nightName, places, stageText, type Night, type ScrimSession } from "@/lib/scrims";
import { useApi } from "@/lib/useApi";

/** One session's lobby: where sign-up is, places taken and the teams playing. */
export function SessionLobby({ s, showWaitlist = true }: { s: ScrimSession; showWaitlist?: boolean }) {
  const { taken } = places(s);
  return (
    <div className="card p-4 sm:p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-display text-3xl leading-none font-black uppercase">{s.session}</h3>
        <span className="num text-2xl leading-none">
          {taken}
          <span className="ml-1 text-xs tracking-[0.14em] text-muted">TEAMS</span>
        </span>
      </div>
      <p className={`mt-1 text-sm ${s.stage === "open" ? "text-accent" : "text-muted"}`}>{stageText(s)}</p>
      {s.playing.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{s.stage === "soon" ? "No teams yet." : "No teams signed up yet."}</p>
      ) : (
        <ol className="mt-4 grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
          {s.playing.map((e, i) => (
            <li key={e.team.id} className="flex min-w-0 items-center gap-2">
              <span className="num w-5 shrink-0 text-right text-sm text-muted">{i + 1}</span>
              <TeamBadge team={e.team} />
            </li>
          ))}
        </ol>
      )}
      {showWaitlist && s.waitlist.length > 0 && (
        <p className="mt-3 text-xs text-muted">
          Waitlist: {s.waitlist.map((e) => e.team.name).join(", ")}
        </p>
      )}
    </div>
  );
}

function lobbyTitle(date: string): string {
  const name = nightName(date);
  return name === "Tonight" ? "Tonight's scrims" : `Next scrims · ${name}`;
}

/** The next scrim night's two sessions and who's playing, for the home and Predict pages. */
export default function ScrimLobby({ title }: { title?: string }) {
  const night = useApi<Night>("/scrims/tonight");
  const data = night.data;
  if (!data?.date) return null;
  return (
    <section>
      <SectionHeader title={title ?? lobbyTitle(data.date)} />
      <div className="grid gap-4 md:grid-cols-2">
        {data.sessions.map((s) => (
          <SessionLobby key={s.session} s={s} />
        ))}
      </div>
    </section>
  );
}
