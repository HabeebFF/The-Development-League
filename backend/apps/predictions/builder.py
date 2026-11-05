"""Bet builder: several picks on the same match in one multiple, with the odds cut because
results in one match go together. Worked out here on the server; the slip only shows it.

For the picks in one match, in market order:

- Picks that can't both win are refused: two teams finishing in the same single place
  (two Booyahs), or one team given finishing ranges that don't overlap (Booyah and first
  out, or Booyah and "outside the top 3").
- A pick already certain when another pick wins (Booyah makes "top 3" and "finishes 1st"
  certain) counts at odds 1.00.
- Every other pick after the first is cut: by ``SAME_SUBJECT`` when it is about a team or
  player an earlier pick is about (a player counts as their team), else by
  ``SAME_MATCH``. Odds never go below 1.00.

Whole-session markets still can't share a multiple with that session's matches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal

from apps.league.models import RosterEntry

from .markets import BANDS, MarketError, lobby_team_ids
from .models import Market, Outcome

C = Market.Category
SAME_SUBJECT = Decimal("0.75")  # same team or player: strongly linked
SAME_MATCH = Decimal("0.90")  # different teams, same match: loosely linked
MAX_PER_MATCH = 4
LAST = 99  # "finishes last" when the lobby size is unknown


@dataclass
class Pick:
    market: Market
    outcome: Outcome
    teams: set[int] = field(default_factory=set)  # who the pick is about
    players: set[int] = field(default_factory=set)
    places: dict[int, tuple[int, int]] = field(default_factory=dict)  # team -> finish range
    counted: Decimal = Decimal(1)
    note: str = ""


def _team_of(code: str) -> int | None:
    return int(code.split(":")[1]) if code.startswith("team:") else None


def describe(market: Market, outcome: Outcome) -> Pick:
    """What a pick says about the match: its teams, players and finishing ranges."""
    pick = Pick(market, outcome, counted=outcome.odds)
    p, cat, code = market.params, market.category, outcome.code
    if cat == C.BOOYAH and (t := _team_of(code)) is not None:
        pick.teams.add(t)
        pick.places[t] = (1, 1)
    elif cat == C.TOP_N:
        t, n = p["team"], int(p["n"])
        pick.teams.add(t)
        pick.places[t] = (1, n) if code == "yes" else (n + 1, LAST)
    elif cat == C.FINISH_BAND:
        t = p["team"]
        pick.teams.add(t)
        lo, hi = BANDS[code]
        pick.places[t] = (lo, min(hi, LAST))
    elif cat == C.FIRST_OUT and (t := _team_of(code)) is not None:
        pick.teams.add(t)
        last = len(lobby_team_ids(market.fixture)) if market.fixture else LAST
        pick.places[t] = (last, last) if last > 1 else (2, LAST)
    elif cat in (C.TEAM_KILLS,):
        pick.teams.add(p["team"])
    elif cat in (C.KILLS_HANDICAP, C.POINTS_HANDICAP, C.H2H_PLACEMENT, C.H2H_KILLS, C.H2H_POINTS):
        pick.teams.update(p.get("teams", []))
    elif cat == C.FIRST_BLOOD and (t := _team_of(code)) is not None:
        pick.teams.add(t)
    elif cat in (C.PLAYER_KILLS, C.PLAYER_DAMAGE):
        pick.players.add(p["player"])
    elif cat in (C.TOP_FRAGGER, C.FIRST_DEATH) and outcome.player_id:
        pick.players.add(outcome.player_id)
    elif cat == C.PLAYER_H2H:
        pick.players.update(p.get("players", []))
    return pick


def _subjects(pick: Pick, team_of: dict[int, int]) -> set[str]:
    out = {f"t{t}" for t in pick.teams}
    for pl in pick.players:
        out.add(f"p{pl}")
        if pl in team_of:
            out.add(f"t{team_of[pl]}")
    return out


def _clashes(a: Pick, b: Pick) -> bool:
    """True when a and b can't both win."""
    for t, (lo, hi) in a.places.items():
        if t in b.places:
            blo, bhi = b.places[t]
            if max(lo, blo) > min(hi, bhi):
                return True
    # Two different teams pinned to the same single place.
    for t, (lo, hi) in a.places.items():
        for u, (ulo, uhi) in b.places.items():
            if t != u and lo == hi == ulo == uhi:
                return True
    return False


def _implies(a: Pick, b: Pick) -> bool:
    """True when a winning makes b certain (b only says things a already says)."""
    if not b.places or b.players or b.teams - set(b.places):
        return False
    for t, (blo, bhi) in b.places.items():
        if t not in a.places:
            return False
        lo, hi = a.places[t]
        if not (blo <= lo and hi <= bhi):
            return False
    return True


def _cut(odds: Decimal, factor: Decimal) -> Decimal:
    return max(Decimal("1.00"), (odds * factor).quantize(Decimal("0.01"), rounding=ROUND_FLOOR))


def price_match(picks: list[Pick], season_id: int) -> None:
    """Set ``counted`` (and a note) on each pick of one match, or refuse the set."""
    if len(picks) > MAX_PER_MATCH:
        raise MarketError(
            f"At most {MAX_PER_MATCH} picks can come from one match.", "same_match_limit"
        )
    picks.sort(key=lambda x: x.market.pk)
    for i, a in enumerate(picks):
        for b in picks[i + 1 :]:
            if _clashes(a, b):
                raise MarketError(
                    f"{a.outcome.label} and {b.outcome.label} can't both happen, so they can't "
                    "be in one bet.",
                    "contradiction",
                    markets=[a.market.pk, b.market.pk],
                )
    players = {pl for x in picks for pl in x.players}
    team_of = dict(
        RosterEntry.objects.filter(season_id=season_id, player_id__in=players).values_list(
            "player_id", "team_id"
        )
    )
    implied: set[int] = set()
    for i, b in enumerate(picks):
        for j, a in enumerate(picks):
            if i != j and j not in implied and _implies(a, b):
                implied.add(i)
                b.counted = Decimal("1.00")
                b.note = f"Certain if {a.outcome.label} wins, so it adds nothing."
                break
    seen: set[str] = set()
    first = True
    for i, x in enumerate(picks):
        subj = _subjects(x, team_of)
        if i in implied:
            seen |= subj
            continue
        if first:
            first = False
        elif subj & seen:
            x.counted = _cut(x.outcome.odds, SAME_SUBJECT)
            x.note = "Linked to another pick on the same team or player."
        else:
            x.counted = _cut(x.outcome.odds, SAME_MATCH)
            x.note = "Same match as another pick."
        seen |= subj


def match_key(market: Market) -> tuple | None:
    """The match a market is about (only for single-match markets)."""
    f = market.fixture
    if f is None or f.match_number is None:
        return None
    return (f.season_id, f.date, f.session, f.match_number)


def price(legs: list[tuple[Market, Outcome]]) -> list[Pick]:
    """Every leg as a priced Pick, in the order given. Legs on the same match are priced
    together as a bet builder; the rest count at their own odds."""
    picks = [describe(m, o) for m, o in legs]
    groups: dict[tuple, list[Pick]] = {}
    for p in picks:
        if (key := match_key(p.market)) is not None:
            groups.setdefault(key, []).append(p)
    for key, group in groups.items():
        if len(group) > 1:
            price_match(group, key[0])
    return picks
