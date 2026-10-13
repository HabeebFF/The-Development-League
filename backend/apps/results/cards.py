"""Player cards, FIFA Ultimate Team style: an overall rating, a role and six stats from 0 to
99 (grenaders get Grenade as an extra), rebuilt every week from what the logs recorded.

A card for the week starting on Monday ``week`` looks at the four weeks up to and including
it; matches in that week count double. Every stat compares the player with every other
player who has enough matches in the same window:

1. A number per match (or a rate), pulled towards the league average as if the player had
   played ``PRIOR`` extra average matches, so one lucky night can't give a 99.
2. Their place among everyone (0 = league worst, 1 = league best), turned into
   ``40 + 59 x place``. Grenade is the exception: naders are placed among naders only, since
   next to players who hardly throw anything every nader would sit near 99.

Some stats need data not every match has. Grenade and sniping need the weapon, so
they only use matches where most kills have one (Day 15 logged many without); close quarters
and utility need the replay files. A stat without enough such matches keeps last week's
rating, marked stale.

Design: /mnt/project-files/design/FUT-CARDS.md (Habeeb approved 2026-10-11).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.league.models import Match, Player

from .awards import GRENADER, _weapon_classes, match_lines, matches_between, period_of
from .models import CardWeights, MatchEvent, PlayerCard, PlayerMatchResult

RULES = "cards-v2"  # v2: Grenade counts knocks, naders ranked among naders, no Utility
WINDOW_WEEKS = 4
RECENT_WEIGHT = 2  # the week the card is for counts this many times
MIN_MATCHES = 4  # matches (of the kind a stat needs) before a stat is rated
PRIOR = 3  # extra average matches every player is given
PRIOR_EVENTS = 5  # the same for rates: extra average knocks, chances or kills
FLOOR, SPAN = 40, 59
WEAPON_COVERAGE = 0.7  # share of a match's kills that must have a weapon
LONG_M = 80.0  # a long-range kill
SNIPE_FALLBACK_M = 120.0  # a kill this far with no weapon logged counts as a snipe
SNIPERS = {"SNIPER", "MARKSMAN"}

RUSHER, GRENADER_ROLE, SNIPER, ALL_ROUNDER = "RUSHER", "GRENADER", "SNIPER", "ALL_ROUNDER"
ROLE_LABELS = {
    RUSHER: "Rusher",
    GRENADER_ROLE: "Grenader",
    SNIPER: "Sniper",
    ALL_ROUNDER: "All-rounder",
}

STATS = {
    "ENT": "Entry",
    "CQC": "Close quarters",
    "FIN": "Finishing",
    "AIM": "Aim",
    "TRD": "Trading",
    "SUR": "Survival",
    "AWR": "Awareness",
    "NAD": "Grenade",
    "UTL": "Utility",
    "SNP": "Sniping",
    "RNG": "Range",
}

ROLE_STATS = {
    RUSHER: ["ENT", "CQC", "FIN", "AIM", "TRD", "SUR"],
    GRENADER_ROLE: ["ENT", "CQC", "FIN", "AIM", "TRD", "SUR", "NAD"],
    SNIPER: ["SNP", "RNG", "AIM", "FIN", "AWR", "SUR"],
    ALL_ROUNDER: ["FIN", "AIM", "ENT", "TRD", "AWR", "SUR"],
}
EXTRAS = {GRENADER_ROLE: {"NAD"}}
# A nader: at least this share of their knocks and kills (in matches with weapons) came from
# grenades and launchers. Grenade is ranked among naders only.
NADER_SHARE = 0.15

DEFAULT_WEIGHTS = {
    RUSHER: {"CQC": 25, "ENT": 20, "FIN": 20, "AIM": 15, "TRD": 10, "SUR": 10},
    GRENADER_ROLE: {
        "NAD": 35,
        "CQC": 15,
        "FIN": 15,
        "ENT": 10,
        "AIM": 10,
        "TRD": 10,
        "SUR": 5,
    },  # fmt: skip
    SNIPER: {"SNP": 25, "RNG": 20, "AIM": 15, "FIN": 15, "AWR": 15, "SUR": 10},
    ALL_ROUNDER: {k: 1 for k in ROLE_STATS[ALL_ROUNDER]},
}


# Cards come out every Saturday at 11:00 in Lagos (10:00 UTC), for the week that ended the
# day before: a card week runs Saturday to Friday, so it takes in Friday night's scrims.
RELEASE_WEEKDAY = 5  # Saturday
RELEASE_UTC = time(10, 0)


def card_week(day: date) -> date:
    """The Saturday that starts the card week ``day`` is in."""
    return day - timedelta(days=(day.weekday() - RELEASE_WEEKDAY) % 7)


# Team of the Month stays locked until midnight in Lagos after the month's last day.
MONTH_TZ = "Africa/Lagos"


def month_opens(end: date) -> datetime:
    """When the Team of the Month for the month ending ``end`` can be turned over."""
    from zoneinfo import ZoneInfo

    return datetime.combine(end + timedelta(days=1), time(0), tzinfo=ZoneInfo(MONTH_TZ))


def release_of(week: date) -> datetime:
    """When the cards of the week starting ``week`` come out: the Saturday after it."""
    return datetime.combine(week + timedelta(days=7), RELEASE_UTC, tzinfo=UTC)


def tier(overall: int) -> str:
    return "gold" if overall >= 75 else "silver" if overall >= 65 else "bronze"


# -- One match ------------------------------------------------------------------------------


@dataclass
class MatchLine:
    """One player's numbers in one match, as the cards need them."""

    team: int | None = None
    kills: int = 0
    knocks: int = 0
    headshots: int = 0
    openings: int = 0
    deaths: int | None = None
    tracks: bool = False  # the match has the replay files: close knocks and utility count
    close_knocks: int = 0
    utility: int = 0
    weapons_ok: bool = False  # most of the match's kills have a weapon: nades and snipes count
    weapon_kills: int = 0  # kills in a weapons_ok match (what snipes and nades are out of)
    weapon_knocks: int = 0  # knocks in a weapons_ok match
    snipes: int = 0
    nades: int = 0
    nade_knocks: int = 0
    measured: int = 0  # kills with both positions logged
    long_kills: int = 0
    longest: float = 0.0
    review: bool = False  # the coach's after-match counts exist for this player
    alive_s: float | None = None
    trades: int = 0
    trade_chances: int = 0
    alone_downs: int = 0
    known_downs: int = 0
    first_down: bool = False


