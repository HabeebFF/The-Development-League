"""Perks: player perks from the wallet, team perks from the team pot, staff review."""

import datetime as dt
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membership, StaffProfile
from apps.dc import perks, ranks, rewards
from apps.dc.models import PerkPurchase, TeamPot
from apps.league.models import Team
from apps.predictions.models import LedgerEntry
from apps.predictions.services import check_wallets, lagos_today, post_entry, wallet_for
from apps.scrims import services as scrims
from apps.scrims.models import Registration, ScrimSession

from .conftest import make_user, upload

pytestmark = pytest.mark.django_db
S = PerkPurchase.Status
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00"
    b"\x00\x00IEND\xaeB`\x82"
)


def once():
    return uuid.uuid4().hex


def rich(user, amount=200_000):
    post_entry(wallet_for(user), LedgerEntry.Kind.ADJUSTMENT, amount, f"gift-{once()}")


def test_name_colour_comes_out_of_the_wallet_and_shows(league):
    user = league["user"]
    rich(user)
    row = perks.buy(user, "NAME_COLOUR", {"colour": "gold"}, once())
    assert row.status == S.ACTIVE and row.ends_at - row.starts_at == dt.timedelta(days=7)
    assert wallet_for(user).balance == 201_000 - 15_000
    assert perks.name_colours() == {league["p"]["a1"].pk: "gold"}
    # A second week starts when the first ends.
    second = perks.buy(user, "NAME_COLOUR", {"colour": "cyan"}, once())
    assert second.starts_at == row.ends_at
    assert check_wallets() == []


def test_same_tap_twice_buys_once(league):
    rich(league["user"])
    key = once()
    a = perks.buy(league["user"], "PIN", {"match_id": upload(league).pk, "at_s": 90}, key)
    b = perks.buy(league["user"], "PIN", {"match_id": a.data["match_id"]}, key)
    assert a.pk == b.pk
    assert wallet_for(league["user"]).balance == 201_000 - 5_000


def test_not_enough_dc(league):
    with pytest.raises(perks.PerkError, match="Not enough DC"):
        perks.buy(league["user"], "SHOUTOUT", {"text": "GG all"}, once())


def test_fans_and_staff_cant_buy(league):
    fan = make_user("fan@tdl.test")
    rich(fan)
    with pytest.raises(perks.PerkError, match="league players"):
        perks.buy(fan, "NAME_COLOUR", {"colour": "gold"}, once())
    StaffProfile.objects.create(user=league["user"])
    with pytest.raises(perks.PerkError, match="staff"):
        perks.buy(league["user"], "NAME_COLOUR", {"colour": "gold"}, once())


def test_pin_must_be_your_own_match(league):
    rich(league["user"])
    other = upload(league, number=2, kills={"b1": 1})
    with pytest.raises(perks.PerkError, match="you played"):
        perks.buy(league["user"], "PIN", {"match_id": other.pk}, once())
    mine = upload(league, number=3)
    perks.buy(league["user"], "PIN", {"match_id": mine.pk, "at_s": 125, "note": "4 kills"}, once())
    pin = perks.pinned(league["p"]["a1"])
    assert pin["match_id"] == mine.pk and pin["at_s"] == 125


def test_shoutout_waits_for_staff_then_runs_a_day(league):
    rich(league["user"])
    row = perks.buy(league["user"], "SHOUTOUT", {"text": "  GG   Bravo, see you tonight "}, once())
    assert row.status == S.PENDING and row.data["text"] == "GG Bravo, see you tonight"
    assert perks.shoutouts() == []
    boss = make_user("staff@tdl.test")
    perks.review(row, boss, approve=True)
    assert [s["text"] for s in perks.shoutouts()] == ["GG Bravo, see you tonight"]
    with pytest.raises(perks.PerkError):
        perks.review(row, boss, approve=False)


def test_rejected_shoutout_is_refunded(league):
    rich(league["user"])
    row = perks.buy(league["user"], "SHOUTOUT", {"text": "something rude"}, once())
    perks.review(row, make_user("staff@tdl.test"), approve=False, note="Keep it friendly")
    assert wallet_for(league["user"]).balance == 201_000
    assert check_wallets() == []


def test_team_pot_chip_in_and_manager_spends(league):
    user = league["user"]
    rich(user)
    perks.chip_in(user, league["alpha"], 30_000, once())
    assert TeamPot.objects.get(team=league["alpha"]).balance == 30_000
    assert wallet_for(user).balance == 171_000
    # No manager: any player of the team can spend. Colours are applied to the team.
    perks.buy(user, "THEME", {"primary": "#FF0000", "secondary": "#000000"}, once())
    alpha = Team.objects.get(pk=league["alpha"].pk)
    assert (alpha.primary_color, alpha.secondary_color) == ("#ff0000", "#000000")
    assert TeamPot.objects.get(team=alpha).balance == 10_000
    with pytest.raises(perks.PerkError, match="team pot has 10,000"):
        perks.buy(user, "THEME", {"primary": "#00ff00", "secondary": "#000000"}, once())


def test_only_the_manager_spends_when_there_is_one(league):
    user = league["user"]
    rich(user)
    perks.chip_in(user, league["alpha"], 60_000, once())
    Membership.objects.create(
        user=make_user("boss@tdl.test"), team=league["alpha"], role=Membership.Role.MANAGER
    )
    with pytest.raises(perks.PerkError, match="manager"):
        perks.buy(user, "THEME", {"primary": "#ff0000", "secondary": "#000000"}, once())


