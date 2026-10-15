"""Settling, voiding and correcting markets.

Staff confirm every result. The site suggests one from the published match (the evidence),
and staff must give a reason to settle any other way. Each decision is a new ``Settlement``
version; coins move through ``post_entry`` with keys that include the version, so repeating
a request never pays, refunds or corrects twice.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.league.models import Match, MatchDay, Team
from apps.results.models import MatchEvent, PlayerMatchResult, StandingRow, TeamMatchResult
from apps.results.standings import Tally, rank

from .markets import (
    BANDS,
    DEAD_HEAT,
    H2H,
    HANDICAPS,
    PLAYER_MARKETS,
    RANGE_MARKETS,
    SEASON_MARKETS,
    SESSION_MARKETS,
    MarketError,
    dead_heat_return,
)
from .models import Bet, Market, MarketEvent, Outcome, Settlement, Wallet
from .services import Kind, post_entry

C = Market.Category
S = Market.Status
B = Bet.Status


# -- the suggested result ------------------------------------------------------------------------


def linked_match(market: Market) -> Match:
    """The published match a match-level market is about; raises ``MarketError`` if not ready."""
    fixture = market.fixture
    if fixture is None or fixture.match_number is None:
        raise MarketError("This market isn't about one match.", "not_ready")
    if fixture.match_id is None:
        raise MarketError("Link the fixture to its uploaded match first.", "not_ready")
    match = fixture.match
    if match.status != Match.Status.PUBLISHED:
        raise MarketError("The match isn't published yet.", "not_ready")
    return match


def suggest(market: Market) -> dict:
    """What the published results say the result is.

    Returns ``{"kind", "winners": [outcome ids], "voids": [outcome ids], "dead_heat", "note",
    "evidence"}``. ``dead_heat`` is how many teams share the win (1 when nobody ties).
    """
    if market.category in SESSION_MARKETS:
        return _suggest_session(market)
    if market.category in SEASON_MARKETS:
        return _suggest_season(market)
    return _suggest_match(market)


def _settle(winners, voids=(), note="", evidence=None, dead_heat=1) -> dict:
    return {
        "kind": "SETTLE",
        "winners": [o.pk for o in winners],
        "voids": [o.pk for o in voids],
        "dead_heat": dead_heat,
        "note": note,
        "evidence": evidence or {},
    }


def _void(note: str, evidence=None) -> dict:
    return {
        "kind": "VOID",
        "winners": [],
        "voids": [],
        "dead_heat": 1,
        "note": note,
        "evidence": evidence or {},
    }


def _suggest_match(market: Market) -> dict:
    match = linked_match(market)
    outcomes = list(market.outcomes.all())
    rows = {
        r.team_id: r for r in TeamMatchResult.objects.filter(match=match).select_related("team")
    }
    evidence = {
        "match": match.pk,
        "match_title": str(match),
        "started_at": match.started_at.isoformat() if match.started_at else None,
        "teams_in_lobby": len(rows),
        "results": [
            {
                "team": r.team_id,
                "name": r.team.name,
                "placement": r.placement,
                "kills": r.kills,
                "points": r.total_points,
            }
            for r in sorted(rows.values(), key=lambda r: r.placement)
            if r.team_id in _teams(market)
        ],
    }
    if not rows:
        raise MarketError("The match has no results.", "not_ready")

    def by_team(team_id: int) -> Outcome:
        return next(o for o in outcomes if o.team_id == team_id)

    def void(note: str) -> dict:
        return _void(note, evidence)

    def settle(winners, voids=(), note="") -> dict:
        return _settle(winners, voids, note, evidence)

    if market.category == C.BOOYAH:
        absent = [o for o in outcomes if o.team_id not in rows]
        first = next((r for r in rows.values() if r.placement == 1), None)
        winners = [by_team(first.team_id)] if first and first.team_id in _teams(market) else []
        note = "" if winners else "The Booyah team isn't one of the choices: every bet loses."
        if absent:
            note = (note + " " if note else "") + "Teams that didn't play are refunded."
        return settle(winners, absent, note.strip())

    if market.category == C.TOP_N:
        row = rows.get(market.params["team"])
        if row is None:
            return void("The team didn't play: everyone is refunded.")
        code = "yes" if row.placement <= market.params["n"] else "no"
        return settle([next(o for o in outcomes if o.code == code)])

    if market.category in H2H:
        a, b = market.params["teams"]
        if a not in rows or b not in rows:
            return void("One of the teams didn't play: everyone is refunded.")
        if market.category == C.H2H_PLACEMENT:
            winner = a if rows[a].placement < rows[b].placement else b
        else:
            field = "kills" if market.category == C.H2H_KILLS else "total_points"
            va, vb = getattr(rows[a], field), getattr(rows[b], field)
            if va == vb:
                return void("A tie: everyone is refunded.")
            winner = a if va > vb else b
        return settle([by_team(winner)])

    if market.category == C.TEAM_KILLS:
        row = rows.get(market.params["team"])
        if row is None:
            return void("The team didn't play: everyone is refunded.")
        code = "yes" if row.kills >= market.params["line"] else "no"
        return settle([next(o for o in outcomes if o.code == code)], note=f"{row.kills} kills.")

    def by_code(code: str) -> Outcome:
        return next(o for o in outcomes if o.code == code)

    if market.category == C.TOTAL_KILLS:
        total = sum(r.kills for r in rows.values())
        evidence["total_kills"] = total
        code = "yes" if total >= market.params["line"] else "no"
        return settle([by_code(code)], note=f"{total} kills in the match.")

    if market.category in HANDICAPS:
        (a, b), line = market.params["teams"], market.params["line"]
        if a not in rows or b not in rows:
            return void("One of the teams didn't play: everyone is refunded.")
        field = "kills" if market.category == C.KILLS_HANDICAP else "total_points"
        lead = getattr(rows[a], field) - getattr(rows[b], field)
        # The first team gives a head start of line - 0.5, so there is never a tie.
        return settle([by_team(a if lead >= line else b)], note=f"Margin {lead:+d}.")

    if market.category == C.FINISH_BAND:
        row = rows.get(market.params["team"])
        if row is None:
            return void("The team didn't play: everyone is refunded.")
        code = next(c for c, (lo, hi) in BANDS.items() if lo <= row.placement <= hi)
        return settle([by_code(code)], note=f"Finished #{row.placement}.")

    if market.category == C.FIRST_OUT:
        last = max(r.placement for r in rows.values())
        out = next(r for r in rows.values() if r.placement == last)
        absent = [o for o in outcomes if o.team_id not in rows]
        winners = [by_team(out.team_id)] if out.team_id in _teams(market) else []
        notes = [f"{out.team.name} went out first (#{last})."]
        if not winners:
            notes.append("That team isn't one of the choices: every bet loses.")
        if absent:
            notes.append("Teams that didn't play are refunded.")
        return settle(winners, absent, " ".join(notes))

    if market.category == C.FIRST_BLOOD:
        first = (
            MatchEvent.objects.filter(
                match=match, kind=MatchEvent.Kind.KILL, game_time_s__isnull=False
            )
            .exclude(actor_team__isnull=True)
            .exclude(actor_team=F("target_team"))
            .select_related("actor_team")
            .order_by("game_time_s", "pk")
            .first()
        )
        if first is None:
            return void("The logs have no timed kills: everyone is refunded.")
        evidence["first_blood"] = {"team": first.actor_team_id, "at_s": first.game_time_s}
        absent = [o for o in outcomes if o.team_id not in rows]
        winners = [by_team(first.actor_team_id)] if first.actor_team_id in _teams(market) else []
        notes = [f"{first.actor_team.name} got the first kill at {first.game_time_s:.0f}s."]
        if not winners:
            notes.append("That team isn't one of the choices: every bet loses.")
        if absent:
            notes.append("Teams that didn't play are refunded.")
        return settle(winners, absent, " ".join(notes))

    if market.category in PLAYER_MARKETS:
        return _suggest_player(market, match, outcomes, evidence)

    raise MarketError("No automatic result for this kind of market.", "not_ready")


def _suggest_player(market: Market, match: Match, outcomes, evidence: dict) -> dict:
    """Player markets, settled from the match scoreboard and its events."""
    p = market.params
    listed = list(p.get("players") or [p["player"]])
    players = {
        r.player_id: r
        for r in PlayerMatchResult.objects.filter(match=match).select_related("player")
    }
    if not players:
        raise MarketError("The match has no player results.", "not_ready")
    evidence["players"] = [
        {
            "player": r.player_id,
            "name": r.display_name,
            "team": r.team_id,
            "kills": r.kills,
            "damage": r.damage_dealt,
        }
        for pid, r in players.items()
        if pid in listed
    ]
    by_player = {o.player_id: o for o in outcomes if o.player_id and o.code.startswith("player:")}
    absent = [o for pid, o in by_player.items() if pid not in players]

    def yes_no(value, what: str) -> dict:
        code = "yes" if value >= p["line"] else "no"
        winner = next(o for o in outcomes if o.code == code)
        return _settle([winner], note=f"{value} {what}.", evidence=evidence)

    def shared(winners_ids: list[int], what: str) -> dict:
        winners = [by_player[pid] for pid in winners_ids if pid in by_player]
        notes = []
        if not winners:
            notes.append(f"The {what} isn't one of the choices: every bet loses.")
        if len(winners_ids) > 1:
            notes.append(
                f"{len(winners_ids)} players tie: winning bets are paid odds / {len(winners_ids)}."
            )
        if absent:
            notes.append("Players who didn't play are refunded.")
        return _settle(winners, absent, " ".join(notes), evidence, len(winners_ids))

    if market.category in (C.PLAYER_KILLS, C.PLAYER_DAMAGE):
        row = players.get(p["player"])
        if row is None:
            return _void("The player didn't play: everyone is refunded.", evidence)
        if market.category == C.PLAYER_KILLS:
            return yes_no(row.kills, "kills")
        if row.damage_dealt is None:
            return _void("This match has no damage figures: everyone is refunded.", evidence)
        return yes_no(row.damage_dealt, "damage")

    if market.category == C.PLAYER_H2H:
        a, b = listed
        if a not in players or b not in players:
            return _void("One of the players didn't play: everyone is refunded.", evidence)
        if players[a].kills == players[b].kills:
            return _void("A tie: everyone is refunded.", evidence)
        winner = a if players[a].kills > players[b].kills else b
        return _settle([by_player[winner]], evidence=evidence)

    if market.category == C.TOP_FRAGGER:
        most = max(r.kills for r in players.values())
        if most == 0:
            return _void("Nobody got a kill: everyone is refunded.", evidence)
        evidence["most_kills"] = most
        return shared([pid for pid, r in players.items() if r.kills == most], "top fragger")

    # FIRST_DEATH: the earliest death in the replay (any cause, zone included).
    deaths = MatchEvent.objects.filter(
        match=match, kind=MatchEvent.Kind.DEATH, game_time_s__isnull=False
    ).exclude(actor_player__isnull=True)
    first = deaths.order_by("game_time_s").values_list("game_time_s", flat=True).first()
    if first is None:
        return _void("The logs have no timed deaths: everyone is refunded.", evidence)
    dead = list(
        dict.fromkeys(deaths.filter(game_time_s=first).values_list("actor_player_id", flat=True))
    )
    evidence["first_death"] = {"players": dead, "at_s": first}
    return shared(dead, "first player to die")


def _standings(season_id: int, scope: str, results) -> dict[int, StandingRow]:
    """The standings table for ``scope``, if it has caught up with ``results`` (the published
    team results it should count); raises ``MarketError`` while it is being rebuilt."""
    rows = {
        r.team_id: r
        for r in StandingRow.objects.filter(season_id=season_id, scope=scope).select_related("team")
    }
    counted = sum(r.matches_played for r in rows.values())
    if not rows or counted != results.count():
        raise MarketError("The standings are still being updated. Try again shortly.", "not_ready")
    return rows


def _table(rows: dict[int, StandingRow], teams: set[int]) -> list[dict]:
    return [
        {
            "team": r.team_id,
            "name": r.team.name,
            "rank": r.rank,
            "points": r.total_points,
            "kills": r.kills,
            "booyahs": r.booyahs,
            "matches": r.matches_played,
        }
        for r in sorted(rows.values(), key=lambda r: (r.rank, r.team.name))
        if r.team_id in teams or r.rank == 1
    ]


def _by_team(market: Market) -> dict[int, Outcome]:
    return {o.team_id: o for o in market.outcomes.all() if o.team_id}


def _team_winners(market, rows, tied: set[int], what: str, evidence: dict) -> dict:
    """Settle a one-choice-per-team market: ``tied`` teams share the win; listed teams that
    didn't play are refunded."""
    choices = _by_team(market)
    winners = [choices[t] for t in tied if t in choices]
    voids = [o for t, o in choices.items() if t not in rows]
    notes = []
    if not winners:
        notes.append(f"The {what} isn't one of the choices: every bet loses.")
    if len(tied) > 1:
        names = ", ".join(sorted(rows[t].team.name for t in tied))
        notes.append(f"{len(tied)} teams tie ({names}): winning bets are paid odds / {len(tied)}.")
    if voids:
        notes.append("Teams that didn't play are refunded.")
    return _settle(winners, voids, " ".join(notes), evidence, len(tied))


