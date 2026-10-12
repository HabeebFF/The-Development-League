import {
  BLANK_PHOTO,
  cardFooter,
  changeText,
  roleShort,
  TIER_COLORS,
  type CardStat,
  type PlayerCard as Card,
} from "@/lib/cards";

// The card's outline: a FUT style shield with cut top corners and a pointed base.
export const CARD_SHAPE =
  "polygon(12% 0, 88% 0, 100% 7%, 100% 90%, 50% 100%, 0 90%, 0 7%)";

/** A player's FUT style card. Everything is sized in em, so ``size`` scales it all. */
export default function PlayerCard({
  card,
  size = 1,
}: {
  card: Card;
  size?: number;
}) {
  const [top, bottom, ink, line] = TIER_COLORS[card.tier];
  const main = card.stats.filter((s) => !s.extra);
  const extras = card.stats.filter((s) => s.extra);
  const totw = card.tier === "totw";
  const totm = card.tier === "totm";
  const rising = card.tier === "rising";
  const icon = card.tier === "icon";
  return (
    <div
      className="relative aspect-[5/7] w-[15em] select-none"
      style={{
        fontSize: `${size * 16}px`,
        color: ink,
        filter: totw
          ? "drop-shadow(0 0 0.9em rgb(255 90 31 / 0.55))"
          : totm
            ? "drop-shadow(0 0 0.9em rgb(242 193 78 / 0.5))"
            : rising
              ? "drop-shadow(0 0 0.9em rgb(62 230 176 / 0.5))"
              : icon
                ? "drop-shadow(0 0 1em rgb(255 244 205 / 0.6))"
                : undefined,
      }}
    >
      <div
        className="absolute inset-0"
        style={{
          clipPath: CARD_SHAPE,
          background: `linear-gradient(160deg, ${top}, ${bottom})`,
          boxShadow: "inset 0 0 0 0.12em rgb(255 255 255 / 0.25)",
        }}
      >
        {/* Sheen and pattern, like the real thing. */}
        <span className="absolute inset-0 bg-[linear-gradient(115deg,transparent_30%,rgb(255_255_255/0.28)_45%,transparent_60%)]" />
        <span className="absolute inset-0 bg-[repeating-linear-gradient(60deg,rgb(255_255_255/0.05)_0_2px,transparent_2px_12px)]" />
        {totm && (
          <span className="absolute inset-0 bg-[radial-gradient(circle_at_70%_25%,rgb(242_193_78/0.35),transparent_55%),radial-gradient(circle_at_20%_85%,rgb(150_80_255/0.35),transparent_60%)]" />
        )}
        {totw && (
          <span className="absolute inset-0 bg-[radial-gradient(circle_at_70%_25%,rgb(255_90_31/0.45),transparent_60%)]" />
        )}
        {rising && (
          <span className="absolute inset-0 bg-[radial-gradient(circle_at_70%_25%,rgb(62_230_176/0.4),transparent_60%),linear-gradient(0deg,rgb(62_230_176/0.18),transparent_40%)]" />
        )}
        {icon && (
          <span className="absolute inset-0 bg-[radial-gradient(circle_at_70%_25%,rgb(255_255_255/0.8),transparent_55%),radial-gradient(circle_at_20%_90%,rgb(168_129_31/0.35),transparent_60%)]" />
        )}
        <span
          className="absolute inset-[0.35em]"
          style={{
            clipPath: CARD_SHAPE,
            boxShadow: `inset 0 0 0 0.08em ${line}`,
          }}
        />

        {/* Rating, role and team down the left; the photo on the right. */}
        <div className="absolute top-[1.4em] left-[1.5em] flex w-[3.2em] flex-col items-center">
          <span className="font-display text-[3em] leading-[0.85]">
            {card.overall}
          </span>
          <span className="mt-[0.15em] font-display text-[1.05em] tracking-wider uppercase">
            {roleShort(card.role)}
          </span>
          <span
            className="mt-[0.35em] h-px w-[2.4em]"
            style={{ background: ink, opacity: 0.35 }}
          />
          {card.team &&
            (card.team.logo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={card.team.logo}
                alt={card.team.name}
                className="mt-[0.45em] h-[2em] w-[2em] object-contain"
              />
            ) : (
              <span
                className="mt-[0.45em] flex h-[2em] min-w-[2em] items-center justify-center px-[0.2em] font-display text-[0.8em] text-white"
                style={{
                  background: card.team.primary_color || "#181b26",
                  clipPath: "polygon(0 0, 100% 0, 100% 78%, 78% 100%, 0 100%)",
                }}
                title={card.team.name}
              >
                {(card.team.tag || card.team.name).slice(0, 4).toUpperCase()}
              </span>
            ))}
          {card.overall_change ? (
            <span
              className={`mt-[0.4em] text-[0.7em] font-bold ${card.overall_change > 0 ? "text-ok" : "text-bad"}`}
              style={
                totw || totm || rising
                  ? undefined
                  : { textShadow: "0 0 2px rgb(0 0 0 / 0.35)" }
              }
            >
              {changeText(card.overall_change)}
            </span>
          ) : null}
        </div>
        <div className="absolute top-[1.1em] right-[1.1em] h-[7.4em] w-[7.6em]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={card.photo || BLANK_PHOTO}
            alt=""
            className="h-full w-full object-cover object-top"
            style={{
              maskImage: "linear-gradient(180deg, black 70%, transparent)",
              WebkitMaskImage:
                "linear-gradient(180deg, black 70%, transparent)",
            }}
            loading="lazy"
          />
        </div>

        {/* Positions sit on plain wrappers: an em inside a resized text element is its own em. */}
        <div className="absolute inset-x-[0.8em] top-[8.75em]">
          <p className="truncate text-center font-display text-[1.45em] leading-none tracking-wide uppercase">
            {card.name}
          </p>
        </div>
        <span
          className="absolute inset-x-[2em] top-[10.5em] h-px"
          style={{ background: ink, opacity: 0.35 }}
        />

        <div
          className={`absolute inset-x-[1.6em] grid grid-cols-2 gap-x-[1em] ${extras.length ? "top-[10.8em] gap-y-[0.05em]" : "top-[11em] gap-y-[0.2em]"}`}
        >
          {main.map((s) => (
            <Stat key={s.key} stat={s} ink={ink} />
          ))}
        </div>
        {extras.length > 0 && (
          <div
            className="absolute inset-x-[2.3em] top-[15.15em] grid grid-cols-2 gap-x-[1em] border-t pt-[0.1em]"
            style={{
              borderColor: `color-mix(in srgb, ${ink} 35%, transparent)`,
            }}
          >
            {extras.map((s) => (
              <Stat key={s.key} stat={s} ink={ink} />
            ))}
          </div>
        )}
        <div className="absolute inset-x-0 bottom-[1.3em]">
          <p className="text-center text-[0.5em] font-bold tracking-[0.25em] uppercase opacity-70">
            {cardFooter(card)}
          </p>
        </div>
      </div>
    </div>
  );
}

function Stat({ stat, ink }: { stat: CardStat; ink: string }) {
  const change = stat.change && !stat.stale ? stat.change : 0;
  return (
    <span
      className={`flex items-baseline gap-[0.3em] ${stat.stale ? "opacity-55" : ""}`}
      title={`${stat.label}: ${stat.detail}`}
    >
      <span className="w-[1.4em] text-right font-display text-[1.15em] leading-tight">
        {stat.rating ?? "–"}
      </span>
      <span
        className="font-display text-[0.95em] tracking-wide uppercase"
        style={{ color: stat.extra ? undefined : ink }}
      >
        {stat.key}
      </span>
      {change !== 0 && (
        <span
          className={`text-[0.55em] font-bold ${change > 0 ? "text-ok" : "text-bad"}`}
        >
          {change > 0 ? "▲" : "▼"}
        </span>
      )}
    </span>
  );
}
