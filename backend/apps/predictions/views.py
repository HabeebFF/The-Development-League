"""Wallet endpoints for players, and wallet tools for staff.

Balances are only ever read here; the one write (a staff adjustment) goes through
``services.post_entry`` like every other coin movement.
"""

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.pagination import DefaultPagination
from common.permissions import IsStaff, IsSuperAdmin

from .models import LedgerEntry, Wallet
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