def linked_day(market: Market) -> tuple[MatchDay, list[Match]]:
    """The match day a session market is about and its published matches."""
    fixture = market.fixture
    if fixture is None or fixture.match_number is not None:
        raise MarketError("This market isn't about a whole session.", "not_ready")
    if fixture.match_day_id is None:
        raise MarketError("Link the fixture to its uploaded match day first.", "not_ready")
    day = fixture.match_day
    matches = list(day.matches.all())
    waiting = [
        m for m in matches if m.status in (Match.Status.PROCESSING, Match.Status.NEEDS_REVIEW)
    ]
    if waiting:
        raise MarketError(
            f"{len(waiting)} match(es) of this session still need publishing.", "not_ready"
        )
    published = [m for m in matches if m.status == Match.Status.PUBLISHED]
    if not published:
        raise MarketError("No match of this session is published yet.", "not_ready")
    return day, published


def _suggest_session(market: Market) -> dict:
    day, matches = linked_day(market)
    results = TeamMatchResult.objects.filter(match__in=matches)
    rows = _standings(day.stage.season_id, f"day:{day.pk}", results)
    teams = _teams(market)
    evidence = {
        "match_day": day.pk,
        "match_day_title": str(day),
        "matches": [m.pk for m in matches],
        "left_out": [m.pk for m in day.matches.all() if m.status == Match.Status.DRAFT],
        "standings": _table(rows, teams),
    }
    if market.category == C.SESSION_WINNER:
        tied = {t for t, r in rows.items() if r.rank == 1}
        return _team_winners(market, rows, tied, "session winner", evidence)
    if market.category == C.SESSION_FRAGGER:
        return _fragger(market, matches, evidence)
    if market.category == C.SESSION_KILLS:
        row = rows.get(market.params["team"])
        if row is None:
            return _void("The team didn't play in this session: everyone is refunded.", evidence)
        code = "yes" if row.kills >= market.params["line"] else "no"
        winner = next(o for o in market.outcomes.all() if o.code == code)
        return _settle([winner], note=f"{row.kills} kills in the session.", evidence=evidence)
    if market.category == C.SESSION_H2H:
        a, b = market.params["teams"]
        if a not in rows or b not in rows:
            return _void("One of the teams didn't play: everyone is refunded.", evidence)
        if rows[a].total_points == rows[b].total_points:
            return _void("A tie on points: everyone is refunded.", evidence)
        winner = a if rows[a].total_points > rows[b].total_points else b
        return _settle([_by_team(market)[winner]], evidence=evidence)
    most = max(r.booyahs for r in rows.values())
    if most == 0:
        return _void("Nobody has a Booyah: everyone is refunded.", evidence)
    tied = {t for t, r in rows.items() if r.booyahs == most}
    evidence["most_booyahs"] = most
    return _team_winners(market, rows, tied, "team with most Booyahs", evidence)