def lines_for_match(match: Match, classes: dict[int, str]) -> dict[int, MatchLine]:
    """Every player's numbers in ``match``, keyed by player id."""
    from apps.coach.models import MatchReview
    from apps.rotations.models import PlayerTrack

    base = match_lines(match, classes)
    tracks = PlayerTrack.objects.filter(match=match).exists()
    out: dict[int, MatchLine] = {}
    for pid, ln in base.items():
        out[pid] = MatchLine(
            team=ln.team,
            kills=ln.kills,
            knocks=ln.knocks,
            headshots=ln.headshots,
            openings=ln.openings,
            tracks=tracks,
            close_knocks=ln.close_knocks if tracks else 0,
        )
    for pid, deaths in PlayerMatchResult.objects.filter(match=match).values_list(
        "player_id", "deaths"
    ):
        if pid in out:
            out[pid].deaths = deaths

    kills = [
        e
        for e in MatchEvent.objects.filter(match=match, kind=MatchEvent.Kind.KILL)
        if e.actor_player_id is not None and e.actor_team_id != e.target_team_id
    ]
    with_weapon = sum(1 for e in kills if (e.weapon_id or 0) > 0)
    ok = bool(kills) and with_weapon / len(kills) >= WEAPON_COVERAGE
    for e in kills:
        line = out.setdefault(e.actor_player_id, MatchLine(tracks=tracks))
        line.weapons_ok = ok
        dist = None
        if None not in (e.x, e.z, e.tx, e.tz):
            dist = math.dist((e.x, e.z), (e.tx, e.tz))
            line.measured += 1
            line.long_kills += dist >= LONG_M
            line.longest = max(line.longest, dist)
        if not ok:
            continue
        kind = classes.get(e.weapon_id)
        line.weapon_kills += 1
        if kind in SNIPERS or ((e.weapon_id or 0) <= 0 and (dist or 0) >= SNIPE_FALLBACK_M):
            line.snipes += 1
        elif kind in GRENADER:
            line.nades += 1
    if ok:
        for e in MatchEvent.objects.filter(
            match=match, kind=MatchEvent.Kind.KNOCK, actor_player__isnull=False
        ):
            if e.actor_team_id == e.target_team_id:
                continue
            line = out.setdefault(e.actor_player_id, MatchLine(tracks=tracks))
            line.weapon_knocks += 1
            line.nade_knocks += classes.get(e.weapon_id) in GRENADER
    for line in out.values():
        line.weapons_ok = ok

    for review in MatchReview.objects.filter(match=match):
        for r in review.players:
            pid = r.get("player")
            if pid is None:
                continue
            line = out.setdefault(pid, MatchLine(team=review.team_id, tracks=tracks))
            line.review = True
            line.alive_s = r.get("alive_s")
            line.trades = r.get("trades") or 0
            line.trade_chances = r.get("trade_chances") or 0
            line.alone_downs = r.get("alone_downs") or 0
            line.known_downs = r.get("known_downs") or 0
            line.first_down = bool(r.get("first_down"))
            if tracks:
                line.utility = sum((r.get("utility") or {}).values())
    return out


