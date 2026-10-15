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

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import StaffProfile, User
from apps.league.models import Match, MatchDay, ScoringRule, Season, Stage, Team
from apps.predictions.markets import (
    MATCH_MARKETS,
    SEASON_MARKETS,
    SESSION_MARKETS,
    MarketError,
    create_market,
    outcome_specs,
    place_bet,
    transition,
)
from apps.predictions.models import Bet, Fixture, LedgerEntry, Market, Settlement, Wallet
from apps.predictions.services import check_wallets, initial_coins, wallet_for
from apps.predictions.settlement import correct, settle, suggest, void
from apps.results.models import TeamMatchResult
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
            date = now.date() + dt.timedelta(days=d)
            day = MatchDay.objects.create(
                stage=stage, number=d + 1, date=date, title=f"SIM {d} 8PM"
            )
            whole = self.fixture(season, date, None, now)
            days.append((day, whole, []))
            for kind in sorted(SESSION_MARKETS):
                markets.append(self.market(staff, season, whole, kind, teams, now))
            for n in range(1, opts["matches"] + 1):
                one = self.fixture(season, date, n, now)
                days[-1][2].append(one)
                for kind in sorted(MATCH_MARKETS):
                    markets.append(self.market(staff, season, one, kind, teams, now))
        for kind in sorted(SEASON_MARKETS):
            markets.append(self.market(staff, season, None, kind, teams, now))
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

    def market(self, staff, season, fixture, kind, teams, now) -> Market:
        rng = self.rng
        if kind in (C.TOP_N, C.OVERALL_TOP_N):
            params = {"team": rng.choice(teams).pk, "n": rng.choice([3, 5, 10])}
        elif kind == C.TEAM_KILLS:
            params = {"team": rng.choice(teams).pk, "line": rng.randint(3, 12)}
        elif kind in (C.H2H_PLACEMENT, C.H2H_KILLS, C.H2H_POINTS):
            params = {"teams": [t.pk for t in rng.sample(teams, 2)]}
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
        rng = self.rng
        order = rng.sample(teams, len(teams))
        for place, team in enumerate(order, start=1):
            TeamMatchResult.objects.create(
                match=match, team=team, in_game_name=team.name, placement=place,
                kills=rng.randint(0, 14), placement_points=0, kill_points=0, total_points=0,
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
        for user in users:
            w = Wallet.objects.get(user=user)
            mine = bets.filter(user=user)
            owed = start - sum(b.stake for b in mine) + sum(b.payout or 0 for b in mine)
            if w.balance + sum(b.unrecovered for b in mine) != owed:
                problems.append(f"{user.email}: balance {w.balance} doesn't match its bets")
            if w.balance < 0:
                problems.append(f"{user.email}: negative balance")

        coins = sum(Wallet.objects.filter(user__in=users).values_list("balance", flat=True))
        unrecovered = sum(b.unrecovered for b in bets)
        self.lines.append(
            f"- Coins: {start * len(users):,} handed out, {coins:,} held at the end; "
            f"{unrecovered} couldn't be taken back by corrections (recorded on the bets)"
        )
        self.lines.append(f"- Bets checked against the rules: {bets.count()}")
        if problems:
            self.lines.append(f"- **{len(problems)} problem(s):**")
            self.lines += [f"  - {p}" for p in problems[:50]]
            return False
        self.lines.append("- Every wallet matches its ledger and every bet was paid by the rules.")
        return True

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
