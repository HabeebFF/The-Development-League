"""Who plays in a tournament: invited top teams, teams that register with DC, qualifiers.

- A tournament with a *qualifier* (a stage before its final stage) takes registrations. The
  top ``invite_count`` teams of the scrim standings are invited straight into the final (free,
  frozen when registration opens). Every other approved team can register for the qualifier,
  paying ``entry_fee`` DC from the registering player's wallet or from the team pot.
- ``places`` teams get a place, first come first served; after that teams join a waitlist and
  pay nothing until a place frees up (then the fee is taken from the same wallet or pot).
- Refunds: withdrawing before registration closes, staff removing a team (unless they keep
  the fee for a rule break), and cancelling the tournament. Playing, being knocked out or not
  showing up keeps the fee. Fees are spent (they leave the game), like scrim fees.
- When the qualifier is over, staff send its top ``qualify_count`` teams to the final.

A tournament without a qualifier works as before: staff invite or pick its teams.
``Tournament.teams`` always mirrors the teams that are in (any stage).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.league.models import Stage, Team
from apps.results.models import StandingRow

from .models import Entry, Tournament
from .services import TournamentError, final_stage, top_teams

S, V, P = Entry.Status, Entry.Via, Entry.PaidFrom


# -- stages --------------------------------------------------------------------------------------


def qualifier_stage(t: Tournament) -> Stage | None:
    """The stage registered teams play in: the first stage, when there is more than one."""
    stages = list(t.season.stages.order_by("order", "pk"))
    return stages[0] if len(stages) > 1 else None


def current_stage(t: Tournament) -> Stage:
    """Where new uploads go: the qualifier until its teams are sent through, then the final."""
    q = qualifier_stage(t)
    return q if q is not None and t.advanced_at is None else final_stage(t)


@transaction.atomic
def add_qualifier(t: Tournament, name: str = "Qualifier") -> Stage:
    q = qualifier_stage(t)
    if q is not None:
        return q
    final = final_stage(t)
    if final.order <= 1:
        final.order = 2
        final.save(update_fields=["order", "updated_at"])
    return Stage.objects.create(season=t.season, name=name, order=1, kind=Stage.Kind.GROUP)


# -- registration window -------------------------------------------------------------------------


def reg_state(t: Tournament, now=None) -> str:
    """off (no qualifier or no dates), cancelled, soon, open or closed."""
    now = now or timezone.now()
    if t.cancelled_at:
        return "cancelled"
    if qualifier_stage(t) is None or not t.reg_opens_at or not t.reg_closes_at:
        return "off"
    if t.confirmed_at or now >= t.reg_closes_at:
        return "closed"
    if now < t.reg_opens_at:
        return "soon"
    return "open"


def taken(t: Tournament, stage: Stage) -> int:
    return Entry.objects.filter(tournament=t, stage=stage, status=S.IN).count()


def sync_teams(t: Tournament) -> None:
    ids = set(Entry.objects.filter(tournament=t, status=S.IN).values_list("team_id", flat=True))
    t.teams.set(Team.objects.filter(pk__in=ids))


def active_entry(t: Tournament, team: Team) -> Entry | None:
    """The team's live entry (in or waitlisted), the latest stage first."""
    return (
        Entry.objects.filter(tournament=t, team=team, status__in=[S.IN, S.WAITLIST])
        .select_related("stage")
        .order_by("-stage__order", "-pk")
        .first()
    )


def _row(t: Tournament, stage: Stage, team: Team) -> Entry:
    """The (tournament, stage, team) row, made if new. Locked."""
    row, _ = Entry.objects.select_for_update().get_or_create(
        tournament=t, stage=stage, team=team, defaults={"via": V.STAFF, "status": S.REMOVED}
    )
    return row


# -- DC ------------------------------------------------------------------------------------------


def _pays(user) -> bool:
    """Staff put teams in for free (they can't hold DC)."""
    return bool(user and user.is_authenticated and not user.is_league_staff)


def _label(row: Entry) -> str:
    return f"{row.team.name}: {row.tournament.name} entry"


