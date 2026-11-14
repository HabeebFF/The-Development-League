"""Card shop endpoints. Browsing is open like the predictions pages; buying, equipping and the
fan card need an account (staff can't buy, as they can't bet). Staff run the shop under
``admin/shop/``."""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.league.models import Player, Team
from apps.predictions.models import Bet, Multiple
from apps.predictions.services import Kind, can_play, wallet_for
from apps.predictions.views import CanPlay, PredictionsOn
from common.pagination import DefaultPagination
from common.permissions import IsStaff, PublicRead

from . import looks, milestones, services
from .models import CardDesign, Equipped, OwnedDesign
from .services import ShopError, available, design_data

LOW_BALANCE_WARNING = 100


def _refused(exc: ShopError) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _sold() -> Count:
    return Count("owners", filter=Q(owners__refunded_at__isnull=True))


def shop_design(design: CardDesign, owned: dict, equipped_id: int | None, now) -> dict:
    sold = design.sold
    mine = owned.get(design.pk)
    return {
        **design_data(design, mine.copy_number if mine else None),
        "price": design.price,
        "rarity_label": design.get_rarity_display(),
        "sold": sold,
        "left": None if design.copies is None else max(design.copies - sold, 0),
        "sale_ends": design.sale_ends,
        "available": available(design, now),
        "owned": mine is not None,
        "equipped": equipped_id == design.pk,
    }


def _mine(user) -> tuple[dict, int | None]:
    if not (user and user.is_authenticated):
        return {}, None
    owned = {
        o.design_id: o for o in OwnedDesign.objects.filter(user=user, refunded_at__isnull=True)
    }
    eq = Equipped.objects.filter(user=user).first()
    return owned, (eq.design_id if eq and eq.design_id in owned else None)


# -- player shop -----------------------------------------------------------------------------


def _player_item(design: CardDesign, owned: dict, eq: Equipped | None, stats, now) -> dict:
    slot = services.SLOTS.get(design.kind)
    on = bool(eq and slot and getattr(eq, f"{slot}_id") == design.pk and design.pk in owned)
    parsed = milestones.parse(design.unlock)
    return {
        **shop_design(design, owned, None, now),
        "kind": design.kind,
        "kind_label": design.get_kind_display(),
        "equipped": on,
        "unlock": (
            {
                "stat": parsed[0],
                "target": parsed[1],
                "label": milestones.label(design.unlock),
                "progress": stats.get(parsed[0], 0) if stats else 0,
            }
            if parsed
            else None
        ),
    }


class PlayerShopView(APIView):
    """GET: the Player shop. Anyone can look; only an account linked to a league player can
    buy (``can_buy``). Opening it also hands out any milestone frames the player has reached.
    Buying goes through the same ``shop/designs/<id>/buy`` as the fan shop."""

    permission_classes = [PredictionsOn, PublicRead]

    def get(self, request):
        now = timezone.now()
        user = request.user
        player = services.linked_player(user)
        staff = user.is_authenticated and not can_play(user)
        if player is not None and not staff:
            milestones.grant(user, player)
        stats = milestones.progress(player) if player is not None else None
        owned, _ = _mine(user)
        eq = Equipped.objects.filter(user=user).first() if user.is_authenticated else None
        qs = (
            CardDesign.objects.filter(players_only=True)
            .annotate(sold=_sold())
            .order_by("order", "price", "name")
        )
        items = [
            _player_item(d, owned, eq, stats, now) for d in qs if available(d, now) or d.pk in owned
        ]
        return Response(
            {
                "signed_in": user.is_authenticated,
                "staff": staff,
                "player": (
                    {"id": player.pk, "name": player.display_name, "country": player.country}
                    if player
                    else None
                ),
                "can_buy": player is not None and not staff,
                "balance": wallet_for(user).balance if player and not staff else None,
                "items": items,
                "number": eq.shirt_number if eq else None,
                "flag": (eq.flag if eq else "") or None,
                "owns_number": bool(player) and services.owns_number(user),
                "progress": stats,
                "low_balance_warning": LOW_BALANCE_WARNING,
            }
        )


class AurasView(APIView):
    """GET: ``{"auras": {player_id: palette}}``, players whose name glows (a Mythic design)."""

    permission_classes = [PublicRead]

    def get(self, request):
        return Response({"auras": services.name_auras()})


class PlayerEquipView(APIView):
    """POST ``{"kind": "FRAME" | "TITLE" | "GLOW", "design": id | null}``."""

    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def post(self, request):
        kind = request.data.get("kind", CardDesign.Kind.FRAME)
        design_id = request.data.get("design")
        if design_id is not None and not isinstance(design_id, int):
            raise ValidationError({"design": "Send a design id or null."})
        try:
            eq = services.equip(request.user, design_id, kind)
        except ShopError as exc:
            return _refused(exc)
        return Response({"frame": eq.design_id, "title": eq.title_id, "glow": eq.glow_id})


