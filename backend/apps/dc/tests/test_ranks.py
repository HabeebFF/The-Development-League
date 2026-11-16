"""DC ranks, the team DC table and the monthly DC King."""

import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile
from apps.dc import ranks, rewards
from apps.dc.models import DcSettings, Spotlight
from apps.predictions.models import LedgerEntry
from apps.predictions.services import lagos_today, post_entry, wallet_for
from apps.shop.models import OwnedDesign

from .test_rewards import _on, league, make_user, upload  # noqa: F401

pytestmark = pytest.mark.django_db
K = LedgerEntry.Kind


def test_rank_for_steps():
    steps = DcSettings.get().rank_steps
    assert ranks.rank_for(4_999, steps) is None
    assert ranks.rank_for(5_000, steps)["key"] == "bronze"
    assert ranks.rank_for(150_000, steps)["key"] == "gold"
    assert ranks.rank_for(9_000_000, steps)["key"] == "legend"


def test_shop_spending_never_lowers_earned(league):
    user = league["user"]
    wallet = wallet_for(user)
    post_entry(wallet, K.DAILY_BONUS, 200, "bonus-1")
    post_entry(wallet, K.PURCHASE, -1_000, "buy-1")
    assert ranks.earned_by_user()[user.pk] == 200


def test_player_earned_covers_linked_and_waiting(league):
    rewards.sync_match(upload(league))
    earned = ranks.player_earned()
    assert earned[league["p"]["a1"].pk] == 1850  # paid to the wallet
    assert earned[league["p"]["b1"].pk] == 250  # waiting, not linked yet


def test_staff_are_not_ranked(league):
    StaffProfile.objects.create(user=league["user"])
    post_entry(wallet_for(league["user"]), K.ADJUSTMENT, 50_000, "gift")
    assert league["p"]["a1"].pk not in ranks.player_earned()


def test_team_table_this_month(league):
    rewards.sync_match(upload(league))
    teams = ranks.team_month(ranks.month_start(lagos_today()))
    assert [t["name"] for t in teams] == ["Alpha", "Bravo"]
    assert teams[0]["dc"] == 1850 + 1150


def test_dc_king_is_crowned_once_and_gets_the_title(league):
    user = league["user"]
    other = make_user("b1@tdl.test")
    league["p"]["b1"].user = other
    league["p"]["b1"].save()
    last = ranks.month_start(ranks.month_start(lagos_today()) - dt.timedelta(days=1))
    when = timezone.make_aware(dt.datetime.combine(last + dt.timedelta(days=3), dt.time(12)))
    for u, amount in ((user, 3_000), (other, 9_000)):
        e, _ = post_entry(wallet_for(u), K.DAILY_BONUS, amount, f"b-{u.pk}")
        LedgerEntry.objects.filter(pk=e.pk).update(created_at=when)
    # This month doesn't count for last month's King.
    post_entry(wallet_for(user), K.DAILY_BONUS, 50_000, "now")

    spot = ranks.crown_last_month()
    assert spot.player == league["p"]["b1"] and spot.earned == 9_000
    assert ranks.crown_last_month().pk == spot.pk
    assert Spotlight.objects.count() == 1
    assert OwnedDesign.objects.filter(user=other, design__slug="title-dc-king").exists()
    assert ranks.board()["king"]["name"] == "B1"


def test_hidden_king_is_not_shown(league):
    last = ranks.month_start(ranks.month_start(lagos_today()) - dt.timedelta(days=1))
    Spotlight.objects.create(month=last, player=league["p"]["a1"], earned=1, hidden=True)
    assert ranks.current_spotlight() is None


def test_nobody_earned_means_no_king(league):
    assert ranks.crown_last_month() is None


def test_board_and_staff_endpoints(league):
    rewards.sync_match(upload(league))
    data = APIClient().get("/api/v1/dc/ranks").json()
    assert data["steps"][0]["key"] == "bronze"
    assert data["players"][str(league["p"]["a1"].pk)] == 1850
    assert data["teams"][0]["slug"] == league["alpha"].slug

    boss = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=boss)
    client = APIClient()
    client.force_authenticate(boss)
    res = client.patch(
        "/api/v1/admin/dc/settings",
        {"rank_steps": [{"name": "Gold", "min": 10}, {"name": "Iron", "min": 1}]},
        format="json",
    )
    assert res.status_code == 200
    assert [s["key"] for s in res.json()["rank_steps"]] == ["iron", "gold"]
    bad = client.patch("/api/v1/admin/dc/settings", {"rank_steps": [{"name": ""}]}, format="json")
    assert bad.status_code == 400

    last = ranks.month_start(ranks.month_start(lagos_today()) - dt.timedelta(days=1))
    s = Spotlight.objects.create(month=last, player=league["p"]["a1"], earned=5)
    rows = client.patch("/api/v1/admin/dc/spotlights", {"id": s.pk, "hidden": True}).json()
    assert rows[0]["hidden"] is True
    assert APIClient().get("/api/v1/dc/ranks").json()["king"] is None