def _suggest_season(market: Market) -> dict:
    results = TeamMatchResult.objects.filter(
        match__match_day__stage__season=market.season_id, match__status=Match.Status.PUBLISHED
    )
    rows = _standings(market.season_id, "season", results)
    if market.category in RANGE_MARKETS:
        return _suggest_range(market)
    if market.category == C.SEASON_FRAGGER:
        matches = Match.objects.filter(
            match_day__stage__season=market.season_id, status=Match.Status.PUBLISHED
        )
        return _fragger(market, list(matches), {"season": market.season_id})
    teams = _teams(market)
    evidence = {
        "season": market.season_id,
        "matches_counted": results.values("match").distinct().count(),
        "standings": _table(rows, teams),
    }
    if market.category == C.OVERALL_WINNER:
        tied = {t for t, r in rows.items() if r.rank == 1}
        return _team_winners(market, rows, tied, "overall winner", evidence)
    row = rows.get(market.params["team"])
    if row is None:
        return _void("The team hasn't played this season: everyone is refunded.", evidence)
    code = "yes" if row.rank <= market.params["n"] else "no"
    winner = next(o for o in market.outcomes.all() if o.code == code)
    return _settle([winner], note=f"Ranked {row.rank}.", evidence=evidence)


def range_matches(market: Market) -> list[Match]:
    """The published matches of a date-range market, once the range is over and settled."""
    start = dt.date.fromisoformat(market.params["from"])
    end = dt.date.fromisoformat(market.params["to"])
    if timezone.localdate() <= end:
        raise MarketError(f"The dates run until {end:%d %b}: settle it after that.", "not_ready")
    matches = list(
        Match.objects.filter(
            match_day__stage__season=market.season_id,
            match_day__date__gte=start,
            match_day__date__lte=end,
        )
    )
    waiting = [
        m for m in matches if m.status in (Match.Status.PROCESSING, Match.Status.NEEDS_REVIEW)
    ]
    if waiting:
        raise MarketError(
            f"{len(waiting)} match(es) in these dates still need publishing.", "not_ready"
        )
    published = [m for m in matches if m.status == Match.Status.PUBLISHED]
    if not published:
        raise MarketError("No match in these dates is published.", "not_ready")
    return published