class PlayerNumberView(APIView):
    """POST ``{"number": 0-99 | null, "flag": "NG" | ""}`` (needs Number and flag)."""

    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def post(self, request):
        number = request.data.get("number")
        if number is not None and (isinstance(number, bool) or not isinstance(number, int)):
            raise ValidationError({"number": "Send a number from 0 to 99, or null."})
        try:
            eq = services.set_number(request.user, number, request.data.get("flag") or "")
        except ShopError as exc:
            return _refused(exc)
        return Response({"number": eq.shirt_number, "flag": eq.flag or None})


class DesignListView(APIView):
    """GET: every design on sale, plus any the viewer owns that went off sale."""

    permission_classes = [PredictionsOn, PublicRead]

    def get(self, request):
        now = timezone.now()
        owned, equipped_id = _mine(request.user)
        qs = (
            CardDesign.objects.filter(players_only=False)
            .annotate(sold=_sold())
            .order_by("order", "price", "name")
        )
        designs = [
            shop_design(d, owned, equipped_id, now)
            for d in qs
            if available(d, now) or d.pk in owned
        ]
        return Response(
            {
                "designs": designs,
                "equipped": equipped_id,
                "low_balance_warning": LOW_BALANCE_WARNING,
            }
        )


class BuyView(APIView):
    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def post(self, request, pk: int):
        try:
            owned = services.buy(request.user, pk)
        except ShopError as exc:
            return _refused(exc)
        if request.data.get("equip"):
            services.equip_any(request.user, owned.design)
        return Response(
            {
                "owned": str(owned.pk),
                "design": design_data(owned.design, owned.copy_number),
                "price_paid": owned.price_paid,
                "balance": wallet_for(request.user).balance,
                "equipped": bool(request.data.get("equip")),
            },
            status=status.HTTP_201_CREATED,
        )


class EquipView(APIView):
    """POST ``{"design": id}`` to put an owned design on, ``{"design": null}`` for Default."""

    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def post(self, request):
        design_id = request.data.get("design")
        if design_id is not None and not isinstance(design_id, int):
            raise ValidationError({"design": "Send a design id or null."})
        try:
            eq = services.equip(request.user, design_id)
        except ShopError as exc:
            return _refused(exc)
        return Response({"equipped": eq.design_id})


def _fan_stats(user) -> dict:
    wallet = wallet_for(user)
    won = Bet.objects.filter(user=user, status=Bet.Status.WON).count() + (
        Multiple.objects.filter(user=user, status=Bet.Status.WON).count()
    )
    lost = Bet.objects.filter(user=user, status=Bet.Status.LOST).count() + (
        Multiple.objects.filter(user=user, status=Bet.Status.LOST).count()
    )
    spent = -(
        wallet.entries.filter(kind__in=[Kind.PURCHASE, Kind.SHOP_REFUND]).aggregate(
            n=Sum("amount")
        )["n"]
        or 0
    )
    settled = won + lost
    return {
        "balance": wallet.balance,
        "shop_spent": spent,
        "net": wallet.balance + spent,
        "won": won,
        "lost": lost,
        "accuracy": round(won / settled, 4) if settled else None,
    }


def _team(team: Team | None) -> dict | None:
    if team is None:
        return None
    return {
        "id": team.pk,
        "name": team.name,
        "tag": team.tag,
        "slug": team.slug,
        "logo": team.logo.url if team.logo else None,
        "primary_color": team.primary_color,
    }


class MeView(APIView):
    """GET: my fan card (name, favourite team, predictor stats, equipped design), my designs,
    and my player id if my account is linked to a league player (their FUT card takes the
    design too). PATCH ``{"favourite_team": slug | null}``."""

    permission_classes = [PredictionsOn, IsAuthenticated, CanPlay]

    def get(self, request):
        user = request.user
        owned, equipped_id = _mine(user)
        eq = Equipped.objects.filter(user=user).select_related("favourite_team").first()
        player = Player.objects.filter(user=user, hide_card=False).first()
        equipped = owned.get(equipped_id)
        return Response(
            {
                "name": user.display_name or "Fan",
                "favourite_team": _team(eq.favourite_team if eq else None),
                "design": design_data(equipped.design, equipped.copy_number) if equipped else None,
                "player_id": player.pk if player else None,
                "stats": _fan_stats(user),
                "owned": [
                    {
                        "id": str(o.pk),
                        "design": design_data(o.design, o.copy_number),
                        "price_paid": o.price_paid,
                        "gift": o.gifted_by_id is not None,
                        "bought_at": o.created_at,
                    }
                    for o in sorted(owned.values(), key=lambda o: o.created_at, reverse=True)
                ],
            }
        )

    def patch(self, request):
        if "favourite_team" not in request.data:
            raise ValidationError({"favourite_team": "Send a team slug or null."})
        slug = request.data.get("favourite_team")
        team = None
        if slug:
            team = Team.objects.filter(slug=slug).first()
            if team is None:
                raise ValidationError({"favourite_team": "No such team."})
        eq, _ = Equipped.objects.get_or_create(user=request.user)
        eq.favourite_team = team
        eq.save(update_fields=["favourite_team", "updated_at"])
        return self.get(request)


