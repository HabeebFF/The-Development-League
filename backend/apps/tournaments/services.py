"""Tournament rules: making one, inviting teams, moving match days in, prizes and payouts."""

from __future__ import annotations

from collections import Counter, defaultdict

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.league.models import Match, MatchDay, Player, Season, Stage, Team, unique_slug
from apps.results.models import PlayerMatchResult, StandingRow
from apps.results.standings import rebuild_season

from .models import PrizePayout, Tournament


class TournamentError(Exception):
    pass


def scrim_season() -> Season | None:
    """The league season the site shows by default (never a tournament's own season)."""
    return (
        Season.objects.filter(is_active=True, tournament__isnull=True).first()
        or Season.objects.filter(tournament__isnull=True).first()
    )


def is_tournament_season(season_id: int | None) -> bool:
    return bool(season_id) and Tournament.objects.filter(season_id=season_id).exists()


@transaction.atomic
def create_tournament(name: str, **fields) -> Tournament:
    """A tournament and its own season (the league's points table) with a Grand final stage."""
    league = scrim_season()
    if league is None:
        raise TournamentError("Make the league season first: the tournament copies its points.")
    season = Season.objects.create(
        name=name,
        scoring_rule=league.scoring_rule,
        tiebreakers=league.tiebreakers,
        starts_on=fields.get("starts_on"),
        ends_on=fields.get("ends_on"),
    )
    Stage.objects.create(season=season, name="Grand final", kind=Stage.Kind.FINAL)
    return Tournament.objects.create(
        name=name, slug=unique_slug(Tournament, name), season=season, **fields
    )


def top_teams(n: int = 12) -> list[Team]:
    """The top ``n`` of the league's overall standings right now."""
    league = scrim_season()
    if league is None:
        return []
    rows = (
        StandingRow.objects.filter(season=league, scope="season")
        .select_related("team")
        .order_by("rank")[:n]
    )
    return [r.team for r in rows]


def final_stage(t: Tournament) -> Stage:
    stage = t.season.stages.order_by("-order", "-pk").first()
    if stage is None:
        stage = Stage.objects.create(season=t.season, name="Grand final", kind=Stage.Kind.FINAL)
    return stage


@transaction.atomic
def move_days(t: Tournament, day_ids: list[int]) -> list[MatchDay]:
    """Move match days (uploaded into the league season, say for predictions) into the
    tournament, so they count for its table and not the scrim standings."""
    if t.confirmed_at:
        raise TournamentError("The prizes are already paid; the matches can't change now.")
    stage = final_stage(t)
    days = list(MatchDay.objects.select_related("stage").filter(pk__in=day_ids))
    if len(days) != len(set(day_ids)):
        raise TournamentError("Some of those match days don't exist.")
    before = {d.stage.season_id for d in days}
    used = set(MatchDay.objects.filter(stage=stage, group=None).values_list("number", flat=True))
    for day in sorted(days, key=lambda d: (d.date or timezone.now().date(), d.number)):
        if day.stage_id == stage.pk:
            continue
        number = day.number
        if number in used:
            number = max(used | {0}) + 1
        used.add(number)
        day.stage, day.group, day.number = stage, None, number
        day.save(update_fields=["stage", "group", "number", "updated_at"])
    for season_id in before | {t.season_id}:
        rebuild_season(Season.objects.get(pk=season_id))
    return days


def matches(t: Tournament) -> list[Match]:
    return list(
        Match.objects.filter(match_day__stage__season=t.season, status=Match.Status.PUBLISHED)
        .select_related("match_day")
        .order_by("match_day__date", "match_day__number", "number")
    )


# -- prizes --------------------------------------------------------------------------------------


def places_of(key: str) -> list[int]:
    """ "place:1" -> [1]; "place:5-8" -> [5, 6, 7, 8]; anything else -> []."""
    kind, _, spec = key.partition(":")
    if kind != "place" or not spec:
        return []
    lo, _, hi = spec.partition("-")
    try:
        return list(range(int(lo), int(hi or lo) + 1))
    except ValueError:
        return []


def clean_prizes(prizes) -> list[dict]:
    if not isinstance(prizes, list) or not prizes:
        raise TournamentError("Give the prize table as a list of rows.")
    out, seen = [], set()
    for row in prizes:
        if not isinstance(row, dict):
            raise TournamentError("Each prize is a row with key, label, cash and dc.")
        key = str(row.get("key", ""))
        if key not in ("mvp", "top_kills", "best_igl") and not places_of(key):
            raise TournamentError(f"Unknown prize {key!r}.")
        if key in seen:
            raise TournamentError(f"{key} is in the table twice.")
        seen.add(key)
        cash, dc = row.get("cash", 0), row.get("dc", 0)
        for v in (cash, dc):
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise TournamentError("Cash and DC are whole numbers, 0 or more.")
        out.append({"key": key, "label": str(row.get("label") or key)[:60], "cash": cash, "dc": dc})
    return out


