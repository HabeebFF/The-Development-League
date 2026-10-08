"use client";

import Konva from "konva";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Group, Image as KImage, Line, Rect, Text } from "react-konva";

import { layout, shorten, textWidth, type LabelItem, type Placed } from "@/lib/labels";

// Broadcast-style map labels: a compact see-through pill with a thin team-colour border,
// the team logo and a bold condensed name. Sizes are in screen pixels (``px`` turns them
// into map pixels), so labels stay the same size whatever the zoom.

export type LabelStatus = "ok" | "knocked" | "out";

const GREY = "#6b7280";
const PILL = "rgba(8, 8, 12, 0.72)";
const GAP = 4;
/** How long a label takes to glide to a new spot, in seconds. */
const GLIDE = 0.3;

type Sizes = { font: number; logo: number; pad: number; max: number };
const PLAYER: Sizes = { font: 11.5, logo: 12, pad: 3, max: 12 };
const PLAYER_PHONE: Sizes = { font: 9.5, logo: 10, pad: 2.5, max: 10 };
const TEAM: Sizes = { font: 13, logo: 16, pad: 3.5, max: 14 };
const TEAM_PHONE: Sizes = { font: 11, logo: 13, pad: 3, max: 10 };

export type LabelSpec = {
  id: string;
  /** The dot, in map pixels. */
  x: number;
  y: number;
  kind: "player" | "team";
  text: string;
  /** Shown when the team has no logo. */
  tag: string;
  logo: string | null;
  color: string;
  status?: LabelStatus;
  /** The highlighted or followed team: drawn on top and brighter. */
  focus?: boolean;
};

function sizes(kind: LabelSpec["kind"], compact: boolean): Sizes {
  if (kind === "team") return compact ? TEAM_PHONE : TEAM;
  return compact ? PLAYER_PHONE : PLAYER;
}

/** Pill size in screen pixels. Players: logo over name. Teams: logo beside name. */
function measure(spec: LabelSpec, compact: boolean) {
  const s = sizes(spec.kind, compact);
  const text = shorten(spec.status === "out" ? `✕ ${spec.text}` : spec.text, s.max);
  const tw = textWidth(text, s.font);
  if (spec.kind === "team") return { s, text, w: s.logo + 4 + tw + s.pad * 2, h: Math.max(s.logo, s.font) + s.pad * 2 };
  return { s, text, w: Math.max(s.logo, tw) + s.pad * 2, h: s.logo + 1 + s.font + s.pad * 2 };
}

/** Every label, nudged apart where they would overlap. Focused labels drawn last (on top).
 * Each label remembers its last spot (in screen pixels, so zooming doesn't move it) and
 * keeps it while it's clear; when it must move, it glides there instead of jumping. */
export function MapLabels({ labels, px }: { labels: LabelSpec[]; px: (n: number) => number }) {
  // Last placements, kept across renders. A Map held in state is never replaced, only
  // updated, so it acts as memory without causing renders.
  const [memory] = useState(() => new Map<string, Placed>());
  const compact = useCompact();
  const font = useDisplayFont();
  const logos = useImages(labels.map((l) => l.logo));
  const measured = labels.map((l) => ({ spec: l, ...measure(l, compact) }));
  const items: LabelItem[] = measured.map((m) => ({
    id: m.spec.id,
    x: m.spec.x,
    y: m.spec.y,
    w: px(m.w),
    h: px(m.h),
    rank: (m.spec.focus ? 10 : 0) + (m.spec.kind === "team" ? 5 : 0) + (m.spec.status === "out" ? -3 : 0),
  }));
  const unit = px(1);
  const prev: Record<string, Placed> = {};
  for (const [id, p] of memory) prev[id] = { ...p, dx: p.dx * unit, dy: p.dy * unit };
  const placed = layout(items, px(GAP), px(5), 10, prev);
  memory.clear();
  for (const [id, p] of Object.entries(placed)) memory.set(id, { ...p, dx: p.dx / unit, dy: p.dy / unit });
  const order = [...measured].sort((a, b) => Number(!!a.spec.focus) - Number(!!b.spec.focus));
  return (
    <Group listening={false}>
      {order
        .filter((m) => !placed[m.spec.id].hidden)
        .map((m) => (
          <Pill key={m.spec.id} m={m} at={placed[m.spec.id]} px={px} font={font} logo={m.spec.logo ? logos[m.spec.logo] : undefined} />
        ))}
    </Group>
  );
}