@dataclass
class RangeRow:
    """One team's line in a table worked out for a date range (shaped like a StandingRow)."""

    team: Team
    rank: int
    total_points: int
    kills: int
    booyahs: int
    matches_played: int

    @property
    def team_id(self) -> int:
        return self.team.pk


def _suggest_range(market: Market) -> dict:
    matches = range_matches(market)
    evidence = {
        "from": market.params["from"],
        "to": market.params["to"],
        "matches": [m.pk for m in matches],
    }
    if market.category == C.RANGE_FRAGGER:
        return _fragger(market, matches, evidence)
    season = market.season
    tallies: dict[int, Tally] = {}
    results = TeamMatchResult.objects.filter(match__in=matches).order_by(
        "match__match_day__date", "match__match_day__number", "match__number", "placement"
    )
    for r in results:
        tallies.setdefault(r.team_id, Tally(r.team_id)).add(r)
    names = dict(Team.objects.filter(pk__in=tallies).values_list("pk", "name"))
    teams = Team.objects.in_bulk(list(tallies))
    rows = {
        t.team_id: RangeRow(
            teams[t.team_id], position, t.total_points, t.kills, t.booyahs, t.matches_played
        )
        for position, t in rank(list(tallies.values()), season.tiebreakers, names)
    }
    evidence["standings"] = _table(rows, _teams(market))
    if market.category == C.RANGE_WINNER:
        tied = {t for t, r in rows.items() if r.rank == 1}
        return _team_winners(market, rows, tied, "winner over these dates", evidence)
    row = rows.get(market.params["team"])
    if row is None:
        return _void("The team didn't play in these dates: everyone is refunded.", evidence)
    code = "yes" if row.rank <= market.params["n"] else "no"
    winner = next(o for o in market.outcomes.all() if o.code == code)
    return _settle([winner], note=f"Ranked {row.rank}.", evidence=evidence)


