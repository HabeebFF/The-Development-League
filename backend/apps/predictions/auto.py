"""Markets the site makes by itself each scrim day, so staff only adjust odds if they want.

From 10:00 Lagos time on a scrim day the hourly task makes tonight's fixtures (the 8PM and
10PM sessions, matches 1 to 5) and opens the standard markets on them with suggested odds:

- each match: Booyah, total kills over/under, first blood;
- each session: winner, most Booyahs, top fragger and two head-to-heads;
- Mondays: most points over the week (Monday to Sunday).

A session's teams (its lobby) are the ones that played the last published session at the
same hour, unless staff already set the lobby. Every market is recorded by what it is for
(``AutoMarket.key``), so a re-run only fills gaps and never brings back a market staff
deleted, and nothing staff made or edited is touched. Markets close as their session
starts; settling stays a staff tap.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from statistics import median
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.accounts.models import User
from apps.league.models import Match, MatchDay, Season, Team
from apps.results.models import PlayerMatchResult, TeamMatchResult

from .markets import MarketError, create_market, transition
from .models import AutoMarket, AutoSettings, Fixture, Market
from .odds import suggest_odds

C, S = Market.Category, Market.Status

SESSIONS = {"8PM": dt.time(20), "10PM": dt.time(22)}
MATCHES = 5  # matches in a session
STARTS_AT = dt.time(10)  # local time markets are made from
FRAGGERS = 8  # players in a session top fragger market
WEEK_TEAMS = 8  # teams in the weekly market
HEAD_TO_HEADS = 2
RECENT = 20  # recent published matches used to rank teams and players
SYSTEM_EMAIL = "auto-markets@tdl.invalid"


def local_tz() -> ZoneInfo:
    return ZoneInfo(settings.ANALYTICS_TIME_ZONE)


def today() -> dt.date:
    return timezone.localtime(timezone.now(), local_tz()).date()


def session_start(date: dt.date, session: str) -> dt.datetime:
    return dt.datetime.combine(date, SESSIONS[session], tzinfo=local_tz())


def system_user() -> User:
    """The account automatic markets are made by: it can't sign in or play."""
    user, made = User.objects.get_or_create(
        email=SYSTEM_EMAIL, defaults={"display_name": "Automatic", "is_active": False}
    )
    if made:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def current_season() -> Season | None:
    return Season.objects.filter(is_active=True).first() or Season.objects.first()


def is_scrim_day(conf: AutoSettings, date: dt.date) -> bool:
    return date.weekday() in (conf.weekdays or []) and date.isoformat() not in (
        conf.skip_dates or []
    )


# -- who plays -------------------------------------------------------------------------------------


def last_lobby(session: str, before: dt.date) -> list[int]:
    """Teams in the last published session at this hour ("... 8PM"), before ``before``."""
    days = (
        MatchDay.objects.filter(title__iendswith=f" {session}", date__lt=before)
        .filter(matches__status=Match.Status.PUBLISHED)
        .distinct()
        .order_by("-date", "-pk")
    )
    for day in days[:1]:
        return sorted(
            set(
                TeamMatchResult.objects.filter(
                    match__match_day=day, match__status=Match.Status.PUBLISHED
                ).values_list("team_id", flat=True)
            )
        )
    return []


def team_form(teams: list[int]) -> dict[int, float]:
    """Average points over each team's recent published matches (0 with none)."""
    rows = TeamMatchResult.objects.filter(
        team_id__in=teams, match__status=Match.Status.PUBLISHED
    ).order_by("-match__started_at", "-match_id")
    seen: dict[int, list[int]] = defaultdict(list)
    for team, points in rows.values_list("team_id", "total_points"):
        if len(seen[team]) < RECENT:
            seen[team].append(points)
    return {t: (sum(seen[t]) / len(seen[t]) if seen[t] else 0.0) for t in teams}


