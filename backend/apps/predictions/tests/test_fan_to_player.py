"""A fan switching to a player account (My account): linking a game UID keeps their DC,
designs and history, refunds open predictions now on themselves or their team, and settling
those markets later leaves the refunds alone."""

import uuid
from unittest import mock

import pytest

from apps.accounts.models import PlayerClaim
from apps.predictions import settlement as st
from apps.predictions.markets import transition
from apps.predictions.models import Bet, LedgerEntry, Market
from apps.predictions.multiples import place_multiple
from apps.predictions.services import wallet_for

from .test_player_rules import _on, bet, booyah, lg, market, staff  # noqa: F401
from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db
S, C = Market.Status, Market.Category
ACE_UID = "7000"  # Ace plays for Alpha (see ``lg``)


def link(user, uid=ACE_UID):
    return as_user(user).post("/api/v1/me/link-uid", {"game_uid": uid}, format="json")


def settle(m, staff, winner):  # noqa: F811
    """Settle with ``winner`` as what the (here imaginary) uploaded match says."""
    transition(m, S.CLOSED, actor=staff)
    pk = m.outcomes.get(label=winner).pk
    said = {"kind": "SETTLE", "winners": [pk], "voids": [], "evidence": {}}
    with mock.patch.object(st, "suggest", return_value=said):
        st.settle(m, actor=staff, winners=[pk])


def test_preview_shows_the_player_and_what_gets_refunded(lg, staff):  # noqa: F811
    m = booyah(lg, staff)
    fan = make_user("kola@tdl.test")
    bet(fan, m, "Alpha", stake=200)
    bet(fan, m, "Bravo", stake=30)
    res = as_user(fan).get(f"/api/v1/me/link-uid?uid={ACE_UID}")
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["player"]["name"] == "Ace" and body["player"]["team"]["name"] == "Alpha"
    assert body["taken"] is False
    assert [v["stake"] for v in body["voids"]] == [200] and body["refund"] == 200
    # Only a preview: nothing changed.
    assert Bet.objects.filter(user=fan, status=Bet.Status.PENDING).count() == 2
    assert lg["players"]["Ace"].user is None

    new = as_user(fan).get("/api/v1/me/link-uid?uid=99887766").json()
    assert new["player"] is None and new["voids"] == []
    assert as_user(fan).get("/api/v1/me/link-uid?uid=abc").status_code == 400


def test_switching_links_keeps_dc_and_refunds_open_bets_on_own_team(lg, staff):  # noqa: F811
    m = booyah(lg, staff)
    fan = make_user("kola@tdl.test")
    own = bet(fan, m, "Alpha", stake=200)
    other = bet(fan, m, "Bravo", stake=30)
    balance = wallet_for(fan).balance

    res = link(fan)
    assert res.status_code == 201, res.content
    assert res.json()["status"] == "APPROVED" and res.json()["switched"] is True
    assert res.json()["voided_bets"] == 1
    lg["players"]["Ace"].refresh_from_db()
    assert lg["players"]["Ace"].user == fan
    assert wallet_for(fan).balance == balance + 200

    own.refresh_from_db()
    other.refresh_from_db()
    assert own.status == Bet.Status.VOID and own.withdrawn_at and own.payout == 200
    assert other.status == Bet.Status.PENDING
    refund = LedgerEntry.objects.get(bet=own, kind=LedgerEntry.Kind.REFUND)
    assert "Ace" in refund.reason

    # Alpha wins: the refunded pick isn't paid again, the other one just loses.
    settle(m, staff, "Alpha")
    own.refresh_from_db()
    other.refresh_from_db()
    assert own.status == Bet.Status.VOID and own.payout == 200
    assert other.status == Bet.Status.LOST
    assert wallet_for(fan).balance == balance + 200
    assert LedgerEntry.objects.filter(bet=own).count() == 2  # stake + the one refund


def test_settled_bets_stay_as_they_are(lg, staff):  # noqa: F811
    m = booyah(lg, staff)
    fan = make_user("kola@tdl.test")
    won = bet(fan, m, "Alpha", stake=100)
    settle(m, staff, "Alpha")
    won.refresh_from_db()
    balance = wallet_for(fan).balance
    assert won.status == Bet.Status.WON
    assert link(fan).json()["voided_bets"] == 0
    won.refresh_from_db()
    assert won.status == Bet.Status.WON and wallet_for(fan).balance == balance


