/** The banner at the top of a public page: an eyebrow line, a big title and an optional note. */
export default function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="relative overflow-hidden border-b border-line">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(110deg,rgb(255_90_31/0.14),transparent_45%)]" />
      <div className="pointer-events-none absolute -right-10 top-0 h-full w-1/2 -skew-x-12 bg-[repeating-linear-gradient(90deg,rgb(255_255_255/0.025)_0_2px,transparent_2px_14px)]" />
      <div className="relative mx-auto max-w-6xl px-4 py-8 sm:py-12">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="mt-1 font-display text-5xl leading-none uppercase sm:text-6xl">{title}</h1>
        {children && <div className="mt-3 text-sm text-muted">{children}</div>}
      </div>
    </div>
  );
}