def top_players(teams: list[int], n: int = FRAGGERS) -> list[int]:
    """The ``n`` players of these teams with the most kills a match lately (3+ matches)."""
    rows = (
        PlayerMatchResult.objects.filter(
            player__current_team_id__in=teams, match__status=Match.Status.PUBLISHED
        )
        .order_by("-match__started_at", "-match_id")
        .values_list("player_id", "kills")
    )
    kills: dict[int, list[int]] = defaultdict(list)
    for player, k in rows:
        if len(kills[player]) < RECENT:
            kills[player].append(k)
    ranked = sorted(
        (p for p in kills if len(kills[p]) >= 3),
        key=lambda p: (-sum(kills[p]) / len(kills[p]), p),
    )
    return ranked[:n]


def close_pairs(teams: list[int], form: dict[int, float], n: int = HEAD_TO_HEADS) -> list[list]:
    """``n`` head-to-heads between the closest-matched teams, no team twice."""
    order = sorted(teams, key=lambda t: (-form[t], t))
    gaps = sorted(
        (
            (abs(form[a] - form[b]), i)
            for i, (a, b) in enumerate(zip(order, order[1:], strict=False))
        ),
    )
    used: set[int] = set()
    pairs = []
    for _, i in gaps:
        a, b = order[i], order[i + 1]
        if a in used or b in used:
            continue
        pairs.append([a, b])
        used |= {a, b}
        if len(pairs) == n:
            break
    return pairs


def kills_line(season: Season) -> int:
    """A total-kills line near the middle of recent matches (so over and under are close)."""
    totals = list(
        TeamMatchResult.objects.filter(match__status=Match.Status.PUBLISHED)
        .values("match")
        .annotate(n=Count("id"))
        .order_by("-match__started_at", "-match")
        .values_list("match", flat=True)[:30]
    )
    sums = defaultdict(int)
    for match, k in TeamMatchResult.objects.filter(match_id__in=totals).values_list(
        "match_id", "kills"
    ):
        sums[match] += k
    return max(1, round(median(sums.values()))) if sums else 40


# -- making markets --------------------------------------------------------------------------------


class Run:
    def __init__(self, date: dt.date, actor):
        self.date, self.actor = date, actor
        self.made: list[str] = []
        self.notes: list[str] = []
        self.season = current_season()
        self.now = timezone.now()

    def market(self, key: str, category: str, title: str, params: dict, closes_at, fixture=None):
        """Make one market with suggested odds and open it, unless ``key`` was made before."""
        key = f"{self.date.isoformat()}:{key}"
        if AutoMarket.objects.filter(key=key).exists():
            return
        try:
            odds = suggest_odds(
                season=self.season, category=category, params=params, fixture=fixture
            )["odds"]
            with transaction.atomic():
                m = create_market(
                    actor=self.actor, category=category, title=title, season=self.season,
                    fixture=fixture, params=params, odds=odds, opens_at=self.now,
                    closes_at=closes_at,
                    description="Made automatically with suggested odds.",
                )  # fmt: skip
                transition(m, S.OPEN, actor=self.actor)
                AutoMarket.objects.create(key=key, market=m)
        except MarketError as exc:
            note = f"{Market.Category(category).label}: not made. {exc}"
            if note not in self.notes:  # once, not once a match
                self.notes.append(note)
            return
        self.made.append(title)

    def session(self, session: str) -> None:
        closes = session_start(self.date, session)
        if closes <= self.now:
            return
        common = {"season": self.season, "date": self.date, "session": session}
        whole, _ = Fixture.objects.get_or_create(
            **common, match_number=None, defaults={"scheduled_at": closes}
        )
        teams = sorted(whole.teams.values_list("pk", flat=True))
        if not teams:
            teams = last_lobby(session, self.date)
            if len(teams) < 2:
                self.notes.append(
                    f"{session}: no earlier {session} session to copy teams from. "
                    "Set the lobby, then press Make tonight's now."
                )
                return
            whole.teams.set(teams)
        matches = [
            Fixture.objects.get_or_create(
                **common, match_number=n, defaults={"scheduled_at": closes}
            )[0]
            for n in range(1, MATCHES + 1)
        ]
        line = kills_line(self.season)
        for f in matches:
            n, k = f.match_number, f"{session}:m{f.match_number}"
            self.market(f"{k}:booyah", C.BOOYAH, f"Booyah · Match {n}", {"teams": teams}, closes, f)
            self.market(
                f"{k}:kills", C.TOTAL_KILLS, f"Total kills · Match {n}", {"line": line}, closes, f
            )
            self.market(
                f"{k}:first-blood", C.FIRST_BLOOD, f"First blood · Match {n}",
                {"teams": teams}, closes, f,
            )  # fmt: skip
        self.market(
            f"{session}:winner", C.SESSION_WINNER, f"{session} winner", {"teams": teams},
            closes, whole,
        )  # fmt: skip
        self.market(
            f"{session}:booyahs", C.MOST_BOOYAHS, f"Most Booyahs · {session}", {"teams": teams},
            closes, whole,
        )  # fmt: skip
        players = top_players(teams)
        if len(players) >= 2:
            self.market(
                f"{session}:fragger", C.SESSION_FRAGGER, f"{session} top fragger",
                {"players": players}, closes, whole,
            )  # fmt: skip
        names = dict(Team.objects.filter(pk__in=teams).values_list("pk", "name"))
        for a, b in close_pairs(teams, team_form(teams)):
            self.market(
                f"{session}:h2h:{a}-{b}", C.SESSION_H2H,
                f"{names[a]} v {names[b]}: more points ({session})",
                {"teams": [a, b]}, closes, whole,
            )  # fmt: skip

    def week(self) -> None:
        """Mondays: most points from today to Sunday, between the teams in form."""
        if self.date.weekday() != 0:
            return
        closes = session_start(self.date, "8PM")
        if closes <= self.now:
            return
        since = self.date - dt.timedelta(days=14)
        recent = sorted(
            set(
                TeamMatchResult.objects.filter(
                    match__status=Match.Status.PUBLISHED, match__match_day__date__gte=since
                ).values_list("team_id", flat=True)
            )
        )
        form = team_form(recent)
        teams = sorted(recent, key=lambda t: (-form[t], t))[:WEEK_TEAMS]
        if len(teams) < 2:
            return
        end = self.date + dt.timedelta(days=6)
        self.market(
            "week:winner", C.RANGE_WINNER,
            f"Most points this week ({self.date:%d %b} - {end:%d %b})",
            {"teams": teams, "from": self.date.isoformat(), "to": end.isoformat()}, closes,
        )  # fmt: skip