def test_a_multiple_with_an_own_team_pick_is_refunded_whole(lg, staff):  # noqa: F811
    m1 = booyah(lg, staff, fixture=1)
    m2 = booyah(lg, staff, fixture=2)
    fan = make_user("kola@tdl.test")
    picks = [
        {"market": m1.pk, "outcome": m1.outcomes.get(label="Alpha").pk},
        {"market": m2.pk, "outcome": m2.outcomes.get(label="Bravo").pk},
    ]
    multiple, _ = place_multiple(fan, picks=picks, stake=80, client_key=uuid.uuid4())
    balance = wallet_for(fan).balance
    assert link(fan).json()["voided_bets"] == 1
    multiple.refresh_from_db()
    assert multiple.status == Bet.Status.VOID and multiple.withdrawn_at
    assert wallet_for(fan).balance == balance + 80
    settle(m1, staff, "Alpha")
    settle(m2, staff, "Bravo")
    multiple.refresh_from_db()
    assert multiple.status == Bet.Status.VOID and wallet_for(fan).balance == balance + 80


def test_a_pick_on_another_team_stays(lg, staff):  # noqa: F811
    season = market(lg, staff, C.OVERALL_WINNER, teams=["Alpha", "Bravo"])
    fan = make_user("kola@tdl.test")
    b = bet(fan, season, "Bravo", stake=40)
    # Overall winner has a choice per team: only the Alpha choice would be closed.
    assert link(fan).json()["voided_bets"] == 0
    b.refresh_from_db()
    assert b.status == Bet.Status.PENDING


def test_linked_players_change_uid_only_through_staff(lg, staff):  # noqa: F811
    fan = make_user("kola@tdl.test")
    assert link(fan).status_code == 201
    again = link(fan, "7001")
    assert again.status_code == 400 and "staff" in str(again.json())
    assert link(fan).status_code == 400  # the same UID twice
    assert as_user(fan).get("/api/v1/me/link-uid?uid=7001").status_code == 400


def test_a_taken_uid_waits_for_staff_and_refunds_only_when_approved(lg, staff):  # noqa: F811
    owner = make_user("owner@tdl.test")
    assert link(owner).json()["status"] == "APPROVED"
    m = booyah(lg, staff)
    fan = make_user("kola@tdl.test")
    b = bet(fan, m, "Alpha", stake=60)
    preview = as_user(fan).get(f"/api/v1/me/link-uid?uid={ACE_UID}").json()
    assert preview["taken"] is True and preview["voids"] == []
    res = link(fan)
    assert res.status_code == 201 and res.json()["status"] == "PENDING"
    b.refresh_from_db()
    assert b.status == Bet.Status.PENDING
    assert as_user(fan).get("/api/v1/me").json()["pending_uid_claim"] == ACE_UID

    # Staff unlink the first account, then approve this one: the refund happens now.
    first = PlayerClaim.objects.get(user=owner)
    as_user(staff).post(f"/api/v1/admin/player-claims/{first.pk}/unlink")
    claim = PlayerClaim.objects.get(user=fan, status="PENDING")
    res = as_user(staff).post(f"/api/v1/admin/player-claims/{claim.pk}/approve")
    assert res.status_code == 200, res.content
    assert res.json()["voided_bets"] == 1
    b.refresh_from_db()
    assert b.status == Bet.Status.VOID


def test_sign_up_claims_are_not_marked_switched(lg):  # noqa: F811
    res = as_user(make_user("a@tdl.test")).post(
        "/api/v1/me/link-uid", {"game_uid": "123"}, format="json"
    )
    assert res.json()["switched"] is True
    from apps.accounts.views import link_claim

    claim = PlayerClaim.objects.create(user=make_user("b@tdl.test"), game_uid=456)
    link_claim(claim)
    claim.refresh_from_db()
    assert claim.switched is False and claim.status == "APPROVED"
