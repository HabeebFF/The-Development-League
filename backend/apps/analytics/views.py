"""Page view tracking (anyone) and the analytics pages (staff only)."""

from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from common.authentication import CookieJWTAuthentication
from common.permissions import IsStaff

from . import detail
from .summary import RANGES, range_start, summary
from .tracking import add_action, record, report_time, view_for


def _data(request) -> dict:
    return request.data if isinstance(request.data, dict) else {}


class HitView(APIView):
    """The site's tracker calls this once per page opened. The answer's ``key`` lets it
    report time on page and actions; bots and bad paths get 204 and nothing is stored."""

    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analytics_hit"

    def post(self, request):
        data = _data(request)
        view = record(
            request,
            str(data.get("path", ""))[:500],
            referrer=str(data.get("referrer", ""))[:500],
            ref=str(data.get("ref", ""))[:60],
        )
        if view is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"key": str(view.key)}, status=status.HTTP_201_CREATED)


class _ByKey(APIView):
    """Reports about a page view already recorded: the key is the only proof needed, so no
    sign-in (and no CSRF token) is involved and the browser can send them as it leaves."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analytics_event"

    def view(self, request):
        return view_for(_data(request).get("key"))


class TimeView(_ByKey):
    def post(self, request):
        view = self.view(request)
        if view:
            report_time(view, _data(request).get("seconds"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ActionView(_ByKey):
    def post(self, request):
        view = self.view(request)
        if view:
            add_action(view, _data(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


def _range(request) -> str:
    key = request.query_params.get("range", "7d")
    if key not in RANGES:
        raise ValidationError({"range": f"Use one of: {', '.join(RANGES)}."})
    return key


def _who(request) -> str:
    who = request.query_params.get("who", "everyone")
    if who not in detail.WHO:
        raise ValidationError({"who": f"Use one of: {', '.join(detail.WHO)}."})
    return who


def _date(request) -> date:
    raw = request.query_params.get("date")
    if not raw:
        return timezone.localdate(timezone=detail.league_tz())
    try:
        return date.fromisoformat(raw)
    except ValueError as e:
        raise ValidationError({"date": "Use YYYY-MM-DD."}) from e


class SummaryView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response(summary(_range(request), who=_who(request)))


class DayView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response(detail.day(_date(request), _who(request)))


class TimelineView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        data = detail.timeline(request.query_params.get("person", ""), _date(request))
        if data is None:
            raise NotFound("Nobody by that code on that day.")
        return Response(data)


class PeopleView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        try:
            days = min(400, max(1, int(request.query_params.get("days", 30))))
        except ValueError as e:
            raise ValidationError({"days": "A number of days."}) from e
        return Response(detail.people(days))


class ActionsView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        now = timezone.now()
        start = range_start(_range(request), now)
        path = request.query_params.get("path", "")[:200]
        return Response(detail.actions_report(start, now, _who(request), path))
