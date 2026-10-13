from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.league.models import Match
from apps.results.models import MatchEvent

from ...parsers import replay_info
from ...services import storage
from ...services.assemble import POSITION_JOIN_S, latest_sources


class Command(BaseCommand):
    help = (
        "Fill in the weapon on knocks of matches uploaded before knocks had one, from each "
        "match's ReplayInfo file. Only knocks without a weapon are changed."
    )

    def handle(self, *args, **opts):
        changed = filled = 0
        for match in Match.objects.filter(game_match_id__isnull=False).order_by("pk"):
            knocks = list(
                MatchEvent.objects.filter(
                    match=match,
                    kind=MatchEvent.Kind.KNOCK,
                    weapon_id__isnull=True,
                    actor_entity__isnull=False,
                    game_time_s__isnull=False,
                )
            )
            if not knocks:
                continue
            source = latest_sources(match.game_match_id).replay
            if source is None:
                continue
            parsed = replay_info.parse(source.original_name, storage.read_bytes(source.storage_key))
            if parsed.data is None:
                continue
            actions = defaultdict(list)
            for a in parsed.data.actions:
                actions[a.entity_id].append(a)
            for k in knocks:
                near = [
                    a for a in actions.get(k.actor_entity, [])
                    if abs(a.time - k.game_time_s) <= POSITION_JOIN_S
                ]  # fmt: skip
                if near:
                    k.weapon_id = min(near, key=lambda a: abs(a.time - k.game_time_s)).weapon_id
                    filled += 1
            MatchEvent.objects.bulk_update(knocks, ["weapon_id"])
            changed += 1
        self.stdout.write(f"Filled the weapon on {filled} knocks in {changed} matches.")
