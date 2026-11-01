"""Daily player cards: a player's card for one match day, made from that day's matches only,
so a team can see who was in form today and not over the last four weeks.

They look like the weekly cards (``apps.results.cards``): the same role, stats and weights,
but every stat compares the player with everyone who played that day. A player needs
``DAY_MIN`` matches that day for a card; with fewer, only the day's numbers are kept. Both
sessions of a day (8PM and 10PM) make one card.

Only the player's own team (and league staff) can see them.

Design: /mnt/project-files/design/DAILY-CARDS.md (Habeeb approved 2026-11-01).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from datetime import date

from django.db import transaction
from django.db.models import Max

from apps.league.models import Match, Player

from . import cards
from .awards import _weapon_classes, match_date, matches_between, published
from .models import CardWeights, PlayerCard, PlayerDayCard, PlayerMatchRating, PlayerMatchResult

log = logging.getLogger(__name__)

RULES = "day-cards-v1"
DAY_MIN = 2  # matches in the day for a card, and for each stat's data


def _roles(players: dict[int, Player], day: date) -> dict[int, str]:
    """Each player's role on their weekly card (staff's pick first)."""
    roles = {pid: p.card_role for pid, p in players.items() if p.card_role}
    rest = [pid for pid in players if pid not in roles]
    for card in PlayerCard.objects.filter(player__in=rest, week__lte=cards.card_week(day)).order_by(
        "player", "-week"
    ):
        roles.setdefault(card.player_id, card.role)
    return roles


def _stamp(day: date, matches: list[Match]) -> str:
    """A fingerprint of everything the day's cards come from."""
    ids = [m.pk for m in matches]
    players = sorted(
        set(PlayerMatchResult.objects.filter(match__in=ids).values_list("player_id", flat=True))
    )
    saved = CardWeights.objects.first()
    text = json.dumps(
        [
            RULES,
            cards.RULES,
            saved.updated_at if saved else None,
            sorted((m.pk, m.updated_at) for m in matches),
            sorted(
                set(PlayerMatchRating.objects.filter(match__in=ids).values_list("match", "stamp"))
            ),
            sorted(Player.objects.filter(pk__in=players).values_list("pk", "card_role")),
            PlayerCard.objects.filter(player__in=players, week__lte=cards.card_week(day)).aggregate(
                t=Max("updated_at")
            )["t"],
        ],
        default=str,
    )
    return hashlib.md5(text.encode()).hexdigest()


def build_day(day: date, stamp: str | None = None) -> int:
    """Every player's card for ``day``. Returns how many players have a row."""
    matches = matches_between(day, day)
    if not matches:
        PlayerDayCard.objects.filter(day=day).delete()
        return 0
    stamp = stamp or _stamp(day, matches)
    classes = _weapon_classes()
    version = hashlib.md5(json.dumps(sorted(classes.items())).encode()).hexdigest()[:10]
    cards._fresh_reviews([m.pk for m in matches])

    windows: dict[int, cards.Window] = defaultdict(cards.Window)
    for m in matches:
        for pid, line in cards._cached(m, classes, version).items():
            windows[pid].add(line, 1, True)
    players = Player.objects.in_bulk(list(windows))
    windows = {pid: w for pid, w in windows.items() if pid in players and w.n}

    rated = {pid: w for pid, w in windows.items() if w.n >= DAY_MIN}
    roles = _roles(players, day)
    naders = {pid for pid in rated if roles.get(pid) == cards.GRENADER_ROLE}
    places = cards.rate_windows(rated, naders, least=DAY_MIN)
    ws = cards.weights()

    ratings: dict[int, list[float]] = defaultdict(list)
    for pid, r in PlayerMatchRating.objects.filter(match__in=matches).values_list(
        "player_id", "rating"
    ):
        ratings[pid].append(r)

    with transaction.atomic():
        PlayerDayCard.objects.filter(day=day).exclude(player__in=list(windows)).delete()
        for pid, w in windows.items():
            s = w.sums
            mine = places.get(pid, {})
            role = roles.get(pid) or cards.suggest_role(w, mine, DAY_MIN)
            stats, ovr = [], None
            if pid in rated:
                for key in cards.ROLE_STATS[role]:
                    value, detail = cards._detail(key, w)
                    ok = key in mine
                    stats.append(
                        {
                            "key": key,
                            "rating": cards.rating(mine[key]) if ok else None,
                            "change": None,
                            "stale": not ok,
                            "extra": key in cards.EXTRAS.get(role, ()),
                            "value": value if ok else None,
                            "detail": detail if ok else "Not enough of this data today",
                        }
                    )
                ovr = cards.overall(stats, ws[role])
            day_ratings = ratings.get(pid)
            PlayerDayCard.objects.update_or_create(
                player_id=pid,
                day=day,
                defaults=dict(
                    team_id=max(w.teams, key=w.teams.get) if w.teams else
                    players[pid].current_team_id,
                    role=role, overall=ovr, stats=stats if ovr is not None else [],
                    matches=w.n, kills=round(s["kills"]), knocks=round(s["knocks"]),
                    damage=round(s["damage"]) if w.counts["damage"] else None,
                    rating=round(sum(day_ratings) / len(day_ratings), 1) if day_ratings else None,
                    stamp=stamp, rules=RULES,
                ),
            )  # fmt: skip
    return len(windows)


def refresh(matches: list[Match] | None = None, force: bool = False) -> int:
    """Build the cards of every day with a new or changed match among ``matches`` (every
    published match when None, which also clears days that have none left). Returns days
    built."""
    if matches is None:
        matches = list(Match.objects.filter(published()).select_related("match_day"))
        days = {d for m in matches if (d := match_date(m))}
        PlayerDayCard.objects.exclude(day__in=days).delete()
    days = sorted({d for m in matches if (d := match_date(m))})
    have = defaultdict(set)
    for day, stamp in PlayerDayCard.objects.filter(day__in=days).values_list("day", "stamp"):
        have[day].add(stamp)
    done = 0
    for day in days:
        try:
            ms = matches_between(day, day)
            stamp = _stamp(day, ms) if ms else ""
            if not force and ms and have.get(day) == {stamp}:
                continue
            build_day(day, stamp or None)
            done += 1
        except Exception:  # one broken day must not stop the rest
            log.exception("Day cards for %s failed", day)
    return done