def _fragger(market: Market, matches: list[Match], evidence: dict) -> dict:
    """Most kills added up over ``matches``: those level share the win; listed players who
    didn't play in any of them are refunded."""
    kills = dict(
        PlayerMatchResult.objects.filter(match__in=matches)
        .values("player")
        .annotate(k=Sum("kills"))
        .values_list("player", "k")
    )
    if not kills:
        raise MarketError("These matches have no player results.", "not_ready")
    choices = {o.player_id: o for o in market.outcomes.all() if o.player_id}
    evidence["kills"] = {str(p): kills.get(p, 0) for p in choices}
    most = max(kills.values())
    if most == 0:
        return _void("Nobody got a kill: everyone is refunded.", evidence)
    evidence["most_kills"] = most
    tied = [p for p, k in kills.items() if k == most]
    winners = [choices[p] for p in tied if p in choices]
    voids = [o for p, o in choices.items() if p not in kills]
    notes = []
    if not winners:
        notes.append("The top fragger isn't one of the choices: every bet loses.")
    if len(tied) > 1:
        notes.append(
            f"{len(tied)} players tie on {most} kills: winning bets are paid odds / {len(tied)}."
        )
    if voids:
        notes.append("Players who didn't play are refunded.")
    return _settle(winners, voids, " ".join(notes), evidence, len(tied))


