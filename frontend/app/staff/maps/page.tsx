"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type GameMap, type Paged } from "@/lib/api";

import { useStaff } from "../StaffGate";

export default function StaffMaps() {
  const me = useStaff();
  const [maps, setMaps] = useState<GameMap[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Paged<GameMap>>("/admin/maps")
      .then((d) => setMaps(d.results))
      .catch((e) => setError(e.message));
  }, []);

  if (!me.is_super_admin) return <p className="p-6 text-muted">Only the Super Admin can calibrate maps.</p>;
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-4xl uppercase">Maps</h1>
      {error && <p className="mt-6 text-bad">{error}</p>}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {maps?.map((m) => (
          <Link key={m.slug} href={`/staff/maps/${m.slug}/calibrate`} className="overflow-hidden rounded-lg border border-line bg-panel hover:border-accent">
            <div className="aspect-square bg-panel-2">
              {m.image && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={m.image} alt="" className="h-full w-full object-cover" />
              )}
            </div>
            <div className="p-4">
              <h2 className="font-display text-xl uppercase">{m.name}</h2>
              <p className={`text-sm ${m.is_calibrated ? "text-ok" : "text-muted"}`}>
                {!m.image
                  ? "No image yet"
                  : m.is_calibrated
                    ? `Calibrated (error ${m.calibration_error ?? 0} px)`
                    : "Needs calibration"}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