def _cached(match: Match, classes: dict[int, str], version: str) -> dict[int, MatchLine]:
    key = f"cards:{RULES}:{match.pk}:{match.updated_at.timestamp()}:{version}"
    lines = cache.get(key)
    if lines is None:
        lines = lines_for_match(match, classes)
        cache.set(key, lines, 60 * 60 * 24)
    return lines


# -- Adding up a window ---------------------------------------------------------------------


@dataclass
class Window:
    """One player's weighted totals over the window. ``*_n`` are plain match counts."""

    n: int = 0
    week_n: int = 0
    m: float = 0.0
    teams: dict = field(default_factory=lambda: defaultdict(float))
    sums: dict = field(default_factory=lambda: defaultdict(float))
    counts: dict = field(default_factory=lambda: defaultdict(int))
    longest: float = 0.0

    def add(self, line: MatchLine, w: float, recent: bool) -> None:
        s, c = self.sums, self.counts
        self.n += 1
        self.week_n += recent
        self.m += w
        if line.team:
            self.teams[line.team] += w
        for k in ("kills", "knocks", "headshots", "openings", "measured", "long_kills"):
            s[k] += w * getattr(line, k)
        if line.deaths is not None:
            s["deaths"] += w * line.deaths
            s["deaths_m"] += w
            c["deaths"] += 1
        if line.tracks:
            s["close"] += w * line.close_knocks
            s["utility"] += w * line.utility
            s["tracks_m"] += w
            c["tracks"] += 1
        if line.weapons_ok:
            s["snipes"] += w * line.snipes
            s["nades"] += w * line.nades
            s["nade_knocks"] += w * line.nade_knocks
            s["weapon_knocks"] += w * line.weapon_knocks
            s["weapon_kills"] += w * line.weapon_kills
            s["weapons_m"] += w
            c["weapons"] += 1
        if line.review:
            for k in ("trades", "trade_chances", "alone_downs", "known_downs"):
                s[k] += w * getattr(line, k)
            s["first_downs"] += w * line.first_down
            s["review_m"] += w
            c["review"] += 1
            if line.alive_s is not None:
                s["alive"] += w * line.alive_s
                s["alive_m"] += w
                c["alive"] += 1
        c["measured"] += line.measured
        self.longest = max(self.longest, line.longest)


