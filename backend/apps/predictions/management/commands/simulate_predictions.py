"""Play a whole predictions season with made-up users and results, then check every coin.

Everything happens inside one transaction that is rolled back at the end (unless --keep),
so it is safe on staging: no user, team, match or wallet it makes survives. The report
says what was played, what was refused, and whether every wallet and bet adds up.
"""

from __future__ import annotations

import datetime as dt
import random
import uuid
from collections import Counter
from decimal import Decimal
from fractions import Fraction

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import StaffProfile, User
from apps.league.models import Match, MatchDay, Player, ScoringRule, Season, Stage, Team
from apps.predictions.markets import (
    HANDICAPS,
    MATCH_MARKETS,
    RANGE_MARKETS,
    SEASON_MARKETS,
    SESSION_MARKETS,
    MarketError,
    create_market,
    outcome_specs,
    place_bet,
    transition,
)
from apps.predictions.models import (
    Bet,
    Fixture,
    LedgerEntry,
    Market,
    Multiple,
    Settlement,
    Wallet,
)
from apps.predictions.multiples import place_multiple
from apps.predictions.services import check_wallets, initial_coins, wallet_for
from apps.predictions.settlement import correct, settle, suggest, void
from apps.results.models import MatchEvent, PlayerMatchResult, TeamMatchResult
from apps.results.standings import rebuild_season

C, S, B = Market.Category, Market.Status, Bet.Status
DOMAIN = "sim.invalid"


class Rollback(Exception):
    """Raised at the end to undo everything the simulation made."""


