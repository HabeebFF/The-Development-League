"""Accounts: sign-in cookies, CSRF, /me, invites, members, UID claims, staff, features."""

from __future__ import annotations

import re

import pytest
from django.core import mail
from django.urls import get_resolver
from rest_framework.test import APIClient

from apps.accounts.models import Invite, Membership, Plan, PlayerClaim, StaffProfile, User
from apps.league.models import Player, Team

pytestmark = pytest.mark.django_db
PASSWORD = "a-Long-password-42"


@pytest.fixture(autouse=True)
def _no_throttle(settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"login": None, "password_reset": None, "invite_accept": None},
    }


def make_user(email: str, **extra) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, **extra)


def as_user(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def team() -> Team:
    return Team.objects.create(name="NOOBZ ESPORTS", tag="NB")


@pytest.fixture
def superadmin() -> User:
    return User.objects.create_superuser(email="habeeb@tdl.test", password=PASSWORD)


@pytest.fixture
def staff() -> User:
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user, role=StaffProfile.Role.ANALYST)
    return user


@pytest.fixture
def manager(team) -> User:
    user = make_user("manager@tdl.test")
    Membership.objects.create(user=user, team=team, role=Membership.Role.MANAGER)
    return user


# -- sign-in ----------------------------------------------------------------------------------


def csrf_client() -> tuple[APIClient, str]:
    client = APIClient(enforce_csrf_checks=True)
    resp = client.get("/api/v1/auth/csrf")
    assert resp.status_code == 204
    return client, resp.cookies["csrftoken"].value