# Each stat is one or more parts: (kind, numerator, denominator, count needed, weight, sign).
# "per": numerator per (weighted) match; "rate": numerator over denominator; "max": longest.
PARTS = {
    "ENT": [("per", "openings", "m", "n", 1, 1)],
    "CQC": [("per", "close", "tracks_m", "tracks", 1, 1)],
    "FIN": [("per", "kills", "m", "n", 0.7, 1), ("rate", "kills", "knocks", "n", 0.3, 1)],
    "AIM": [("rate", "headshots", "knocks", "n", 1, 1)],
    "TRD": [("rate", "trades", "trade_chances", "review", 1, 1)],
    "SUR": [
        ("per", "alive", "alive_m", "alive", 0.7, 1),
        ("per", "deaths", "deaths_m", "deaths", 0.3, -1),
    ],  # fmt: skip
    "AWR": [
        ("rate", "alone_downs", "known_downs", "review", 0.6, -1),
        ("per", "first_downs", "review_m", "review", 0.4, -1),
    ],  # fmt: skip
    "NAD": [
        ("per", "nade_knocks", "weapons_m", "weapons", 0.7, 1),
        ("per", "nades", "weapons_m", "weapons", 0.3, 1),
    ],  # fmt: skip
    "UTL": [("per", "utility", "tracks_m", "tracks", 1, 1)],
    "SNP": [("per", "snipes", "weapons_m", "weapons", 1, 1)],
    "RNG": [
        ("rate", "long_kills", "measured", "measured", 0.85, 1),
        ("max", "longest", None, "measured", 0.15, 1),
    ],  # fmt: skip
}
# How many of a thing must be behind a part ("measured" counts kills, not matches).
NEEDS = {"measured": 3}


def _count(w: Window, need: str) -> int:
    return w.n if need == "n" else w.counts[need]


def _part_value(w: Window, part, league: dict[str, float]) -> float | None:
    kind, num, den, need, _, sign = part
    if _count(w, need) < NEEDS.get(need, MIN_MATCHES):
        return None
    if kind == "max":
        return sign * w.longest
    top, bottom = w.sums[num], w.m if den == "m" else w.sums[den]
    prior = league.get(f"{num}/{den}", 0.0)
    extra = PRIOR if kind == "per" else PRIOR_EVENTS
    return sign * (top + prior * extra) / (bottom + extra)


def _place(value: float, pool: list[float]) -> float:
    """0 for the lowest value in ``pool``, 1 for the highest (ties share the middle)."""
    if len(pool) < 2:
        return 0.5
    less = sum(1 for v in pool if v < value)
    equal = sum(1 for v in pool if v == value)
    return (less + (equal - 1) / 2) / (len(pool) - 1)


def is_nader(w: Window) -> bool:
    """At least ``NADER_SHARE`` of their knocks and kills came from grenades and launchers."""
    s = w.sums
    total = s["weapon_kills"] + s["weapon_knocks"]
    return (
        w.counts["weapons"] >= MIN_MATCHES
        and total >= 5
        and (s["nades"] + s["nade_knocks"]) / total >= NADER_SHARE
    )


def rate_windows(
    windows: dict[int, Window], naders: set[int] | None = None
) -> dict[int, dict[str, float]]:
    """Each player's place (0 to 1) in every stat they have enough matches for. With
    ``naders``, those players' Grenade is placed among themselves only."""
    league: dict[str, float] = {}
    for parts in PARTS.values():
        for kind, num, den, *_ in parts:
            if kind == "max":
                continue
            top = sum(w.sums[num] for w in windows.values())
            bottom = sum(w.m if den == "m" else w.sums[den] for w in windows.values())
            league[f"{num}/{den}"] = top / bottom if bottom else 0.0

    places: dict[int, dict[str, float]] = defaultdict(dict)
    for key, parts in PARTS.items():
        values = [{pid: _part_value(w, p, league) for pid, w in windows.items()} for p in parts]
        pools = [[v for v in vals.values() if v is not None] for vals in values]
        group = set(naders or ()) & set(windows) if key == "NAD" else set()
        own = [[vals[pid] for pid in group if vals[pid] is not None] for vals in values]
        for pid in windows:
            mine = own if pid in group and all(len(p) >= 2 for p in own) else pools
            got = [
                (p[4], _place(vals[pid], pool))
                for p, vals, pool in zip(parts, values, mine, strict=True)
                if vals[pid] is not None
            ]
            # Every part of a stat is needed, except a range tie-break without the main part.
            if len(got) == len(parts) or (key == "SUR" and got):
                places[pid][key] = sum(w * x for w, x in got) / sum(w for w, _ in got)
    return places


