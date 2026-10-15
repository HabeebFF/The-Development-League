"""Virtual coins: a wallet per user and an append-only ledger of every coin movement.

Coins have no money value: they can't be bought, cashed out or sent to another user.

The ledger is the record of what happened; ``Wallet.balance`` is a stored copy kept in the
same database transaction as each entry (see ``services.post_entry``), so it can be read
and locked cheaply. ``check_wallets`` proves the two agree.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

MIN_ODDS = Decimal("1.01")
MAX_ODDS = Decimal("1000.00")


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="wallet"
    )
    balance = models.BigIntegerField(default=0, help_text="Whole coins; never below 0")
    entry_count = models.PositiveIntegerField(default=0, help_text="Ledger entries so far")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(balance__gte=0), name="predictions_wallet_balance_not_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} ({self.balance} coins)"


class LedgerEntry(models.Model):
    """One coin movement. Never edited or deleted; mistakes are fixed with a new entry."""

    class Kind(models.TextChoices):
        INITIAL = "INITIAL", "Starting coins"
        STAKE = "STAKE", "Stake"
        PAYOUT = "PAYOUT", "Winning payout"
        REFUND = "REFUND", "Refund (void)"
        CORRECTION = "CORRECTION", "Settlement correction"
        ADJUSTMENT = "ADJUSTMENT", "Staff adjustment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="entries")
    seq = models.PositiveIntegerField(help_text="1, 2, 3... per wallet, in order")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.BigIntegerField(help_text="Coins added (positive) or taken (negative)")
    balance_before = models.BigIntegerField()
    balance_after = models.BigIntegerField()
    idempotency_key = models.CharField(
        max_length=120, unique=True, help_text="The same operation can only happen once"
    )
    reason = models.CharField(max_length=300, blank=True)
    bet = models.ForeignKey(
        "Bet", on_delete=models.PROTECT, null=True, blank=True, related_name="entries"
    )
    settlement = models.ForeignKey(
        "Settlement", on_delete=models.PROTECT, null=True, blank=True, related_name="entries"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="The staff member who made an adjustment",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "ledger entries"
        constraints = [
            models.UniqueConstraint(fields=["wallet", "seq"], name="predictions_entry_seq"),
            models.CheckConstraint(
                condition=Q(balance_after=F("balance_before") + F("amount")),
                name="predictions_entry_adds_up",
            ),
            models.CheckConstraint(
                condition=Q(balance_after__gte=0), name="predictions_entry_not_negative"
            ),
            models.CheckConstraint(condition=~Q(amount=0), name="predictions_entry_not_zero"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.amount:+d} -> {self.balance_after}"


# -- markets -------------------------------------------------------------------------------------


class Fixture(models.Model):
    """A planned match (or a whole session) that markets are about.

    Matches only exist on the site once their logs are uploaded, after they are played, so
    markets hang off a fixture; staff link it to the real match afterwards.
    """

    class Session(models.TextChoices):
        PM8 = "8PM", "8PM"
        PM10 = "10PM", "10PM"

    season = models.ForeignKey("league.Season", on_delete=models.PROTECT, related_name="+")
    date = models.DateField()
    session = models.CharField(max_length=4, choices=Session.choices)
    match_number = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Empty for the whole session"
    )
    title = models.CharField(max_length=120, blank=True)
    scheduled_at = models.DateTimeField(help_text="Planned start")
    match = models.ForeignKey(
        "league.Match", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    match_day = models.ForeignKey(
        "league.MatchDay", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "session", "match_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["season", "date", "session", "match_number"],
                nulls_distinct=False,
                name="predictions_fixture_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.title or self.default_title()

    def default_title(self) -> str:
        what = f"Match {self.match_number}" if self.match_number else "Session"
        return f"{self.date:%d %b} {self.session} {what}"


class Market(models.Model):
    class Category(models.TextChoices):
        BOOYAH = "BOOYAH", "Booyah (match winner)"
        TOP_N = "TOP_N", "Team finishes in the top N"
        H2H_PLACEMENT = "H2H_PLACEMENT", "Head-to-head: finishes higher"
        H2H_KILLS = "H2H_KILLS", "Head-to-head: more kills"
        H2H_POINTS = "H2H_POINTS", "Head-to-head: more points"
        TEAM_KILLS = "TEAM_KILLS", "Team kills"
        SESSION_WINNER = "SESSION_WINNER", "Session winner"
        MOST_BOOYAHS = "MOST_BOOYAHS", "Most Booyahs in the session"
        OVERALL_WINNER = "OVERALL_WINNER", "Overall winner"
        OVERALL_TOP_N = "OVERALL_TOP_N", "Overall top N"
        TOTAL_KILLS = "TOTAL_KILLS", "Total kills in the match"
        KILLS_HANDICAP = "KILLS_HANDICAP", "Kills handicap"
        POINTS_HANDICAP = "POINTS_HANDICAP", "Points handicap"
        FINISH_BAND = "FINISH_BAND", "Finishing position"
        FIRST_OUT = "FIRST_OUT", "First team out"
        FIRST_BLOOD = "FIRST_BLOOD", "First blood"
        PLAYER_KILLS = "PLAYER_KILLS", "Player kills"
        TOP_FRAGGER = "TOP_FRAGGER", "Top fragger"
        PLAYER_H2H = "PLAYER_H2H", "Player head-to-head: more kills"
        FIRST_DEATH = "FIRST_DEATH", "First player to die"
        PLAYER_DAMAGE = "PLAYER_DAMAGE", "Player damage"
        SESSION_FRAGGER = "SESSION_FRAGGER", "Session top fragger"
        SESSION_KILLS = "SESSION_KILLS", "Team kills in the session"
        SESSION_H2H = "SESSION_H2H", "Session head-to-head: more points"
        RANGE_WINNER = "RANGE_WINNER", "Most points over chosen dates"
        RANGE_TOP_N = "RANGE_TOP_N", "Top N over chosen dates"
        RANGE_FRAGGER = "RANGE_FRAGGER", "Top fragger over chosen dates"
        SEASON_FRAGGER = "SEASON_FRAGGER", "Season top fragger"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        SUSPENDED = "SUSPENDED", "Suspended"
        CLOSED = "CLOSED", "Closed"
        SETTLED = "SETTLED", "Settled"
        VOID = "VOID", "Void"

    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=16, choices=Category.choices)
    season = models.ForeignKey("league.Season", on_delete=models.PROTECT, related_name="+")
    fixture = models.ForeignKey(
        Fixture, on_delete=models.PROTECT, null=True, blank=True, related_name="markets"
    )
    params = models.JSONField(default=dict, blank=True, help_text="Teams, N, ...")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["closes_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(closes_at__gt=F("opens_at")), name="predictions_market_window"
            ),
        ]

    def __str__(self) -> str:
        return self.title


class Outcome(models.Model):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name="outcomes")
    code = models.CharField(max_length=40, help_text="team:<id>, player:<id>, yes, no, band:<n>")
    label = models.CharField(max_length=120)
    team = models.ForeignKey(
        "league.Team", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    player = models.ForeignKey(
        "league.Player", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    odds = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(MIN_ODDS), MaxValueValidator(MAX_ODDS)],
    )
    is_active = models.BooleanField(default=True)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["market", "sort", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["market", "code"], name="predictions_outcome_code"),
            models.CheckConstraint(
                condition=Q(odds__gte=MIN_ODDS) & Q(odds__lte=MAX_ODDS),
                name="predictions_outcome_odds_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label} @ {self.odds}"


class OddsChange(models.Model):
    outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, related_name="odds_changes")
    old = models.DecimalField(max_digits=7, decimal_places=2)
    new = models.DecimalField(max_digits=7, decimal_places=2)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]


class MarketEvent(models.Model):
    """Every status change of a market, with who did it and why."""

    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=10, blank=True)
    to_status = models.CharField(max_length=10)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reason = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at", "-pk"]


class Bet(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        WON = "WON", "Won"
        LOST = "LOST", "Lost"
        VOID = "VOID", "Void"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bets"
    )
    market = models.ForeignKey(Market, on_delete=models.PROTECT, related_name="bets")
    outcome = models.ForeignKey(Outcome, on_delete=models.PROTECT, related_name="bets")
    stake = models.PositiveIntegerField()
    odds_accepted = models.DecimalField(max_digits=7, decimal_places=2)
    potential_return = models.PositiveIntegerField(help_text="stake x odds, rounded down")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    payout = models.PositiveIntegerField(
        null=True, blank=True, help_text="What the latest settlement says this bet is owed"
    )
    unrecovered = models.PositiveIntegerField(
        default=0, help_text="Coins a correction could not take back (balance was too low)"
    )
    client_key = models.UUIDField(help_text="One per tap on Confirm, so a resend is not a new bet")
    placed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-placed_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "client_key"], name="predictions_bet_once"),
            models.CheckConstraint(condition=Q(stake__gt=0), name="predictions_bet_stake"),
            models.CheckConstraint(
                condition=Q(odds_accepted__gte=MIN_ODDS), name="predictions_bet_odds"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.stake} on {self.outcome}"


class Settlement(models.Model):
    """One decision about a market's result. Never edited: a correction is a new version
    that supersedes the previous one, so the full history stays readable."""

    class Kind(models.TextChoices):
        SETTLE = "SETTLE", "Settled"
        VOID = "VOID", "Voided"

    market = models.ForeignKey(Market, on_delete=models.PROTECT, related_name="settlements")
    version = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=6, choices=Kind.choices)
    winning_outcomes = models.ManyToManyField(Outcome, blank=True, related_name="+")
    void_outcomes = models.ManyToManyField(
        Outcome, blank=True, related_name="+", help_text="Bets on these are refunded"
    )
    evidence = models.JSONField(default=dict, blank=True, help_text="Results it was based on")
    reference = models.CharField(max_length=300, blank=True)
    reason = models.CharField(
        max_length=300, blank=True, help_text="Why it was voided, corrected or overridden"
    )
    summary = models.JSONField(default=dict, blank=True, help_text="Bets won, lost, refunded...")
    dead_heat = models.PositiveSmallIntegerField(
        default=1,
        help_text="Teams tied for the win: a winning bet is paid stake x odds / this number",
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="superseded_by"
    )
    request_key = models.CharField(
        max_length=120, unique=True, null=True, blank=True, help_text="Makes a resend a no-op"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["market", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["market", "version"], name="predictions_settlement_v"),
            models.CheckConstraint(
                condition=Q(dead_heat__gte=1), name="predictions_settlement_dead_heat"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.market} v{self.version} {self.kind}"
