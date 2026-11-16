import datetime as dt

from django.core.cache import cache
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsStaff

from . import rewards
from .models import DcSettings

WAITING_CACHE = "dc:waiting"


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
        fields = ["rewards_enabled", "per_kill", "booyah", "mvp", "played", "start_date"]
        read_only_fields = ["start_date"]

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