# -- staff -----------------------------------------------------------------------------------


class DesignAdminSerializer(serializers.ModelSerializer):
    sold = serializers.IntegerField(read_only=True)

    class Meta:
        model = CardDesign
        fields = [
            "id",
            "slug",
            "name",
            "kind",
            "players_only",
            "unlock",
            "rarity",
            "price",
            "parts",
            "copies",
            "sale_ends",
            "on_sale",
            "order",
            "sold",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_parts(self, value):
        try:
            return looks.clean_parts(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_unlock(self, value):
        if value and milestones.parse(value) is None:
            raise serializers.ValidationError(
                "Use kills:<n>, booyahs:<n> or totw:<n>, or leave empty."
            )
        return value

    def validate(self, attrs):
        get = lambda k, d=None: attrs.get(k, getattr(self.instance, k, d))  # noqa: E731
        if not get("unlock", "") and (get("price", 0) or 0) < 1:
            raise serializers.ValidationError({"price": "A design costs at least 1 DC."})
        if get("unlock", "") and not get("players_only", False):
            raise serializers.ValidationError(
                {"unlock": "Milestone items are for players: tick Players only."}
            )
        if get("kind", CardDesign.Kind.FRAME) != CardDesign.Kind.FRAME and not get(
            "players_only", False
        ):
            raise serializers.ValidationError(
                {"kind": "Titles, numbers and glows are Player shop items: tick Players only."}
            )
        return attrs

    def validate_copies(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Leave empty for unlimited, or 1 or more.")
        return value


class DesignAdminViewSet(viewsets.ModelViewSet):
    """Staff: add, edit and hide designs. A design someone owns can't be deleted (hide it)."""

    permission_classes = [IsStaff]
    serializer_class = DesignAdminSerializer
    pagination_class = None

    def get_queryset(self):
        return CardDesign.objects.annotate(sold=_sold()).order_by("order", "price", "name")

    def destroy(self, request, *args, **kwargs):
        design = self.get_object()
        if design.owners.exists():
            return Response(
                {"detail": "People own this design, so it can't be deleted. Hide it instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def parts(self, request):
        return Response(looks.catalogue())


def sale_data(o: OwnedDesign) -> dict:
    return {
        "id": str(o.pk),
        "user_id": o.user_id,
        "name": o.user.display_name or o.user.email,
        "email": o.user.email,
        "design": design_data(o.design, o.copy_number),
        "price_paid": o.price_paid,
        "gift": o.gifted_by_id is not None,
        "gift_note": o.gift_note,
        "bought_at": o.created_at,
        "refunded_at": o.refunded_at,
    }


class GiftSerializer(serializers.Serializer):
    email = serializers.EmailField()
    design = serializers.IntegerField()
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class SalesAdminView(APIView):
    """Staff: purchases and gifts, newest first. ``?search=`` name, email or design."""

    permission_classes = [IsStaff]

    def get(self, request):
        qs = OwnedDesign.objects.select_related("user", "design").order_by("-created_at")
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(user__display_name__icontains=search)
                | Q(design__name__icontains=search)
            )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        totals = OwnedDesign.objects.filter(refunded_at__isnull=True).aggregate(
            copies=Count("pk"), dc=Sum("price_paid")
        )
        resp = paginator.get_paginated_response([sale_data(o) for o in page])
        resp.data["totals"] = {"copies": totals["copies"], "dc": totals["dc"] or 0}
        return resp


class RefundAdminView(APIView):
    permission_classes = [IsStaff]

    def post(self, request, pk):
        try:
            owned = services.refund(pk, request.user)
        except ShopError as exc:
            return _refused(exc)
        owned = OwnedDesign.objects.select_related("user", "design").get(pk=owned.pk)
        return Response(sale_data(owned))


class GiftAdminView(APIView):
    permission_classes = [IsStaff]

    def post(self, request):
        data = GiftSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        user = get_user_model().objects.filter(email__iexact=v["email"]).first()
        if user is None:
            raise ValidationError({"email": "No account with that email."})
        if not can_play(user):
            raise ValidationError({"email": "League staff don't collect designs."})
        try:
            owned = services.gift(user, v["design"], request.user, v["note"])
        except ShopError as exc:
            return _refused(exc)
        owned = OwnedDesign.objects.select_related("user", "design").get(pk=owned.pk)
        return Response(sale_data(owned), status=status.HTTP_201_CREATED)


class UnequipAdminView(APIView):
    """Staff: take whatever design a user has on off their cards (they keep owning it)."""

    permission_classes = [IsStaff]

    def post(self, request):
        user_id = request.data.get("user")
        if not isinstance(user_id, int):
            raise ValidationError({"user": "Send the user id."})
        changed = Equipped.objects.filter(user_id=user_id, design__isnull=False).update(design=None)
        return Response({"unequipped": bool(changed)})
