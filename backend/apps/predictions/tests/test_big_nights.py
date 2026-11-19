"""Big nights (a tournament final): sessions with 6 matches, and no stake cap on singles."""

import datetime as dt
import uuid

import pytest
from django.core.cache import cache

from apps.predictions import auto, autosettle
from apps.predictions.markets import MarketError, place_bet
from apps.predictions.models import AutoSettings, Fixture, Market
from apps.predictions.multiples import place_multiple
from apps.predictions.services import wallet_for
from apps.results.standings import rebuild_season

from .test_auto import lg, next_weekday  # noqa: F401  (fixture)
from .test_autosettle import (  # noqa: F401  (fixtures)
    _on,
    bet,
    close,
    fans,
    fresh,
    market,
    night,
    staff,
    upload,
)
from .test_settlement import as_user

pytestmark = pytest.mark.django_db
S, C = Market.Status, Market.Category


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def set_conf(**fields):
    AutoSettings.objects.update_or_create(pk=1, defaults=fields)
    cache.clear()


def key(date, session):
    return f"{date.isoformat()} {session}"


def test_a_six_match_night_gets_six_matches_of_markets(lg):  # noqa: F811
    date = next_weekday(2)
    set_conf(long_sessions={key(date, "10PM"): 6})
    auto.run(date)
    assert Fixture.objects.filter(date=date, session="10PM").count() == 7  # 6 + the session
    assert Fixture.objects.filter(date=date, session="8PM").count() == 6  # 5 as usual
    ten = Market.objects.filter(fixture__date=date, fixture__session="10PM")
    assert ten.filter(category=C.BOOYAH).count() == 6


def test_session_markets_wait_for_the_sixth_match(night, staff, fans):  # noqa: F811
    t = night["teams"]
    set_conf(long_sessions={key(night["date"], "8PM"): 6})
    m = market(night, staff, C.SESSION_WINNER, number=None)
    bet(fans[0], m, t["Alpha"])
    close(m)
    for n in range(1, 6):
        upload(night, n)
    rebuild_season(night["season"])
    autosettle.run()
    assert fresh(m).status == S.CLOSED  # 5 of 6: still waiting
    upload(night, 6)
    rebuild_season(night["season"])
    autosettle.run()
    assert fresh(m).status == S.SETTLED


def test_an_uncapped_night_takes_big_single_predictions(night, staff, fans, settings):  # noqa: F811
    settings.PREDICTIONS_MAX_STAKE = 500  # only matters when a cap is switched back on
    t = night["teams"]
    m = market(night, staff, C.BOOYAH, number=1)
    fan = fans[0]
    wallet = wallet_for(fan)
    wallet.balance = 5000
    wallet.save(update_fields=["balance"])
    outcome = m.outcomes.get(team=t["Alpha"])

    def stake(n):
        return place_bet(
            fan, market_id=m.pk, outcome_id=outcome.pk, stake=n, client_key=uuid.uuid4()
        )

    with pytest.raises(MarketError):
        stake(501)  # capped as usual
    set_conf(uncapped_sessions=[key(night["date"], "8PM")])
    stake(2000)
    stake(1500)  # no 500 total per choice either
    with pytest.raises(MarketError):
        stake(5000)  # but never more than the wallet
    assert wallet_for(fan).balance == 5000 - 3500


def test_multiples_keep_the_cap_on_uncapped_nights(night, staff, fans, settings):  # noqa: F811
    settings.PREDICTIONS_MAX_STAKE = 500
    t = night["teams"]
    set_conf(uncapped_sessions=[key(night["date"], "8PM")])
    a = market(night, staff, C.BOOYAH, number=1)
    b = market(night, staff, C.BOOYAH, number=2)
    picks = [
        {"market": a.pk, "outcome": a.outcomes.get(team=t["Alpha"]).pk},
        {"market": b.pk, "outcome": b.outcomes.get(team=t["Alpha"]).pk},
    ]
    with pytest.raises(MarketError):
        place_multiple(fans[0], picks=picks, stake=600, client_key=uuid.uuid4())


def test_markets_say_their_stake_cap(night, staff, fans, settings):  # noqa: F811
    m = market(night, staff, C.BOOYAH, number=1)
    client = as_user(fans[0])
    # No cap by default.
    assert client.get(f"/api/v1/predictions/markets/{m.pk}").json()["max_stake"] is None
    settings.PREDICTIONS_MAX_STAKE = 500
    assert client.get(f"/api/v1/predictions/markets/{m.pk}").json()["max_stake"] == 500
    set_conf(uncapped_sessions=[key(night["date"], "8PM")])
    assert client.get(f"/api/v1/predictions/markets/{m.pk}").json()["max_stake"] is None


def test_staff_set_big_nights(night, staff):  # noqa: F811
    client = as_user(staff)
    day = (auto.today() + dt.timedelta(days=1)).isoformat()
    res = client.patch(
        "/api/v1/admin/predictions/auto",
        {
            "long_sessions": {f"{day} 10PM": 6, "2001-01-01 10PM": 6},
            "uncapped_sessions": [f"{day} 10PM", f"{day} 10PM"],
        },
        format="json",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["long_sessions"] == {f"{day} 10PM": 6}  # old nights dropped
    assert body["uncapped_sessions"] == [f"{day} 10PM"]
    for bad in (
        {"long_sessions": {f"{day} 9PM": 6}},
        {"long_sessions": {f"{day} 10PM": 40}},
        {"uncapped_sessions": ["tomorrow 10PM"]},
    ):
        assert client.patch("/api/v1/admin/predictions/auto", bad, format="json").status_code == 400
