import { ratingText, ratingTone, TONE_CLASSES, type Band } from "@/lib/ratings";

const SIZES = { sm: "min-w-9 px-1 py-0.5 text-sm", md: "min-w-11 px-1.5 py-0.5 text-lg", lg: "min-w-20 px-3 py-1 text-4xl" };

/**
 * A rating out of 10 on its colour: red under 6, amber 6 to 7.4, green 7.5+, a gold glow at 9+.
 * ``band`` is still accepted from the API rows but the colour follows the number.
 */
export default function RatingBadge({ rating, size = "md" }: { rating: number; band?: Band; size?: keyof typeof SIZES }) {
  const tone = ratingTone(rating);
  return (
    <span
      className={`inline-flex shrink-0 justify-center font-display leading-none font-black tabular-nums ${SIZES[size]} ${TONE_CLASSES[tone]}`}
      // A clip-path would cut off the 9+ glow, so elite badges stay square.
      style={tone === "elite" ? undefined : { clipPath: "polygon(4px 0, 100% 0, calc(100% - 4px) 100%, 0 100%)" }}
      title={`Rating ${ratingText(rating)} out of 10`}
    >
      {ratingText(rating)}
    </span>
  );
}