def test_login_sets_httponly_cookies_and_me_works():
    make_user("Player@TDL.test", display_name="VALSI")
    client, csrf = csrf_client()
    resp = client.post(
        "/api/v1/auth/login",
        {"email": "player@tdl.test", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["email"] == "player@tdl.test"
    access = resp.cookies["tdl_access"]
    assert access["httponly"] and resp.cookies["tdl_refresh"]["path"] == "/api/v1/auth/"
    assert client.get("/api/v1/me").json()["display_name"] == "VALSI"


def test_login_needs_csrf_and_right_password():
    make_user("p@tdl.test")
    client, csrf = csrf_client()
    no_csrf = client.post("/api/v1/auth/login", {"email": "p@tdl.test", "password": PASSWORD})
    assert no_csrf.status_code == 403
    wrong = client.post(
        "/api/v1/auth/login",
        {"email": "p@tdl.test", "password": "nope"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert wrong.status_code == 400


def test_cookie_auth_requires_csrf_on_writes():
    make_user("p@tdl.test")
    client, csrf = csrf_client()
    client.post(
        "/api/v1/auth/login",
        {"email": "p@tdl.test", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert client.patch("/api/v1/me", {"display_name": "x"}, format="json").status_code == 403
    ok = client.patch("/api/v1/me", {"display_name": "x"}, format="json", HTTP_X_CSRFTOKEN=csrf)
    assert ok.status_code == 200


def test_refresh_rotates_and_logout_revokes():
    make_user("p@tdl.test")
    client, csrf = csrf_client()
    client.post(
        "/api/v1/auth/login",
        {"email": "p@tdl.test", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    first_refresh = client.cookies["tdl_refresh"].value
    resp = client.post("/api/v1/auth/refresh", HTTP_X_CSRFTOKEN=csrf)
    assert resp.status_code == 204
    assert client.cookies["tdl_refresh"].value != first_refresh

    # The old refresh token is dead after rotation.
    replay = APIClient(enforce_csrf_checks=True)
    replay.cookies["tdl_refresh"] = first_refresh
    replay.cookies["csrftoken"] = csrf
    assert replay.post("/api/v1/auth/refresh", HTTP_X_CSRFTOKEN=csrf).status_code == 401

    current = client.cookies["tdl_refresh"].value
    assert client.post("/api/v1/auth/logout", HTTP_X_CSRFTOKEN=csrf).status_code == 204
    again = APIClient(enforce_csrf_checks=True)
    again.cookies["tdl_refresh"] = current
    again.cookies["csrftoken"] = csrf
    assert again.post("/api/v1/auth/refresh", HTTP_X_CSRFTOKEN=csrf).status_code == 401


def test_password_reset_flow():
    user = make_user("p@tdl.test")
    client = APIClient()
    assert (
        client.post("/api/v1/auth/password-reset", {"email": "nobody@tdl.test"}).status_code == 204
    )
    assert len(mail.outbox) == 0
    assert client.post("/api/v1/auth/password-reset", {"email": "P@tdl.test"}).status_code == 204
    link = re.search(r"uid=(\S+)&token=(\S+)", mail.outbox[0].body)
    uid, token = link.group(1), link.group(2)

    weak = client.post(
        "/api/v1/auth/password-reset/confirm",
        {"uid": uid, "token": token, "new_password": "123"},
    )
    assert weak.status_code == 400
    resp = client.post(
        "/api/v1/auth/password-reset/confirm",
        {"uid": uid, "token": token, "new_password": "Another-long-pass-7"},
    )
    assert resp.status_code == 204
    user.refresh_from_db()
    assert user.check_password("Another-long-pass-7")
    reuse = client.post(
        "/api/v1/auth/password-reset/confirm",
        {"uid": uid, "token": token, "new_password": "Third-long-pass-8"},
    )
    assert reuse.status_code == 400


# -- me, roles and features -------------------------------------------------------------------


def test_me_shows_roles_memberships_and_features(team, manager, staff, superadmin):
    me = as_user(manager).get("/api/v1/me").json()
    assert me["staff_role"] is None
    assert me["memberships"][0]["team"]["slug"] == team.slug
    assert me["memberships"][0]["role"] == "MANAGER"
    assert "rotations.view" in me["features"]

    assert as_user(staff).get("/api/v1/me").json()["staff_role"] == "ANALYST"
    admin = as_user(superadmin).get("/api/v1/me").json()
    assert admin["staff_role"] == "SUPER_ADMIN" and admin["is_super_admin"]

    outsider = make_user("x@tdl.test")
    assert as_user(outsider).get("/api/v1/me").json()["features"] == []


def test_new_league_teams_get_the_league_plan():
    team = Team.objects.create(name="SAGE UNITED")
    assert team.plan.code == Plan.LEAGUE_TEAM
    outside = Team.objects.create(name="Guest", is_league_member=False)
    assert outside.plan is None


def test_feature_gating_follows_the_plan(team, manager):
    assert manager.has_feature("zone_analysis")
    basic = Plan.objects.create(code="external_basic", name="Basic")
    team.plan = basic
    team.save()
    assert not manager.has_feature("zone_analysis")


# -- invites ----------------------------------------------------------------------------------


def test_manager_invites_player_who_signs_up(team, manager, django_capture_on_commit_callbacks):
    client = as_user(manager)
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            f"/api/v1/teams/{team.slug}/invites", {"email": "New@Player.test"}, format="json"
        )
    assert resp.status_code == 201, resp.content
    token = Invite.objects.get().token
    assert token in mail.outbox[0].body

    anon = APIClient()
    info = anon.get(f"/api/v1/invites/{token}").json()
    assert info["team"]["name"] == team.name and info["account_exists"] is False

    missing_pw = anon.post(f"/api/v1/invites/{token}", {}, format="json")
    assert missing_pw.status_code == 400
    resp = anon.post(
        f"/api/v1/invites/{token}",
        {"password": PASSWORD, "display_name": "Jay"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert "tdl_access" in resp.cookies
    user = User.objects.get(email="new@player.test")
    assert Membership.objects.get(user=user).role == "PLAYER"
    assert anon.post(f"/api/v1/invites/{token}", {"password": PASSWORD}).status_code == 400


def test_existing_account_accepts_while_signed_in(team, manager):
    existing = make_user("old@tdl.test")
    invite = Invite.objects.create(team=team, email="old@tdl.test", invited_by=manager)
    assert (
        APIClient().post(f"/api/v1/invites/{invite.token}", {"password": PASSWORD}).status_code
        == 400
    )
    other = make_user("other@tdl.test")
    assert as_user(other).post(f"/api/v1/invites/{invite.token}").status_code == 403
    resp = as_user(existing).post(f"/api/v1/invites/{invite.token}")
    assert resp.status_code == 200
    assert resp.json()["memberships"][0]["team"]["slug"] == team.slug


def test_only_staff_invite_managers_and_revoke(team, manager, staff):
    resp = as_user(manager).post(
        f"/api/v1/teams/{team.slug}/invites",
        {"email": "boss@tdl.test", "role": "MANAGER"},
        format="json",
    )
    assert resp.status_code == 400
    resp = as_user(staff).post(
        f"/api/v1/teams/{team.slug}/invites",
        {"email": "boss@tdl.test", "role": "MANAGER"},
        format="json",
    )
    assert resp.status_code == 201
    invite_id = resp.json()["id"]
    assert (
        as_user(manager).delete(f"/api/v1/teams/{team.slug}/invites/{invite_id}").status_code == 204
    )
    assert not Invite.objects.get(pk=invite_id).is_open


def test_players_and_outsiders_cannot_invite(team):
    player = make_user("pl@tdl.test")
    Membership.objects.create(user=player, team=team)
    other_team = Team.objects.create(name="Cliq")
    other_manager = make_user("om@tdl.test")
    Membership.objects.create(user=other_manager, team=other_team, role="MANAGER")
    for user in (player, other_manager):
        resp = as_user(user).post(
            f"/api/v1/teams/{team.slug}/invites", {"email": "a@b.test"}, format="json"
        )
        assert resp.status_code == 403


# -- members ----------------------------------------------------------------------------------


def test_members_list_and_last_manager_guard(team, manager, staff):
    player = make_user("pl@tdl.test")
    pm = Membership.objects.create(user=player, team=team)
    assert len(as_user(player).get(f"/api/v1/teams/{team.slug}/members").json()["results"]) == 2
    assert as_user(player).delete(f"/api/v1/teams/{team.slug}/members/{pm.pk}").status_code == 403

    own = Membership.objects.get(user=manager)
    resp = as_user(manager).delete(f"/api/v1/teams/{team.slug}/members/{own.pk}")
    assert resp.status_code == 400  # last manager

    promote = as_user(manager).patch(
        f"/api/v1/teams/{team.slug}/members/{pm.pk}", {"role": "MANAGER"}, format="json"
    )
    assert promote.status_code == 400  # only staff promote
    assert (
        as_user(staff)
        .patch(f"/api/v1/teams/{team.slug}/members/{pm.pk}", {"role": "MANAGER"}, format="json")
        .status_code
        == 200
    )
    assert as_user(manager).delete(f"/api/v1/teams/{team.slug}/members/{own.pk}").status_code == 204
    own.refresh_from_db()
    assert own.is_active is False
    assert as_user(manager).get("/api/v1/me").json()["memberships"] == []


# -- game UID claims --------------------------------------------------------------------------


def test_uid_claim_approved_by_staff(staff, team):
    Player.objects.create(
        game_uid=2063288734,
        current_name_raw="NBㅤVALSI",
        display_name="NB VALSI",
        search_name="nb valsi",
    )
    user = make_user("valsi@tdl.test")
    resp = as_user(user).post("/api/v1/me/link-uid", {"game_uid": "2063288734"}, format="json")
    assert resp.status_code == 201
    assert as_user(user).get("/api/v1/me").json()["pending_uid_claim"] == "2063288734"
    assert as_user(user).get("/api/v1/admin/player-claims").status_code == 403

    claims = as_user(staff).get("/api/v1/admin/player-claims?status=PENDING").json()["results"]
    assert claims[0]["player_name"] == "NB VALSI"
    approve = as_user(staff).post(f"/api/v1/admin/player-claims/{claims[0]['id']}/approve")
    assert approve.status_code == 200
    me = as_user(user).get("/api/v1/me").json()
    assert me["player"] == {"game_uid": "2063288734", "display_name": "NB VALSI"}

    thief = make_user("thief@tdl.test")
    taken = as_user(thief).post("/api/v1/me/link-uid", {"game_uid": "2063288734"}, format="json")
    assert taken.status_code == 400


def test_uid_claim_for_unknown_player_creates_one(staff):
    user = make_user("new@tdl.test", display_name="Newbie")
    as_user(user).post("/api/v1/me/link-uid", {"game_uid": "123456789"}, format="json")
    claim = PlayerClaim.objects.get()
    as_user(staff).post(f"/api/v1/admin/player-claims/{claim.pk}/approve")
    assert Player.objects.get(game_uid=123456789).user == user
    assert as_user(staff).post(f"/api/v1/admin/player-claims/{claim.pk}/reject").status_code == 400


# -- staff management -------------------------------------------------------------------------


def test_only_super_admin_manages_staff(superadmin, staff):
    target = make_user("analyst@tdl.test")
    assert as_user(staff).get("/api/v1/admin/staff").status_code == 403
    resp = as_user(superadmin).post(
        "/api/v1/admin/staff", {"email": "Analyst@tdl.test", "role": "ANALYST"}, format="json"
    )
    assert resp.status_code == 201, resp.content
    assert target.is_league_staff
    profile_id = resp.json()["id"]
    assert as_user(superadmin).delete(f"/api/v1/admin/staff/{profile_id}").status_code == 204
    assert not User.objects.get(pk=target.pk).is_league_staff


# -- every endpoint declares its permissions --------------------------------------------------


def test_every_api_view_declares_permission_classes():
    missing = []

    def walk(patterns, prefix=""):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                walk(p.url_patterns, prefix + str(p.pattern))
                continue
            view = getattr(p.callback, "cls", None)
            if view is None or not (prefix + str(p.pattern)).startswith("api/"):
                continue
            declared = any(
                "permission_classes" in vars(k)
                for k in view.__mro__[:-1]
                if k.__module__.startswith(("apps.", "common."))
            )
            if not declared:
                missing.append(prefix + str(p.pattern))

    walk(get_resolver().url_patterns)
    assert missing == []