def rating(place: float) -> int:
    return round(FLOOR + SPAN * place)


def suggest_role(w: Window, places: dict[str, float]) -> str:
    """What the numbers say this player plays as."""
    weapon_kills = w.sums["weapon_kills"]
    if w.counts["weapons"] >= MIN_MATCHES and weapon_kills >= 5:
        if w.sums["snipes"] / weapon_kills > 0.3:
            return SNIPER
    if is_nader(w):
        return GRENADER_ROLE
    rush = [places[k] for k in ("ENT", "CQC") if k in places]
    if rush and sum(rush) / len(rush) >= 0.5:
        return RUSHER
    return ALL_ROUNDER


def _detail(key: str, w: Window) -> tuple[str, str]:
    """The plain numbers behind a stat: a short value and a sentence."""
    s, c = w.sums, w.counts

    def per(num: str, den: str = "m") -> float:
        bottom = w.m if den == "m" else s[den]
        return s[num] / bottom if bottom else 0.0

    def pct(num: str, den: str) -> str:
        return f"{round(100 * s[num] / s[den])}%" if s[den] else "n/a"

    if key == "ENT":
        return f"{per('openings'):.1f}", f"{per('openings'):.1f} fights opened a match"
    if key == "CQC":
        v = per("close", "tracks_m")
        return f"{v:.1f}", f"{v:.1f} knocks from 15 m or closer a match ({c['tracks']} replays)"
    if key == "FIN":
        conv = f"{s['kills'] / s['knocks']:.1f}" if s["knocks"] else "n/a"
        return f"{per('kills'):.1f}", f"{per('kills'):.1f} kills a match, {conv} kills per knock"
    if key == "AIM":
        return pct("headshots", "knocks"), f"{pct('headshots', 'knocks')} of knocks were headshots"
    if key == "TRD":
        if not s["trade_chances"]:
            return "n/a", "No teammate was knocked near them yet, so nothing to trade"
        return pct("trades", "trade_chances"), (
            f"Hit back within seconds after {pct('trades', 'trade_chances')} of nearby"
            " teammate knocks"
        )
    if key == "SUR":
        deaths = f"{per('deaths', 'deaths_m'):.1f} deaths a match" if s["deaths_m"] else ""
        if not s["alive_m"]:
            return f"{per('deaths', 'deaths_m'):.1f}", deaths
        alive = per("alive", "alive_m")
        clock = f"{int(alive // 60)}:{int(alive % 60):02d}"
        return clock, f"Alive {clock} on average" + (f", {deaths}" if deaths else "")
    if key == "AWR":
        if not s["known_downs"]:
            return "0%", (
                f"Never knocked where we could tell, team's first down in"
                f" {pct('first_downs', 'review_m')} of matches"
            )
        return pct("alone_downs", "known_downs"), (
            f"Caught alone in {pct('alone_downs', 'known_downs')} of knocks, team's first down"
            f" in {pct('first_downs', 'review_m')} of matches"
        )
    if key == "NAD":
        knocks, kills = per("nade_knocks", "weapons_m"), per("nades", "weapons_m")
        return (
            f"{knocks + kills:.1f}",
            f"{knocks:.1f} knocks and {kills:.1f} kills a match with grenades and launchers",
        )
    if key == "UTL":
        v = per("utility", "tracks_m")
        return f"{v:.1f}", f"{v:.1f} UAVs, Bolt Makers and Dinoculars used a match"
    if key == "SNP":
        v = per("snipes", "weapons_m")
        return f"{v:.1f}", f"{v:.1f} sniper and marksman kills a match"
    long = pct("long_kills", "measured")
    return long, f"{long} of kills from {LONG_M:g} m or further, longest {w.longest:.0f} m"


