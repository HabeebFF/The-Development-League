"""Fans: the fan table (shared with the leaderboard) and the home page's Fan zone.

Fans are accounts with a wallet: they predict with DC (play coins, never real money) and dress
their fan card with designs from the card shop.
"""

import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Bet, LedgerEntry, Leg, Market, Multiple, Outcome, Wallet
from .services import Kind, can_play, lagos_today

ACCURACY_MIN_SETTLED = 10
TOP_CARDS = 3  # fan cards on the podium
BOARD_TO = 8  # places 4 to 8 as a list
BIG_WINS = 4
CROWD_MARKETS = 3
CROWD_MIN_BACKERS = 5  # one big bet is not "the crowd"
RARE_DESIGNS = 3
CACHE_KEY = "predictions:fan-zone:v1"
CACHE_SECONDS = 60


def _settled(model, status_: str):
    """How many of a wallet owner's single bets or multiples ended with ``status_``."""
    rows = (
        model.objects.filter(user=OuterRef("user"), status=status_)
        .values("user")
        .annotate(n=Count("pk"))
        .values("n")
    )
    return Coalesce(Subquery(rows, output_field=IntegerField()), Value(0))


def ranked_wallets():
    """Every wallet with ``won``, ``lost``, ``shop_spent`` and ``net`` (balance + DC spent in
    the card shop, so buying a design never costs a place). Not ordered."""
    spent = (
        LedgerEntry.objects.filter(
            wallet=OuterRef("pk"), kind__in=[Kind.PURCHASE, Kind.SHOP_REFUND]
        )
        .values("wallet")
        .annotate(n=Sum("amount"))
        .values("n")
    )
    return (
        Wallet.objects.select_related("user")
        .annotate(
            won=_settled(Bet, Bet.Status.WON) + _settled(Multiple, Bet.Status.WON),
            lost=_settled(Bet, Bet.Status.LOST) + _settled(Multiple, Bet.Status.LOST),
        )
        .annotate(shop_spent=-Coalesce(Subquery(spent, output_field=IntegerField()), Value(0)))
        .annotate(net=F("balance") + F("shop_spent"))
    )


NET_ORDER = ("-net", "created_at")


def fan_name(wallet: Wallet) -> str:
    return wallet.user.display_name or f"Player {wallet.pk}"


def accuracy(won: int, lost: int) -> float | None:
    settled = won + lost
    return round(won / settled, 4) if settled else None


def week_start(now=None) -> dt.datetime:
    """Monday 00:00 in Lagos for the week ``now`` is in (weeks run Monday to Sunday)."""
    tz = ZoneInfo(settings.ANALYTICS_TIME_ZONE)
    local = (now or timezone.now()).astimezone(tz)
    monday = local.date() - dt.timedelta(days=local.weekday())
    return dt.datetime.combine(monday, dt.time.min, tzinfo=tz)


def _team(team) -> dict | None:
    if team is None:
        return None
    return {
        "id": team.pk,
        "name": team.name,
        "tag": team.tag,
        "slug": team.slug,
        "logo": team.logo.url if team.logo else None,
        "primary_color": team.primary_color,
    }


def _card(w: Wallet, rank: int, designs: dict, teams: dict) -> dict:
    return {
        "rank": rank,
        "name": fan_name(w),
        "favourite_team": _team(teams.get(w.user_id)),
        "design": designs.get(w.user_id),
        "stats": {
            "balance": w.balance,
            "shop_spent": w.shop_spent,
            "net": w.net,
            "won": w.won,
            "lost": w.lost,
            "accuracy": accuracy(w.won, w.lost),
        },
    }


def _teams(user_ids) -> dict:
    from apps.shop.models import Equipped

    return {
        e.user_id: e.favourite_team
        for e in Equipped.objects.filter(
            user_id__in=list(user_ids), favourite_team__isnull=False
        ).select_related("favourite_team")
    }


def _leader(w: Wallet | None, value, designs: dict) -> dict | None:
    if w is None:
        return None
    return {
        "name": fan_name(w),
        "design": designs.get(w.user_id),
        "value": value,
        "settled": w.won + w.lost,
    }


