import LionMark from "./LionMark";

/** A shimmering slanted placeholder block. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} style={{ clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }} aria-hidden />;
}

/** The lion breathing next to what is loading. */
export function LionLoader({ label = "Loading" }: { label?: string }) {
  return (
    <span className="flex items-center gap-3 font-display text-sm font-bold tracking-[0.2em] text-muted uppercase">
      <LionMark className="lion-breathe h-8 w-8" />
      {label}
    </span>
  );
}

/** Placeholder rows shaped like a table or list, under the breathing lion. */
export default function LoadingSkeleton({ count = 5, className = "h-12", label }: { count?: number; className?: string; label?: string }) {
  return (
    <div className="space-y-2" role="status" aria-label={label ?? "Loading"}>
      <LionLoader label={label} />
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className={className} />
      ))}
    </div>
  );
}