function Pill({
  m,
  at,
  px,
  font,
  logo,
}: {
  m: ReturnType<typeof measure> & { spec: LabelSpec };
  at: Placed;
  px: (n: number) => number;
  font: string;
  logo?: HTMLImageElement;
}) {
  const { spec, s, text } = m;
  const out = spec.status === "out";
  // The pill is drawn in screen pixels inside a group scaled by px(1): text drawn at a
  // sub-pixel font size and scaled up loses its spaces and dots on a zoomed-in map.
  const k = at.scale;
  const [w, h] = [m.w * k, m.h * k];
  const border = out ? GREY : spec.color;
  const opacity = (spec.status === "knocked" ? 0.55 : out ? 0.7 : spec.focus ? 1 : 0.9) * (at.crowded ? 0.6 : 1);
  const unit = px(1);
  // Offset from the dot in screen pixels.
  const dx = at.dx / unit;
  const dy = at.dy / unit;
  const logoSize = s.logo * k;
  const fontSize = s.font * k;
  const pad = s.pad * k;
  const team = spec.kind === "team";
  const logoX = team ? -w / 2 + pad : -logoSize / 2;
  const logoY = team ? -logoSize / 2 : -h / 2 + pad;
  const textX = team ? logoX + logoSize + 4 * k : -w / 2;
  const textY = team ? -fontSize / 2 : logoY + logoSize + 1 * k;
  const textW = team ? w / 2 - pad - textX : w;
  const [pillRef, lineRef] = useGlide(dx, dy);
  return (
    <Group x={spec.x} y={spec.y} scaleX={unit} scaleY={unit} opacity={opacity}>
      <Line ref={lineRef} stroke={border} strokeWidth={1} opacity={0.6} />
      <Group ref={pillRef}>
        <Rect
          x={-w / 2}
          y={-h / 2}
          width={w}
          height={h}
          fill={PILL}
          stroke={border}
          strokeWidth={spec.focus ? 1.6 : 1}
          cornerRadius={3}
          shadowColor={spec.focus ? border : "#000"}
          shadowBlur={spec.focus ? 6 : 2}
          shadowOpacity={spec.focus ? 0.6 : 0.4}
        />
        {logo ? (
          <KImage image={logo} x={logoX} y={logoY} width={logoSize} height={logoSize} opacity={out ? 0.4 : 1} />
        ) : (
          <Group x={logoX} y={logoY}>
            <Rect width={logoSize} height={logoSize} fill={out ? GREY : spec.color} cornerRadius={2} />
            <Text
              text={spec.tag.slice(0, 2).toUpperCase()}
              width={logoSize}
              height={logoSize}
              align="center"
              verticalAlign="middle"
              fontSize={logoSize * 0.55}
              fontFamily={font}
              fontStyle="bold"
              fill="#0b0b0f"
            />
          </Group>
        )}
        <Text
          text={text}
          x={textX}
          y={textY}
          width={textW}
          align={team ? "left" : "center"}
          wrap="none"
          ellipsis
          fontSize={fontSize}
          fontFamily={font}
          fontStyle="bold"
          fill={out ? "#9ca3af" : spec.focus ? "#ffffff" : "#e5e7eb"}
        />
      </Group>
    </Group>
  );
}

/** Moves a pill and its leader line to (dx, dy): at once the first time, then gliding. */
function useGlide(dx: number, dy: number) {
  const pill = useRef<Konva.Group>(null);
  const line = useRef<Konva.Line>(null);
  const tweens = useRef<Konva.Tween[]>([]);
  const placed = useRef(false);
  useLayoutEffect(() => {
    const [p, l] = [pill.current, line.current];
    if (!p || !l) return;
    if (!placed.current || (Math.abs(p.x() - dx) < 0.5 && Math.abs(p.y() - dy) < 0.5)) {
      placed.current = true;
      p.position({ x: dx, y: dy });
      l.points([0, 0, dx, dy]);
      return;
    }
    for (const t of tweens.current) t.destroy();
    const easing = Konva.Easings.EaseInOut;
    tweens.current = [
      new Konva.Tween({ node: p, x: dx, y: dy, duration: GLIDE, easing }),
      new Konva.Tween({ node: l, points: [0, 0, dx, dy], duration: GLIDE, easing }),
    ];
    for (const t of tweens.current) t.play();
  }, [dx, dy]);
  useEffect(() => () => tweens.current.forEach((t) => t.destroy()), []);
  return [pill, line] as const;
}

/** Small screens get smaller labels. */
export function useCompact(): boolean {
  const query = "(max-width: 640px)";
  const [compact, setCompact] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const on = () => setCompact(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return compact;
}

/** The site's condensed heading font (Barlow Condensed), once it has loaded. */
function useDisplayFont(): string {
  const [font, setFont] = useState("Arial Narrow, sans-serif");
  useEffect(() => {
    const family = getComputedStyle(document.body).getPropertyValue("--font-display").trim();
    if (!family) return;
    document.fonts.ready.then(() => setFont(family));
  }, []);
  return font;
}

const cache = new Map<string, HTMLImageElement>();

/** Loaded images by URL (logos appear once they've downloaded). */
function useImages(urls: (string | null)[]): Record<string, HTMLImageElement> {
  const key = [...new Set(urls.filter((u): u is string => !!u))].sort().join("|");
  const [, bump] = useState(0);
  useEffect(() => {
    for (const url of key ? key.split("|") : []) {
      if (cache.has(url)) continue;
      const img = new window.Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        cache.set(url, img);
        bump((n) => n + 1);
      };
      img.src = url;
    }
  }, [key]);
  return Object.fromEntries([...cache.entries()]);
}
