import type { ReactNode } from "react";

import LionMark from "./LionMark";

/** Sign in, sign up and invites: one centred angled card over a dark glow and a faint watermark. */
export default function AuthShell({ eyebrow, title, children }: { eyebrow?: string; title?: string; children: ReactNode }) {
  return (
    <section className="relative isolate overflow-hidden px-4 py-12 sm:py-20">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(36rem_24rem_at_50%_10%,rgb(245_165_36/0.16),transparent_70%)]" />
      <div aria-hidden className="hex-grid pointer-events-none absolute inset-0 -z-10 opacity-40" />
      <LionMark className="pointer-events-none absolute top-8 left-1/2 -z-10 h-[26rem] w-[26rem] -translate-x-1/2 opacity-[0.05]" />
      <div className="card mx-auto max-w-sm border-t-4 border-lion p-6 shadow-[0_24px_80px_rgb(0_0_0/0.55)] sm:p-8">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        {/* Without a title the page inside brings its own heading. */}
        {title && (
          <>
            <h1 className="mt-1 font-display text-4xl leading-none font-black uppercase">{title}</h1>
            <span aria-hidden className="mt-3 block h-1 w-12 -skew-x-[18deg] bg-gradient-to-r from-lion-hot to-lion-deep" />
          </>
        )}
        {children}
      </div>
    </section>
  );
}
