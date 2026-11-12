import type { CSSProperties } from "react";


const SIZE = { sm: "h-9 w-9", md: "h-11 w-11", lg: "h-16 w-16", xl: "h-28 w-24" };

/**
 * A player's photo in a clipped frame with a strip of their team colour; the blank silhouette when there
 * is no photo. Photos are user uploads served from /media, so a plain <img> keeps them lazy and uncropped.
 */
export default function PlayerAvatar({
  src,
  name,
  colour,
  size = "md",
  className = "",
}: {
  src?: string | null;
  name: string;
  colour?: string | null;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  return (
    <span
      className={`relative block shrink-0 overflow-hidden bg-panel-2 ${SIZE[size]} ${className}`}
      style={{ clipPath: "polygon(0 0, 100% 0, 100% 75%, 75% 100%, 0 100%)" } as CSSProperties}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={name} className="h-full w-full object-cover object-top" loading="lazy" />
      ) : (
        <svg viewBox="0 0 100 100" className="absolute inset-x-[10%] bottom-0 h-[88%] w-[80%] fill-[#3a4054]" role="img" aria-label={name}>
          <path d="M50 8c13 0 21 10 21 24s-9 26-21 26-21-12-21-26S37 8 50 8M10 100c2-22 17-34 40-34s38 12 40 34z" />
        </svg>
      )}
      <span className="absolute inset-x-0 bottom-0 h-[3px]" style={{ background: colour || "var(--accent)" }} aria-hidden />
    </span>
  );
}