def _big_wins(since, designs_for) -> list[dict]:
    singles = [
        (b.payout - b.stake, b)
        for b in Bet.objects.filter(status=Bet.Status.WON, settled_at__gte=since)
        .select_related("user", "market", "outcome")
        .order_by("-payout")[:20]
    ]
    multiples = [
        (m.payout - m.stake, m)
        for m in Multiple.objects.filter(status=Bet.Status.WON, settled_at__gte=since)
        .select_related("user")
        .annotate(picks=Count("legs"))
        .order_by("-payout")[:20]
    ]
    wins = sorted(singles + multiples, key=lambda pw: (-pw[0], -pw[1].settled_at.timestamp()))
    wins = [(p, w) for p, w in wins if p > 0][:BIG_WINS]
    designs = designs_for({w.user_id for _, w in wins})
    out = []
    for _, w in wins:
        single = isinstance(w, Bet)
        out.append(
            {
                "name": w.user.display_name or "Fan",
                "design": designs.get(w.user_id),
                "pick": w.outcome.label if single else f"{w.picks}-pick multiple",
                "context": w.market.title
                if single
                else timezone.localtime(
                    w.settled_at, ZoneInfo(settings.ANALYTICS_TIME_ZONE)
                ).strftime("%a %-d %b"),
                "stake": w.stake,
                "payout": w.payout,
                "odds": str(w.odds_accepted if single else w.odds),
                "settled_at": w.settled_at.isoformat(),
            }
        )
    return out


def _crowd(now) -> list[dict]:
    """Open markets with the most backers (single bets and multiple picks), and the pick with
    the biggest share of them."""
    open_markets = Market.objects.filter(
        status=Market.Status.OPEN, opens_at__lte=now, closes_at__gt=now
    )
    picks: dict[int, dict[int, set]] = {}
    for market_id, outcome_id, user_id in Bet.objects.filter(
        market__in=open_markets, status=Bet.Status.PENDING
    ).values_list("market_id", "outcome_id", "user_id"):
        picks.setdefault(market_id, {}).setdefault(outcome_id, set()).add(user_id)
    for market_id, outcome_id, user_id in Leg.objects.filter(
        market__in=open_markets, multiple__status=Bet.Status.PENDING
    ).values_list("market_id", "outcome_id", "multiple__user_id"):
        picks.setdefault(market_id, {}).setdefault(outcome_id, set()).add(user_id)

    rows = []
    for market_id, by_outcome in picks.items():
        backers = len(set().union(*by_outcome.values()))
        if backers < CROWD_MIN_BACKERS:
            continue
        outcome_id, users = max(by_outcome.items(), key=lambda kv: (len(kv[1]), -kv[0]))
        rows.append((backers, market_id, outcome_id, len(users)))
    rows.sort(key=lambda r: (-r[0], r[1]))
    rows = rows[:CROWD_MARKETS]
    outcomes = Outcome.objects.select_related("market").in_bulk([r[2] for r in rows])
    return [
        {
            "market_id": market_id,
            "market": outcomes[outcome_id].market.title,
            "outcome": outcomes[outcome_id].label,
            "share": round(on_it / backers, 4),
            "backers": backers,
            "odds": str(outcomes[outcome_id].odds),
        }
        for backers, market_id, outcome_id, on_it in rows
    ]


def _rare() -> list[dict]:
    from apps.shop.models import CardDesign, OwnedDesign
    from apps.shop.services import design_data

    designs = list(
        CardDesign.objects.filter(copies__isnull=False).order_by("-price", "order", "pk")[
            :RARE_DESIGNS
        ]
    )
    out = []
    for d in designs:
        owners = list(
            OwnedDesign.objects.filter(design=d, refunded_at__isnull=True)
            .select_related("user")
            .order_by("-created_at")
        )
        out.append(
            {
                "design": design_data(d),
                "owners": [o.user.display_name or "Fan" for o in owners],
                "left": max(d.copies - len(owners), 0),
            }
        )
    return out


