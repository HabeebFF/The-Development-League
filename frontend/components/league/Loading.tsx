/** A shimmering placeholder block. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

/** Placeholder rows shaped like a table or list. */
export function SkeletonRows({ count = 5, className = "h-12" }: { count?: number; className?: string }) {
  return (
    <div className="space-y-1.5" role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className={className} />
      ))}
    </div>
  );
}

/** What a public page shows while its data loads (a skeleton), or when it fails. */
export default function Loading({ error, count = 5 }: { error?: string | null; count?: number }) {
  return error ? <p className="text-bad">{error}</p> : <SkeletonRows count={count} />;
}
