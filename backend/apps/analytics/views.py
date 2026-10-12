"""Page view tracking (anyone) and the analytics summary (staff only)."""

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from common.authentication import CookieJWTAuthentication
from common.permissions import IsStaff

from .summary import RANGES, summary
from .tracking import record


class HitView(APIView):
    """The site's tracker calls this once per page opened. Always answers 204."""

    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analytics_hit"

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        record(
            request,
            str(data.get("path", ""))[:500],
            referrer=str(data.get("referrer", ""))[:500],
            ref=str(data.get("ref", ""))[:60],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SummaryView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        key = request.query_params.get("range", "7d")
        if key not in RANGES:
            raise ValidationError({"range": f"Use one of: {', '.join(RANGES)}."})
        return Response(summary(key))