class Command(BaseCommand):
    help = "Simulate users betting on every market type, settle it all, and check every coin."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=40)
        parser.add_argument("--teams", type=int, default=12)
        parser.add_argument("--matches", type=int, default=4, help="Matches in each session")
        parser.add_argument("--sessions", type=int, default=2)
        parser.add_argument("--bets", type=int, default=12, help="Bets each user tries")
        parser.add_argument("--multiples", type=int, default=3, help="Multiples each user tries")
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument("--report", default="", help="Write the report to this file too")
        parser.add_argument(
            "--keep", action="store_true", help="Keep what it made (local only, never live)"
        )

    def handle(self, *args, **opts):
        if opts["keep"] and not settings.DEBUG:
            raise CommandError("--keep only works with DEBUG on (never on a live server).")
        seed = opts["seed"] if opts["seed"] is not None else random.randrange(1_000_000)
        self.rng = random.Random(seed)
        self.counts: Counter = Counter()
        self.lines: list[str] = []
        try:
            with transaction.atomic():
                ok = self.play(opts)
                if not opts["keep"]:
                    raise Rollback
        except Rollback:
            pass
        kept = "kept" if opts["keep"] else "rolled back: nothing was saved"
        report = "\n".join([f"# Predictions simulation (seed {seed}, {kept})", "", *self.lines, ""])
        if opts["report"]:
            with open(opts["report"], "w", encoding="utf-8") as fh:
                fh.write(report)
        self.stdout.write(report)
        if not ok:
            raise CommandError("The simulation found problems (see above).")

    # -- the season ------------------------------------------------------------------------------

    def play(self, opts) -> bool:
        rng, now = self.rng, timezone.now()
        tag = uuid.uuid4().hex[:6]
        rule = ScoringRule.objects.create(
            name=f"Sim {tag}", placement_points={"1": 12, "2": 9, "3": 8, "4": 7, "5": 6}
        )
        season = Season.objects.create(name=f"Sim {tag}", slug=f"sim-{tag}", scoring_rule=rule)
        stage = Stage.objects.create(season=season, name="Sim")
        teams = [Team.objects.create(name=f"Sim {tag} T{i + 1}") for i in range(opts["teams"])]
        base = rng.randint(10**15, 10**16)
        self.squads = {
            t.pk: [
                Player.objects.create(
                    game_uid=base + n * 4 + k,
                    current_name_raw=f"{t.name} P{k}",
                    display_name=f"{t.name} P{k}",
                    search_name=f"{t.name} p{k}".casefold(),
                    current_team=t,
                )  # fmt: skip
                for k in range(4)
            ]
            for n, t in enumerate(teams)
        }
        players = [p for squad in self.squads.values() for p in squad]
        staff = User.objects.create_user(email=f"staff-{tag}@{DOMAIN}", password=None)
        StaffProfile.objects.create(user=staff)
        users = [
            User.objects.create_user(
                email=f"u{i}-{tag}@{DOMAIN}", password=None, display_name=f"Sim{tag}{i}"
            )
            for i in range(opts["users"])
        ]

        # Fixtures and markets: every type, before anything is played.
        markets: list[Market] = []
        days = []
        for d in range(opts["sessions"]):
            # Days already gone, so date-range markets over them can be settled today.
            date = now.date() - dt.timedelta(days=opts["sessions"] - d)
            day = MatchDay.objects.create(
                stage=stage, number=d + 1, date=date, title=f"SIM {d} 8PM"
            )
            whole = self.fixture(season, date, None, now)
            days.append((day, whole, []))
            for kind in sorted(SESSION_MARKETS):
                markets.append(self.market(staff, season, whole, kind, teams, now, players))
            for n in range(1, opts["matches"] + 1):
                one = self.fixture(season, date, n, now)
                days[-1][2].append(one)
                for kind in sorted(MATCH_MARKETS):
                    markets.append(self.market(staff, season, one, kind, teams, now, players))
        self.span = (days[0][0].date, days[-1][0].date)
        for kind in sorted(SEASON_MARKETS):
            markets.append(self.market(staff, season, None, kind, teams, now, players))
        kinds = Counter(m.category for m in markets)
        self.lines.append(
            f"- {len(users)} players, {len(teams)} teams, {len(markets)} markets "
            f"({', '.join(f'{k}: {v}' for k, v in sorted(kinds.items()))})"
        )

        # Betting, including requests the server must refuse.
        for user in users:
            for _ in range(opts["bets"]):
                self.try_bet(user, rng.choice(markets))
            self.try_refused(user, rng.choice(markets))
        self.lines.append(
            f"- Bets placed: {self.counts['placed']}; resends that didn't charge twice: "
            f"{self.counts['resend_ok']}; refused as they should be: {self.counts['refused_ok']}; "
            f"refused for other reasons: {self.counts['refused_other']}"
        )
        for user in users:
            for _ in range(opts["multiples"]):
                self.try_multiple(user, markets)
        self.lines.append(
            f"- Multiples placed: {self.counts['multiples']}; refused for picks on the same "
            f"match: {self.counts['same_match']}; for coins: {self.counts['multiple_coins']}; "
            f"for other reasons: {self.counts['multiple_other']}"
        )

        # Play the matches, publish them and rebuild the standings.
        for day, whole, ones in days:
            for one in ones:
                match = Match.objects.create(
                    match_day=day, number=one.match_number, status=Match.Status.PUBLISHED
                )
                self.results(match, teams)
                one.match = match
                one.save(update_fields=["match"])
            whole.match_day = day
            whole.save(update_fields=["match_day"])
        rebuild_season(season)

        # Settle everything from the results; void one market, correct a few.
        for m in markets:
            transition(m, S.CLOSED, actor=staff)
        to_void = rng.choice(markets)
        for m in markets:
            m = Market.objects.get(pk=m.pk)
            if m == to_void:
                void(m, actor=staff, reason="Simulation: void one market")
                self.counts["voided"] += 1
                continue
            s = suggest(m)
            if s["kind"] == "VOID":
                void(m, actor=staff, reason=s["note"] or "Void")
                self.counts["voided"] += 1
                continue
            settle(m, actor=staff, winners=s["winners"], voids=s["voids"])
            self.counts["settled"] += 1
            if s["dead_heat"] > 1:
                self.counts["dead_heats"] += 1
        settled = [m for m in markets if Market.objects.get(pk=m.pk).status == S.SETTLED]
        for m in rng.sample(settled, min(3, len(settled))):
            others = list(m.outcomes.values_list("pk", flat=True))
            correct(
                Market.objects.get(pk=m.pk),
                actor=staff,
                kind=Settlement.Kind.SETTLE,
                reason="Simulation: result corrected",
                winners=[rng.choice(others)],
                key=str(uuid.uuid4()),
            )
            self.counts["corrected"] += 1
        self.lines.append(
            f"- Markets settled: {self.counts['settled']} "
            f"({self.counts['dead_heats']} dead heats), voided: {self.counts['voided']}, "
            f"corrected afterwards: {self.counts['corrected']}"
        )
        return self.audit(users, markets)

    def fixture(self, season, date, number, now) -> Fixture:
        return Fixture.objects.create(
            season=season,
            date=date,
            session="8PM",
            match_number=number,
            scheduled_at=now + dt.timedelta(hours=1),
        )

    def market(self, staff, season, fixture, kind, teams, now, players=()) -> Market:
        rng = self.rng
        if kind in RANGE_MARKETS:
            start, end = self.span
            span = {"from": start.isoformat(), "to": end.isoformat()}
        if kind in (C.TOP_N, C.OVERALL_TOP_N):
            params = {"team": rng.choice(teams).pk, "n": rng.choice([3, 5, 10])}
        elif kind == C.RANGE_TOP_N:
            params = {"team": rng.choice(teams).pk, "n": rng.choice([3, 5, 10]), **span}
        elif kind == C.RANGE_WINNER:
            params = {
                "teams": [t.pk for t in rng.sample(teams, rng.randint(3, len(teams)))],
                **span,
            }
        elif kind == C.RANGE_FRAGGER:
            params = {"players": [p.pk for p in rng.sample(players, rng.randint(3, 8))], **span}
        elif kind in (C.SESSION_FRAGGER, C.SEASON_FRAGGER):
            params = {"players": [p.pk for p in rng.sample(players, rng.randint(3, 8))]}
        elif kind == C.SESSION_KILLS:
            params = {"team": rng.choice(teams).pk, "line": rng.randint(10, 40)}
        elif kind == C.SESSION_H2H:
            params = {"teams": [t.pk for t in rng.sample(teams, 2)]}
        elif kind == C.TEAM_KILLS:
            params = {"team": rng.choice(teams).pk, "line": rng.randint(3, 12)}
        elif kind in (C.H2H_PLACEMENT, C.H2H_KILLS, C.H2H_POINTS):
            params = {"teams": [t.pk for t in rng.sample(teams, 2)]}
        elif kind == C.TOTAL_KILLS:
            params = {"line": rng.randint(len(teams) * 4, len(teams) * 10)}
        elif kind in HANDICAPS:
            params = {"teams": [t.pk for t in rng.sample(teams, 2)], "line": rng.randint(1, 8)}
        elif kind == C.FINISH_BAND:
            params = {"team": rng.choice(teams).pk}
        elif kind == C.PLAYER_KILLS:
            params = {"player": rng.choice(players).pk, "line": rng.randint(1, 5)}
        elif kind == C.PLAYER_DAMAGE:
            params = {"player": rng.choice(players).pk, "line": rng.randint(4, 20) * 100}
        elif kind == C.PLAYER_H2H:
            params = {"players": [p.pk for p in rng.sample(players, 2)]}
        elif kind in (C.TOP_FRAGGER, C.FIRST_DEATH):
            params = {"players": [p.pk for p in rng.sample(players, rng.randint(3, 8))]}
        else:
            params = {"teams": [t.pk for t in rng.sample(teams, rng.randint(3, len(teams)))]}
        odds = {spec["code"]: f"{rng.uniform(1.2, 9):.2f}" for spec in outcome_specs(kind, params)}
        m = create_market(
            actor=staff,
            category=kind,
            title=f"Sim {kind}",
            season=season,
            fixture=fixture,
            params=params,
            odds=odds,
            opens_at=now - dt.timedelta(minutes=1),
            closes_at=now + dt.timedelta(hours=1),
        )
        return transition(m, S.OPEN, actor=staff)

    def try_bet(self, user, market) -> None:
        rng = self.rng
        outcome = rng.choice(list(market.outcomes.all()))
        key = uuid.uuid4()
        stake = rng.choice([10, 25, 50, 100, 150, 250, 500])
        try:
            bet, _ = place_bet(
                user, market_id=market.pk, outcome_id=outcome.pk, stake=stake, client_key=key
            )
        except MarketError as exc:
            self.counts["refused_ok" if exc.code in ("coins", "stake") else "refused_other"] += 1
            return
        self.counts["placed"] += 1
        if rng.random() < 0.2:  # the phone sends the same tap again
            again, created = place_bet(
                user, market_id=market.pk, outcome_id=outcome.pk, stake=stake, client_key=key
            )
            self.counts["resend_ok" if not created and again.pk == bet.pk else "resend_bad"] += 1

    def try_multiple(self, user, markets) -> None:
        rng = self.rng
        picks = []
        for m in rng.sample(markets, rng.randint(2, 4)):
            o = rng.choice(list(m.outcomes.all()))
            picks.append({"market": m.pk, "outcome": o.pk, "expected_odds": str(o.odds)})
        stake = rng.choice([10, 20, 50, 100])
        try:
            place_multiple(user, picks=picks, stake=stake, client_key=uuid.uuid4())
        except MarketError as exc:
            key = {"same_match": "same_match", "coins": "multiple_coins"}
            self.counts[key.get(exc.code, "multiple_other")] += 1
            return
        self.counts["multiples"] += 1

    def try_refused(self, user, market) -> None:
        outcome = market.outcomes.first()
        balance = wallet_for(user).balance
        for stake in (5, 501, balance + 1 if balance + 1 >= 10 else 5):
            try:
                place_bet(
                    user,
                    market_id=market.pk,
                    outcome_id=outcome.pk,
                    stake=stake,
                    client_key=uuid.uuid4(),
                )
            except MarketError:
                self.counts["refused_ok"] += 1
            else:
                self.counts["accepted_bad"] += 1

    def results(self, match, teams) -> None:
        """Team and player results, kill and death times, and damage (missing in one match
        out of five, as when the replay doesn't cover it)."""
        rng = self.rng
        order = rng.sample(teams, len(teams))
        has_damage = rng.random() > 0.2
        deaths = []
        for place, team in enumerate(order, start=1):
            squad = self.squads[team.pk]
            kills = [rng.choice([0, 0, 1, 1, 2, 3, 4, 6]) for _ in squad]
            TeamMatchResult.objects.create(
                match=match, team=team, in_game_name=team.name, placement=place,
                kills=sum(kills), placement_points=0, kill_points=0, total_points=0,
            )  # fmt: skip
            for player, k in zip(squad, kills, strict=True):
                PlayerMatchResult.objects.create(
                    match=match, player=player, team=team, raw_name=player.display_name,
                    display_name=player.display_name, kills=k,
                    damage_dealt=k * 220 + rng.randint(0, 600) if has_damage else None,
                )  # fmt: skip
                # Whole seconds, so two players sometimes die at the same moment.
                deaths.append((rng.randint(60, 1500), player, team))
        for at, player, team in deaths:
            MatchEvent.objects.create(
                match=match, kind=MatchEvent.Kind.DEATH, source=MatchEvent.Source.REPLAY_INFO,
                game_time_s=at, actor_player=player, actor_team=team,
            )  # fmt: skip
        killer, victim = rng.sample(teams, 2)
        MatchEvent.objects.create(
            match=match, kind=MatchEvent.Kind.KILL, source=MatchEvent.Source.REPLAY_INFO,
            game_time_s=rng.randint(30, 59), actor_team=killer, target_team=victim,
        )  # fmt: skip

    # -- checks ----------------------------------------------------------------------------------

    def audit(self, users, markets) -> bool:
        problems: list[str] = []
        problems += [f"wallet {p.wallet_id}: {p.problem}" for p in check_wallets()]
        if self.counts["resend_bad"]:
            problems.append(f"{self.counts['resend_bad']} resend(s) charged twice")
        if self.counts["accepted_bad"]:
            problems.append(f"{self.counts['accepted_bad']} bad stake(s) were accepted")

        start = initial_coins()
        bets = Bet.objects.filter(market__in=markets).select_related("market", "outcome")
        for bet in bets:
            latest = bet.market.settlements.order_by("-version").first()
            want = self.expected_payout(bet, latest)
            if bet.status == B.PENDING:
                problems.append(f"bet {bet.pk} still pending")
            elif bet.payout != want:
                problems.append(f"bet {bet.pk}: paid {bet.payout}, rules say {want}")
            if LedgerEntry.objects.filter(bet=bet, kind="STAKE").count() != 1:
                problems.append(f"bet {bet.pk}: stake not taken exactly once")
        multiples = Multiple.objects.filter(user__in=users).prefetch_related("legs__market")
        for m in multiples:
            want = self.expected_multiple(m)
            if m.status == B.PENDING:
                problems.append(f"multiple {m.pk} still pending")
            elif m.payout != want:
                problems.append(f"multiple {m.pk}: paid {m.payout}, rules say {want}")
            if LedgerEntry.objects.filter(multiple=m, kind="STAKE").count() != 1:
                problems.append(f"multiple {m.pk}: stake not taken exactly once")
        for user in users:
            w = Wallet.objects.get(user=user)
            mine = [*bets.filter(user=user), *multiples.filter(user=user)]
            owed = start - sum(b.stake for b in mine) + sum(b.payout or 0 for b in mine)
            if w.balance + sum(b.unrecovered for b in mine) != owed:
                problems.append(f"{user.email}: balance {w.balance} doesn't match its bets")
            if w.balance < 0:
                problems.append(f"{user.email}: negative balance")

        coins = sum(Wallet.objects.filter(user__in=users).values_list("balance", flat=True))
        unrecovered = sum(b.unrecovered for b in bets) + sum(m.unrecovered for m in multiples)
        self.lines.append(
            f"- Coins: {start * len(users):,} handed out, {coins:,} held at the end; "
            f"{unrecovered} couldn't be taken back by corrections (recorded on the bets)"
        )
        self.lines.append(
            f"- Bets checked against the rules: {bets.count()} singles, "
            f"{multiples.count()} multiples"
        )
        if problems:
            self.lines.append(f"- **{len(problems)} problem(s):**")
            self.lines += [f"  - {p}" for p in problems[:50]]
            return False
        self.lines.append("- Every wallet matches its ledger and every bet was paid by the rules.")
        return True

    @staticmethod
    def expected_multiple(m: Multiple) -> int:
        """Worked out again from scratch: each pick from its market's latest result."""
        total = Fraction(m.stake)
        voids = 0
        legs = list(m.legs.all())
        for leg in legs:
            latest = leg.market.settlements.order_by("-version").first()
            if (
                latest.kind == Settlement.Kind.VOID
                or latest.void_outcomes.filter(pk=leg.outcome_id).exists()
            ):
                voids += 1
            elif latest.winning_outcomes.filter(pk=leg.outcome_id).exists():
                total *= Fraction(leg.odds_accepted) / latest.dead_heat
            else:
                return 0
        if voids == len(legs):
            return m.stake
        return min(int(total), settings.PREDICTIONS_MAX_RETURN)

    @staticmethod
    def expected_payout(bet: Bet, latest: Settlement | None) -> int:
        """Worked out again from scratch, without the settlement code."""
        if latest is None:
            return 0
        if (
            latest.kind == Settlement.Kind.VOID
            or latest.void_outcomes.filter(pk=bet.outcome_id).exists()
        ):
            return bet.stake
        if latest.winning_outcomes.filter(pk=bet.outcome_id).exists():
            return int(Decimal(bet.stake) * bet.odds_accepted / latest.dead_heat)  # rounded down
        return 0