def _charge(row: Entry, user, pay_from: str) -> None:
    """Take the entry fee from the player's wallet or the team pot. TournamentError if short."""
    from apps.dc.models import PotEntry, TeamPot
    from apps.dc.perks import pot_for
    from apps.predictions.models import LedgerEntry
    from apps.predictions.services import NotEnoughCoins, post_entry, wallet_for

    fee = row.tournament.entry_fee
    if row.fee_paid or fee <= 0 or not _pays(user):
        return
    row.fee_round += 1
    if pay_from == P.POT:
        pot = TeamPot.objects.select_for_update().get(pk=pot_for(row.team).pk)
        if pot.balance < fee:
            raise TournamentError(
                f"The {row.team.name} pot has {pot.balance:,} DC; entry costs {fee:,} DC."
            )
        pot.balance -= fee
        pot.save(update_fields=["balance", "updated_at"])
        PotEntry.objects.create(
            pot=pot, user=user, amount=-fee, balance_after=pot.balance, note=_label(row)[:120]
        )
    else:
        try:
            post_entry(
                wallet_for(user), LedgerEntry.Kind.CUP_FEE, -fee,
                f"cup-fee:{row.pk}:{row.fee_round}", reason=_label(row), actor=user,
            )  # fmt: skip
        except NotEnoughCoins as exc:
            raise TournamentError(f"Entry costs {fee:,} DC. {exc}") from exc
    row.fee_paid, row.paid_by, row.paid_from = fee, user, pay_from
    row.save(update_fields=["fee_round", "fee_paid", "paid_by", "paid_from", "updated_at"])


def _refund(row: Entry, actor=None, why: str = "") -> int:
    """Give the fee back to the wallet or pot it came from (once). Returns the DC given back."""
    from apps.dc.models import PotEntry, TeamPot
    from apps.dc.perks import pot_for
    from apps.predictions.models import LedgerEntry
    from apps.predictions.services import post_entry, wallet_for

    amount = row.fee_paid
    if not amount:
        return 0
    reason = f"{_label(row)} refund. {why}".strip()
    if row.paid_from == P.POT:
        pot = TeamPot.objects.select_for_update().get(pk=pot_for(row.team).pk)
        pot.balance += amount
        pot.save(update_fields=["balance", "updated_at"])
        PotEntry.objects.create(
            pot=pot, user=actor, amount=amount, balance_after=pot.balance, note=reason[:120]
        )
    elif row.paid_by_id is not None:
        post_entry(
            wallet_for(row.paid_by), LedgerEntry.Kind.CUP_REFUND, amount,
            f"cup-refund:{row.pk}:{row.fee_round}", reason=reason[:300], actor=actor,
        )  # fmt: skip
    else:
        return 0
    row.fee_paid, row.refunded = 0, row.refunded + amount
    row.save(update_fields=["fee_paid", "refunded", "updated_at"])
    return amount


# -- who may -------------------------------------------------------------------------------------


def can_register(user, team: Team) -> bool:
    from apps.scrims.services import can_register as scrim_rule

    return scrim_rule(user, team)


def can_use_pot(user, team: Team) -> bool:
    from apps.dc.perks import can_spend_pot

    return bool(user and user.is_authenticated and can_spend_pot(user, team))


def _check_team(team: Team) -> None:
    from apps.scrims.services import ScrimError, _check_approved, _check_suspension

    try:
        _check_approved(team)
        _check_suspension(team)
    except ScrimError as exc:
        raise TournamentError(str(exc).replace("scrims", "tournaments")) from exc


# -- teams register, withdraw and decline --------------------------------------------------------


def _locked(t: Tournament) -> Tournament:
    return Tournament.objects.select_for_update().select_related("season").get(pk=t.pk)


