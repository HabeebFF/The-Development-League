/** What a public page shows while its data loads, or when it fails. */
export default function Loading({ error }: { error?: string | null }) {
  return error ? <p className="text-bad">{error}</p> : <p className="text-muted">Loading...</p>;
}
