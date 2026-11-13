"use client";

import { useCallback, useEffect, useState } from "react";

import FanCard from "@/components/predict/FanCard";
import { api, type Paged } from "@/lib/api";
import {
  RARITY_COLORS,
  RARITY_LABELS,
  type CardDesign,
  type DesignParts,
} from "@/lib/cardDesigns";
import { coins } from "@/lib/predictions";

type StaffDesign = {
  id: number;
  slug: string;
  name: string;
  rarity: CardDesign["rarity"];
  price: number;
  parts: DesignParts;
  copies: number | null;
  sale_ends: string | null;
  on_sale: boolean;
  order: number;
  sold: number;
};
type Parts = Record<keyof DesignParts, { key: string; label: string }[]>;
type Sale = {
  id: string;
  user_id: number;
  name: string;
  email: string;
  design: CardDesign;
  price_paid: number;
  gift: boolean;
  gift_note: string;
  bought_at: string;
  refunded_at: string | null;
};
type Sales = Paged<Sale> & { totals: { copies: number; dc: number } };

const BLANK: Omit<StaffDesign, "id" | "sold"> = {
  slug: "",
  name: "",
  rarity: "RARE",
  price: 300,
  parts: { palette: "gold", pattern: "none", effect: "none" },
  copies: null,
  sale_ends: null,
  on_sale: true,
  order: 100,
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Africa/Lagos",
  });
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);
}