def register(t: Tournament, team: Team, user, pay_from: str = P.WALLET) -> Entry:
    """Someone on the team enters it into the qualifier, paying the fee: a place if one is
    free, else the waitlist (paying nothing until a place frees up)."""
    if pay_from not in (P.WALLET, P.POT):
        raise TournamentError("Pay from your wallet or the team pot.")
    if not can_register(user, team):
        raise TournamentError("Only the team's manager or its players can register it.")
    if pay_from == P.POT and _pays(user) and not can_use_pot(user, team):
        raise TournamentError("Only your team's manager can spend the team pot.")
    if pay_from == P.WALLET and user.is_authenticated and not _pays(user):
        pay_from = P.NONE
    _check_team(team)
    with transaction.atomic():
        t = _locked(t)
        state = reg_state(t)
        if state == "soon":
            raise TournamentError("Registration hasn't opened yet.")
        if state != "open":
            raise TournamentError("Registration is closed.")
        live = active_entry(t, team)
        if live is not None:
            where = "invited to" if live.via == V.INVITED else "already in"
            raise TournamentError(f"{team.name} is {where} {t.name} ({live.stage.name}).")
        stage = qualifier_stage(t)
        row = _row(t, stage, team)
        row.via, row.registered_by, row.pay_from, row.note = V.REGISTERED, user, pay_from, ""
        if taken(t, stage) < t.places:
            _charge(row, user, pay_from)
            row.status, row.queued_at = S.IN, None
        else:
            row.status, row.queued_at = S.WAITLIST, timezone.now()
        row.save()
        sync_teams(t)
    return row


def withdraw(t: Tournament, team: Team, user) -> Entry:
    """The team leaves before registration closes: its fee comes back, and an invited team
    declines its invite. The next waitlisted team takes a freed qualifier place."""
    if not can_register(user, team):
        raise TournamentError("Only the team's manager or its players can do that.")
    with transaction.atomic():
        t = _locked(t)
        row = active_entry(t, team)
        if row is None:
            raise TournamentError(f"{team.name} isn't in {t.name}.")
        row = Entry.objects.select_for_update().get(pk=row.pk)
        if row.via == V.QUALIFIED:
            raise TournamentError("Ask TDL staff to take a qualified team out.")
        if row.via != V.INVITED and reg_state(t) != "open":
            raise TournamentError("Registration has closed; ask TDL staff to take the team out.")
        if t.confirmed_at or t.cancelled_at:
            raise TournamentError("The tournament is over.")
        had_place = row.status == S.IN
        _refund(row, user, "Withdrew.")
        row.status, row.note = S.WITHDRAWN, ("Declined the invite" if row.via == V.INVITED else "")
        row.save(update_fields=["status", "note", "updated_at"])
        if had_place and row.stage_id == getattr(qualifier_stage(t), "pk", None):
            fill(t)
        sync_teams(t)
    return row


def fill(t: Tournament) -> int:
    """Give freed qualifier places to waitlisted teams in order (while registration is open),
    taking the fee then. A team whose wallet or pot is short is dropped from the waitlist."""
    stage = qualifier_stage(t)
    if stage is None or reg_state(t) != "open":
        return 0
    moved = 0
    waiting = (
        Entry.objects.select_for_update(of=("self",))
        .filter(tournament=t, stage=stage, status=S.WAITLIST)
        .select_related("team", "registered_by", "tournament")
    )
    for row in waiting.order_by("queued_at", "pk"):
        if taken(t, stage) >= t.places:
            break
        try:
            with transaction.atomic():
                _charge(row, row.registered_by, row.pay_from)
        except TournamentError as exc:
            row.status, row.note = S.REMOVED, f"Dropped from the waitlist: {exc}"[:200]
            row.save(update_fields=["status", "note", "updated_at"])
            continue
        row.status, row.queued_at = S.IN, None
        row.save(update_fields=["status", "queued_at", "updated_at"])
        moved += 1
    return moved


# -- staff ---------------------------------------------------------------------------------------


def _not_over(t: Tournament) -> None:
    if t.confirmed_at:
        raise TournamentError("The prizes were already paid; the teams can't change now.")
    if t.cancelled_at:
        raise TournamentError("The tournament was cancelled.")


