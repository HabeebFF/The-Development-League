"""Wallet endpoints for players, and wallet tools for staff.

Balances are only ever read here; the one write (a staff adjustment) goes through
``services.post_entry`` like every other coin movement.
"""

from django.conf import settings
from django.db import transaction
from django.db.models import Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import Match, MatchDay, Season
from common.pagination import DefaultPagination
from common.permissions import IsStaff, IsSuperAdmin, PublicRead

from . import settlement
from .markets import (
    MarketError,
    accepting_bets,
    create_market,
    place_bet,
    set_active,
    set_odds,
    transition,
)
from .models import (
    Bet,
    Fixture,
    LedgerEntry,
    Market,
    OddsChange,
    Outcome,
    Settlement,
    Wallet,
)
from .services import CoinError, Kind, can_play, initial_coins, post_entry, wallet_for


class PredictionsOn(BasePermission):
    """The player side is hidden (404) until ``PREDICTIONS_ENABLED`` is switched on."""

    def has_permission(self, request, view) -> bool:
        if not settings.PREDICTIONS_ENABLED:
            raise NotFound()
        return True


class CanPlay(BasePermission):
    message = "League staff can't play predictions."

    def has_permission(self, request, view) -> bool:
        return can_play(request.user)


class EntrySerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "seq",
            "kind",
            "kind_label",
            "amount",
            "balance_before",
            "balance_after",
            "reason",
            "created_at",
        ]


class WalletView(APIView):
    """GET: my balance. The first visit creates the wallet with the starting coins."""

    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def get(self, request):
        wallet = wallet_for(request.user)
        return Response(
            {
                "balance": wallet.balance,
                "starting_coins": initial_coins(),
                "created_at": wallet.created_at,
            }
        )


class WalletEntriesView(APIView):
    """GET: my transaction history, newest first."""

    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def get(self, request):
        wallet = wallet_for(request.user)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(wallet.entries.order_by("-seq"), request, view=self)
        return paginator.get_paginated_response(EntrySerializer(page, many=True).data)


# -- staff ---------------------------------------------------------------------------------------


class StaffWalletSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = Wallet
        fields = ["id", "email", "display_name", "balance", "entry_count", "created_at"]


class StaffEntrySerializer(EntrySerializer):
    actor = serializers.CharField(source="actor.email", default=None, read_only=True)

    class Meta(EntrySerializer.Meta):
        fields = [*EntrySerializer.Meta.fields, "idempotency_key", "actor"]


class AdjustSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=-1_000_000, max_value=1_000_000)
    reason = serializers.CharField(min_length=5, max_length=300)
    key = serializers.UUIDField(help_text="Made once by the form, so a resend changes nothing")

    def validate_amount(self, value: int) -> int:
        if value == 0:
            raise serializers.ValidationError("The amount can't be 0.")
        return value


class WalletAdminViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Staff: every wallet, its ledger, and (Super Admin only) adjustments with a reason."""

    permission_classes = [IsStaff]
    serializer_class = StaffWalletSerializer

    def get_queryset(self):
        qs = Wallet.objects.select_related("user").order_by("-balance", "pk")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search) | Q(user__display_name__icontains=search)
            )
        return qs

    @action(detail=True, methods=["get"])
    def entries(self, request, pk=None):
        wallet = get_object_or_404(Wallet, pk=pk)
        page = self.paginate_queryset(wallet.entries.select_related("actor").order_by("-seq"))
        return self.get_paginated_response(StaffEntrySerializer(page, many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[IsStaff, IsSuperAdmin])
    def adjust(self, request, pk=None):
        wallet = get_object_or_404(Wallet, pk=pk)
        data = AdjustSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            entry, created = post_entry(
                wallet,
                Kind.ADJUSTMENT,
                v["amount"],
                f"adjust:{v['key']}",
                reason=v["reason"],
                actor=request.user,
            )
        except CoinError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(
            StaffEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# -- markets and bets ----------------------------------------------------------------------------

S = Market.Status


def _is_staff(request) -> bool:
    u = request.user
    return bool(u and u.is_authenticated and u.is_league_staff)


def _team(t) -> dict | None:
    if t is None:
        return None
    return {
        "id": t.pk,
        "name": t.name,
        "tag": t.tag,
        "slug": t.slug,
        "logo": t.logo.url if t.logo else None,
        "primary_color": t.primary_color,
    }


def _fixture(f: Fixture | None) -> dict | None:
    if f is None:
        return None
    return {
        "id": f.pk,
        "title": str(f),
        "date": f.date,
        "session": f.session,
        "match_number": f.match_number,
        "scheduled_at": f.scheduled_at,
        "match": f.match_id,
    }


def shown_status(market: Market, now=None) -> str:
    """OPEN or SUSPENDED past the closing time already counts as closed."""
    now = now or timezone.now()
    if market.status in (S.OPEN, S.SUSPENDED) and market.closes_at <= now:
        return S.CLOSED
    return market.status


def market_data(market: Market, now=None) -> dict:
    now = now or timezone.now()
    return {
        "id": market.pk,
        "title": market.title,
        "description": market.description,
        "category": market.category,
        "category_label": market.get_category_display(),
        "season": {"id": market.season_id, "name": market.season.name},
        "fixture": _fixture(market.fixture),
        "status": shown_status(market, now),
        "accepting": accepting_bets(market, now),
        "opens_at": market.opens_at,
        "closes_at": market.closes_at,
        "winners": _winners(market),
        "outcomes": [
            {
                "id": o.pk,
                "code": o.code,
                "label": o.label,
                "team": _team(o.team),
                "odds": str(o.odds),
                "is_active": o.is_active,
            }
            for o in market.outcomes.all()
        ],
    }


def _winners(market: Market) -> list[int]:
    """The winning outcomes of a settled market (latest settlement), else empty."""
    if market.status != S.SETTLED:
        return []
    latest = market.settlements.order_by("-version").first()
    return list(latest.winning_outcomes.values_list("pk", flat=True)) if latest else []


def _markets():
    return Market.objects.select_related("season", "fixture").prefetch_related("outcomes__team")


def _refused(exc: MarketError) -> Response:
    code = {
        "not_found": status.HTTP_404_NOT_FOUND,
        "not_allowed": status.HTTP_403_FORBIDDEN,
        "odds_changed": status.HTTP_409_CONFLICT,
        "key_reused": status.HTTP_409_CONFLICT,
    }.get(exc.code, status.HTTP_400_BAD_REQUEST)
    return Response({"detail": str(exc), "code": exc.code, **exc.extra}, status=code)


class MarketListView(APIView):
    """Markets people can see (never drafts). ``?status=open|closed|settled|void|all``."""

    permission_classes = [PredictionsOn, PublicRead]

    def get(self, request):
        now = timezone.now()
        qs = _markets().exclude(status=S.DRAFT)
        if fixture := request.query_params.get("fixture"):
            qs = (
                qs.filter(fixture__isnull=True)
                if fixture == "none"
                else qs.filter(fixture_id=fixture)
            )
        if season := request.query_params.get("season"):
            qs = qs.filter(season_id=season)
        wanted = request.query_params.get("status", "open").upper()
        if wanted == "OPEN":
            qs = qs.filter(status__in=[S.OPEN, S.SUSPENDED], closes_at__gt=now)
        elif wanted == "CLOSED":
            qs = qs.filter(
                Q(status=S.CLOSED) | Q(status__in=[S.OPEN, S.SUSPENDED], closes_at__lte=now)
            )
        elif wanted in (S.SETTLED, S.VOID):
            qs = qs.filter(status=wanted).order_by("-closes_at")
        elif wanted != "ALL":
            raise ValidationError({"status": "Use open, closed, settled, void or all."})
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([market_data(m, now) for m in page])


class MarketDetailView(APIView):
    permission_classes = [PredictionsOn, PublicRead]

    def get(self, request, pk: int):
        market = get_object_or_404(_markets().exclude(status=S.DRAFT), pk=pk)
        return Response(market_data(market))


class PlaceBetSerializer(serializers.Serializer):
    market = serializers.IntegerField()
    outcome = serializers.IntegerField()
    stake = serializers.IntegerField()
    client_key = serializers.UUIDField()
    expected_odds = serializers.CharField(required=False, max_length=12)


def bet_data(bet: Bet) -> dict:
    return {
        "id": str(bet.pk),
        "market": {
            "id": bet.market_id,
            "title": bet.market.title,
            "status": shown_status(bet.market),
            "fixture": _fixture(bet.market.fixture),
        },
        "outcome": {"id": bet.outcome_id, "label": bet.outcome.label},
        "stake": bet.stake,
        "odds_accepted": str(bet.odds_accepted),
        "potential_return": bet.potential_return,
        "potential_profit": bet.potential_return - bet.stake,
        "payout": bet.payout,
        "status": bet.status,
        "placed_at": bet.placed_at,
        "settled_at": bet.settled_at,
    }


def _bets():
    return Bet.objects.select_related("market__fixture", "outcome")


class BetsView(APIView):
    """GET: my bets (``?status=pending|won|lost|void``). POST: place one."""

    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def get(self, request):
        qs = _bets().filter(user=request.user)
        if wanted := request.query_params.get("status"):
            if wanted.upper() not in Bet.Status.values:
                raise ValidationError({"status": "Use pending, won, lost or void."})
            qs = qs.filter(status=wanted.upper())
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([bet_data(b) for b in page])

    def post(self, request):
        data = PlaceBetSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            bet, created = place_bet(
                request.user,
                market_id=v["market"],
                outcome_id=v["outcome"],
                stake=v["stake"],
                client_key=v["client_key"],
                expected_odds=v.get("expected_odds"),
            )
        except MarketError as exc:
            return _refused(exc)
        bet = _bets().get(pk=bet.pk)
        balance = Wallet.objects.get(user=request.user).balance
        return Response(
            {**bet_data(bet), "balance": balance},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BetDetailView(APIView):
    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def get(self, request, pk):
        return Response(bet_data(get_object_or_404(_bets(), pk=pk, user=request.user)))


# -- staff: fixtures and markets -----------------------------------------------------------------


class FixtureSerializer(serializers.ModelSerializer):
    display_title = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Fixture
        fields = [
            "id",
            "season",
            "date",
            "session",
            "match_number",
            "title",
            "display_title",
            "scheduled_at",
            "match",
            "match_day",
        ]
        validators = []  # the unique check below gives a readable message

    def validate(self, attrs):
        get = lambda k: attrs.get(k, getattr(self.instance, k, None))  # noqa: E731
        clash = Fixture.objects.filter(
            season=get("season"),
            date=get("date"),
            session=get("session"),
            match_number=get("match_number"),
        )
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise ValidationError("That fixture already exists.")
        return attrs


class FixtureAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaff]
    serializer_class = FixtureSerializer

    def get_queryset(self):
        qs = Fixture.objects.order_by("-date", "session", "match_number")
        if season := self.request.query_params.get("season"):
            qs = qs.filter(season_id=season)
        return qs

    @action(detail=True, methods=["get"], url_path="candidate-matches")
    def candidate_matches(self, request, pk=None):
        """Uploaded matches on the fixture's date, the likely one first (same session and
        number), so staff can link the fixture to the real match."""
        fixture = self.get_object()
        qs = (
            Match.objects.filter(Q(match_day__date=fixture.date) | Q(started_at__date=fixture.date))
            .select_related("match_day", "map")
            .order_by("match_day__title", "number")
        )

        def likely(m: Match) -> bool:
            title = (m.match_day.title or "").upper()
            return fixture.session in title and (
                fixture.match_number is None or m.number == fixture.match_number
            )

        rows = [
            {
                "id": m.pk,
                "title": str(m),
                "number": m.number,
                "map": m.map.name if m.map else None,
                "status": m.status,
                "started_at": m.started_at,
                "likely": likely(m),
            }
            for m in qs
        ]
        return Response(sorted(rows, key=lambda r: not r["likely"]))

    @action(detail=True, methods=["get"], url_path="candidate-days")
    def candidate_days(self, request, pk=None):
        """Match days on the fixture's date, the likely one (same session) first, so staff can
        link a whole-session fixture to its uploaded match day."""
        fixture = self.get_object()
        days = (
            MatchDay.objects.filter(
                Q(date=fixture.date) | Q(matches__started_at__date=fixture.date)
            )
            .distinct()
            .prefetch_related("matches")
            .order_by("title", "pk")
        )
        rows = [
            {
                "id": d.pk,
                "title": str(d),
                "matches": len(d.matches.all()),
                "published": sum(m.status == Match.Status.PUBLISHED for m in d.matches.all()),
                "likely": fixture.session in (d.title or "").upper(),
            }
            for d in days
        ]
        return Response(sorted(rows, key=lambda r: not r["likely"]))

    def perform_destroy(self, fixture):
        if fixture.markets.exists():
            raise ValidationError({"detail": "This fixture has markets; void them instead."})
        fixture.delete()


class MarketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=140)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=Market.Category.choices)
    season = serializers.PrimaryKeyRelatedField(queryset=Season.objects.all())
    fixture = serializers.PrimaryKeyRelatedField(
        queryset=Fixture.objects.all(), required=False, allow_null=True
    )
    params = serializers.DictField()
    odds = serializers.DictField(child=serializers.CharField(max_length=12))
    opens_at = serializers.DateTimeField()
    closes_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["closes_at"] <= attrs["opens_at"]:
            raise ValidationError({"closes_at": "Must be after the opening time."})
        fixture = attrs.get("fixture")
        if fixture and fixture.season_id != attrs["season"].pk:
            raise ValidationError({"fixture": "That fixture is in another season."})
        return attrs


class MarketUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=140, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    opens_at = serializers.DateTimeField(required=False)
    closes_at = serializers.DateTimeField(required=False)


class TransitionSerializer(serializers.Serializer):
    to = serializers.ChoiceField(choices=[S.OPEN, S.SUSPENDED, S.CLOSED])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)


def staff_market_data(market: Market) -> dict:
    data = market_data(market)
    data["stored_status"] = market.status
    data["params"] = market.params
    totals = {
        row["outcome"]: row
        for row in market.bets.values("outcome").annotate(bets=Count("pk"), staked=Sum("stake"))
    }
    for o in data["outcomes"]:
        row = totals.get(o["id"], {})
        o["bets"], o["staked"] = row.get("bets", 0), row.get("staked") or 0
    data["bets"] = sum(o["bets"] for o in data["outcomes"])
    return data


class SettleSerializer(serializers.Serializer):
    winners = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
    voids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=300)
    override_reason = serializers.CharField(required=False, allow_blank=True, max_length=300)
    dead_heat = serializers.IntegerField(required=False, min_value=1, max_value=100)


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=300)


class CorrectSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Settlement.Kind.choices)
    winners = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    voids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    reason = serializers.CharField(max_length=300)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=300)
    key = serializers.UUIDField()
    dead_heat = serializers.IntegerField(required=False, min_value=1, max_value=100)


class SettlementActions:
    """Mixed into ``MarketAdminViewSet``: result, settle, void, correct, settlement history."""

    @action(detail=True, methods=["get"], url_path="suggested-result")
    def suggested_result(self, request, pk=None):
        try:
            return Response(settlement.suggest(self.get_market(pk)))
        except MarketError as exc:
            return _refused(exc)

    def _decided(self, request, pk, run) -> Response:
        try:
            done, created = run(self.get_market(pk))
        except MarketError as exc:
            return _refused(exc)
        return Response(
            settlement.settlement_data(done),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        data = SettleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        return self._decided(
            request,
            pk,
            lambda m: settlement.settle(
                m,
                actor=request.user,
                winners=v["winners"],
                voids=v["voids"],
                reference=v.get("reference", ""),
                override_reason=v.get("override_reason", ""),
                dead_heat=v.get("dead_heat"),
            ),
        )

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        data = VoidSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        return self._decided(
            request,
            pk,
            lambda m: settlement.void(
                m, actor=request.user, reason=v["reason"], reference=v.get("reference", "")
            ),
        )

    @action(detail=True, methods=["post"])
    def correct(self, request, pk=None):
        data = CorrectSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        return self._decided(
            request,
            pk,
            lambda m: settlement.correct(
                m,
                actor=request.user,
                kind=v["kind"],
                reason=v["reason"],
                winners=v["winners"],
                voids=v["voids"],
                reference=v.get("reference", ""),
                key=str(v["key"]),
                dead_heat=v.get("dead_heat"),
            ),
        )

    @action(detail=True, methods=["get"])
    def settlements(self, request, pk=None):
        market = self.get_market(pk)
        return Response(
            [
                settlement.settlement_data(s)
                for s in market.settlements.select_related("actor", "supersedes")
            ]
        )


class MarketAdminViewSet(SettlementActions, viewsets.ViewSet):
    """Staff: create markets, edit times and text, move status, see bets and history."""

    permission_classes = [IsStaff]

    def get_market(self, pk) -> Market:
        return get_object_or_404(_markets(), pk=pk)

    def list(self, request):
        qs = _markets().order_by("-closes_at", "-pk")
        if wanted := request.query_params.get("status"):
            qs = qs.filter(status=wanted.upper())
        if fixture := request.query_params.get("fixture"):
            qs = (
                qs.filter(fixture__isnull=True)
                if fixture == "none"
                else qs.filter(fixture_id=fixture)
            )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([staff_market_data(m) for m in page])

    def retrieve(self, request, pk=None):
        return Response(staff_market_data(self.get_market(pk)))

    def create(self, request):
        data = MarketCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = dict(data.validated_data)
        try:
            market = create_market(
                actor=request.user,
                category=v.pop("category"),
                odds=v.pop("odds"),
                **v,
            )
        except MarketError as exc:
            return _refused(exc)
        return Response(
            staff_market_data(self.get_market(market.pk)), status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, pk=None):
        data = MarketUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            market = Market.objects.select_for_update().get(pk=self.get_market(pk).pk)
            if market.status in (S.SETTLED, S.VOID):
                raise ValidationError({"detail": "A settled or void market can't be edited."})
            for field, value in data.validated_data.items():
                setattr(market, field, value)
            if market.closes_at <= market.opens_at:
                raise ValidationError({"closes_at": "Must be after the opening time."})
            market.updated_by = request.user
            market.save()
        return Response(staff_market_data(self.get_market(pk)))

    def destroy(self, request, pk=None):
        market = self.get_market(pk)
        if market.status != S.DRAFT or market.bets.exists():
            raise ValidationError({"detail": "Only a draft with no bets can be deleted."})
        market.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        data = TransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            transition(
                self.get_market(pk),
                data.validated_data["to"],
                actor=request.user,
                reason=data.validated_data.get("reason", ""),
            )
        except MarketError as exc:
            return _refused(exc)
        return Response(staff_market_data(self.get_market(pk)))

    @action(detail=True, methods=["get"])
    def bets(self, request, pk=None):
        market = self.get_market(pk)
        qs = market.bets.select_related("user", "outcome").order_by("-placed_at")
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            [
                {
                    "id": str(b.pk),
                    "user": {"id": b.user_id, "email": b.user.email, "name": b.user.display_name},
                    "outcome": b.outcome.label,
                    "stake": b.stake,
                    "odds_accepted": str(b.odds_accepted),
                    "potential_return": b.potential_return,
                    "payout": b.payout,
                    "status": b.status,
                    "placed_at": b.placed_at,
                }
                for b in page
            ]
        )

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        market = self.get_market(pk)
        events = [
            {
                "type": "status",
                "at": e.at,
                "from": e.from_status,
                "to": e.to_status,
                "by": e.actor.email if e.actor else "system",
                "reason": e.reason,
            }
            for e in market.events.select_related("actor")
        ]
        odds = [
            {
                "type": "odds",
                "at": c.at,
                "outcome": c.outcome.label,
                "from": str(c.old),
                "to": str(c.new),
                "by": c.by.email,
            }
            for c in OddsChange.objects.filter(outcome__market=market).select_related(
                "outcome", "by"
            )
        ]
        return Response(sorted(events + odds, key=lambda r: r["at"], reverse=True))


class OutcomeUpdateSerializer(serializers.Serializer):
    odds = serializers.CharField(required=False, max_length=12)
    is_active = serializers.BooleanField(required=False)


class OutcomeAdminView(APIView):
    """PATCH an outcome's odds or switch it off. Placed bets keep their accepted odds."""

    permission_classes = [IsStaff]

    def patch(self, request, pk: int):
        outcome = get_object_or_404(Outcome, pk=pk)
        data = OutcomeUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            if "odds" in v:
                outcome = set_odds(outcome, v["odds"], actor=request.user)
            if "is_active" in v:
                outcome = set_active(outcome, v["is_active"], actor=request.user)
        except MarketError as exc:
            return _refused(exc)
        return Response(staff_market_data(_markets().get(pk=outcome.market_id)))


