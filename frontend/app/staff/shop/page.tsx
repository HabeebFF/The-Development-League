"use client";

import CardShopManager from "@/components/staff/CardShopManager";

export default function StaffShop() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl leading-none font-extrabold uppercase">Card shop</h1>
      <p className="mt-2 text-sm text-muted">
        Card designs people buy with DC. Designs change how a card looks, never its numbers. Hide a design to take it off sale; people who own
        it keep it.
      </p>
      <CardShopManager />
    </section>
  );
}
