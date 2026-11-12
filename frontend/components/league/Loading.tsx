import LoadingSkeleton, { Skeleton } from "@/components/ui/LoadingSkeleton";

export { Skeleton };

/** Placeholder rows shaped like a table or list, under the breathing lion. */
export function SkeletonRows({ count = 5, className = "h-12" }: { count?: number; className?: string }) {
  return <LoadingSkeleton count={count} className={className} />;
}

/** What a public page shows while its data loads (a skeleton), or when it fails. */
export default function Loading({ error, count = 5 }: { error?: string | null; count?: number }) {
  return error ? (
    <p className="border-l-2 border-bad bg-bad/10 px-3 py-2 text-sm text-bad" role="alert">
      {error}
    </p>
  ) : (
    <SkeletonRows count={count} />
  );
}
