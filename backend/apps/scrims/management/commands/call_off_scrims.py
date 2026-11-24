"""Call off scrim nights from the command line: refunds every sign-up fee and every open
prediction, like the Call off button on Staff > Scrims.

    python manage.py call_off_scrims 2026-11-24 2026-11-26 --reason "Scrims off this week" \\
        --by staff@example.com            # shows what it would do
    python manage.py call_off_scrims 2026-11-24 ... --by staff@example.com --yes   # does it
"""

import datetime as dt

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.scrims import services as sv


class Command(BaseCommand):
    help = "Call off scrim nights (or one session): refund sign-up DC and open predictions."

    def add_arguments(self, parser):
        parser.add_argument("dates", nargs="+", help="Nights, YYYY-MM-DD")
        parser.add_argument("--session", choices=list(sv.SESSIONS), help="Only this session")
        parser.add_argument("--reason", default="", help="Shown to teams and on refunds")
        parser.add_argument("--by", required=True, help="Email of the staff member doing it")
        parser.add_argument("--yes", action="store_true", help="Do it (without: only show)")

    def handle(self, *args, dates, session, reason, by, yes, **opts):
        try:
            days = [dt.date.fromisoformat(d) for d in dates]
        except ValueError as exc:
            raise CommandError("Dates look like 2026-11-24.") from exc
        actor = get_user_model().objects.filter(email__iexact=by).first()
        if actor is None or not actor.is_league_staff:
            raise CommandError(f"No staff account with the email {by}.")
        which = [session] if session else None
        for day in days:
            report = sv.call_off(day, actor, reason, which) if yes else sv.call_off_plan(day, which)
            for s in report["sessions"]:
                line = (
                    f"{day:%a %d %b} {s['session']}: {s['teams']} teams, "
                    f"{s['fees']} fees = {s['dc']:,} DC back; {s['markets']} open markets, "
                    f"{s['bets']} predictions, {s['multiples']} multiples refunded"
                )
                if s["settled"]:
                    line += f" ({s['settled']} settled markets left alone)"
                if s["started"]:
                    line += " [session time has passed]"
                if s["called_off"]:
                    line += " [already called off]"
                self.stdout.write(line)
        if not yes:
            self.stdout.write(self.style.WARNING("Nothing changed. Add --yes to do it."))
        else:
            self.stdout.write(self.style.SUCCESS("Done."))
