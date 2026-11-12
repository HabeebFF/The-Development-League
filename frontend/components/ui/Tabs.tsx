"use client";

import Link from "next/link";
import { useRef, type KeyboardEvent } from "react";

export type Tab<K extends string> = { key: K; label: string; href?: string };

/**
 * Slanted tabs. With ``onChange`` they are buttons (arrow keys move between them); give each tab an
 * ``href`` instead for tabs that are separate pages.
 */
export default function Tabs<K extends string>({
  tabs,
  value,
  onChange,
  label,
  className = "",
}: {
  tabs: Tab<K>[];
  value: K;
  onChange?: (k: K) => void;
  /** What the tabs choose, for screen readers ("Period"). */
  label: string;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const onKey = (e: KeyboardEvent) => {
    if (!onChange || (e.key !== "ArrowRight" && e.key !== "ArrowLeft")) return;
    const i = tabs.findIndex((t) => t.key === value);
    const next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
    onChange(next.key);
    ref.current?.querySelector<HTMLElement>(`[data-key="${next.key}"]`)?.focus();
  };
  const cls = (on: boolean) =>
    `flex min-h-11 shrink-0 items-center px-4 font-display text-[15px] font-extrabold tracking-[0.1em] uppercase transition-colors sm:min-h-10 ${
      on ? "bg-gradient-to-br from-lion-hot to-lion text-accent-ink" : "bg-panel text-muted hover:text-text"
    }`;
  const clip = { clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" };
  return (
    <div
      ref={ref}
      role={onChange ? "tablist" : undefined}
      aria-label={label}
      onKeyDown={onKey}
      className={`-mx-1 flex gap-1 overflow-x-auto px-1 [scrollbar-width:none] ${className}`}
    >
      {tabs.map((t) => {
        const on = t.key === value;
        return t.href ? (
          <Link key={t.key} href={t.href} className={cls(on)} style={clip} aria-current={on ? "page" : undefined}>
            {t.label}
          </Link>
        ) : (
          <button
            key={t.key}
            type="button"
            role="tab"
            data-key={t.key}
            aria-selected={on}
            tabIndex={on ? 0 : -1}
            className={cls(on)}
            style={clip}
            onClick={() => onChange?.(t.key)}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
