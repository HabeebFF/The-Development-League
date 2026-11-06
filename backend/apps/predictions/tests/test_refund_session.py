"""Staff can refund a whole session (8PM, 10PM) in one go: every market in it that isn't
settled yet is voided and every stake comes back."""

import uuid

import pytest

from apps.predictions.models import Bet, Market, Multiple
from apps.predictions.multiples import place_multiple
from apps.predictions.services import wallet_for

from . import test_player_rules as tpr
from .test_player_rules import bet, booyah, market
from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db
S, C = Market.Status, Market.Category
# The player-rules tests' fixtures, used here too.
_on, lg, staff = tpr._on, tpr.lg, tpr.staff


def coins(user) -> int:
    return wallet_for(user).balance


def test_refund_a_whole_session(lg, staff):
    fan, other = make_user("fan@tdl.test"), make_user("other@tdl.test")
    m1, m2 = booyah(lg, staff, 1), booyah(lg, staff, 2)
    whole = market(lg, staff, C.SESSION_WINNER, "session", teams=["Alpha", "Bravo"])
    season = market(lg, staff, C.OVERALL_WINNER, teams=["Alpha", "Bravo"])
    for m in (m1, m2, whole):
        bet(fan, m, stake=100)
    acc, _ = place_multiple(
        other,
        picks=[{"market": m.pk, "outcome": m.outcomes.first().pk} for m in (m1, season)],
        stake=50,
        client_key=uuid.uuid4(),
    )
    assert coins(fan) == 700 and coins(other) == 950

    url = f"/api/v1/admin/predictions/fixtures/{lg['fixtures']['session'].pk}/refund"
    plan = as_user(staff).get(url).json()
    assert plan == {"markets": 3, "bets": 3, "multiples": 1, "settled": 0, "already_void": 0}
    assert as_user(staff).post(url, {}, format="json").status_code == 400  # needs a reason
    res = as_user(staff).post(url, {"reason": "Server down"}, format="json")
    assert res.status_code == 200, res.content
    assert res.json()["voided"] == 3

    done = Market.objects.filter(pk__in=[m1.pk, m2.pk, whole.pk])
    assert set(done.values_list("status", flat=True)) == {S.VOID}
    assert coins(fan) == 1000
    assert set(Bet.objects.filter(user=fan).values_list("status", flat=True)) == {"VOID"}
    # The multiple's Match 1 pick drops out; its season pick still stands.
    season.refresh_from_db()
    assert season.status == S.OPEN
    acc = Multiple.objects.get(pk=acc.pk)
    assert acc.status == "PENDING"
    # Repeating it changes nothing.
    again = as_user(staff).post(url, {"reason": "Server down"}, format="json").json()
    assert again["voided"] == 0 and again["already_void"] == 3
    assert coins(fan) == 1000


def test_refund_one_match_and_settled_markets_are_left(lg, staff):
    fan = make_user("fan@tdl.test")
    m1, m2 = booyah(lg, staff, 1), booyah(lg, staff, 2)
    bet(fan, m1, stake=100)
    bet(fan, m2, stake=100)
    Market.objects.filter(pk=m2.pk).update(status=S.SETTLED)
    url = f"/api/v1/admin/predictions/fixtures/{lg['fixtures'][1].pk}/refund"
    res = as_user(staff).post(url, {"reason": "Lobby bug"}, format="json").json()
    assert res["voided"] == 1
    assert Market.objects.get(pk=m2.pk).status == S.SETTLED
    session = f"/api/v1/admin/predictions/fixtures/{lg['fixtures']['session'].pk}/refund"
    assert as_user(staff).get(session).json()["settled"] == 1
    assert coins(fan) == 900


def test_only_staff_can_refund(lg, staff):
    url = f"/api/v1/admin/predictions/fixtures/{lg['fixtures']['session'].pk}/refund"
    assert (
        as_user(make_user("fan@tdl.test")).post(url, {"reason": "x"}, format="json").status_code
        == 403
    )