/** Staff > Card shop: designs (add, edit, hide), sales, refunds, gifts. */
export default function CardShopManager() {
  const [designs, setDesigns] = useState<StaffDesign[]>([]);
  const [parts, setParts] = useState<Parts | null>(null);
  const [sales, setSales] = useState<Sales | null>(null);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<
    (Omit<StaffDesign, "id" | "sold"> & { id?: number }) | null
  >(null);
  const [gift, setGift] = useState({ email: "", design: "", note: "" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setDesigns(await api<StaffDesign[]>("/admin/shop/designs"));
      setParts(await api<Parts>("/admin/shop/designs/parts"));
      setSales(
        await api<Sales>(
          `/admin/shop/sales${search ? `?search=${encodeURIComponent(search)}` : ""}`,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load the shop.");
    }
  }, [search]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loads from the server
    load();
  }, [load]);

  async function run(job: () => Promise<unknown>, done: string) {
    setError(null);
    setNotice(null);
    try {
      await job();
      setNotice(done);
      await load();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
      return false;
    }
  }

  async function save() {
    if (!editing) return;
    const { id, ...body } = editing;
    const ok = await run(
      () =>
        api(id ? `/admin/shop/designs/${id}` : "/admin/shop/designs", {
          method: id ? "PATCH" : "POST",
          body: { ...body, slug: body.slug || slugify(body.name) },
        }),
      id ? "Design saved." : "Design added.",
    );
    if (ok) setEditing(null);
  }

  return (
    <div className="mt-8 space-y-10">
      {error && <p className="text-sm text-bad">{error}</p>}
      {notice && <p className="text-sm text-ok">{notice}</p>}

      <section>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-display text-2xl uppercase">Designs</h2>
          {sales && (
            <span className="text-sm text-muted">
              {sales.totals.copies} owned · {coins(sales.totals.dc)} spent
            </span>
          )}
          <button
            type="button"
            className="btn btn-primary ml-auto px-4 py-1.5 text-sm"
            onClick={() => setEditing({ ...BLANK })}
          >
            Add design
          </button>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="table w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">Design</th>
                <th className="text-left">Rarity</th>
                <th className="text-right">Price</th>
                <th className="text-right">Owned</th>
                <th className="pl-6 text-left">On sale</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {designs.map((d) => (
                <tr key={d.id} className={d.on_sale ? "" : "opacity-60"}>
                  <td className="font-semibold">{d.name}</td>
                  <td style={{ color: RARITY_COLORS[d.rarity] }}>
                    {RARITY_LABELS[d.rarity]}
                  </td>
                  <td className="text-right">{coins(d.price)}</td>
                  <td className="text-right">
                    {d.sold}
                    {d.copies !== null && ` / ${d.copies}`}
                  </td>
                  <td className="pl-6">
                    {d.on_sale ? "Yes" : "Hidden"}
                    {d.sale_ends && (
                      <span className="block text-xs text-muted">
                        until {when(d.sale_ends)}
                      </span>
                    )}
                  </td>
                  <td className="text-right whitespace-nowrap">
                    <button
                      type="button"
                      className="btn btn-ghost px-3 py-1 text-xs"
                      onClick={() => setEditing({ ...d })}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost px-3 py-1 text-xs"
                      onClick={() =>
                        run(
                          () =>
                            api(`/admin/shop/designs/${d.id}`, {
                              method: "PATCH",
                              body: { on_sale: !d.on_sale },
                            }),
                          d.on_sale
                            ? `${d.name} hidden.`
                            : `${d.name} back on sale.`,
                        )
                      }
                    >
                      {d.on_sale ? "Hide" : "Show"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {editing && parts && (
        <section className="card grid gap-6 p-5 md:grid-cols-[1fr_auto]">
          <div className="grid gap-3 sm:grid-cols-2">
            <h3 className="font-display text-xl uppercase sm:col-span-2">
              {editing.id ? `Edit ${editing.name}` : "New design"}
            </h3>
            <Field label="Name">
              <input
                className="input"
                value={editing.name}
                maxLength={60}
                onChange={(e) =>
                  setEditing({ ...editing, name: e.target.value })
                }
              />
            </Field>
            <Field label="Rarity">
              <select
                className="input"
                value={editing.rarity}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    rarity: e.target.value as StaffDesign["rarity"],
                  })
                }
              >
                {Object.entries(RARITY_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Price (DC)">
              <input
                className="input"
                type="number"
                min={1}
                value={editing.price}
                onChange={(e) =>
                  setEditing({ ...editing, price: Number(e.target.value) })
                }
              />
            </Field>
            <Field label="Copies (empty = unlimited)">
              <input
                className="input"
                type="number"
                min={1}
                value={editing.copies ?? ""}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    copies: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </Field>
            {(["palette", "pattern", "effect"] as const).map((k) => (
              <Field key={k} label={k[0].toUpperCase() + k.slice(1)}>
                <select
                  className="input"
                  value={editing.parts[k]}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      parts: { ...editing.parts, [k]: e.target.value },
                    })
                  }
                >
                  {parts[k].map((o) => (
                    <option key={o.key} value={o.key}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
            ))}
            <Field label="Off sale after (optional)">
              <input
                className="input"
                type="datetime-local"
                value={editing.sale_ends ? editing.sale_ends.slice(0, 16) : ""}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    sale_ends: e.target.value
                      ? new Date(e.target.value).toISOString()
                      : null,
                  })
                }
              />
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={editing.on_sale}
                onChange={(e) =>
                  setEditing({ ...editing, on_sale: e.target.checked })
                }
              />
              On sale
            </label>
            <div className="flex gap-2 sm:col-span-2">
              <button
                type="button"
                className="btn"
                onClick={() => setEditing(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!editing.name || editing.price < 1}
                onClick={save}
              >
                Save
              </button>
            </div>
          </div>
          <div className="flex justify-center">
            <FanCard
              size={0.9}
              fan={{
                name: "Preview",
                favourite_team: null,
                design: {
                  id: 0,
                  slug: editing.slug,
                  name: editing.name,
                  rarity: editing.rarity,
                  parts: editing.parts,
                  copy_number: editing.copies ? 1 : null,
                  copies: editing.copies,
                },
                stats: {
                  balance: 1000,
                  shop_spent: 0,
                  net: 1000,
                  won: 12,
                  lost: 7,
                  accuracy: 0.63,
                },
              }}
            />
          </div>
        </section>
      )}

      <section>
        <h2 className="font-display text-2xl uppercase">Gift a design</h2>
        <p className="mt-1 text-sm text-muted">
          Free, for example to an award winner. It counts as one of a limited
          design&apos;s copies.
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_1fr_auto]">
          <input
            className="input"
            type="email"
            placeholder="Their email"
            value={gift.email}
            onChange={(e) => setGift({ ...gift, email: e.target.value })}
          />
          <select
            className="input"
            value={gift.design}
            onChange={(e) => setGift({ ...gift, design: e.target.value })}
          >
            <option value="">Pick a design</option>
            {designs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          <input
            className="input"
            placeholder="Note (optional)"
            maxLength={200}
            value={gift.note}
            onChange={(e) => setGift({ ...gift, note: e.target.value })}
          />
          <button
            type="button"
            className="btn btn-primary"
            disabled={!gift.email || !gift.design}
            onClick={async () => {
              const ok = await run(
                () =>
                  api("/admin/shop/gift", {
                    method: "POST",
                    body: {
                      email: gift.email,
                      design: Number(gift.design),
                      note: gift.note,
                    },
                  }),
                "Design gifted.",
              );
              if (ok) setGift({ email: "", design: "", note: "" });
            }}
          >
            Gift
          </button>
        </div>
      </section>

      <section>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-display text-2xl uppercase">Sales</h2>
          <input
            className="input ml-auto max-w-xs"
            placeholder="Search name, email or design"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="table w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">When</th>
                <th className="text-left">Who</th>
                <th className="text-left">Design</th>
                <th className="text-right">Paid</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sales?.results.map((s) => (
                <tr key={s.id} className={s.refunded_at ? "opacity-60" : ""}>
                  <td className="whitespace-nowrap text-muted">
                    {when(s.bought_at)}
                  </td>
                  <td>
                    {s.name}
                    <span className="block text-xs text-muted">{s.email}</span>
                  </td>
                  <td>
                    {s.design.name}
                    {s.design.copy_number && (
                      <span className="text-muted">
                        {" "}
                        #{s.design.copy_number}
                      </span>
                    )}
                    {s.gift && (
                      <span className="ml-2 chip">
                        Gift{s.gift_note && `: ${s.gift_note}`}
                      </span>
                    )}
                  </td>
                  <td className="text-right">
                    {s.gift ? "–" : coins(s.price_paid)}
                  </td>
                  <td className="text-right whitespace-nowrap">
                    {s.refunded_at ? (
                      <span className="text-xs text-muted">
                        Refunded {when(s.refunded_at)}
                      </span>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="btn btn-ghost px-3 py-1 text-xs"
                          onClick={() =>
                            run(
                              () =>
                                api("/admin/shop/unequip", {
                                  method: "POST",
                                  body: { user: s.user_id },
                                }),
                              `Took the design off ${s.name}'s card.`,
                            )
                          }
                        >
                          Take off card
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost px-3 py-1 text-xs text-bad"
                          onClick={() =>
                            run(
                              () =>
                                api(`/admin/shop/sales/${s.id}/refund`, {
                                  method: "POST",
                                }),
                              `Refunded ${s.name}: ${s.gift ? "design taken back" : coins(s.price_paid) + " returned"}.`,
                            )
                          }
                        >
                          {s.gift ? "Take back" : "Refund"}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {sales && sales.results.length === 0 && (
            <p className="mt-3 text-sm text-muted">No sales yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-muted">{label}</span>
      {children}
    </label>
  );
}