# -- Building a week ------------------------------------------------------------------------


def weights() -> dict[str, dict[str, float]]:
    saved = CardWeights.objects.first()
    out = {role: dict(ws) for role, ws in DEFAULT_WEIGHTS.items()}
    for role, ws in ((saved.weights if saved else None) or {}).items():
        if role in out:
            # A saved role replaces its defaults: a stat staff left out counts for nothing.
            out[role] = {k: float(ws.get(k, 0)) for k in ROLE_STATS[role]}
            if role == GRENADER_ROLE and "UTL" in ws:
                # Utility left the grenader card (cards-v2); its share went to Grenade.
                out[role]["NAD"] += float(ws["UTL"])
    return out


def overall(stats: list[dict], ws: dict[str, float]) -> int | None:
    rated = [(ws.get(s["key"], 0), s["rating"]) for s in stats if s["rating"] is not None]
    total = sum(w for w, _ in rated)
    return round(sum(w * r for w, r in rated) / total) if total else None


def windows_for(week: date) -> dict[int, Window]:
    start = week - timedelta(weeks=WINDOW_WEEKS - 1)
    end = week + timedelta(days=6)
    classes = _weapon_classes()
    version = hashlib.md5(json.dumps(sorted(classes.items())).encode()).hexdigest()[:10]
    _fresh_reviews([m.pk for m in matches_between(start, end)])
    windows: dict[int, Window] = defaultdict(Window)
    from .awards import match_date

    for m in matches_between(start, end):
        recent = match_date(m) >= week
        for pid, line in _cached(m, classes, version).items():
            windows[pid].add(line, RECENT_WEIGHT if recent else 1, recent)
    return dict(windows)


def _fresh_reviews(match_ids: list[int]) -> None:
    """The coach's after-match counts (trades, time alive...) for every match in the window."""
    from apps.coach import moments
    from apps.coach.models import MatchReview

    fresh = set(
        MatchReview.objects.filter(match__in=match_ids, rules=moments.RULES).values_list(
            "match_id", flat=True
        )
    )
    for pk in match_ids:
        if pk not in fresh:
            try:
                moments.save_reviews(pk)
            except Exception:  # a review that can't be built only leaves those stats out
                import logging

                logging.getLogger(__name__).exception("Review for match %s failed", pk)


def _week_winners(week: date) -> dict[int, list[str]]:
    """The award winners over the card's own week (Saturday to Friday)."""
    from .awards import awards

    won: dict[int, list[str]] = defaultdict(list)
    for a in awards("week", week, between=(week, week + timedelta(days=6)))["awards"]:
        if a["top"] and a["top"][0].get("player_id"):
            won[a["top"][0]["player_id"]].append(a["key"])
    return won


