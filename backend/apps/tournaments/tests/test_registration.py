"""Tournament registration: top teams invited into the final, others pay DC for the qualifier."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.accounts.models import Membership
from apps.dc.models import TeamPot
from apps.dc.perks import pot_for
from apps.league.models import MatchDay, Team
from apps.predictions.models import LedgerEntry
from apps.predictions.services import post_entry, wallet_for
from apps.results.standings import rebuild_season
from apps.scrims.models import Suspension
from apps.tournaments import entries, services
from apps.tournaments.models import Entry
from apps.tournaments.services import TournamentError

from .test_tournaments import NAMES, client, lg, play, user  # noqa: F401

pytestmark = pytest.mark.django_db
S, V = Entry.Status, Entry.Via
FEE = 10000


@pytest.fixture
def cup(lg):  # noqa: F811
    """A cup with a qualifier: registration open now, top 8 invited, 4 places, 2 go through."""
    t = services.create_tournament("TDL Cup 3", keyword="CUP")
    entries.add_qualifier(t)
    now = timezone.now()
    t.reg_opens_at, t.reg_closes_at = now - dt.timedelta(hours=1), now + dt.timedelta(days=1)
    t.places, t.qualify_count = 4, 2
    t.save()
    assert entries.open_due() == 1  # registration opened: the top 8 are invited
    t.refresh_from_db()
    return t


def player_user(lg, name, i=0, coins=FEE):  # noqa: F811
    """A linked player of team ``name`` with ``coins`` more DC."""
    u = user(f"{name.lower()}p{i}@x.com")
    p = lg["players"][(name, i)]
    p.user = u
    p.save()
    if coins:
        post_entry(wallet_for(u), LedgerEntry.Kind.ADJUSTMENT, coins, f"test:{u.pk}")
    return u


def balance(u) -> int:
    return wallet_for(u).balance


def team(name) -> Team:
    return Team.objects.get(name=name)


def test_registration_opening_invites_and_freezes_the_top_teams(lg, cup):  # noqa: F811
    final = services.final_stage(cup)
    invited = Entry.objects.filter(tournament=cup, stage=final, via=V.INVITED, status=S.IN)
    assert sorted(e.team.name for e in invited) == NAMES[:8]
    assert entries.open_due() == 0  # only once
    assert entries.qualifier_stage(cup).name == "Qualifier"
    assert entries.current_stage(cup) == entries.qualifier_stage(cup)
    assert sorted(cup.teams.values_list("name", flat=True)) == NAMES[:8]


def test_a_player_registers_paying_from_their_wallet(lg, cup):  # noqa: F811
    u = player_user(lg, "T09")
    before = balance(u)
    row = entries.register(cup, team("T09"), u)
    assert row.status == S.IN and row.via == V.REGISTERED and row.fee_paid == FEE
    assert balance(u) == before - FEE
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.CUP_FEE, amount=-FEE).count() == 1
    with pytest.raises(TournamentError, match="already in"):
        entries.register(cup, team("T09"), u)


def test_short_of_dc_cant_register(lg, cup):  # noqa: F811
    u = player_user(lg, "T09", coins=0)
    with pytest.raises(TournamentError, match="Entry costs 10,000 DC"):
        entries.register(cup, team("T09"), u)
    assert not Entry.objects.filter(team__name="T09", status=S.IN).exists()


def test_invited_teams_and_strangers_cant_register(lg, cup):  # noqa: F811
    with pytest.raises(TournamentError, match="invited to"):
        entries.register(cup, team("T01"), player_user(lg, "T01"))
    with pytest.raises(TournamentError, match="manager or its players"):
        entries.register(cup, team("T10"), player_user(lg, "T09"))


def test_unapproved_or_suspended_teams_cant_register(lg, cup):  # noqa: F811
    u = player_user(lg, "T09")
    Team.objects.filter(name="T09").update(status=Team.Status.PENDING)
    with pytest.raises(TournamentError, match="approve"):
        entries.register(cup, team("T09"), u)
    Team.objects.filter(name="T09").update(status=Team.Status.APPROVED)
    Suspension.objects.create(team=team("T09"), reason="cheating")
    with pytest.raises(TournamentError, match="suspended"):
        entries.register(cup, team("T09"), u)


def test_registration_only_while_open(lg, cup):  # noqa: F811
    u = player_user(lg, "T09")
    cup.reg_opens_at = timezone.now() + dt.timedelta(hours=1)
    cup.save()
    with pytest.raises(TournamentError, match="hasn't opened"):
        entries.register(cup, team("T09"), u)
    cup.reg_opens_at = timezone.now() - dt.timedelta(days=2)
    cup.reg_closes_at = timezone.now() - dt.timedelta(days=1)
    cup.save()
    with pytest.raises(TournamentError, match="closed"):
        entries.register(cup, team("T09"), u)


def test_the_manager_pays_from_the_team_pot(lg, cup):  # noqa: F811
    manager = user("boss@x.com")
    Membership.objects.create(user=manager, team=team("T09"), role=Membership.Role.MANAGER)
    pot = pot_for(team("T09"))
    pot.balance = 12000
    pot.save()
    row = entries.register(cup, team("T09"), manager, "POT")
    assert row.paid_from == "POT" and TeamPot.objects.get(pk=pot.pk).balance == 2000
    # a player can't spend the pot when the team has a manager
    pot_for(team("T10"))
    Membership.objects.create(
        user=user("boss2@x.com"), team=team("T10"), role=Membership.Role.MANAGER
    )
    with pytest.raises(TournamentError, match="manager can spend"):
        entries.register(cup, team("T10"), player_user(lg, "T10"), "POT")


def test_pot_short_is_refused(lg, cup):  # noqa: F811
    manager = user("boss@x.com")
    Membership.objects.create(user=manager, team=team("T09"), role=Membership.Role.MANAGER)
    with pytest.raises(TournamentError, match="pot has 0 DC"):
        entries.register(cup, team("T09"), manager, "POT")


def test_waitlist_pays_nothing_until_a_place_frees(lg, cup):  # noqa: F811
    users = {n: player_user(lg, n) for n in ("T09", "T10", "T11", "T12", "T13")}
    for n in ("T09", "T10", "T11", "T12"):
        entries.register(cup, team(n), users[n])
    waiting = entries.register(cup, team("T13"), users["T13"])
    assert waiting.status == S.WAITLIST and waiting.fee_paid == 0
    before = balance(users["T13"])
    # T10 withdraws: refunded in full, T13 moves up and pays now
    b10 = balance(users["T10"])
    entries.withdraw(cup, team("T10"), users["T10"])
    assert balance(users["T10"]) == b10 + FEE
    waiting.refresh_from_db()
    assert waiting.status == S.IN and waiting.fee_paid == FEE
    assert balance(users["T13"]) == before - FEE


def test_a_waitlisted_team_short_of_dc_is_skipped(lg, cup):  # noqa: F811
    users = {n: player_user(lg, n) for n in ("T09", "T10", "T11", "T12")}
    for n in ("T09", "T10", "T11", "T12"):
        entries.register(cup, team(n), users[n])
    broke = player_user(lg, "T13", coins=FEE)
    rich = player_user(lg, "T14")
    entries.register(cup, team("T13"), broke)
    entries.register(cup, team("T14"), rich)
    post_entry(wallet_for(broke), LedgerEntry.Kind.ADJUSTMENT, -FEE, "spent")  # spends it
    entries.withdraw(cup, team("T09"), users["T09"])
    t13 = Entry.objects.get(tournament=cup, team__name="T13")
    t14 = Entry.objects.get(tournament=cup, team__name="T14")
    assert t13.status == S.REMOVED and "waitlist" in t13.note
    assert t14.status == S.IN and t14.fee_paid == FEE


def test_no_withdrawing_after_close_but_staff_can_remove(lg, cup):  # noqa: F811
    staff = user("staff@x.com", staff=True)
    u = player_user(lg, "T09")
    row = entries.register(cup, team("T09"), u)
    cup.reg_closes_at = timezone.now() - dt.timedelta(minutes=1)
    cup.save()
    with pytest.raises(TournamentError, match="has closed"):
        entries.withdraw(cup, team("T09"), u)
    before = balance(u)
    entries.staff_remove(cup, row, staff)
    assert balance(u) == before + FEE


def test_staff_can_keep_the_fee_for_a_rule_break(lg, cup):  # noqa: F811
    staff = user("staff@x.com", staff=True)
    u = player_user(lg, "T09")
    row = entries.register(cup, team("T09"), u)
    before = balance(u)
    entries.staff_remove(cup, row, staff, keep_fee=True)
    row.refresh_from_db()
    assert balance(u) == before and row.status == S.REMOVED and row.fee_paid == FEE


def test_cancelling_refunds_every_fee(lg, cup):  # noqa: F811
    staff = user("staff@x.com", staff=True)
    users = {n: player_user(lg, n) for n in ("T09", "T10")}
    for n, u in users.items():
        entries.register(cup, team(n), u)
    before = {n: balance(u) for n, u in users.items()}
    assert entries.cancel(cup, staff) == 2 * FEE
    for n, u in users.items():
        assert balance(u) == before[n] + FEE
    cup.refresh_from_db()
    assert services.status(cup) == "cancelled" and entries.reg_state(cup) == "cancelled"
    with pytest.raises(TournamentError, match="already cancelled"):
        entries.cancel(cup, staff)


def test_an_invited_team_declines_and_staff_invite_the_next(lg, cup):  # noqa: F811
    u = player_user(lg, "T03")
    entries.withdraw(cup, team("T03"), u)
    assert not cup.teams.filter(name="T03").exists()
    assert entries.invite_next(cup).name == "T09"
    assert cup.teams.filter(name="T09").exists()


def test_inviting_a_registered_team_refunds_its_fee(lg, cup):  # noqa: F811
    u = player_user(lg, "T09")
    entries.register(cup, team("T09"), u)
    before = balance(u)
    entries.invite_next(cup)  # T09 is next in the standings
    assert balance(u) == before + FEE
    q = Entry.objects.get(tournament=cup, team__name="T09", stage=entries.qualifier_stage(cup))
    assert q.status == S.REMOVED


def test_the_qualifier_top_go_through_and_prizes_use_the_final_table(lg, cup):  # noqa: F811
    users = {n: player_user(lg, n) for n in ("T09", "T10", "T11", "T12")}
    for n, u in users.items():
        entries.register(cup, team(n), u)
    q = entries.qualifier_stage(cup)
    day = MatchDay.objects.create(stage=q, number=1, title="CUP QUALIFIER 10PM")
    play(day, 1, ["T12", "T11", "T10", "T09"], lg["players"], lg["teams"])
    rebuild_season(cup.season)
    top = entries.qualifier_top(cup)
    assert [r["team"]["name"] for r in top if r["through"]] == ["T12", "T11"]
    entries.advance(cup, None)
    cup.refresh_from_db()
    final = services.final_stage(cup)
    assert entries.current_stage(cup) == final
    finalists = Entry.objects.filter(tournament=cup, stage=final, status=S.IN)
    assert sorted(e.team.name for e in finalists) == sorted(NAMES[:8] + ["T11", "T12"])
    # the final: T11 wins it, but the qualifier counts nowhere in the prizes
    day2 = MatchDay.objects.create(stage=final, number=1, title="CUP GF 10PM")
    play(day2, 1, ["T11", "T12"] + NAMES[:8], lg["players"], lg["teams"])
    rebuild_season(cup.season)
    first = next(p for p in services.preview(cup)["prizes"] if p["key"] == "place:1")
    assert first["winners"][0]["team"]["name"] == "T11"


def test_api_register_withdraw_and_my_entry(lg, cup):  # noqa: F811
    u = player_user(lg, "T09")
    c = client(u)
    me = c.get(f"/api/v1/tournaments/{cup.slug}/me").json()
    assert me["team"]["name"] == "T09" and me["entry"] is None and me["can_register"]
    assert me["registration"]["state"] == "open" and me["registration"]["fee"] == FEE
    r = c.post(f"/api/v1/tournaments/{cup.slug}/register", {"pay_from": "WALLET"}, format="json")
    assert r.status_code == 200, r.content
    assert r.json()["entry"]["status"] == "IN"
    assert r.json()["registration"]["taken"] == 1
    r = c.post(f"/api/v1/tournaments/{cup.slug}/withdraw", {}, format="json")
    assert r.status_code == 200 and r.json()["entry"] is None
    r = c.post(f"/api/v1/tournaments/{cup.slug}/register", {"pay_from": "POT"}, format="json")
    assert r.status_code == 400  # no pot money


def test_api_staff_tools(lg, cup):  # noqa: F811
    staff = client(user("staff@x.com", staff=True))
    base = f"/api/v1/admin/tournaments/{cup.slug}"
    r = staff.patch(base, {"entry_fee": 5000, "places": 6}, format="json")
    assert r.status_code == 200 and r.json()["registration"]["fee"] == 5000
    r = staff.post(
        f"{base}/entries",
        {"team": team("T14").pk, "stage": entries.qualifier_stage(cup).pk},
        format="json",
    )
    assert r.status_code == 200
    row = next(e for e in r.json()["entries"] if e["team"]["name"] == "T14")
    assert row["via"] == "STAFF"
    r = staff.post(f"{base}/entries/{row['id']}/remove", {}, format="json")
    assert r.status_code == 200
    detail = staff.get(base).json()
    assert any(e["status"] == "REMOVED" for e in detail["entries"])
    r = staff.post(f"{base}/cancel", {}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    # players can't use staff tools
    assert client(player_user(lg, "T09")).post(f"{base}/cancel").status_code == 403


def test_a_cup_without_a_qualifier_works_as_before(lg):  # noqa: F811
    t = services.create_tournament("Old Cup")
    assert entries.reg_state(t) == "off"
    entries.invite_top(t)
    assert t.teams.count() == 12
    staff = user("staff@x.com", staff=True)
    entries.set_final_teams(t, [team("T01").pk, team("T14").pk], staff)
    assert sorted(t.teams.values_list("name", flat=True)) == ["T01", "T14"]
