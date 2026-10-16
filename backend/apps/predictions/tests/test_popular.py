"""Popular markets: prediction counts on every market and the most-predicted list."""

import uuid

import pytest

from apps.predictions.markets import place_bet

from .test_multiples import fan, lg, market, pick, place, staff  # noqa: F401  (fixtures)
from .test_settlement import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _on(settings):
    settings.PREDICTIONS_ENABLED = True


def test_counts_singles_and_multiple_picks(client, lg, staff, fan):  # noqa: F811
    quiet, busy, some = market(lg, staff, "m1"), market(lg, staff, "sat"), market(lg, staff, None)
    others = [make_user(f"p{i}@tdl.test") for i in range(3)]
    for user in others:
        o = busy.outcomes.first()
        place_bet(user, market_id=busy.pk, outcome_id=o.pk, stake=10, client_key=uuid.uuid4())
    place(fan, [pick(busy, "Alpha"), pick(some, "Bravo")])
    rows = client.get("/api/v1/predictions/markets").json()["results"]
    assert {r["id"]: r["predictions"] for r in rows} == {quiet.pk: 0, busy.pk: 4, some.pk: 1}
    popular = client.get("/api/v1/predictions/markets?sort=popular").json()["results"]
    assert [r["id"] for r in popular] == [busy.pk, some.pk]  # none for the quiet one
    detail = client.get(f"/api/v1/predictions/markets/{busy.pk}").json()
    assert detail["predictions"] == 4
