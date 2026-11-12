/**
 * The Development League logo: four rising bars (two white, two gold) and an up arrow, with the
 * "DEVELOPMENT / LEAGUE" wordmark. Redrawn from the league's own logo, in the site's gold.
 */
export function TdlMark({ className = "h-8 w-auto", title }: { className?: string; title?: string }) {
  return (
    <svg viewBox="0 0 240 130" className={className} role={title ? "img" : undefined} aria-hidden={title ? undefined : true} aria-label={title}>
      <rect x="0" y="84" width="28" height="44" fill="var(--text)" />
      <rect x="40" y="56" width="28" height="72" fill="var(--text)" />
      <rect x="80" y="28" width="28" height="100" fill="var(--lion)" />
      <rect x="120" y="0" width="28" height="128" fill="var(--lion)" />
      <g fill="none" stroke="var(--lion)" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round">
        <path d="M174 110 L198 86 L210 96 L234 68" />
        <path d="M218 66 H236 V84" />
      </g>
    </svg>
  );
}

/** Mark plus wordmark. ``tagline`` adds the "Nigeria · Free Fire" line under it. */
export default function TdlLogo({ size = "md", tagline = false }: { size?: "sm" | "md" | "lg"; tagline?: boolean }) {
  const s = { sm: ["h-5", "text-[15px]", "text-[11px]"], md: ["h-7", "text-[19px]", "text-[14px]"], lg: ["h-10", "text-[28px]", "text-[20px]"] }[size];
  return (
    <span className="flex items-center gap-2.5">
      <TdlMark className={`${s[0]} w-auto shrink-0`} />
      <span className="flex flex-col font-display leading-[0.85] font-black uppercase">
        <span className={`${s[1]} tracking-[0.02em] text-text`}>Development</span>
        <span className={`${s[2]} tracking-[0.08em] text-accent`}>League</span>
        {tagline && <span className="mt-1.5 text-[10px] font-semibold tracking-[0.3em] text-muted">Nigeria · Free Fire</span>}
      </span>
    </span>
  );
}
