import datetime as dt

from django.core.cache import cache
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.predictions.services import CoinError
from common.permissions import IsStaff

from . import perks, ranks, rewards
from .models import DcSettings, Spotlight

WAITING_CACHE = "dc:waiting"
BOARD_CACHE = "dc:board"


class MeView(APIView):
    """GET: the signed-in player's DC from matches (total, this month, latest, waiting)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(rewards.summary_for(request.user))


class WaitingView(APIView):
    """GET ``{"waiting": {player_id: dc}}``: DC players without an account can claim."""

    permission_classes = [AllowAny]

    def get(self, request):
        data = cache.get(WAITING_CACHE)
        if data is None:
            data = {str(k): v for k, v in rewards.waiting_by_player().items()}
            cache.set(WAITING_CACHE, data, 120)
        return Response({"waiting": data})


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DcSettings
        fields = [
            "rewards_enabled",
            "per_kill",
            "booyah",
            "mvp",
            "played",
            "start_date",
            "rank_steps",
        ]
        read_only_fields = ["start_date"]

    def validate_rank_steps(self, value):
        if not isinstance(value, list) or not 1 <= len(value) <= 10:
            raise ValidationError("Between 1 and 10 ranks.")
        out, seen = [], set()
        for step in value:
            try:
                name = str(step["name"]).strip()[:20]
                low = int(step["min"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError("Each rank needs a name and the DC to reach it.") from exc
            key = str(step.get("key") or name).strip().lower().replace(" ", "-")[:20]
            if not name or low < 1 or key in seen:
                raise ValidationError("Each rank needs its own name and at least 1 DC.")
            seen.add(key)
            out.append({"key": key, "name": name, "min": low})
        return sorted(out, key=lambda s: s["min"])

    def validate(self, attrs):
        for f in ("per_kill", "booyah", "mvp", "played"):
            if f in attrs and attrs[f] > 100_000:
                raise ValidationError({f: "Keep it at 100,000 DC or less."})
        return attrs


class SettingsAdminView(APIView):
    """GET/PATCH the rates for DC earned by playing. New rates apply to the next upload (and
    to a match whenever it's re-uploaded)."""

    permission_classes = [IsStaff]

    def get(self, request):
        conf = DcSettings.get()
        return Response({**SettingsSerializer(conf).data, "on": rewards.enabled()})

    def patch(self, request):
        conf = DcSettings.get()
        data = SettingsSerializer(conf, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save(updated_by=request.user)
        cache.delete(BOARD_CACHE)
        return self.get(request)


class BoardView(APIView):
    """GET (public): rank steps, earned DC per player, the team DC table for this month and the
    current DC King. Everything the badges need, cached for two minutes."""

    permission_classes = [AllowAny]

    def get(self, request):
        data = cache.get(BOARD_CACHE)
        if data is None:
            data = ranks.board()
            cache.set(BOARD_CACHE, data, 120)
        return Response(data)


class SpotlightAdminView(APIView):
    """GET: every DC King so far. PATCH {id, hidden}: hide one from the site. POST: crown last
    month now (it happens by itself early on the 1st)."""

    permission_classes = [IsStaff]

    def get(self, request):
        rows = Spotlight.objects.select_related("player")[:24]
        return Response([{**ranks.spotlight_data(s), "id": s.pk, "hidden": s.hidden} for s in rows])

    def patch(self, request):
        s = Spotlight.objects.filter(pk=request.data.get("id")).first()
        if s is None:
            raise ValidationError({"id": "No such DC King."})
        s.hidden = bool(request.data.get("hidden"))
        s.save(update_fields=["hidden"])
        cache.delete(BOARD_CACHE)
        return self.get(request)

    def post(self, request):
        ranks.crown_last_month()
        cache.delete(BOARD_CACHE)
        return self.get(request)


def _since(request) -> dt.date:
    raw = request.query_params.get("since") or request.data.get("since")
    try:
        return dt.date.fromisoformat(str(raw))
    except (TypeError, ValueError) as exc:
        raise ValidationError({"since": "Pick a day (YYYY-MM-DD)."}) from exc


class BackpayAdminView(APIView):
    """GET ?since=: what paying matches from that day would cost. POST {since}: pay them."""

    permission_classes = [IsStaff]

    def get(self, request):
        return Response(rewards.backpay_preview(_since(request)))

    def post(self, request):
        since = _since(request)
        if since > DcSettings.get().start_date:
            raise ValidationError({"since": "Pick a day before the current start day."})
        report = rewards.backpay(since, user=request.user)
        cache.delete(WAITING_CACHE)
        return Response({**report, "start_date": DcSettings.get().start_date})


# -- perks ---------------------------------------------------------------------------------------

LIVE_CACHE = "dc:perks-live"


def _perk_row(p):
    return {
        "key": p.key,
        "name": p.get_key_display(),
        "price": p.price,
        "days": p.days,
        "for_team": p.for_team,
        "enabled": p.enabled,
    }


def _purchase_row(r):
    return {
        "id": r.pk,
        "key": r.perk.key,
        "name": r.perk.get_key_display(),
        "status": r.status,
        "status_label": r.get_status_display(),
        "price": r.price_paid,
        "from_pot": r.from_pot,
        "data": {k: v for k, v in r.data.items() if k != "once"},
        "image": r.image.url if r.image else None,
        "starts_at": r.starts_at,
        "ends_at": r.ends_at,
        "player": r.player.display_name if r.player else None,
        "team": r.team.name if r.team else None,
        "buyer": r.user.display_name or r.user.email if r.user_id else None,
        "review_note": r.review_note,
        "created_at": r.created_at,
    }


class PerksView(APIView):
    """GET: the perks on sale, and for a signed-in player their wallet, team pot and perks."""

    permission_classes = [AllowAny]

    def get(self, request):
        from apps.predictions.services import wallet_for

        from .models import Perk, PerkPurchase

        out = {
            "perks": [_perk_row(p) for p in Perk.objects.filter(enabled=True)],
            "name_colours": perks.NAME_COLOURS,
            "me": None,
        }
        user = request.user if request.user.is_authenticated else None
        player = perks.player_of(user) if user else None
        if user and player and not user.is_league_staff:
            team = player.current_team
            pot = perks.pot_for(team) if team else None
            mine = PerkPurchase.objects.filter(user=user).select_related(
                "perk", "player", "team", "user"
            )[:20]
            out["me"] = {
                "balance": wallet_for(user).balance,
                "player_id": player.pk,
                "team": {"id": team.pk, "name": team.name, "slug": team.slug} if team else None,
                "pot": pot.balance if pot else 0,
                "pot_entries": [
                    {
                        "amount": e.amount,
                        "note": e.note,
                        "by": (e.user.display_name or "") if e.user_id else "",
                        "at": e.created_at,
                    }
                    for e in (pot.entries.select_related("user")[:10] if pot else [])
                ],
                "can_spend_pot": bool(team and perks.can_spend_pot(user, team)),
                "purchases": [_purchase_row(r) for r in mine],
            }
        return Response(out)


class BuyPerkView(APIView):
    """POST {key, once, data} (multipart with ``image`` for a banner): buy a perk."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        import json

        data = request.data.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError as exc:
                raise ValidationError({"data": "Bad details."}) from exc
        once = str(request.data.get("once") or "")[:64]
        if len(once) < 8:
            raise ValidationError({"once": "Missing."})
        try:
            row = perks.buy(
                request.user,
                str(request.data.get("key", "")),
                data,
                once,
                image=request.FILES.get("image"),
            )
        except perks.PerkError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        cache.delete(LIVE_CACHE)
        return Response(_purchase_row(row), status=201)


class PotView(APIView):
    """POST {amount, once}: chip DC into your team's pot."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        team = perks.team_of(request.user)
        try:
            amount = int(request.data.get("amount"))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"amount": "Pick an amount of DC."}) from exc
        once = str(request.data.get("once") or "")[:64]
        if team is None or len(once) < 8:
            raise ValidationError({"detail": "You're not on a team yet."})
        try:
            pot = perks.chip_in(request.user, team, amount, once)
        except (perks.PerkError, CoinError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response({"pot": pot.balance})


class LivePerksView(APIView):
    """GET (public): shoutouts on now, name colours, team banners and pinned moments."""

    permission_classes = [AllowAny]

    def get(self, request):
        data = cache.get(LIVE_CACHE)
        if data is None:
            from .models import PerkPurchase

            pins = {}
            for r in PerkPurchase.objects.filter(
                perk__key="PIN", status=PerkPurchase.Status.ACTIVE
            ).select_related("player"):
                if r.player and str(r.player_id) not in pins:
                    pin = perks.pinned(r.player)
                    if pin:
                        pins[str(r.player_id)] = pin
            data = {
                "shoutouts": perks.shoutouts(),
                "name_colours": {str(k): v for k, v in perks.name_colours().items()},
                "banners": {str(k): v for k, v in perks.banners().items()},
                "pins": pins,
            }
            cache.set(LIVE_CACHE, data, 60)
        return Response(data)


class PerksAdminView(APIView):
    """GET: perks, shoutouts waiting and recent buys. PATCH {key, price?, days?, enabled?}."""

    permission_classes = [IsStaff]

    def get(self, request):
        from .models import Perk, PerkPurchase

        rows = PerkPurchase.objects.select_related("perk", "player", "team", "user")
        return Response(
            {
                "perks": [_perk_row(p) for p in Perk.objects.all()],
                "pending": [
                    _purchase_row(r) for r in rows.filter(status=PerkPurchase.Status.PENDING)
                ],
                "recent": [_purchase_row(r) for r in rows[:40]],
            }
        )

    def patch(self, request):
        from .models import Perk

        p = Perk.objects.filter(key=request.data.get("key")).first()
        if p is None:
            raise ValidationError({"key": "No such perk."})
        if "price" in request.data:
            price = request.data["price"]
            if not isinstance(price, int) or not 0 < price <= 10_000_000:
                raise ValidationError({"price": "Between 1 and 10,000,000 DC."})
            p.price = price
        if "enabled" in request.data:
            p.enabled = bool(request.data["enabled"])
        p.save()
        cache.delete(LIVE_CACHE)
        return self.get(request)


class PurchaseAdminView(APIView):
    """POST {action: approve|reject|remove, note, refund}: review a shoutout or take a perk down."""

    permission_classes = [IsStaff]

    def post(self, request, pk):
        from .models import PerkPurchase

        row = PerkPurchase.objects.filter(pk=pk).first()
        if row is None:
            raise ValidationError({"detail": "Not found."})
        action = request.data.get("action")
        note = str(request.data.get("note") or "")
        try:
            if action in ("approve", "reject"):
                row = perks.review(row, request.user, action == "approve", note)
            elif action == "remove":
                row = perks.remove(row, request.user, bool(request.data.get("refund")), note)
            else:
                raise ValidationError({"action": "approve, reject or remove"})
        except perks.PerkError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        cache.delete(LIVE_CACHE)
        return Response(_purchase_row(row))
