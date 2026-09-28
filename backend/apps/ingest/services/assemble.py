"""Turn the stored files of one match into database rows.

Sources, newest upload of each kind wins (across all batches):
- MatchResult (required): placements, kills, players -> standings data
- debugger block (optional): entity <-> UID, knocks, headshots, respawns, zones, kill times
- ReplayInfo JSON (optional): map, room, duration, kill/death positions, elimination times
- SafeZone files (optional): kept on the match for reference

Re-running is safe: the match is found by its game match id and every derived row is
replaced inside one transaction, so a re-upload updates and never duplicates.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.league.models import Match, MatchDay, Player, Team, TeamAlias
from apps.maps.models import Map
from apps.results.models import MatchEvent, PlayerMatchResult, TeamMatchResult, ZonePhase
from apps.results.standings import schedule_rebuild
from apps.rotations.auto import draft_rotations

from ..models import DebuggerBlock, ParseRun, UploadBatch, UploadedFile
from ..parsers import debugger, match_result, replay_info
from ..parsers.base import ParseResult
from ..parsers.debugger import DebuggerBlock as ParsedBlock
from ..parsers.debugger import team_slot
from ..parsers.filenames import FileKind
from ..parsers.names import clean
from . import storage
from .grouping import log_time
from .time_align import Timeline, align

PS = UploadedFile.ParseStatus
USABLE = [PS.OK, PS.WARNINGS]
# How close (game seconds) a debugger kill and a ReplayInfo position must be to join.
POSITION_JOIN_S = 3.0


class AssembleError(Exception):
    """A problem staff must fix (missing file, unknown team, clashing match number)."""


@dataclass
class Sources:
    match_result: UploadedFile | None = None
    replay: UploadedFile | None = None
    block: DebuggerBlock | None = None
    safe_zones: list[UploadedFile] = field(default_factory=list)

    def describe(self) -> dict[str, Any]:
        return {
            "match_result": self.match_result.pk if self.match_result else None,
            "replay_info": self.replay.pk if self.replay else None,
            "debugger_block": self.block.pk if self.block else None,
            "safe_zones": [f.pk for f in self.safe_zones],
        }


def latest_sources(game_match_id: int) -> Sources:
    files = UploadedFile.objects.filter(game_match_id=game_match_id, parse_status__in=USABLE)
    newest = files.order_by("-created_at")
    return Sources(
        match_result=newest.filter(kind=FileKind.MATCH_RESULT).first(),
        replay=newest.filter(kind=FileKind.REPLAY_JSON).first(),
        block=DebuggerBlock.objects.filter(game_match_id=game_match_id)
        .exclude(file__parse_status__in=[PS.FAILED, PS.DUPLICATE])
        .select_related("file")
        .order_by("-created_at")
        .first(),
        safe_zones=list(files.filter(kind=FileKind.SAFE_ZONE).order_by("file_timestamp")),
    )


@dataclass
class Assignment:
    game_match_id: int
    match_day: MatchDay | None = None  # required for a new match
    number: int | None = None  # required for a new match
    map: Map | None = None
    team_ids: dict[str, int] = field(default_factory=dict)  # in-game name -> Team id
    create_missing_teams: bool = True


def assemble(assignment: Assignment, *, batch: UploadBatch | None = None, user=None) -> ParseRun:
    """Build or rebuild one match. Always returns the ParseRun (FAILED on error)."""
    match = Match.objects.filter(game_match_id=assignment.game_match_id).first()
    if match is None:
        if assignment.match_day is None or assignment.number is None:
            raise AssembleError("A new match needs a match day and a match number.")
        _check_number_free(assignment.match_day, assignment.number, None)
        match = Match.objects.create(
            game_match_id=assignment.game_match_id,
            match_day=assignment.match_day,
            number=assignment.number,
            status=Match.Status.PROCESSING,
        )
    run = ParseRun.objects.create(match=match, batch=batch, triggered_by=user)
    old_season_id = match.match_day.stage.season_id
    try:
        with transaction.atomic():
            counts, warnings = _build(match, assignment, run)
    except Exception as exc:
        run.status = ParseRun.Status.FAILED
        run.error = str(exc) if isinstance(exc, AssembleError) else f"{type(exc).__name__}: {exc}"
        run.finished_at = timezone.now()
        run.save()
        if not match.team_results.exists():
            Match.objects.filter(pk=match.pk).update(status=Match.Status.NEEDS_REVIEW)
        return run

    run.status = ParseRun.Status.WARNINGS if warnings else ParseRun.Status.OK
    run.counts = counts
    run.warnings = warnings[:200]
    run.finished_at = timezone.now()
    run.save()
    # The match may have moved to another match day (and season): rebuild both tables.
    schedule_rebuild(old_season_id, match.match_day.stage.season_id)
    return run


def _check_number_free(match_day: MatchDay, number: int, match_pk: int | None) -> None:
    clash = Match.objects.filter(match_day=match_day, number=number).exclude(pk=match_pk)
    if clash.exists():
        raise AssembleError(f"{match_day} already has a match number {number}.")


def _build(match: Match, assignment: Assignment, run: ParseRun) -> tuple[dict[str, int], list[str]]:
    sources = latest_sources(assignment.game_match_id)
    run.sources = sources.describe()
    warnings: list[str] = []

    if sources.match_result is None:
        raise AssembleError("MatchResult file missing for this match.")
    mr = _parsed(
        match_result.parse(
            sources.match_result.original_name,
            storage.read_bytes(sources.match_result.storage_key),
        ),
        "MatchResult",
        warnings,
    )
    replay = None
    if sources.replay is not None:
        replay = _parsed(
            replay_info.parse(
                sources.replay.original_name, storage.read_bytes(sources.replay.storage_key)
            ),
            "ReplayInfo",
            warnings,
        )
    block = _read_block(sources.block, assignment.game_match_id, warnings)

    # -- the match row ---------------------------------------------------------------------
    if assignment.match_day is not None and assignment.number is not None:
        _check_number_free(assignment.match_day, assignment.number, match.pk)
        match.match_day, match.number = assignment.match_day, assignment.number
    season = match.match_day.stage.season
    rule = season.scoring_rule

    game_map_id = (replay.map_id if replay else None) or (block.map_id if block else None)
    match.game_map_id = game_map_id
    match.map = assignment.map or Map.objects.filter(game_map_id=game_map_id).first() or match.map
    timeline = align(block, replay)
    match.started_at = log_time(timeline.start) if timeline else None
    match.room_name = replay.room_name if replay else match.room_name
    match.duration_s = replay.duration_s if replay else None
    match.safe_zones = [
        {
            **(f.parse_report.get("point") or {}),
            "at": f.file_timestamp.isoformat() if f.file_timestamp else None,
        }
        for f in sources.safe_zones
    ]
    match.status = Match.Status.PUBLISHED
    match.save()
    if timeline is not None and timeline.method != "kills":
        warnings.append(f"Timeline estimated from {timeline.method.replace('_', ' ')}.")

    # -- teams and players -------------------------------------------------------------------
    teams = _resolve_teams(mr, assignment, season)
    players: dict[int, Player] = {}
    uid_team: dict[int, Team] = {}
    for team_row in mr.teams:
        team = teams[team_row.name_raw]
        for p in team_row.players:
            name = clean(p.name_raw)
            player, _ = Player.objects.update_or_create(
                game_uid=p.uid,
                defaults={
                    "current_name_raw": name.raw,
                    "display_name": name.display,
                    "search_name": name.search,
                    "current_team": team,
                },
            )
            players[p.uid] = player
            uid_team[p.uid] = team

    entity_uid: dict[int, int] = {}
    if replay:
        entity_uid.update(replay.entity_to_uid)
    if block:
        entity_uid.update(block.players)
    uid_entity = {uid: entity for entity, uid in entity_uid.items()}

    def player_of(entity: int | None) -> Player | None:
        return players.get(entity_uid.get(entity)) if entity is not None else None

    def team_of(entity: int | None) -> Team | None:
        return uid_team.get(entity_uid.get(entity)) if entity is not None else None

    # -- wipe derived rows, then rebuild ------------------------------------------------------
    TeamMatchResult.objects.filter(match=match).delete()
    PlayerMatchResult.objects.filter(match=match).delete()
    MatchEvent.objects.filter(match=match).delete()
    ZonePhase.objects.filter(match=match).delete()

    knocks, headshots, deaths, respawns = Counter(), Counter(), Counter(), Counter()
    if block:
        for k in block.knocks:
            knocks[entity_uid.get(k.knocker)] += 1
            headshots[entity_uid.get(k.knocker)] += bool(k.headshot)
        for k in block.kills:
            deaths[entity_uid.get(k.victim)] += 1
        for r in block.respawns:
            respawns[entity_uid.get(r.entity)] += 1

    log_team_ids = {name.strip(): tid for tid, name in block.teams.items()} if block else {}
    eliminated = {e.team_name.strip(): e.time for e in replay.eliminations} if replay else {}

    team_rows, player_rows = [], []
    for team_row in mr.teams:
        team = teams[team_row.name_raw]
        slots = Counter(
            team_slot(uid_entity[p.uid]) for p in team_row.players if p.uid in uid_entity
        )
        placement_points = rule.placement_score(team_row.rank)
        kill_points = rule.kill_score(team_row.kill_score)
        team_rows.append(
            TeamMatchResult(
                match=match,
                team=team,
                in_game_name=team_row.name_raw,
                slot=slots.most_common(1)[0][0] if slots else None,
                log_team_id=log_team_ids.get(team_row.name_raw.strip()),
                placement=team_row.rank,
                kills=team_row.kill_score,
                placement_points=placement_points,
                kill_points=kill_points,
                total_points=placement_points + kill_points,
                reported_rank_score=team_row.rank_score,
                reported_total_score=team_row.total_score,
                eliminated_at_s=eliminated.get(team_row.name_raw.strip()),
            )
        )
        for p in team_row.players:
            name = clean(p.name_raw)
            player_rows.append(
                PlayerMatchResult(
                    match=match,
                    player=players[p.uid],
                    team=team,
                    raw_name=name.raw,
                    display_name=name.display,
                    entity_id=uid_entity.get(p.uid),
                    kills=p.kills,
                    knocks=knocks[p.uid] if block else None,
                    headshot_knocks=headshots[p.uid] if block else None,
                    deaths=deaths[p.uid] if block else None,
                    respawns=respawns[p.uid] if block else None,
                )
            )
    TeamMatchResult.objects.bulk_create(team_rows)
    PlayerMatchResult.objects.bulk_create(player_rows)

    # -- events --------------------------------------------------------------------------------
    events = _events(match, block, replay, timeline, player_of, team_of)
    MatchEvent.objects.bulk_create(events, batch_size=500)
    zones = _zones(match, block, timeline)
    ZonePhase.objects.bulk_create(zones)
    draft_rotations(match)

    # -- consistency checks ----------------------------------------------------------------------
    result_kills = sum(p.kills for p in mr.players)
    if block and len(block.kills) != result_kills:
        warnings.append(
            f"Debugger log has {len(block.kills)} kills but MatchResult has {result_kills}."
        )
    unknown = {e for e in entity_uid.values() if e not in players}
    if unknown:
        warnings.append(f"{len(unknown)} player(s) in the logs are not in MatchResult.")

    counts = {
        "teams": len(team_rows),
        "players": len(player_rows),
        "events": len(events),
        "zones": len(zones),
        "kills": result_kills,
    }
    return counts, warnings


def _parsed(result: ParseResult, label: str, warnings: list[str]):
    if result.data is None:
        raise AssembleError(f"{label} could not be read: {result.warnings[:1]}")
    warnings.extend(f"{label}: {w.message}" for w in result.warnings[:20])
    return result.data


def _read_block(
    row: DebuggerBlock | None, game_match_id: int, warnings: list[str]
) -> ParsedBlock | None:
    if row is None:
        return None
    raw = storage.read_range(row.file.storage_key, row.byte_start, row.byte_end)
    result = debugger.parse_stream(raw.splitlines(keepends=True))
    blocks = result.data.blocks if result.data else []
    block = next((b for b in blocks if b.match_id == game_match_id), None)
    if block is None and len(blocks) == 1:
        block = blocks[0]  # linked by time: the block has no id of its own
    if block is None:
        warnings.append("Debugger block could not be re-read; skipped.")
        return None
    return block


def _resolve_teams(mr, assignment: Assignment, season) -> dict[str, Team]:
    chosen = {name: tid for name, tid in assignment.team_ids.items()}
    teams_by_id = Team.objects.in_bulk(list(chosen.values()))
    resolved: dict[str, Team] = {}
    missing = []
    for team_row in mr.teams:
        name = team_row.name_raw
        team = teams_by_id.get(chosen[name]) if name in chosen else None
        if name in chosen and team is None:
            raise AssembleError(f"Team id {chosen[name]} for '{name}' does not exist.")
        if team is not None:
            TeamAlias.objects.update_or_create(
                in_game_name=name, season=None, defaults={"team": team}
            )
        else:
            team = TeamAlias.resolve(name, season)
        if team is None and assignment.create_missing_teams:
            team, _ = Team.objects.get_or_create(name=team_row.name or name)
            TeamAlias.objects.get_or_create(in_game_name=name, season=None, defaults={"team": team})
        if team is None:
            missing.append(name)
        else:
            resolved[name] = team
    if missing:
        raise AssembleError(f"Unknown in-game team names: {', '.join(missing)}")
    return resolved


def _events(
    match: Match,
    block: ParsedBlock | None,
    replay,
    timeline: Timeline | None,
    player_of,
    team_of,
) -> list[MatchEvent]:
    events: list[MatchEvent] = []

    def game_s(at: datetime) -> float | None:
        return timeline.game_seconds(at) if timeline else None

    def event(kind, source, actor=None, target=None, **kw) -> MatchEvent:
        return MatchEvent(
            match=match,
            kind=kind,
            source=source,
            actor_entity=actor,
            target_entity=target,
            actor_player=player_of(actor),
            target_player=player_of(target),
            actor_team=team_of(actor),
            target_team=team_of(target),
            **kw,
        )

    # ReplayInfo positions, looked up by actor entity for kills.
    actions = defaultdict(list)
    if replay:
        for a in replay.actions:
            actions[a.entity_id].append(a)

    def kill_position(killer: int, t: float | None) -> dict[str, Any]:
        if t is None:
            return {}
        best = min(
            (a for a in actions.get(killer, []) if abs(a.time - t) <= POSITION_JOIN_S),
            key=lambda a: abs(a.time - t),
            default=None,
        )
        if best is None:
            return {}
        out: dict[str, Any] = {"weapon_id": best.weapon_id}
        if best.position:
            out.update(x=best.position.x, y=best.position.y, z=best.position.z)
        if best.victim_position:
            out.update(
                tx=best.victim_position.x, ty=best.victim_position.y, tz=best.victim_position.z
            )
        return out

    D, R, K = MatchEvent.Source.DEBUGGER, MatchEvent.Source.REPLAY_INFO, MatchEvent.Kind
    if block:
        for k in block.kills:
            t = game_s(k.at)
            events.append(
                event(
                    K.KILL,
                    D,
                    k.killer,
                    k.victim,
                    game_time_s=t,
                    wall_time=log_time(k.at),
                    **kill_position(k.killer, t),
                )
            )
        for k in block.knocks:
            events.append(
                event(
                    K.KNOCK,
                    D,
                    k.knocker,
                    k.victim,
                    game_time_s=game_s(k.at),
                    wall_time=log_time(k.at),
                    headshot=k.headshot,
                )
            )
        for kind, items in ((K.RESPAWN, block.respawns), (K.TELEPORT, block.teleports)):
            for p in items:
                events.append(
                    event(
                        kind,
                        D,
                        p.entity,
                        game_time_s=game_s(p.at),
                        wall_time=log_time(p.at),
                        x=p.position.x,
                        y=p.position.y,
                        z=p.position.z,
                    )
                )
    elif replay:
        for k in replay.kills:
            events.append(
                event(
                    K.KILL,
                    R,
                    k.killer_entity,
                    k.victim_entity,
                    game_time_s=k.time,
                    **kill_position(k.killer_entity, k.time),
                )
            )

    if replay:
        for d in replay.deaths:
            pos = d.position
            events.append(
                event(
                    K.DEATH,
                    R,
                    d.entity_id,
                    game_time_s=d.time,
                    **({"x": pos.x, "y": pos.y, "z": pos.z} if pos else {}),
                )
            )
        for e in replay.eliminations:
            events.append(event(K.TEAM_ELIMINATED, R, e.entity_id, game_time_s=e.time))
    return events


def _zones(match: Match, block: ParsedBlock | None, timeline: Timeline | None) -> list[ZonePhase]:
    if block is None:
        return []
    rows: list[ZonePhase] = []
    seen: set[tuple[int, str]] = set()
    inner_radius_by_stage: dict[int, float] = {}
    for z in block.zones:
        if z.inner_radius > 0:  # stage 0 starts STABLE with radius 0
            inner_radius_by_stage[z.stage] = z.inner_radius
    for z in block.zones:
        if (z.stage, z.state) in seen:
            continue
        seen.add((z.stage, z.state))
        rows.append(
            ZonePhase(
                match=match,
                stage_index=z.stage,
                state=z.state,
                game_time_s=timeline.game_seconds(z.at) if timeline else None,
                wall_time=log_time(z.at),
                outer_x=z.outer.x,
                outer_z=z.outer.z,
                outer_radius=inner_radius_by_stage.get(z.stage - 1) if z.stage > 0 else None,
                inner_x=z.inner.x,
                inner_z=z.inner.z,
                inner_radius=z.inner_radius,
            )
        )
    return rows