def run(date: dt.date | None = None, *, force: bool = False, actor=None) -> dict:
    """Make the day's missing markets. ``force`` ignores the switch, the days and the time
    (the staff "Make tonight's now" button). Returns what happened."""
    date = date or today()
    conf = AutoSettings.get()
    now_local = timezone.localtime(timezone.now(), local_tz())
    if not force:
        if not (conf.enabled and settings.PREDICTIONS_ENABLED and is_scrim_day(conf, date)):
            return {"date": date.isoformat(), "made": [], "notes": ["Not a scrim day."]}
        if date == now_local.date() and now_local.time() < STARTS_AT:
            return {"date": date.isoformat(), "made": [], "notes": ["Too early."]}
    job = Run(date, actor or system_user())
    if job.season is None:
        job.notes.append("There's no season yet.")
    else:
        for session in SESSIONS:
            job.session(session)
        job.week()
    report = {"date": date.isoformat(), "made": job.made, "notes": job.notes}
    if force or job.made or job.notes:
        AutoSettings.objects.filter(pk=conf.pk).update(
            last_run_at=timezone.now(), last_report=report
        )
    return report


def rebuild_session(fixture: Fixture, actor) -> dict:
    """After staff change a session's lobby: remake its automatic markets that nobody has
    predicted on yet, with the new teams. Markets with predictions are left as they are."""
    prefix = f"{fixture.date.isoformat()}:{fixture.session}:"
    for row in AutoMarket.objects.filter(key__startswith=prefix).select_related("market"):
        m = row.market
        if m is None:
            continue  # staff deleted it: stays deleted
        if m.status in (S.SETTLED, S.VOID) or m.bets.exists() or m.legs.exists():
            continue
        with transaction.atomic():
            row.delete()
            m.delete()  # its choices, odds history and status log go with it
    job = Run(fixture.date, actor)
    if job.season is not None:
        job.session(fixture.session)
    return {"date": fixture.date.isoformat(), "made": job.made, "notes": job.notes}