# -- leaderboard ---------------------------------------------------------------------------------

ACCURACY_MIN_SETTLED = 10
LEADERBOARD_SIZE = 50


def _name(wallet: Wallet) -> str:
    return wallet.user.display_name or f"Player {wallet.pk}"


class LeaderboardView(APIView):
    """Three separate tables, never mixed:

    - ``balance``: coins now (everyone started with the same amount, so this is profit).
    - ``accuracy``: won / (won + lost), voids left out, only with at least 10 settled bets.
    - ``wins``: number of winning bets.
    """

    permission_classes = [PredictionsOn, PublicRead]

    def get(self, request):
        metric = request.query_params.get("metric", "balance")
        won = Count("user__bets", filter=Q(user__bets__status=Bet.Status.WON))
        lost = Count("user__bets", filter=Q(user__bets__status=Bet.Status.LOST))
        qs = Wallet.objects.select_related("user").annotate(won=won, lost=lost)
        if metric == "balance":
            qs = qs.order_by("-balance", "created_at")
        elif metric == "accuracy":
            qs = qs.annotate(settled=F("won") + F("lost")).filter(settled__gte=ACCURACY_MIN_SETTLED)
            qs = qs.annotate(
                acc=ExpressionWrapper(F("won") * 1.0 / F("settled"), output_field=FloatField())
            ).order_by("-acc", "-settled", "created_at")
        elif metric == "wins":
            qs = qs.filter(won__gt=0).order_by("-won", "lost", "created_at")
        else:
            raise ValidationError({"metric": "Use balance, accuracy or wins."})
        rows = []
        for n, w in enumerate(qs[:LEADERBOARD_SIZE], start=1):
            settled = w.won + w.lost
            rows.append(
                {
                    "rank": n,
                    "name": _name(w),
                    "is_me": request.user.is_authenticated and w.user_id == request.user.pk,
                    "balance": w.balance,
                    "won": w.won,
                    "lost": w.lost,
                    "accuracy": round(w.won / settled, 4) if settled else None,
                }
            )
        return Response(
            {"metric": metric, "accuracy_min_settled": ACCURACY_MIN_SETTLED, "rows": rows}
        )