def _teams(market: Market) -> set[int]:
    p = market.params or {}
    return set(p.get("teams") or []) | ({p["team"]} if p.get("team") else set())


# -- applying a decision -------------------------------------------------------------------------


def _target(
    bet: Bet, kind: str, winners: set[int], voids: set[int], late_from, dead_heat: int = 1
) -> tuple[str, int]:
    """(status, payout) this bet ends up with under a decision."""
    if kind == Settlement.Kind.VOID or bet.outcome_id in voids:
        return B.VOID, bet.stake
    if late_from is not None and bet.placed_at >= late_from:
        return B.VOID, bet.stake  # placed after the match really started
    if bet.outcome_id in winners:
        if dead_heat > 1:
            return B.WON, dead_heat_return(bet.stake, bet.odds_accepted, dead_heat)
        return B.WON, bet.potential_return
    return B.LOST, 0


def _apply(market: Market, settlement: Settlement, late_from) -> dict:
    winners = set(settlement.winning_outcomes.values_list("pk", flat=True))
    voids = set(settlement.void_outcomes.values_list("pk", flat=True))
    n = settlement.version
    now = timezone.now()
    counts: Counter = Counter()
    for bet in market.bets.select_related("user").order_by("placed_at", "pk"):
        status, payout = _target(
            bet, settlement.kind, winners, voids, late_from, settlement.dead_heat
        )
        wallet = Wallet.objects.get(user=bet.user)
        if bet.status == B.PENDING:
            if payout:
                kind = Kind.REFUND if status == B.VOID else Kind.PAYOUT
                prefix = "refund" if status == B.VOID else "payout"
                post_entry(
                    wallet, kind, payout, f"{prefix}:{bet.pk}:v{n}", bet=bet, settlement=settlement
                )
            counts["coins_paid"] += payout
        else:
            delta = payout - (bet.payout or 0)
            if delta > 0:
                # Coins a previous correction couldn't take back are never paid out again.
                offset = min(delta, bet.unrecovered)
                bet.unrecovered -= offset
                if delta - offset:
                    post_entry(
                        wallet,
                        Kind.CORRECTION,
                        delta - offset,
                        f"correction:{bet.pk}:v{n}",
                        bet=bet,
                        settlement=settlement,
                        reason=settlement.reason,
                    )
                counts["coins_paid"] += delta - offset
            elif delta < 0:
                wallet.refresh_from_db()
                take = min(-delta, wallet.balance)
                if take:
                    post_entry(
                        wallet,
                        Kind.CORRECTION,
                        -take,
                        f"correction:{bet.pk}:v{n}",
                        bet=bet,
                        settlement=settlement,
                        reason=settlement.reason,
                    )
                counts["coins_taken"] += take
                if take < -delta:
                    bet.unrecovered += -delta - take
                    counts["coins_unrecovered"] += -delta - take
        counts[status.lower()] += 1
        bet.status, bet.payout, bet.settled_at = status, payout, now
        bet.save(update_fields=["status", "payout", "settled_at", "unrecovered"])
    return dict(counts)


def _late_from(market: Market):
    """When the real play started: bets placed from then on are refunded."""
    fixture = market.fixture
    if fixture is None and market.category in RANGE_MARKETS:
        starts = Match.objects.filter(
            match_day__stage__season=market.season_id,
            match_day__date__gte=market.params["from"],
            match_day__date__lte=market.params["to"],
            started_at__isnull=False,
        ).values_list("started_at", flat=True)
        return min(starts, default=None)
    if fixture is None:
        return None
    if fixture.match_number and fixture.match_id:
        return fixture.match.started_at
    if fixture.match_number is None and fixture.match_day_id:
        starts = [m.started_at for m in fixture.match_day.matches.all() if m.started_at]
        return min(starts) if starts else None
    return None


