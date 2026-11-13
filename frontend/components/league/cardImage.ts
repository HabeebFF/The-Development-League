// Draws a player card onto a canvas, for "Save as image". The on-page card is HTML and CSS,
// which a browser can't save as a picture by itself, so this redraws the same layout.

import {
  AWARD_NAMES,
  BLANK_PHOTO,
  changeText,
  roleShort,
  TIER_COLORS,
  type PlayerCard,
} from "@/lib/cards";
import { copyText, designColors } from "@/lib/cardDesigns";

const W = 750;
const H = 1050;

function load(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

function shape(ctx: CanvasRenderingContext2D, inset = 0) {
  const x = (f: number) => inset + f * (W - 2 * inset);
  const y = (f: number) => inset + f * (H - 2 * inset);
  ctx.beginPath();
  ctx.moveTo(x(0.12), y(0));
  ctx.lineTo(x(0.88), y(0));
  ctx.lineTo(x(1), y(0.07));
  ctx.lineTo(x(1), y(0.9));
  ctx.lineTo(x(0.5), y(1));
  ctx.lineTo(x(0), y(0.9));
  ctx.lineTo(x(0), y(0.07));
  ctx.closePath();
}

/** The card as a PNG. */
export async function cardImage(card: PlayerCard): Promise<Blob | null> {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const font =
    getComputedStyle(document.body).getPropertyValue("--font-display").trim() ||
    "sans-serif";
  const body =
    getComputedStyle(document.body).getPropertyValue("--font-body").trim() ||
    "sans-serif";
  const plainTier = card.tier === "gold" || card.tier === "silver" || card.tier === "bronze";
  const look = plainTier ? designColors(card.design) : null;
  const tierColors = TIER_COLORS[card.tier];
  const [top, bottom, ink, line] = look
    ? [look.top, look.bottom, look.ink, look.line]
    : tierColors;
  const [photo, logo] = await Promise.all([
    load(card.photo || BLANK_PHOTO),
    card.team?.logo ? load(card.team.logo) : null,
  ]);

  shape(ctx);
  ctx.save();
  ctx.clip();
  const g = ctx.createLinearGradient(0, 0, W * 0.6, H);
  g.addColorStop(0, top);
  g.addColorStop(1, bottom);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
  if (card.tier === "totw") {
    const r = ctx.createRadialGradient(
      W * 0.7,
      H * 0.25,
      0,
      W * 0.7,
      H * 0.25,
      W * 0.7,
    );
    r.addColorStop(0, "rgba(255,90,31,0.45)");
    r.addColorStop(1, "rgba(255,90,31,0)");
    ctx.fillStyle = r;
    ctx.fillRect(0, 0, W, H);
  }
  if (card.tier === "rising" || card.tier === "icon") {
    const r = ctx.createRadialGradient(
      W * 0.7,
      H * 0.25,
      0,
      W * 0.7,
      H * 0.25,
      W * 0.65,
    );
    const glow = card.tier === "rising" ? "62,230,176" : "255,255,255";
    r.addColorStop(0, `rgba(${glow},0.4)`);
    r.addColorStop(1, `rgba(${glow},0)`);
    ctx.fillStyle = r;
    ctx.fillRect(0, 0, W, H);
  }
  if (card.tier === "totm") {
    const r = ctx.createRadialGradient(
      W * 0.7,
      H * 0.25,
      0,
      W * 0.7,
      H * 0.25,
      W * 0.6,
    );
    r.addColorStop(0, "rgba(242,193,78,0.35)");
    r.addColorStop(1, "rgba(242,193,78,0)");
    ctx.fillStyle = r;
    ctx.fillRect(0, 0, W, H);
  }
  if (look && card.design) drawDesign(ctx, card.design.parts, look.glow);
  const sheen = ctx.createLinearGradient(0, 0, W, H * 0.6);
  sheen.addColorStop(0.3, "rgba(255,255,255,0)");
  sheen.addColorStop(0.45, "rgba(255,255,255,0.25)");
  sheen.addColorStop(0.6, "rgba(255,255,255,0)");
  ctx.fillStyle = sheen;
  ctx.fillRect(0, 0, W, H);

  // Photo, fading out at the bottom.
  if (photo) {
    const px = W * 0.42,
      py = 55,
      pw = W * 0.5,
      ph = 370;
    const scale = Math.max(pw / photo.width, ph / photo.height);
    const sw = pw / scale,
      sh = ph / scale;
    const off = document.createElement("canvas");
    off.width = pw;
    off.height = ph;
    const o = off.getContext("2d")!;
    o.drawImage(photo, (photo.width - sw) / 2, 0, sw, sh, 0, 0, pw, ph);
    const fade = o.createLinearGradient(0, ph * 0.7, 0, ph);
    fade.addColorStop(0, "rgba(0,0,0,1)");
    fade.addColorStop(1, "rgba(0,0,0,0)");
    o.globalCompositeOperation = "destination-in";
    o.fillStyle = fade;
    o.fillRect(0, 0, pw, ph);
    ctx.drawImage(off, px, py);
  }
  ctx.restore();

  ctx.strokeStyle = line;
  ctx.lineWidth = 4;
  shape(ctx, 18);
  ctx.stroke();

  ctx.fillStyle = ink;
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  const cx = 150;
  if (look) {
    // The tier stays on the rating badge.
    const badge = ctx.createLinearGradient(cx - 80, 60, cx + 80, 215);
    badge.addColorStop(0, tierColors[0]);
    badge.addColorStop(1, tierColors[1]);
    ctx.fillStyle = badge;
    ctx.beginPath();
    ctx.moveTo(cx - 85, 70);
    ctx.lineTo(cx + 85, 70);
    ctx.lineTo(cx + 85, 190);
    ctx.lineTo(cx + 55, 220);
    ctx.lineTo(cx - 85, 220);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = tierColors[2];
  }
  ctx.font = `700 150px ${font}`;
  ctx.fillText(String(card.overall), cx, 200);
  ctx.fillStyle = ink;
  ctx.font = `700 52px ${font}`;
  ctx.fillText(roleShort(card.role), cx, 262);
  ctx.globalAlpha = 0.35;
  ctx.fillRect(cx - 60, 285, 120, 3);
  ctx.globalAlpha = 1;
  if (logo) {
    ctx.drawImage(logo, cx - 50, 305, 100, 100);
  } else if (card.team) {
    ctx.fillStyle = card.team.primary_color || "#181b26";
    ctx.fillRect(cx - 50, 305, 100, 100);
    ctx.fillStyle = "#fff";
    ctx.font = `700 40px ${font}`;
    ctx.fillText(
      (card.team.tag || card.team.name).slice(0, 4).toUpperCase(),
      cx,
      370,
    );
  }
  if (card.overall_change) {
    ctx.fillStyle = card.overall_change > 0 ? "#22c55e" : "#f04444";
    ctx.font = `700 34px ${body}`;
    ctx.fillText(changeText(card.overall_change), cx, 455);
  }

  ctx.fillStyle = ink;
  ctx.font = `700 72px ${font}`;
  let name = card.name.toUpperCase();
  while (ctx.measureText(name).width > W - 120 && name.length > 3)
    name = name.slice(0, -1);
  ctx.fillText(
    name === card.name.toUpperCase() ? name : `${name.slice(0, -1)}…`,
    W / 2,
    500,
  );
  ctx.globalAlpha = 0.35;
  ctx.fillRect(100, 525, W - 200, 3);
  ctx.globalAlpha = 1;

  const main = card.stats.filter((s) => !s.extra);
  const extras = card.stats.filter((s) => s.extra);
  const rowH = extras.length ? 62 : 70;
  const drawStat = (s: (typeof card.stats)[number], x: number, y: number) => {
    ctx.globalAlpha = s.stale ? 0.55 : 1;
    ctx.textAlign = "right";
    ctx.font = `700 58px ${font}`;
    ctx.fillText(s.rating == null ? "–" : String(s.rating), x + 90, y);
    ctx.textAlign = "left";
    ctx.font = `600 48px ${font}`;
    ctx.fillText(s.key, x + 105, y);
    ctx.globalAlpha = 1;
  };
  main.forEach((s, i) =>
    drawStat(s, i % 2 === 0 ? 105 : 395, 600 + Math.floor(i / 2) * rowH),
  );
  if (extras.length) {
    const y = 600 + Math.ceil(main.length / 2) * rowH;
    ctx.globalAlpha = 0.35;
    ctx.fillRect(130, y - 45, W - 260, 3);
    ctx.globalAlpha = 1;
    extras.forEach((s, i) => drawStat(s, i % 2 === 0 ? 105 : 395, y + 20));
  }
  ctx.textAlign = "center";
  ctx.font = `700 22px ${body}`;
  ctx.globalAlpha = 0.7;
  const foot =
    card.tier === "totm"
      ? `TEAM OF THE MONTH · ${(AWARD_NAMES[card.totm ?? ""] ?? "").toUpperCase()}`
      : card.tier === "totw"
        ? "TEAM OF THE WEEK"
        : card.tier === "icon"
          ? "ICON · THE DEVELOPMENT LEAGUE"
          : card.tier === "rising"
            ? `RISING STAR${card.rise ? ` · +${card.rise}` : ""}`
            : "THE DEVELOPMENT LEAGUE";
  const copy = look ? copyText(card.design) : null;
  ctx.fillText(copy ? `${foot} · ${copy}` : foot, W / 2, H - 120);
  ctx.globalAlpha = 1;

  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

/** A shop design's pattern and effect, drawn roughly like the on-page card. */
function drawDesign(
  ctx: CanvasRenderingContext2D,
  parts: { pattern: string; effect: string },
  glow: string,
) {
  const rgb = glow.split(" ").join(",");
  ctx.save();
  if (parts.pattern === "lines" || parts.pattern === "carbon") {
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = parts.pattern === "lines" ? 4 : 3;
    const step = parts.pattern === "lines" ? 36 : 12;
    for (let x = -H; x < W + H; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x + H * 0.5, H);
      ctx.stroke();
    }
  } else if (parts.pattern === "hex" || parts.pattern === "circuit") {
    ctx.fillStyle = parts.pattern === "hex" ? "rgba(255,255,255,0.1)" : `rgba(${rgb},0.14)`;
    for (let y = 0; y < H; y += 36)
      for (let x = (y / 36) % 2 ? 18 : 0; x < W; x += 36) {
        ctx.beginPath();
        ctx.arc(x, y, parts.pattern === "hex" ? 6 : 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
  }
  if (parts.pattern === "flames" || parts.effect === "glow" || parts.effect === "flame") {
    const r = ctx.createRadialGradient(W / 2, H * 1.05, 0, W / 2, H * 1.05, H * 0.65);
    r.addColorStop(0, `rgba(${rgb},0.6)`);
    r.addColorStop(1, `rgba(${rgb},0)`);
    ctx.fillStyle = r;
    ctx.fillRect(0, 0, W, H);
  }
  if (parts.effect === "flame") {
    ctx.strokeStyle = `rgba(${rgb},0.85)`;
    ctx.lineWidth = 16;
    ctx.shadowColor = `rgba(${rgb},1)`;
    ctx.shadowBlur = 30;
    shape(ctx, 8);
    ctx.stroke();
  }
  if (parts.pattern === "paper") {
    ctx.fillStyle = "rgba(90,60,20,0.14)";
    for (let i = 0; i < 900; i++) ctx.fillRect((i * 97) % W, (i * 389) % H, 2, 2);
    const v = ctx.createRadialGradient(W / 2, H * 0.45, W * 0.3, W / 2, H * 0.45, H * 0.75);
    v.addColorStop(0, "rgba(70,40,10,0)");
    v.addColorStop(1, "rgba(70,40,10,0.45)");
    ctx.fillStyle = v;
    ctx.fillRect(0, 0, W, H);
  }
  if (parts.pattern === "facets") {
    const cx = W / 2,
      cy = H * 0.38;
    for (let i = 0; i < 12; i++) {
      const a0 = (i / 12) * Math.PI * 2,
        a1 = ((i + 1) / 12) * Math.PI * 2;
      ctx.fillStyle = i % 2 ? "rgba(255,255,255,0.28)" : "rgba(140,190,240,0.12)";
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(a0) * H, cy + Math.sin(a0) * H);
      ctx.lineTo(cx + Math.cos(a1) * H, cy + Math.sin(a1) * H);
      ctx.closePath();
      ctx.fill();
    }
  }
  if (parts.effect === "sparkle") {
    ctx.fillStyle = "rgba(255,255,255,0.95)";
    for (const [x, y, r] of [[0.2, 0.15, 10], [0.8, 0.3, 14], [0.3, 0.62, 8], [0.75, 0.78, 11], [0.55, 0.1, 7]]) {
      ctx.beginPath();
      ctx.moveTo(W * x, H * y - r * 2);
      ctx.lineTo(W * x + r / 3, H * y);
      ctx.lineTo(W * x, H * y + r * 2);
      ctx.lineTo(W * x - r / 3, H * y);
      ctx.closePath();
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(W * x - r * 2, H * y);
      ctx.lineTo(W * x, H * y + r / 3);
      ctx.lineTo(W * x + r * 2, H * y);
      ctx.lineTo(W * x, H * y - r / 3);
      ctx.closePath();
      ctx.fill();
    }
  }
  if (parts.effect === "shine") {
    const g = ctx.createLinearGradient(0, 0, W, H);
    g.addColorStop(0.3, "rgba(255,255,255,0)");
    g.addColorStop(0.5, "rgba(200,225,255,0.35)");
    g.addColorStop(0.7, "rgba(255,255,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }
  ctx.restore();
}
