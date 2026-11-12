import type { ComponentProps } from "react";

/** A chamfered panel. ``hover`` adds the lift and gold edge for cards that are links. */
export default function Card({ hover = false, className = "", ...rest }: { hover?: boolean } & ComponentProps<"div">) {
  return <div {...rest} className={`card ${hover ? "card-hover" : ""} ${className}`.trim()} />;
}