def _dead_heat(market: Market, winners, dead_heat: int | None, suggestion=None) -> int:
    """How many teams share the win. Only one-choice-per-team session and overall markets
    can tie; given none, it is the suggestion's (when the winners match it) or the number
    of winners chosen."""
    winners = set(winners)
    if dead_heat is None:
        if suggestion and suggestion["kind"] == "SETTLE" and set(suggestion["winners"]) == winners:
            dead_heat = suggestion.get("dead_heat", 1)
        else:
            dead_heat = len(winners) if market.category in DEAD_HEAT else 1
    dead_heat = max(int(dead_heat), 1)
    if dead_heat > 1 and market.category not in DEAD_HEAT:
        raise MarketError("Only session and overall winner markets can be a dead heat.", "outcome")
    if market.category in DEAD_HEAT and dead_heat < len(winners):
        raise MarketError("A dead heat can't be smaller than the number of winners.", "outcome")
    return dead_heat


def _decide(
    market_id: int,
    *,
    kind: str,
    actor,
    winners=(),
    voids=(),
    reference: str = "",
    reason: str = "",
    allowed_from: set[str],
    evidence: dict | None = None,
    request_key: str | None = None,
    dead_heat: int = 1,
) -> tuple[Settlement, bool]:
    with transaction.atomic():
        market = Market.objects.select_for_update().get(pk=market_id)
        latest = market.settlements.order_by("-version").first()
        if market.status not in allowed_from:
            raise MarketError(
                f"A {market.status.lower()} market can't be changed this way.", "wrong_status"
            )
        outcome_ids = set(market.outcomes.values_list("pk", flat=True))
        winners, voids = set(winners), set(voids)
        if not (winners | voids) <= outcome_ids:
            raise MarketError("A chosen outcome isn't part of this market.", "outcome")
        if winners & voids:
            raise MarketError("An outcome can't both win and be refunded.", "outcome")
        late_from = _late_from(market)
        settlement = Settlement.objects.create(
            market=market,
            version=(latest.version + 1) if latest else 1,
            kind=kind,
            evidence=evidence or {},
            reference=reference,
            reason=reason,
            actor=actor,
            supersedes=latest,
            request_key=request_key,
            dead_heat=dead_heat if kind == Settlement.Kind.SETTLE else 1,
        )
        settlement.winning_outcomes.set(winners)
        settlement.void_outcomes.set(voids)
        settlement.summary = _apply(market, settlement, late_from)
        settlement.save(update_fields=["summary"])
        to = S.VOID if kind == Settlement.Kind.VOID else S.SETTLED
        MarketEvent.objects.create(
            market=market,
            from_status=market.status,
            to_status=to,
            actor=actor,
            reason=reason or f"Settlement v{settlement.version}",
        )
        market.status = to
        market.updated_by = actor
        market.save(update_fields=["status", "updated_by", "updated_at"])
    return settlement, True


def settle(
    market: Market,
    *,
    actor,
    winners,
    voids=(),
    reference: str = "",
    override_reason: str = "",
    dead_heat: int | None = None,
) -> tuple[Settlement, bool]:
    """Settle a CLOSED market (first time). Repeating the same request changes nothing."""
    market.refresh_from_db()
    if market.status == S.VOID:
        raise MarketError("This market was voided. Use a correction to settle it.", "wrong_status")
    if market.status == S.SETTLED:
        latest = market.settlements.order_by("-version").first()
        if (
            latest.version == 1
            and set(latest.winning_outcomes.values_list("pk", flat=True)) == set(winners)
            and set(latest.void_outcomes.values_list("pk", flat=True)) == set(voids)
            and (dead_heat is None or latest.dead_heat == dead_heat)
        ):
            return latest, False
        raise MarketError("Already settled. Use a correction to change it.", "already_settled")
    suggestion = suggest(market)  # raises when the match isn't ready
    dead_heat = _dead_heat(market, winners, dead_heat, suggestion)
    matches = (
        suggestion["kind"] == "SETTLE"
        and set(suggestion["winners"]) == set(winners)
        and set(suggestion["voids"]) == set(voids)
        and suggestion.get("dead_heat", 1) == dead_heat
    )
    if not winners and not voids and not matches:
        # "Nobody listed wins" only when the results say so, never by an empty form.
        raise MarketError("Pick the winning outcome.", "outcome")
    if not matches and not override_reason.strip():
        raise MarketError(
            "That isn't what the match result says. Give a reason to override it.", "override"
        )
    try:
        return _decide(
            market.pk,
            kind=Settlement.Kind.SETTLE,
            actor=actor,
            winners=winners,
            voids=voids,
            reference=reference,
            reason=override_reason.strip(),
            allowed_from={S.CLOSED},
            evidence=suggestion["evidence"],
            dead_heat=dead_heat,
        )
    except MarketError as exc:
        if exc.code != "wrong_status":
            raise
        # Another request settled it a moment ago: same answer, same result.
        return settle(market, actor=actor, winners=winners, voids=voids, dead_heat=dead_heat)