def build_week(week: date) -> int:
    """Every player's card for the week starting ``week`` (any day in it is fine)."""
    week = card_week(week)
    windows = windows_for(week)
    players = Player.objects.in_bulk(list(windows))
    rated = {pid: w for pid, w in windows.items() if w.n >= MIN_MATCHES}
    naders = {
        pid
        for pid, w in rated.items()
        if pid in players
        and (players[pid].card_role or (GRENADER_ROLE if is_nader(w) else "")) == GRENADER_ROLE
    }
    places = rate_windows(rated, naders)
    ws = weights()
    winners = _week_winners(week)
    previous = {}
    for card in PlayerCard.objects.filter(player__in=list(windows), week__lt=week).order_by(
        "player", "-week"
    ):
        previous.setdefault(card.player_id, card)

    built = 0
    with transaction.atomic():
        PlayerCard.objects.filter(week=week).exclude(player__in=list(windows)).delete()
        for pid, w in windows.items():
            player, before = players.get(pid), previous.get(pid)
            if player is None or w.week_n == 0:
                # Didn't play this week: no card for it (their last card still shows).
                PlayerCard.objects.filter(player_id=pid, week=week).delete()
                continue
            team = max(w.teams, key=w.teams.get) if w.teams else player.current_team_id
            if w.n < MIN_MATCHES:
                if before is None:
                    PlayerCard.objects.filter(player_id=pid, week=week).delete()
                    continue
                stats = [{**s, "change": 0, "stale": True} for s in before.stats]
                PlayerCard.objects.update_or_create(
                    player_id=pid,
                    week=week,
                    defaults=dict(
                        team_id=team, role=before.role, role_suggested=before.role_suggested,
                        suggested_role=before.suggested_role, overall=before.overall,
                        overall_change=0, stats=stats, matches=w.n, week_matches=w.week_n,
                        stale=True, totw=winners.get(pid, []), rules=RULES,
                    ),
                )  # fmt: skip
                built += 1
                continue

            mine = places.get(pid, {})
            suggested = suggest_role(w, mine)
            role = player.card_role or suggested
            old = {s["key"]: s for s in before.stats} if before else {}
            stats = []
            for key in ROLE_STATS[role]:
                value, detail = _detail(key, w)
                if key in mine:
                    r, stale = rating(mine[key]), False
                else:
                    r, stale = (old.get(key) or {}).get("rating"), True
                was = (old.get(key) or {}).get("rating")
                stats.append(
                    {
                        "key": key,
                        "rating": r,
                        "change": r - was if None not in (r, was) else None,
                        "stale": stale,
                        "extra": key in EXTRAS.get(role, ()),
                        "value": value if not stale else None,
                        "detail": detail if not stale else "Not enough matches with this data yet",
                    }
                )
            ovr = overall(stats, ws[role])
            if ovr is None:
                continue
            PlayerCard.objects.update_or_create(
                player_id=pid,
                week=week,
                defaults=dict(
                    team_id=team, role=role, role_suggested=not player.card_role,
                    suggested_role=suggested, overall=ovr,
                    overall_change=ovr - before.overall if before else None, stats=stats,
                    matches=w.n, week_matches=w.week_n, stale=False,
                    totw=winners.get(pid, []), rules=RULES,
                ),
            )  # fmt: skip
            built += 1
    mark_specials(week)
    return built


# -- Rising Stars and Icons -----------------------------------------------------------------
# Design: /mnt/project-files/design/CARD-REVEALS.md (Habeeb approved 2026-10-12).

RISING_STAR, ICON = "rising_star", "icon"
RISING_MAX = 3  # Rising Stars a week at most: the biggest jumps


def thresholds() -> dict[str, int]:
    """Staff's bars for Rising Stars and Icons (the model's defaults until they save some)."""
    saved = CardWeights.objects.first() or CardWeights()
    return {k: getattr(saved, k) for k in ("rising_min", "icon_min", "icon_weeks")}


def mark_specials(week: date) -> None:
    """The week's Rising Stars (the biggest jumps in overall since the player's last card, if
    big enough) and Icons (``icon_min`` or better for ``icon_weeks`` weeks in a row). Only
    real cards count: a card carried over for too few matches neither rises nor keeps a
    streak going."""
    week = card_week(week)
    bar = thresholds()
    this = list(PlayerCard.objects.filter(week=week).select_related("player"))
    earlier: dict[int, dict[date, PlayerCard]] = defaultdict(dict)
    before_this = PlayerCard.objects.filter(player__in=[c.player_id for c in this], week__lt=week)
    for c in before_this.only("player_id", "week", "overall", "stale"):
        earlier[c.player_id][c.week] = c

    rising: list[tuple[int, PlayerCard]] = []
    for c in this:
        mine = earlier[c.player_id]
        c.streak, at = 0, c
        while at is not None and not at.stale and at.overall >= bar["icon_min"]:
            c.streak += 1
            at = mine.get(at.week - timedelta(weeks=1))
        c.special = ICON if c.streak >= bar["icon_weeks"] else ""
        c.rise = None
        before = mine[max(mine)] if mine else None
        if (
            c.special != ICON
            and before is not None
            and not (before.stale or c.stale or c.player.hide_card)
            and c.week_matches >= MIN_MATCHES
            and c.overall - before.overall >= bar["rising_min"]
        ):
            rising.append((c.overall - before.overall, c))
    rising.sort(key=lambda x: (-x[0], -x[1].overall, x[1].player.display_name.casefold()))
    for rise, c in rising[:RISING_MAX]:
        c.special, c.rise = RISING_STAR, rise
    PlayerCard.objects.bulk_update(this, ["special", "rise", "streak"])


