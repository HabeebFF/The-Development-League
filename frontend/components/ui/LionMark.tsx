import { useId } from "react";

/**
 * The Roaring Lion: TDL's mark. An angular gold mane around a dark face, drawn as vector so it stays sharp
 * from a 20px loading pulse to a full-width watermark. Decorative unless given a ``title``.
 */
export default function LionMark({ className = "h-9 w-9", title }: { className?: string; title?: string }) {
  const id = useId().replace(/:/g, "");
  const g = `url(#lion-${id})`;
  return (
    <svg viewBox="0 0 100 104" className={className} role={title ? "img" : undefined} aria-hidden={title ? undefined : true}>
      {title && <title>{title}</title>}
      <defs>
        <linearGradient id={`lion-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--lion-hot)" />
          <stop offset=".55" stopColor="var(--lion)" />
          <stop offset="1" stopColor="var(--lion-deep)" />
        </linearGradient>
      </defs>
      <polygon
        fill={g}
        points="50,5.9 58.2,16.6 70.4,10.5 73.1,23.7 86.7,23.3 83.3,36.3 95.8,41.8 87,52 95.8,62.2 83.3,67.7 86.7,80.7 73.1,80.3 70.4,93.5 58.2,87.4 50,98.1 41.8,87.4 29.6,93.5 26.9,80.3 13.3,80.7 16.7,67.7 4.2,62.2 13,52 4.2,41.8 16.7,36.3 13.3,23.3 26.9,23.7 29.6,10.5 41.8,16.6"
      />
      <polygon fill="var(--bg)" points="50,22 66,28 72,40 69,60 60,76 50,82 40,76 31,60 28,40 34,28" />
      <polygon fill={g} points="35,43 46,46 45,51 37,49" />
      <polygon fill={g} points="65,43 54,46 55,51 63,49" />
      <polygon fill={g} points="50,52 54,58 54,64 50,67 46,64 46,58" />
      <polygon fill={g} points="43,58 46,58 46,66 50,69 54,66 54,58 57,58 58,68 50,76 42,68" />
      <polygon fill="var(--bg)" points="50,67 54,66 50,72 46,66" />
      <polygon fill={g} points="40,30 50,26 60,30 50,40" />
    </svg>
  );
}