def invite_top(t: Tournament, n: int | None = None, *, dc_wildcard: bool = False) -> list[Team]:
    """Invite the top ``n`` of the scrim standings straight into the final (free), replacing
    earlier invites. The list is frozen: later scrims don't change it."""
    _not_over(t)
    with transaction.atomic():
        t = _locked(t)
        n = n or (t.invite_count if qualifier_stage(t) else 12)
        teams = top_teams(n)
        if not teams:
            raise TournamentError("The league has no standings yet.")
        if dc_wildcard:
            # The last place goes to the DC wildcard: the team outside the top whose players
            # earned the most DC from matches in the 30 days before the Cup.
            from apps.dc.ranks import wildcard
            from apps.predictions.services import lagos_today

            keep = teams[: n - 1]
            pick = wildcard(t.starts_on or lagos_today(), {x.pk for x in keep})
            if pick:
                teams = keep + [Team.objects.get(pk=pick["team_id"])]
        final = final_stage(t)
        wanted = {x.pk for x in teams}
        for row in Entry.objects.select_for_update().filter(
            tournament=t, stage=final, via=V.INVITED, status=S.IN
        ):
            if row.team_id not in wanted:
                row.status, row.note = S.REMOVED, "No longer in the top"
                row.save(update_fields=["status", "note", "updated_at"])
        for team in teams:
            _invite(t, final, team)
        t.invited_at = timezone.now()
        t.save(update_fields=["invited_at", "updated_at"])
        sync_teams(t)
    return teams


def _invite(t: Tournament, final: Stage, team: Team) -> Entry:
    """Invite one team into the final. A team that had registered for the qualifier is taken
    out of it and its fee given back (it doesn't need to qualify any more)."""
    q = qualifier_stage(t)
    if q is not None:
        for row in Entry.objects.select_for_update().filter(
            tournament=t, stage=q, team=team, status__in=[S.IN, S.WAITLIST]
        ):
            _refund(row, None, "Invited to the final instead.")
            row.status, row.note = S.REMOVED, "Invited to the final instead"
            row.save(update_fields=["status", "note", "updated_at"])
    row = _row(t, final, team)
    if row.status != S.IN or row.via != V.INVITED:
        row.via, row.status, row.note = V.INVITED, S.IN, ""
        row.save()
    return row


def invite_next(t: Tournament) -> Team:
    """Invite the best team in the standings that isn't in the tournament (say one declined)."""
    _not_over(t)
    with transaction.atomic():
        t = _locked(t)
        busy = set(
            Entry.objects.filter(tournament=t, status=S.IN, stage=final_stage(t)).values_list(
                "team_id", flat=True
            )
        )
        busy |= set(
            Entry.objects.filter(tournament=t, via=V.INVITED, status=S.WITHDRAWN).values_list(
                "team_id", flat=True
            )
        )
        pick = next((x for x in top_teams(200) if x.pk not in busy), None)
        if pick is None:
            raise TournamentError("Every team in the standings is already in or declined.")
        _invite(t, final_stage(t), pick)
        sync_teams(t)
    return pick


def staff_add(t: Tournament, team: Team, stage: Stage, actor, note: str = "") -> Entry:
    """Put a team in a stage for free, even when the places are full."""
    _not_over(t)
    if stage.season_id != t.season_id:
        raise TournamentError("That stage isn't part of this tournament.")
    with transaction.atomic():
        t = _locked(t)
        row = _row(t, stage, team)
        if row.status == S.IN:
            raise TournamentError(f"{team.name} is already in {stage.name}.")
        _refund(row, actor, "Added by staff for free.")
        row.via, row.status, row.queued_at, row.note = V.STAFF, S.IN, None, note[:200]
        row.registered_by = actor
        row.save()
        sync_teams(t)
    return row


def staff_remove(t: Tournament, entry: Entry, actor, *, keep_fee: bool = False, note="") -> Entry:
    """Take a team out (in or waitlisted). Its fee comes back unless staff keep it (a rule
    break). A freed qualifier place goes to the waitlist while registration is open."""
    _not_over(t)
    with transaction.atomic():
        t = _locked(t)
        row = Entry.objects.select_for_update().select_related("team").get(pk=entry.pk)
        if row.tournament_id != t.pk:
            raise TournamentError("That team isn't in this tournament.")
        if row.status not in (S.IN, S.WAITLIST):
            raise TournamentError(f"{row.team.name} isn't in {t.name} any more.")
        had_place = row.status == S.IN
        if not keep_fee:
            _refund(row, actor, "Removed by TDL staff.")
        row.status = S.REMOVED
        row.note = (note or ("Removed by staff, fee kept" if keep_fee else "Removed by staff"))[
            :200
        ]
        row.save(update_fields=["status", "note", "updated_at"])
        if had_place and row.stage_id == getattr(qualifier_stage(t), "pk", None):
            fill(t)
        sync_teams(t)
    return row