def void(market: Market, *, actor, reason: str, reference: str = "") -> tuple[Settlement, bool]:
    """Refund every bet once. Voiding a void market again changes nothing."""
    if not reason.strip():
        raise MarketError("Give a reason for voiding.", "reason")
    market.refresh_from_db()
    if market.status == S.VOID:
        return market.settlements.order_by("-version").first(), False
    if market.status == S.SETTLED:
        raise MarketError("Already settled. Use a correction to void it.", "already_settled")
    try:
        return _decide(
            market.pk,
            kind=Settlement.Kind.VOID,
            actor=actor,
            reference=reference,
            reason=reason.strip(),
            allowed_from={S.DRAFT, S.OPEN, S.SUSPENDED, S.CLOSED},
        )
    except MarketError as exc:
        if exc.code != "wrong_status":
            raise
        return void(market, actor=actor, reason=reason)


def correct(
    market: Market,
    *,
    actor,
    kind: str,
    reason: str,
    winners=(),
    voids=(),
    reference: str = "",
    key: str = "",
    dead_heat: int | None = None,
) -> tuple[Settlement, bool]:
    """Replace a settled or voided result with a new version.

    Each bet gets one CORRECTION entry for the difference between what it was owed and
    what it is owed now. If a player has already spent coins being taken back, their
    balance stops at 0 and the rest is recorded on the bet as ``unrecovered``.
    ``key`` (from the staff form) makes a resend of the same correction do nothing.
    """
    if not reason.strip():
        raise MarketError("Give a reason for the correction.", "reason")
    market.refresh_from_db()
    request_key = f"correct:{market.pk}:{key}" if key else None
    if request_key and (done := Settlement.objects.filter(request_key=request_key).first()):
        return done, False
    if market.status not in (S.SETTLED, S.VOID) or not market.settlements.exists():
        raise MarketError("Only a settled or voided market can be corrected.", "wrong_status")
    suggestion = None
    try:
        suggestion = suggest(market)
    except MarketError:
        pass  # a void correction may not have a published match
    evidence = suggestion["evidence"] if suggestion else {}
    if kind == Settlement.Kind.SETTLE:
        nobody = suggestion and suggestion["kind"] == "SETTLE" and not suggestion["winners"]
        if not winners and not voids and not nobody:
            raise MarketError("Pick the winning outcome.", "outcome")
        dead_heat = _dead_heat(market, winners, dead_heat, suggestion)
    try:
        return _decide(
            market.pk,
            kind=kind,
            actor=actor,
            winners=winners if kind == Settlement.Kind.SETTLE else (),
            voids=voids if kind == Settlement.Kind.SETTLE else (),
            reference=reference,
            reason=reason.strip(),
            allowed_from={S.SETTLED, S.VOID},
            evidence=evidence,
            request_key=request_key,
            dead_heat=dead_heat or 1,
        )
    except IntegrityError:
        # The same correction was sent twice at once and the other one won.
        done = Settlement.objects.filter(request_key=request_key).first() if request_key else None
        if done is None:
            raise
        return done, False


def settlement_data(s: Settlement) -> dict:
    return {
        "id": s.pk,
        "version": s.version,
        "kind": s.kind,
        "winners": list(s.winning_outcomes.values("id", "label")),
        "voids": list(s.void_outcomes.values("id", "label")),
        "evidence": s.evidence,
        "reference": s.reference,
        "reason": s.reason,
        "summary": s.summary,
        "dead_heat": s.dead_heat,
        "by": s.actor.email,
        "supersedes": s.supersedes.version if s.supersedes else None,
        "created_at": s.created_at,
    }
