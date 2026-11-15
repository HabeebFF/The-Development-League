"""Players ask to join their team from My account; the manager (or staff, when the team has
no manager) accepts or rejects. Only accounts linked to a game UID can ask."""

import pytest

from apps.accounts.models import JoinRequest, Membership
from apps.predictions.models import Bet
from apps.predictions.services import wallet_for

from .test_player_rules import _on, bet, booyah, lg, staff  # noqa: F401
from .test_settlement import as_user, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def ace(lg):  # noqa: F811
    """An account linked to Ace, who plays for Alpha in the logs."""
    user = make_user("ace@tdl.test")
    player = lg["players"]["Ace"]
    player.user = user
    player.save(update_fields=["user"])
    return user


@pytest.fixture
def boss(lg):  # noqa: F811
    user = make_user("boss@tdl.test")
    Membership.objects.create(user=user, team=lg["teams"]["Alpha"], role=Membership.Role.MANAGER)
    return user


def ask(user, team="alpha", note=""):
    return as_user(user).post("/api/v1/me/join-team", {"team": team, "note": note}, format="json")


def test_suggests_the_team_from_the_logs(lg, ace):  # noqa: F811
    body = as_user(ace).get("/api/v1/me/join-team").json()
    assert body["suggested"]["slug"] == "alpha"
    assert "guest" not in [t["slug"] for t in body["teams"]]  # league teams only
    assert body["request"] is None and body["on_team"] is None


def test_only_linked_players_can_ask(lg):  # noqa: F811
    res = ask(make_user("fan@tdl.test"))
    assert res.status_code == 400 and "UID" in str(res.json())


def test_manager_accepts_and_refunds_open_bets_on_the_team(lg, staff, ace, boss):  # noqa: F811
    # Ace's account isn't on Alpha yet (only linked); picture an older bet on Bravo winning.
    m = booyah(lg, staff)
    on_bravo = bet(ace, m, "Bravo", stake=40)
    res = ask(ace, note="Ace here")
    assert res.status_code == 201, res.content
    assert res.json()["player"]["matches_for_team"] == 0
    assert res.json()["player"]["name"] == "Ace"

    waiting = as_user(boss).get("/api/v1/teams/alpha/join-requests").json()
    rows = waiting["results"] if isinstance(waiting, dict) else waiting
    assert [r["note"] for r in rows] == ["Ace here"]
    rid = rows[0]["id"]
    assert as_user(ace).post(f"/api/v1/teams/alpha/join-requests/{rid}/accept").status_code == 403

    done = as_user(boss).post(f"/api/v1/teams/alpha/join-requests/{rid}/accept")
    assert done.status_code == 200, done.content
    assert done.json()["status"] == "ACCEPTED"
    assert Membership.objects.get(user=ace, team=lg["teams"]["Alpha"]).role == "PLAYER"
    on_bravo.refresh_from_db()
    assert on_bravo.status == Bet.Status.PENDING  # not about their team
    again = as_user(boss).post(f"/api/v1/teams/alpha/join-requests/{rid}/reject")
    assert again.status_code == 404  # no longer waiting


def test_accepting_refunds_a_bet_on_the_new_team(lg, staff, boss):  # noqa: F811
    free = make_user("free@tdl.test")  # linked to Free, who has no team in the logs
    player = lg["players"]["Free"]
    player.user = free
    player.save(update_fields=["user"])
    m = booyah(lg, staff)
    on_alpha = bet(free, m, "Alpha", stake=70)
    balance = wallet_for(free).balance
    rid = ask(free).json()["id"]
    done = as_user(boss).post(f"/api/v1/teams/alpha/join-requests/{rid}/accept").json()
    assert done["voided_bets"] == 1
    on_alpha.refresh_from_db()
    assert on_alpha.status == Bet.Status.VOID and wallet_for(free).balance == balance + 70


def test_reject_cancel_and_ask_again(lg, ace, boss):  # noqa: F811
    rid = ask(ace).json()["id"]
    assert as_user(boss).post(f"/api/v1/teams/alpha/join-requests/{rid}/reject").status_code == 200
    assert as_user(ace).get("/api/v1/me/join-team").json()["request"]["status"] == "REJECTED"
    assert not Membership.objects.filter(user=ace).exists()

    second = ask(ace, team="bravo").json()["id"]
    third = ask(ace).json()["id"]  # a new ask replaces the waiting one
    assert JoinRequest.objects.get(pk=second).status == "CANCELLED"
    assert as_user(ace).delete("/api/v1/me/join-team").status_code == 204
    assert JoinRequest.objects.get(pk=third).status == "CANCELLED"
    assert as_user(ace).delete("/api/v1/me/join-team").status_code == 400


def test_other_teams_managers_cant_see_requests(lg, ace, boss):  # noqa: F811
    ask(ace, team="bravo")
    assert as_user(boss).get("/api/v1/teams/bravo/join-requests").status_code == 403
    rows = as_user(boss).get("/api/v1/teams/alpha/join-requests").json()
    assert (rows["results"] if isinstance(rows, dict) else rows) == []


def test_staff_answer_teams_without_a_manager(lg, staff, ace, boss):  # noqa: F811
    ask(ace, team="bravo")  # Bravo has no manager
    other = make_user("x@tdl.test")
    lg["players"]["Ash"].user = other
    lg["players"]["Ash"].save(update_fields=["user"])
    ask(other, team="alpha")  # Alpha has one
    assert as_user(boss).get("/api/v1/admin/join-requests").status_code == 403
    rows = as_user(staff).get("/api/v1/admin/join-requests?unmanaged=1").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert [r["team"]["slug"] for r in rows] == ["bravo"]
    assert rows[0]["team_has_manager"] is False
    rid = rows[0]["id"]
    res = as_user(staff).post(f"/api/v1/teams/bravo/join-requests/{rid}/accept")
    assert res.status_code == 200, res.content
    assert Membership.objects.filter(user=ace, team=lg["teams"]["Bravo"], is_active=True).exists()


def test_already_on_a_team(lg, ace, boss):  # noqa: F811
    Membership.objects.create(user=ace, team=lg["teams"]["Alpha"])
    res = ask(ace)
    assert res.status_code == 400 and "already on Alpha" in str(res.json())
    res = ask(ace, team="bravo")
    assert res.status_code == 400 and "remove you first" in str(res.json())
    assert as_user(ace).get("/api/v1/me/join-team").json()["on_team"]["slug"] == "alpha"