def set_final_teams(t: Tournament, team_ids: list[int], actor) -> None:
    """The staff team picker (add/remove chips) edits who is in the final stage."""
    _not_over(t)
    final = final_stage(t)
    teams = list(Team.objects.filter(pk__in=team_ids))
    if len(teams) != len(set(team_ids)):
        raise TournamentError("Some of those teams don't exist.")
    wanted = {x.pk for x in teams}
    for row in Entry.objects.filter(tournament=t, stage=final, status=S.IN):
        if row.team_id not in wanted:
            staff_remove(t, row, actor)
    have = set(
        Entry.objects.filter(tournament=t, stage=final, status=S.IN).values_list(
            "team_id", flat=True
        )
    )
    for team in teams:
        if team.pk not in have:
            staff_add(t, team, final, actor)
    sync_teams(t)


def qualifier_top(t: Tournament) -> list[dict]:
    """The qualifier's table, best first, with who would go through."""
    q = qualifier_stage(t)
    if q is None:
        return []
    rows = StandingRow.objects.filter(season=t.season, scope=f"stage:{q.pk}").select_related("team")
    return [
        {
            "rank": r.rank,
            "team": {"id": r.team_id, "name": r.team.name, "slug": r.team.slug},
            "points": r.total_points,
            "through": r.rank <= t.qualify_count,
        }
        for r in rows.order_by("rank")
    ]


def advance(t: Tournament, actor, team_ids: list[int] | None = None) -> list[Team]:
    """Send the qualifier's top teams (or the teams staff pick) to the final, replacing an
    earlier send. Uploads go to the final from then on."""
    _not_over(t)
    q = qualifier_stage(t)
    if q is None:
        raise TournamentError("This tournament has no qualifier.")
    if team_ids is None:
        team_ids = [r["team"]["id"] for r in qualifier_top(t) if r["through"]]
    if not team_ids:
        raise TournamentError("The qualifier has no results yet.")
    teams = list(Team.objects.filter(pk__in=team_ids))
    if len(teams) != len(set(team_ids)):
        raise TournamentError("Some of those teams don't exist.")
    final = final_stage(t)
    with transaction.atomic():
        t = _locked(t)
        wanted = {x.pk for x in teams}
        for row in Entry.objects.select_for_update().filter(
            tournament=t, stage=final, via=V.QUALIFIED, status=S.IN
        ):
            if row.team_id not in wanted:
                row.status, row.note = S.REMOVED, "Replaced when staff sent the teams again"
                row.save(update_fields=["status", "note", "updated_at"])
        for team in teams:
            row = _row(t, final, team)
            if row.status != S.IN:
                row.via, row.status, row.note = V.QUALIFIED, S.IN, ""
                row.save()
        t.advanced_at = timezone.now()
        t.save(update_fields=["advanced_at", "updated_at"])
        sync_teams(t)
    return teams


def cancel(t: Tournament, actor) -> int:
    """Call the tournament off: every fee comes back. Returns the DC refunded."""
    if t.confirmed_at:
        raise TournamentError("The prizes were already paid; it can't be cancelled now.")
    with transaction.atomic():
        t = _locked(t)
        if t.cancelled_at:
            raise TournamentError("It's already cancelled.")
        back = 0
        for row in Entry.objects.select_for_update().filter(tournament=t, fee_paid__gt=0):
            back += _refund(row, actor, "The tournament was cancelled.")
        Entry.objects.filter(tournament=t, status=S.WAITLIST).update(
            status=S.REMOVED, note="The tournament was cancelled"
        )
        t.cancelled_at = timezone.now()
        t.save(update_fields=["cancelled_at", "updated_at"])
    return back


def open_due(now=None) -> int:
    """Registration just opened: freeze the invited top teams (once). Run every few minutes."""
    now = now or timezone.now()
    done = 0
    due = Tournament.objects.filter(
        reg_opens_at__lte=now,
        invited_at__isnull=True,
        cancelled_at__isnull=True,
        confirmed_at__isnull=True,
    )
    for t in due:
        if qualifier_stage(t) is None or t.invite_count == 0:
            continue
        try:
            invite_top(t)
            done += 1
        except TournamentError:
            continue
    return done
