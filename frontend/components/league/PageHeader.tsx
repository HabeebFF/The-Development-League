import LionMark from "@/components/ui/LionMark";

/** The banner at the top of a public page: an eyebrow line, a big title and an optional note, over a lion watermark. */
export default function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="relative overflow-hidden border-b border-line">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(40rem_16rem_at_80%_0%,rgb(245_165_36/0.18),transparent_65%),linear-gradient(110deg,rgb(245_165_36/0.08),transparent_45%)]" />
      <div className="hex-grid pointer-events-none absolute inset-0 opacity-30" />
      <LionMark className="pointer-events-none absolute top-1/2 -right-10 h-56 w-56 -translate-y-1/2 opacity-[0.08] sm:right-4 sm:h-72 sm:w-72" />
      <div className="relative mx-auto max-w-6xl px-4 py-8 sm:py-12">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="mt-1 font-display text-5xl leading-[0.9] font-black uppercase sm:text-7xl">{title}</h1>
        <span className="mt-3 block h-1 w-16 -skew-x-[18deg] bg-gradient-to-r from-lion-hot to-lion-deep shadow-[0_0_14px_rgb(245_165_36/0.7)]" aria-hidden />
        {children && <div className="mt-3 text-sm text-muted">{children}</div>}
      </div>
    </div>
  );
}
