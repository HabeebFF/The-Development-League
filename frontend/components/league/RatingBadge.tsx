import { BAND_CLASSES, ratingText, type Band } from "@/lib/ratings";

const SIZES = { sm: "min-w-9 px-1 py-0.5 text-sm", md: "min-w-11 px-1.5 py-0.5 text-lg", lg: "min-w-20 px-3 py-1 text-4xl" };

/** A rating out of 10 on its colour, like the football apps (red, orange, green, blue, gold). */
export default function RatingBadge({ rating, band, size = "md" }: { rating: number; band: Band; size?: keyof typeof SIZES }) {
  return (
    <span
      className={`inline-flex shrink-0 justify-center rounded-sm font-display leading-none font-bold tabular-nums ${SIZES[size]} ${BAND_CLASSES[band]}`}
      title={`Rating ${ratingText(rating)} out of 10`}
    >
      {ratingText(rating)}
    </span>
  );
}
