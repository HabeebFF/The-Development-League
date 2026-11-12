import type { ReactNode } from "react";

import LionMark from "./LionMark";

/** What a section shows when there is nothing in it yet: a faded lion, a title and a line on why. */
export default function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-2 px-6 py-10 text-center">
      <LionMark className="h-16 w-16 opacity-30 grayscale-[0.4]" />
      <h3 className="font-display text-2xl font-extrabold uppercase">{title}</h3>
      {children && <div className="max-w-sm text-sm text-muted">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
