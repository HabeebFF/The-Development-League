"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { WEAPON_CLASSES, type WeaponClass, type WeaponRow } from "@/lib/coach";

/** Every weapon number in our kill logs, most used first, so staff can name each one once. */
export default function WeaponTable() {
  const [rows, setRows] = useState<WeaponRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<number | null>(null);

  useEffect(() => {
    api<WeaponRow[]>("/coach/weapons")
      .then(setRows)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load weapons."));
  }, []);

  function edit(id: number, change: Partial<WeaponRow>) {
    setRows((all) => all?.map((r) => (r.weapon_id === id ? { ...r, ...change } : r)) ?? null);
    setSaved(null);
  }

  async function save(row: WeaponRow) {
    setError(null);
    try {
      if (row.name.trim()) {
        await api(`/coach/weapons/${row.weapon_id}`, {
          method: "PUT",
          body: {
            name: row.name.trim(),
            weapon_class: row.weapon_class,
            note: row.note,
          },
        });
      } else {
        await api(`/coach/weapons/${row.weapon_id}`, { method: "DELETE" });
      }
      setSaved(row.weapon_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save.");
    }
  }

  const unnamed = rows?.filter((r) => !r.name).length ?? 0;
  return (
    <div>
      <p className="text-sm text-muted">
        The match logs only give a number for each weapon. Name them once and the coach can talk about weapons by name.
        {rows ? ` ${unnamed} of ${rows.length} still need a name.` : ""}
      </p>
      {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      {!rows && !error && <p className="mt-4 text-muted">Loading...</p>}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="py-2 pr-3">Number</th>
              <th className="py-2 pr-3">Kills</th>
              <th className="py-2 pr-3">Name</th>
              <th className="py-2 pr-3">Class</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.weapon_id} className="border-t border-line">
                <td className="py-2 pr-3 font-mono">{r.weapon_id}</td>
                <td className="py-2 pr-3">{r.kills}</td>
                <td className="py-2 pr-3">
                  <input
                    className="input min-w-36 py-1"
                    value={r.name}
                    onChange={(e) => edit(r.weapon_id, { name: e.target.value })}
                    aria-label={`Name of weapon ${r.weapon_id}`}
                  />
                </td>
                <td className="py-2 pr-3">
                  <select
                    className="input py-1"
                    value={r.weapon_class}
                    onChange={(e) =>
                      edit(r.weapon_id, {
                        weapon_class: e.target.value as WeaponClass,
                      })
                    }
                    aria-label={`Class of weapon ${r.weapon_id}`}
                  >
                    {WEAPON_CLASSES.map((c) => (
                      <option key={c.key} value={c.key}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-2">
                  <button className="btn px-2 py-1 text-xs" onClick={() => save(r)}>
                    {saved === r.weapon_id ? "Saved" : "Save"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