def icon_hall() -> list[dict]:
    """Every run of Icon weeks, player by player: the current Icons first, then the longest."""
    runs: list[dict] = []
    for c in (
        PlayerCard.objects.filter(special=ICON, player__hide_card=False)
        .select_related("player")
        .order_by("player", "week")
    ):
        last = runs[-1] if runs else None
        if last and last["player"] == c.player and last["to"] + timedelta(weeks=1) == c.week:
            last.update(to=c.week, weeks=last["weeks"] + 1, best=max(last["best"], c.overall))
        else:
            runs.append({"player": c.player, "from": c.week, "to": c.week, "weeks": 1,
                         "best": c.overall})  # fmt: skip
    latest = PlayerCard.objects.order_by("-week").values_list("week", flat=True).first()
    for r in runs:
        r["current"] = r["to"] == latest
    return sorted(runs, key=lambda r: (not r["current"], -r["weeks"], -r["best"]))


def weeks_with_matches(now: datetime | None = None) -> list[date]:
    """Every card week with a published match that is already out (its Saturday release has
    passed), oldest first."""
    from .awards import match_date

    days = {
        match_date(m)
        for m in Match.objects.filter(status=Match.Status.PUBLISHED).select_related("match_day")
    }
    now = now or timezone.now()
    return sorted({w for w in (card_week(d) for d in days if d) if release_of(w) <= now})


# -- Team of the Week -----------------------------------------------------------------------


def team_of_week(week: date) -> list[dict]:
    """The week's award winners on their card for it; a winner without a card (or a hidden
    one) gives the slot to the next player in that award."""
    from .awards import awards

    week = card_week(week)
    by_player = {
        c.player_id: c
        for c in PlayerCard.objects.filter(week=week, player__hide_card=False).select_related(
            "player", "team"
        )
    }
    slots = []
    for a in awards("week", week, between=(week, week + timedelta(days=6)))["awards"]:
        person = next((p for p in a["top"] if p.get("player_id") in by_player), None)
        slots.append(
            {
                "award": a["key"],
                "title": a["title"],
                "detail": person["detail"] if person else a.get("blocked", ""),
                "card": by_player[person["player_id"]] if person else None,
            }
        )
    return slots


# -- Team of the Month ----------------------------------------------------------------------


def team_of_month(day: date) -> list[dict]:
    """The month's award winners (top player, rusher, sniper, grenader), each with the card
    they ended the month on: their latest card from a week that touches the month. A winner
    with no card, or a hidden one, gives the slot to the next player in that award."""
    from .awards import awards

    start, end = period_of("month", day)
    slots = []
    for a in awards("month", start)["awards"]:
        pick = None
        for person in a["top"]:
            pick = (
                PlayerCard.objects.filter(
                    player_id=person.get("player_id"),
                    player__hide_card=False,
                    week__gte=start - timedelta(days=6),
                    week__lte=end,
                )
                .select_related("player", "team")
                .order_by("-week")
                .first()
            )
            if pick:
                slots.append(
                    {
                        "award": a["key"],
                        "title": a["title"],
                        "detail": person["detail"],
                        "card": pick,
                    }
                )
                break
        if pick is None:
            slots.append(
                {
                    "award": a["key"],
                    "title": a["title"],
                    "detail": a.get("blocked", ""),
                    "card": None,
                }
            )
    return slots


def months_with_cards() -> list[date]:
    """The first day of every month with a match on a built card week, newest first."""
    from .awards import match_date

    weeks = set(PlayerCard.objects.values_list("week", flat=True).distinct())
    days = {
        match_date(m)
        for m in Match.objects.filter(status=Match.Status.PUBLISHED).select_related("match_day")
    }
    return sorted({d.replace(day=1) for d in days if d and card_week(d) in weeks}, reverse=True)