def shared_zone(now=None) -> dict:
    """Everything on the Fan zone that is the same for every visitor."""
    from apps.shop.services import equipped_designs

    now = now or timezone.now()
    since = week_start(now)
    ranked = ranked_wallets()
    top = list(ranked.order_by(*NET_ORDER)[:BOARD_TO])
    # Accuracy is a ratio: rank it here over the (small) set that qualifies, like the
    # leaderboard does (best ratio, then more settled bets, then the older wallet).
    qualified = list(
        ranked.annotate(settled=F("won") + F("lost")).filter(settled__gte=ACCURACY_MIN_SETTLED)
    )
    acc_leader = (
        min(qualified, key=lambda w: (-w.won / (w.won + w.lost), -(w.won + w.lost), w.created_at))
        if qualified
        else None
    )
    wins_leader = ranked.filter(won__gt=0).order_by("-won", "lost", "created_at").first()

    leaders = [w for w in (acc_leader, wins_leader) if w is not None]
    designs = equipped_designs({w.user_id for w in top + leaders})
    teams = _teams(w.user_id for w in top[:TOP_CARDS])

    bets = Bet.objects.filter(placed_at__gte=since).aggregate(n=Count("pk"), s=Sum("stake"))
    multis = Multiple.objects.filter(placed_at__gte=since).aggregate(n=Count("pk"), s=Sum("stake"))
    won = Bet.objects.filter(status=Bet.Status.WON, settled_at__gte=since).count() + (
        Multiple.objects.filter(status=Bet.Status.WON, settled_at__gte=since).count()
    )
    return {
        "fans": Wallet.objects.count(),
        "week": {
            "starts": since.date().isoformat(),
            "bets": bets["n"] + multis["n"],
            "staked": (bets["s"] or 0) + (multis["s"] or 0),
            "won": won,
        },
        "top": [_card(w, n, designs, teams) for n, w in enumerate(top[:TOP_CARDS], start=1)],
        "board": [
            {"rank": n, "name": fan_name(w), "net": w.net, "design": designs.get(w.user_id)}
            for n, w in enumerate(top, start=1)
            if n > TOP_CARDS
        ],
        "leaders": {
            "accuracy": _leader(
                acc_leader,
                accuracy(acc_leader.won, acc_leader.lost) if acc_leader else None,
                designs,
            ),
            "wins": _leader(wins_leader, wins_leader.won if wins_leader else None, designs),
            "min_settled": ACCURACY_MIN_SETTLED,
        },
        "big_wins": _big_wins(since, equipped_designs),
        "crowd": _crowd(now),
        "rare": _rare(),
    }


def my_zone(user) -> dict | None:
    """The signed-in fan's own card and place. Never creates a wallet or gives coins: the daily
    bonus is still given on the predict pages, this only says it's waiting."""
    if not can_play(user):
        return None
    from apps.shop.services import equipped_designs

    me = ranked_wallets().filter(user=user).first()
    if me is None:
        return None
    ahead = (
        ranked_wallets()
        .filter(Q(net__gt=me.net) | Q(net=me.net, created_at__lt=me.created_at))
        .count()
    )
    card = _card(me, ahead + 1, equipped_designs([user.pk]), _teams([user.pk]))
    bonus = max(settings.PREDICTIONS_DAILY_BONUS, 0)
    claimed = LedgerEntry.objects.filter(
        wallet=me, idempotency_key=f"daily:{me.pk}:{lagos_today().isoformat()}"
    ).exists()
    return {
        **card,
        "bonus_ready": bonus > 0 and not claimed,
        "daily_bonus": bonus,
        "open_bets": Bet.objects.filter(user=user, status=Bet.Status.PENDING).count()
        + Multiple.objects.filter(user=user, status=Bet.Status.PENDING).count(),
    }


def fan_zone(user) -> dict:
    """``viewer`` says which box goes top left: ``visitor`` (sign up), ``staff`` (can't play),
    ``new`` (signed in, no wallet yet) or ``fan`` (``me`` is their card)."""
    data = cache.get(CACHE_KEY)
    if data is None:
        data = shared_zone()
        cache.set(CACHE_KEY, data, CACHE_SECONDS)
    me = None
    if not (user and user.is_authenticated):
        viewer = "visitor"
    elif not can_play(user):
        viewer = "staff"
    else:
        me = my_zone(user)
        viewer = "fan" if me else "new"
    return {**data, "viewer": viewer, "me": me}