def total_dc(prizes: list[dict]) -> int:
    return sum(p["dc"] * max(len(places_of(p["key"])), 1) for p in prizes)


def total_cash(prizes: list[dict]) -> int:
    return sum(p["cash"] * max(len(places_of(p["key"])), 1) for p in prizes)


def split(amount: int, played: Counter) -> dict[int, int]:
    """Share ``amount`` equally between the players who played; the coins left over go one
    each to those who played most (then by player id), so the shares add up exactly."""
    if not played or amount <= 0:
        return {}
    order = sorted(played, key=lambda pid: (-played[pid], pid))
    each, left = divmod(amount, len(order))
    return {pid: each + (1 if i < left else 0) for i, pid in enumerate(order)}


def _names(ids) -> dict[int, Player]:
    return {p.pk: p for p in Player.objects.filter(pk__in=list(ids)).select_related("user")}


def preview(t: Tournament) -> dict:
    """Every winner and every player's share, worked out from the uploaded matches."""
    from apps.results.ratings import board, points

    played_matches = matches(t)
    # Prizes come from the final stage's table when there is a qualifier before it.
    scope = f"stage:{final_stage(t).pk}" if t.season.stages.count() > 1 else "season"
    rows = {
        r.rank: r
        for r in StandingRow.objects.filter(season=t.season, scope=scope).select_related("team")
    }
    played: dict[int, Counter] = defaultdict(Counter)  # team -> player -> matches
    for r in PlayerMatchResult.objects.filter(match__in=played_matches).values("team", "player"):
        if r["team"] and r["player"]:
            played[r["team"]][r["player"]] += 1
    kills = (
        PlayerMatchResult.objects.filter(match__in=played_matches, player__isnull=False)
        .values("player", "team")
        .annotate(k=Sum("kills"))
        .order_by("-k", "player")
    )
    top_killer = kills[0] if kills else None
    rated = board(played_matches, {**points(), "potd_min": 1}) if played_matches else None
    mvp = None
    if rated and rated["players"]:
        need = max(1, -(-len(played_matches) // 2))  # played at least half the matches
        mvp = next((p for p in rated["players"] if p["matches"] >= need), rated["players"][0])
    winner_row = rows.get(1)
    igl = t.best_igl or (winner_row.team.igl if winner_row and winner_row.team.igl_id else None)

    prizes = []
    for prize in t.prizes:
        key = prize["key"]
        winners = []
        if places_of(key):
            for place in places_of(key):
                row = rows.get(place)
                if row is None:
                    continue
                winners.append(
                    {
                        "place": place,
                        "team": {"id": row.team_id, "name": row.team.name, "slug": row.team.slug},
                        "points": row.total_points,
                        "shares": split(prize["dc"], played[row.team_id]),
                    }
                )
        elif key == "mvp" and mvp:
            team = mvp["team"]
            winners.append(
                {
                    "player_id": mvp["player_id"],
                    "team": team,
                    "detail": f"rating {mvp['rating']:.1f} · {mvp['matches']} matches",
                    "shares": {mvp["player_id"]: prize["dc"]},
                }
            )
        elif key == "top_kills" and top_killer:
            winners.append(
                {
                    "player_id": top_killer["player"],
                    "team": None,
                    "detail": f"{top_killer['k']} kills",
                    "shares": {top_killer["player"]: prize["dc"]},
                }
            )
        elif key == "best_igl" and igl:
            winners.append(
                {
                    "player_id": igl.pk,
                    "team": None,
                    "detail": "picked by staff" if t.best_igl_id else "the winning team's IGL",
                    "shares": {igl.pk: prize["dc"]},
                }
            )
        prizes.append({**prize, "winners": winners})

    people = _names({pid for p in prizes for w in p["winners"] for pid in w["shares"]})
    no_account = set()
    for p in prizes:
        for w in p["winners"]:
            if "player_id" in w:
                w["player"] = people[w["player_id"]].display_name
            w["shares"] = [
                {
                    "player_id": pid,
                    "player": people[pid].display_name,
                    "amount": amount,
                    "has_account": people[pid].user_id is not None,
                }
                for pid, amount in w["shares"].items()
            ]
            no_account |= {s["player_id"] for s in w["shares"] if not s["has_account"]}
    published = len(played_matches)
    return {
        "matches": published,
        "planned_matches": t.planned_matches,
        "ready": published >= t.planned_matches,
        "prizes": prizes,
        "total_dc": sum(s["amount"] for p in prizes for w in p["winners"] for s in w["shares"]),
        "no_account": len(no_account),
        "igl_choices": _igl_choices(played),
    }


def _igl_choices(played: dict[int, Counter]) -> list[dict]:
    ids = {pid for c in played.values() for pid in c}
    return [
        {"id": p.pk, "name": p.display_name}
        for p in sorted(_names(ids).values(), key=lambda p: p.display_name.casefold())
    ]


def confirm(t: Tournament, actor, best_igl: Player | None = None) -> dict:
    """Pay every DC prize, once. Players without an account have theirs held."""
    with transaction.atomic():
        t = Tournament.objects.select_for_update().get(pk=t.pk)
        if t.confirmed_at:
            raise TournamentError("The prizes were already paid.")
        if best_igl is not None:
            t.best_igl = best_igl
            t.save(update_fields=["best_igl", "updated_at"])
        view = preview(t)
        missing = [p["label"] for p in view["prizes"] if p["dc"] and not p["winners"]]
        if any(p["key"] == "best_igl" and not p["winners"] for p in view["prizes"]):
            raise TournamentError("Pick the Best IGL first.")
        if not view["ready"]:
            raise TournamentError(
                f"Only {view['matches']} of {t.planned_matches} matches are uploaded."
            )
        if missing:
            raise TournamentError(f"No winner yet for: {', '.join(missing)}.")
        made = []
        for prize in view["prizes"]:
            for w in prize["winners"]:
                label = f"{t.name}: {prize['label']}"
                for s in w["shares"]:
                    team_id = w["team"]["id"] if w.get("team") else None
                    made.append(
                        PrizePayout.objects.create(
                            tournament=t,
                            prize_key=prize["key"] if "place" not in w else f"place:{w['place']}",
                            label=label,
                            player_id=s["player_id"],
                            team_id=team_id,
                            amount=s["amount"],
                        )
                    )
        t.confirmed_at, t.confirmed_by = timezone.now(), actor
        t.save(update_fields=["confirmed_at", "confirmed_by", "updated_at"])
    paid = sum(1 for p in made if _pay(p, actor))
    _grant_cup_cards({p.player_id for p in made})
    return {"payouts": len(made), "paid": paid, "held": len(made) - paid}


def _grant_cup_cards(player_ids: set[int]) -> None:
    """Give the earned Cup card designs (winners, 2nd, 3rd, MVP) to players with an account.
    Players without one get theirs when they link their UID and open the Player shop."""
    from apps.shop import milestones

    players = Player.objects.filter(pk__in=player_ids, user__isnull=False).select_related("user")
    for player in players:
        milestones.grant(player.user, player)


def _pay(payout: PrizePayout, actor=None) -> bool:
    """Credit one share to the player's wallet if they have an account. Safe to repeat."""
    from apps.predictions.services import Kind, post_entry, wallet_for

    with transaction.atomic():
        p = PrizePayout.objects.select_for_update().select_related("player").get(pk=payout.pk)
        if p.paid_at or p.amount <= 0:
            return bool(p.paid_at)
        user = p.player.user
        if user is None:
            return False
        post_entry(
            wallet_for(user),
            Kind.ADJUSTMENT,
            p.amount,
            f"tournament-prize:{p.pk}",
            reason=f"Prize: {p.label}"[:300],
            actor=actor,
        )
        p.paid_at, p.paid_to = timezone.now(), user
        p.save(update_fields=["paid_at", "paid_to", "updated_at"])
        return True


def pay_held(player_id: int) -> int:
    """Pay a player's held prizes (their game UID was just linked to an account)."""
    paid = sum(
        1 for p in PrizePayout.objects.filter(player_id=player_id, paid_at__isnull=True) if _pay(p)
    )
    _grant_cup_cards({player_id})
    return paid


def status(t: Tournament, today=None) -> str:
    """upcoming, live or finished (once the prizes are confirmed)."""
    today = today or timezone.localdate()
    if t.cancelled_at:
        return "cancelled"
    if t.confirmed_at:
        return "finished"
    if t.starts_on and today < t.starts_on:
        return "upcoming"
    return "live"