def test_chip_in_only_to_your_team(league):
    rich(league["user"])
    with pytest.raises(perks.PerkError, match="own team"):
        perks.chip_in(league["user"], league["bravo"], 1_000, once())


def test_banner_upload_replace_and_remove_with_refund(league):
    user = league["user"]
    rich(user)
    perks.chip_in(user, league["alpha"], 150_000, once())
    img = SimpleUploadedFile("b.png", PNG, content_type="image/png")
    first = perks.buy(user, "BANNER", {}, once(), image=img)
    assert first.image.name.startswith("teams/banners/")
    assert perks.team_look(league["alpha"])["banner"]
    second = perks.buy(
        user, "BANNER", {}, once(), image=SimpleUploadedFile("c.png", PNG, "image/png")
    )
    first.refresh_from_db()
    assert first.status == S.REPLACED
    perks.remove(second, make_user("staff@tdl.test"), give_back=True, note="Not allowed")
    assert TeamPot.objects.get(team=league["alpha"]).balance == 150_000 - 50_000
    assert perks.banners() == {}
    with pytest.raises(perks.PerkError, match="PNG"):
        perks.buy(
            user, "BANNER", {}, once(), image=SimpleUploadedFile("x.gif", b"GIF89a", "image/gif")
        )


def test_perk_spending_never_lowers_a_rank(league):
    user = league["user"]
    post_entry(wallet_for(user), LedgerEntry.Kind.DAILY_BONUS, 20_000, "bonus")
    perks.buy(user, "NAME_COLOUR", {"colour": "gold"}, once())
    perks.chip_in(user, league["alpha"], 1_000, once())
    assert ranks.earned_by_user()[user.pk] == 20_000


def test_expired_perks_stop_showing(league):
    rich(league["user"])
    row = perks.buy(league["user"], "NAME_COLOUR", {"colour": "gold"}, once())
    PerkPurchase.objects.filter(pk=row.pk).update(ends_at=timezone.now() - dt.timedelta(minutes=1))
    assert perks.name_colours() == {}


def test_scrim_waitlist_moves_the_dc_priority_team_up_first(league, settings):
    # Bravo earned the most DC from matches last week.
    day = lagos_today()
    last_week = ranks.week_start(day) - dt.timedelta(days=3)
    from apps.dc.models import DcSettings

    conf = DcSettings.get()
    conf.start_date = last_week
    conf.save()
    rewards.sync_match(upload(league, number=5, kills={"b1": 9}, winner="bravo", date=last_week))
    assert ranks.priority_team(day)["team_id"] == league["bravo"].pk

    scrim = ScrimSession.objects.create(date=day, session="8PM", max_teams=1)
    other = Team.objects.create(name="Charlie")
    Registration.objects.create(scrim=scrim, team=league["alpha"], status="REGISTERED")
    Registration.objects.create(scrim=scrim, team=other, status="WAITLIST")
    Registration.objects.create(scrim=scrim, team=league["bravo"], status="WAITLIST")
    Registration.objects.filter(scrim=scrim, team=league["alpha"]).delete()
    from unittest import mock

    with mock.patch.object(scrims, "stage", return_value="open"):
        scrims._fill(scrim)
    playing = scrim.registrations.get(status="REGISTERED")
    assert playing.team_id == league["bravo"].pk


def test_cup_wildcard_takes_the_last_place(league):
    from apps.dc.ranks import wildcard

    conf_day = lagos_today()
    rewards.sync_match(upload(league, kills={"b1": 4}))
    pick = wildcard(conf_day + dt.timedelta(days=1), {league["alpha"].pk})
    assert pick["team_id"] == league["bravo"].pk


def test_perk_endpoints(league):
    user = league["user"]
    rich(user)
    client = APIClient()
    client.force_authenticate(user)
    page = client.get("/api/v1/dc/perks").json()
    assert {p["key"] for p in page["perks"]} == {
        "BANNER",
        "THEME",
        "SHOUTOUT",
        "PIN",
        "NAME_COLOUR",
    }
    assert page["me"]["team"]["name"] == "Alpha" and page["me"]["can_spend_pot"]
    res = client.post(
        "/api/v1/dc/perks/buy",
        {"key": "NAME_COLOUR", "data": {"colour": "violet"}, "once": once()},
        format="json",
    )
    assert res.status_code == 201
    assert client.post("/api/v1/dc/pot", {"amount": 5_000, "once": once()}).json() == {"pot": 5_000}
    bad = client.post(
        "/api/v1/dc/perks/buy",
        {"key": "NAME_COLOUR", "data": {"colour": "pink"}, "once": once()},
        format="json",
    )
    assert bad.status_code == 400
    live = APIClient().get("/api/v1/dc/perks/live").json()
    assert live["name_colours"][str(league["p"]["a1"].pk)] == "violet"

    shout = client.post(
        "/api/v1/dc/perks/buy",
        {"key": "SHOUTOUT", "data": {"text": "GG lobby"}, "once": once()},
        format="json",
    ).json()
    boss = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=boss)
    client.force_authenticate(boss)
    admin = client.get("/api/v1/admin/dc/perks").json()
    assert [p["id"] for p in admin["pending"]] == [shout["id"]]
    ok = client.post(f"/api/v1/admin/dc/purchases/{shout['id']}", {"action": "approve"})
    assert ok.json()["status"] == "ACTIVE"
    assert (
        client.patch(
            "/api/v1/admin/dc/perks", {"key": "PIN", "price": 7_000}, format="json"
        ).status_code
        == 200
    )
