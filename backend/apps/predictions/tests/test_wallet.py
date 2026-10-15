"""Virtual coins: starting coins, the ledger, locking, retries, staff adjustments and sign-up."""

import threading
import uuid

import pytest
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import StaffProfile, User
from apps.accounts.views import SignupView
from apps.predictions.models import LedgerEntry, Wallet
from apps.predictions.services import (
    CoinError,
    KeyReused,
    Kind,
    NotEnoughCoins,
    check_wallet,
    check_wallets,
    post_entry,
    wallet_for,
)

pytestmark = pytest.mark.django_db
PASSWORD = "a-Long-password-42"


@pytest.fixture(autouse=True)
def _on(settings, monkeypatch):
    settings.PREDICTIONS_ENABLED = True
    settings.PUBLIC_SIGNUP = True
    monkeypatch.setattr(SignupView, "throttle_classes", [])


def make_user(email: str = "fan@tdl.test", **extra) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, **extra)


def as_user(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def fan() -> User:
    return make_user()


@pytest.fixture
def staff() -> User:
    user = make_user("staff@tdl.test")
    StaffProfile.objects.create(user=user)
    return user


@pytest.fixture
def superadmin() -> User:
    return User.objects.create_superuser(email="habeeb@tdl.test", password=PASSWORD)


# -- starting coins ------------------------------------------------------------------------------


def test_new_wallet_gets_exactly_1000_once(fan):
    wallet = wallet_for(fan)
    assert wallet.balance == 1000
    again = wallet_for(fan)
    assert again.pk == wallet.pk and again.balance == 1000
    assert LedgerEntry.objects.filter(wallet=wallet, kind=Kind.INITIAL).count() == 1
    # Even a direct second attempt at the starting coins is refused by its key.
    entry, created = post_entry(wallet, Kind.INITIAL, 1000, f"initial:{wallet.pk}")
    assert not created
    wallet.refresh_from_db()
    assert wallet.balance == 1000 and check_wallet(wallet) == []


def test_wallet_api_creates_wallet_once(fan):
    client = as_user(fan)
    for _ in range(3):
        resp = client.get("/api/v1/predictions/wallet")
        assert resp.status_code == 200
        assert resp.json()["balance"] == 1000
    assert Wallet.objects.filter(user=fan).count() == 1
    entries = client.get("/api/v1/predictions/wallet/entries").json()
    assert entries["count"] == 1 and entries["results"][0]["kind"] == "INITIAL"


def test_starting_coins_follow_setting(fan, settings):
    settings.PREDICTIONS_INITIAL_COINS = 250
    assert wallet_for(fan).balance == 250


# -- the ledger ----------------------------------------------------------------------------------


def test_stake_deducts_and_is_recorded(fan):
    wallet = wallet_for(fan)
    entry, created = post_entry(wallet, Kind.STAKE, -100, "stake:test-1")
    assert created
    assert (entry.balance_before, entry.balance_after, entry.seq) == (1000, 900, 2)
    wallet.refresh_from_db()
    assert wallet.balance == 900


def test_cannot_spend_more_than_balance(fan):
    wallet = wallet_for(fan)
    with pytest.raises(NotEnoughCoins):
        post_entry(wallet, Kind.STAKE, -1001, "stake:too-much")
    wallet.refresh_from_db()
    assert wallet.balance == 1000
    assert not LedgerEntry.objects.filter(idempotency_key="stake:too-much").exists()


def test_retry_with_same_key_changes_nothing(fan):
    wallet = wallet_for(fan)
    first, _ = post_entry(wallet, Kind.PAYOUT, 250, "payout:bet-1:v1")
    second, created = post_entry(wallet, Kind.PAYOUT, 250, "payout:bet-1:v1")
    assert not created and second.pk == first.pk
    wallet.refresh_from_db()
    assert wallet.balance == 1250


def test_reusing_a_key_for_something_else_is_refused(fan):
    wallet = wallet_for(fan)
    post_entry(wallet, Kind.PAYOUT, 250, "payout:bet-2:v1")
    with pytest.raises(KeyReused):
        post_entry(wallet, Kind.PAYOUT, 999, "payout:bet-2:v1")


@pytest.mark.parametrize("amount", [0, 1.5, True])
def test_amount_must_be_whole_and_not_zero(fan, amount):
    with pytest.raises(CoinError):
        post_entry(wallet_for(fan), Kind.ADJUSTMENT, amount, f"adjust:{amount}")


def test_failed_operation_leaves_nothing_behind(fan):
    wallet = wallet_for(fan)
    with pytest.raises(RuntimeError), transaction.atomic():
        post_entry(wallet, Kind.STAKE, -300, "stake:rolled-back")
        raise RuntimeError("the bet could not be saved")
    wallet.refresh_from_db()
    assert wallet.balance == 1000
    assert not LedgerEntry.objects.filter(idempotency_key="stake:rolled-back").exists()
    assert check_wallet(wallet) == []


def test_database_refuses_negative_balance(fan):
    wallet = wallet_for(fan)
    with pytest.raises(IntegrityError), transaction.atomic():
        Wallet.objects.filter(pk=wallet.pk).update(balance=-1)


def test_database_refuses_entry_that_does_not_add_up(fan):
    wallet = wallet_for(fan)
    with pytest.raises(IntegrityError), transaction.atomic():
        LedgerEntry.objects.create(
            wallet=wallet,
            seq=2,
            kind=Kind.ADJUSTMENT,
            amount=10,
            balance_before=1000,
            balance_after=5000,
            idempotency_key="bad",
        )


def test_check_finds_a_balance_changed_behind_the_ledger(fan):
    wallet = wallet_for(fan)
    post_entry(wallet, Kind.STAKE, -100, "stake:x")
    assert check_wallets() == []
    Wallet.objects.filter(pk=wallet.pk).update(balance=5000)
    problems = check_wallets()
    assert len(problems) == 1 and "ledger adds up to 900" in problems[0].problem


def test_balance_always_matches_ledger_after_many_moves(fan):
    wallet = wallet_for(fan)
    for n, amount in enumerate([-100, -50, 400, -10, 25, -1265]):
        kind = Kind.STAKE if amount < 0 else Kind.PAYOUT
        post_entry(wallet, kind, amount, f"move:{n}")
    wallet.refresh_from_db()
    assert wallet.balance == 0
    assert check_wallet(wallet) == []


# -- two requests at once ------------------------------------------------------------------------


def _at_once(n: int, work) -> list:
    """Run ``work(i)`` in ``n`` threads released together; each thread has its own connection."""
    barrier = threading.Barrier(n)
    results: list = [None] * n

    def run(i):
        try:
            barrier.wait()
            results[i] = work(i)
        except Exception as exc:  # noqa: BLE001 - the test inspects what each thread got
            results[i] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


@pytest.mark.django_db(transaction=True)
def test_simultaneous_stakes_cannot_spend_the_same_coins():
    wallet = wallet_for(make_user("racer@tdl.test"))
    results = _at_once(10, lambda i: post_entry(wallet.pk, Kind.STAKE, -200, f"stake:race-{i}"))
    ok = [r for r in results if isinstance(r, tuple)]
    refused = [r for r in results if isinstance(r, NotEnoughCoins)]
    assert len(ok) == 5 and len(refused) == 5, results
    wallet.refresh_from_db()
    assert wallet.balance == 0
    assert check_wallet(wallet) == []


@pytest.mark.django_db(transaction=True)
def test_simultaneous_retries_pay_once():
    wallet = wallet_for(make_user("retry@tdl.test"))
    results = _at_once(8, lambda i: post_entry(wallet.pk, Kind.PAYOUT, 250, "payout:race:v1"))
    created = [r for r in results if isinstance(r, tuple) and r[1]]
    assert len(created) == 1, results
    assert all(isinstance(r, tuple) for r in results), results
    wallet.refresh_from_db()
    assert wallet.balance == 1250


@pytest.mark.django_db(transaction=True)
def test_simultaneous_first_visits_give_starting_coins_once():
    user = make_user("first@tdl.test")
    results = _at_once(6, lambda i: wallet_for(user).pk)
    assert len(set(results)) == 1, results
    wallet = Wallet.objects.get(user=user)
    assert wallet.balance == 1000
    assert wallet.entries.filter(kind=Kind.INITIAL).count() == 1


# -- who can see and change what -----------------------------------------------------------------


def test_wallet_needs_sign_in_and_is_hidden_when_off(fan, settings):
    assert APIClient().get("/api/v1/predictions/wallet").status_code in (401, 403)
    settings.PREDICTIONS_ENABLED = False
    assert as_user(fan).get("/api/v1/predictions/wallet").status_code == 404


def test_staff_cannot_play(staff):
    resp = as_user(staff).get("/api/v1/predictions/wallet")
    assert resp.status_code == 403
    assert not Wallet.objects.filter(user=staff).exists()


def test_users_cannot_change_their_balance_through_the_api(fan):
    client = as_user(fan)
    client.get("/api/v1/predictions/wallet")
    for method in (client.post, client.put, client.patch):
        resp = method("/api/v1/predictions/wallet", {"balance": 99999}, format="json")
        assert resp.status_code == 405
    assert (
        client.post(
            "/api/v1/predictions/wallet/entries", {"amount": 500}, format="json"
        ).status_code
        == 405
    )
    assert Wallet.objects.get(user=fan).balance == 1000


def test_users_only_see_their_own_entries(fan):
    other = make_user("other@tdl.test")
    post_entry(wallet_for(other), Kind.STAKE, -400, "stake:other")
    mine = as_user(fan).get("/api/v1/predictions/wallet/entries").json()
    assert [e["amount"] for e in mine["results"]] == [1000]


def test_only_super_admin_can_adjust(fan, staff, superadmin):
    wallet = wallet_for(fan)
    url = f"/api/v1/admin/predictions/wallets/{wallet.pk}/adjust"
    body = {"amount": 50, "reason": "Refund for a site bug", "key": str(uuid.uuid4())}
    assert as_user(fan).post(url, body, format="json").status_code == 403
    assert as_user(staff).post(url, body, format="json").status_code == 403
    wallet.refresh_from_db()
    assert wallet.balance == 1000

    resp = as_user(superadmin).post(url, body, format="json")
    assert resp.status_code == 201, resp.content
    assert resp.json()["actor"] == "habeeb@tdl.test"
    again = as_user(superadmin).post(url, body, format="json")
    assert again.status_code == 200 and again.json()["id"] == resp.json()["id"]
    wallet.refresh_from_db()
    assert wallet.balance == 1050
    entry = wallet.entries.get(kind=Kind.ADJUSTMENT)
    assert entry.reason == "Refund for a site bug" and entry.actor == superadmin


def test_adjustment_needs_reason_and_cannot_go_below_zero(fan, superadmin):
    wallet = wallet_for(fan)
    url = f"/api/v1/admin/predictions/wallets/{wallet.pk}/adjust"
    client = as_user(superadmin)
    no_reason = client.post(url, {"amount": 5, "key": str(uuid.uuid4())}, format="json")
    assert no_reason.status_code == 400
    too_much = client.post(
        url, {"amount": -5000, "reason": "Take back", "key": str(uuid.uuid4())}, format="json"
    )
    assert too_much.status_code == 400
    wallet.refresh_from_db()
    assert wallet.balance == 1000


def test_staff_can_list_wallets_but_players_cannot(fan, staff):
    wallet_for(fan)
    assert as_user(fan).get("/api/v1/admin/predictions/wallets").status_code == 403
    resp = as_user(staff).get("/api/v1/admin/predictions/wallets?search=fan")
    assert resp.status_code == 200
    assert [w["email"] for w in resp.json()["results"]] == ["fan@tdl.test"]


# -- sign-up -------------------------------------------------------------------------------------


def _signup(client, **body):
    data = {"email": "New@Fan.test", "password": PASSWORD, "display_name": "Blaze"} | body
    return client.post("/api/v1/auth/signup", data, format="json")


def test_signup_creates_a_plain_account_and_signs_in():
    client = APIClient()
    resp = _signup(client)
    assert resp.status_code == 201, resp.content
    assert resp.cookies["tdl_access"]["httponly"]
    user = User.objects.get(email="new@fan.test")
    assert user.display_name == "Blaze"
    assert not user.is_staff and not user.is_superuser and not user.memberships.exists()
    # No coins until the wallet is opened; then exactly the starting coins.
    assert not Wallet.objects.filter(user=user).exists()
    assert client.get("/api/v1/predictions/wallet").json()["balance"] == 1000


def test_signup_refuses_taken_email_name_and_weak_password(fan):
    make_user("named@tdl.test", display_name="Echo")
    client = APIClient()
    assert _signup(client, email="FAN@tdl.test").status_code == 400
    assert _signup(client, display_name="echo").status_code == 400
    assert _signup(client, password="123").status_code == 400
    assert User.objects.count() == 2


def test_signup_is_off_unless_switched_on(settings):
    settings.PUBLIC_SIGNUP = False
    assert _signup(APIClient()).status_code == 404
    assert not User.objects.filter(email="new@fan.test").exists()


def test_signup_needs_csrf():
    client = APIClient(enforce_csrf_checks=True)
    assert _signup(client).status_code == 403


def test_signup_is_throttled(monkeypatch):
    monkeypatch.setattr(SignupView, "throttle_classes", [ScopedRateThrottle])
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"signup": "2/hour"})
    cache.clear()
    codes = [
        _signup(APIClient(), email=f"f{i}@tdl.test", display_name=f"Fan {i}").status_code
        for i in range(3)
    ]
    cache.clear()
    assert codes == [201, 201, 429]


def test_site_reports_switches(settings):
    settings.PUBLIC_SIGNUP = False
    resp = APIClient().get("/api/v1/site").json()
    assert resp["signup"] is False and resp["predictions"] is True
