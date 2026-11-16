"""DC earned by playing: kills, Booyah, MVP and turning up, paid after each upload."""

import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PlayerClaim, StaffProfile
from apps.accounts.views import link_claim
from apps.dc import rewards
from apps.dc.models import DcSettings, MatchReward
from apps.league.models import Match
from apps.predictions.models import LedgerEntry
from apps.predictions.services import check_wallets, lagos_today, wallet_for
from apps.results.models import PlayerMatchRating, PlayerMatchResult, TeamMatchResult

from .conftest import make_user, upload

pytestmark = pytest.mark.django_db


def coins(user) -> int:
    return wallet_for(user).balance


def reward(match, key, league):
    return MatchReward.objects.get(match=match, player=league["p"][key])


def test_linked_player_is_paid_for_kills_booyah_mvp_and_playing(league):
    match = upload(league)
    rewards.sync_match(match)
    # 50 played + 3 x 100 kills + 1,000 Booyah + 500 MVP (most kills, no ratings yet)
    assert reward(match, "a1", league).amount == 1850
    assert coins(league["user"]) == 1000 + 1850
    entry = LedgerEntry.objects.filter(kind=LedgerEntry.Kind.MATCH_REWARD).get()
    assert "3 kills, Booyah, MVP" in entry.reason
    assert check_wallets() == []


def test_running_again_pays_nothing_more(league):
    match = upload(league)
    rewards.sync_match(match)
    rewards.sync_match(match)
    rewards.sweep()
    assert coins(league["user"]) == 2850
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.MATCH_REWARD).count() == 1


def test_mvp_follows_the_ratings(league):
    match = upload(league)
    PlayerMatchRating.objects.create(
        match=match, player=league["p"]["b1"], team=league["bravo"], rating=9.0, raw=9.0
    )
    PlayerMatchRating.objects.create(
        match=match, player=league["p"]["a1"], team=league["alpha"], rating=5.0, raw=5.0
    )
    rewards.sync_match(match)
    assert reward(match, "b1", league).mvp
    assert not reward(match, "a1", league).mvp
    assert coins(league["user"]) == 1000 + 50 + 300 + 1000


def test_reupload_with_fewer_kills_takes_back_the_difference(league):
    match = upload(league)
    rewards.sync_match(match)
    PlayerMatchResult.objects.filter(match=match, player=league["p"]["a1"]).update(kills=1)
    PlayerMatchResult.objects.filter(match=match, player=league["p"]["b1"]).update(kills=5)
    rewards.sync_match(match)
    # a1 now: 50 + 100 + 1,000 (no MVP)
    assert coins(league["user"]) == 1000 + 1150
    assert check_wallets() == []


def test_take_back_never_goes_below_zero(league):
    match = upload(league)
    rewards.sync_match(match)
    wallet = wallet_for(league["user"])
    from apps.predictions.services import post_entry

    post_entry(wallet, LedgerEntry.Kind.ADJUSTMENT, -2800, "spend-it")
    TeamMatchResult.objects.filter(match=match, team=league["alpha"]).update(placement=2)
    TeamMatchResult.objects.filter(match=match, team=league["bravo"]).update(placement=1)
    rewards.sync_match(match)
    row = reward(match, "a1", league)
    assert coins(league["user"]) == 0
    assert row.shortfall == 1000 - 50
    assert check_wallets() == []


def test_deleted_match_takes_its_dc_back(league):
    match = upload(league)
    rewards.sync_match(match)
    match.delete()
    assert coins(league["user"]) == 1000
    assert not MatchReward.objects.exists()


def test_unlinked_player_dc_waits_until_they_link(league):
    match = upload(league)
    rewards.sync_match(match)
    b1 = league["p"]["b1"]
    assert rewards.waiting_by_player() == {league["p"]["a2"].pk: 1150, b1.pk: 250}
    user = make_user("b1@tdl.test")
    claim = PlayerClaim.objects.create(user=user, game_uid=b1.game_uid)
    link_claim(claim)
    rewards.pay_waiting(b1)
    assert coins(user) == 1000 + 250
    assert b1.pk not in rewards.waiting_by_player()


def test_staff_account_is_not_paid(league):
    StaffProfile.objects.create(user=league["user"])
    match = upload(league)
    rewards.sync_match(match)
    assert not LedgerEntry.objects.filter(kind=LedgerEntry.Kind.MATCH_REWARD).exists()


def test_matches_before_the_start_day_and_drafts_earn_nothing(league):
    old = upload(league, number=2, date=lagos_today() - dt.timedelta(days=5))
    draft = upload(league, number=3, status=Match.Status.NEEDS_REVIEW)
    rewards.sync_match(old)
    rewards.sync_match(draft)
    assert coins(league["user"]) == 1000


def test_switched_off_pays_nothing(league, settings):
    settings.DC_MATCH_REWARDS = False
    rewards.sync_match(upload(league))
    assert not MatchReward.objects.exists()


def test_staff_rates_apply(league):
    conf = DcSettings.get()
    conf.per_kill, conf.booyah, conf.mvp, conf.played = 10, 0, 0, 0
    conf.save()
    rewards.sync_match(upload(league))
    assert coins(league["user"]) == 1030


def test_backpay_preview_then_pay(league):
    old = upload(league, number=2, date=lagos_today() - dt.timedelta(days=5))
    since = lagos_today() - dt.timedelta(days=7)
    preview = rewards.backpay_preview(since)
    assert preview == {"matches": 1, "dc": 1850 + 1150 + 250, "linked_dc": 1850,
                       "waiting_dc": 1400}  # fmt: skip
    rewards.backpay(since)
    assert DcSettings.get().start_date == since
    assert reward(old, "a1", league).paid == 1850
    assert coins(league["user"]) == 2850


def test_merging_players_moves_their_rewards(league):
    from apps.league.merge import merge_players

    match = upload(league, kills={"a1": 3, "b1": 2})
    rewards.sync_match(match)
    merge_players(league["p"]["b1"], league["p"]["a2"])
    assert MatchReward.objects.filter(player=league["p"]["a2"]).count() == 1


def test_upload_queues_the_rewards(league, django_capture_on_commit_callbacks):
    from unittest import mock

    from apps.ingest.services import assemble

    with mock.patch("apps.dc.tasks.sync_match_task.delay") as delay:
        with django_capture_on_commit_callbacks(execute=True):
            assemble._schedule_rewards(42)
    delay.assert_called_once_with(42)


def test_me_and_staff_endpoints(league):
    match = upload(league)
    rewards.sync_match(match)
    client = APIClient()
    client.force_authenticate(league["user"])
    me = client.get("/api/v1/dc/me").json()
    assert me["total"] == 1850 and me["this_month"] == 1850 and me["waiting"] == 0
    assert me["latest"][0]["booyah"] and me["latest"][0]["mvp"]
    assert client.get("/api/v1/admin/dc/settings").status_code == 403
    waiting = APIClient().get("/api/v1/dc/waiting").json()["waiting"]
    assert waiting[str(league["p"]["b1"].pk)] == 250

    boss = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=boss)
    client.force_authenticate(boss)
    res = client.patch("/api/v1/admin/dc/settings", {"per_kill": 150}, format="json")
    assert res.status_code == 200 and res.json()["per_kill"] == 150
    since = (lagos_today() - dt.timedelta(days=3)).isoformat()
    assert client.get(f"/api/v1/admin/dc/backpay?since={since}").json()["matches"] == 0
    assert client.post("/api/v1/admin/dc/backpay", {"since": since}).status_code == 200
    assert DcSettings.get().start_date.isoformat() == since
