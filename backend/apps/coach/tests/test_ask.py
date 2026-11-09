"""Ask the coach: reading the question, the template answer, checking AI points, the API."""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Membership, Plan, User
from apps.coach import ask, writer
from apps.coach.models import AiUsage, CoachQuestion
from apps.coach.tests.test_reports import fact
from apps.league.models import Team, TeamAlias

# -- Reading the question --------------------------------------------------------------------

TEAMS = {
    1: ["Solar Flare", "solar flare", "SLF"],
    2: ["Nexiom Flux", "nexiom flux", "NF"],
    3: ["V-ENT Esports", "v ent esports", "VT"],
}


def test_names_and_tags_are_found_as_whole_words_in_order():
    assert ask.mentions("How do we beat SLF and Nexiom Flux?", TEAMS) == [1, 2]
    assert ask.mentions("nexiom flux or solar-flare, who's worse", TEAMS) == [2, 1]
    assert ask.mentions("What does V-ENT do on Bermuda?", TEAMS) == []  # 'v ent' isn't a name
    assert ask.mentions("what does v-ent esports do", TEAMS) == [3]
    # A tag inside another word doesn't count.
    assert ask.mentions("any info on the zone?", TEAMS) == []


def test_maps_need_three_letters():
    maps = {"bermuda": ["Bermuda", "bermuda"], "nexterra": ["NeXTerra", "nexterra"]}
    assert ask.mentions("When should we rotate on nexterra", maps, min_len=3) == ["nexterra"]
    assert ask.mentions("hi", maps, min_len=3) == []


# -- Gathering the facts ---------------------------------------------------------------------


def test_facts_are_tagged_by_whose_they_are():
    facts = [fact("style.label", "Playstyle: aggressive", 4.0, 6, 6, [1, 2])]
    assert ask.tag_facts(facts, "us")[0]["id"] == "us/style.label"
    plays = [{"title": "x", "why": [], "facts": ["style.label"], "matches": [1]}]
    assert ask.tag_items(plays, "slf")[0]["facts"] == ["slf/style.label"]


def test_head_to_head_becomes_a_fact_only_when_the_teams_met():
    never = {"met": [], "fights": 0, "won": 0, "lost": 0, "matches": []}
    assert ask.h2h_fact(never, "a", "A") is None
    met = {"met": [4, 5], "fights": 3, "won": 1, "lost": 2, "matches": [5]}
    f = ask.h2h_fact(met, "slf", "SLF")
    assert f["id"] == "slf/h2h" and f["matches"] == [5]
    assert f["text"] == (
        "Against SLF: in the same lobby in 2 matches, 3 fights between the two, won 1, lost 2"
    )


def test_with_a_map_named_other_maps_facts_are_left_out():
    facts = [
        fact("a", "all maps", 1, 3, 3, [1]),
        fact("bermuda:b", "on Bermuda", 1, 3, 3, [1], "bermuda"),
        fact("kalahari:c", "on Kalahari", 1, 3, 3, [1], "kalahari"),
    ]
    assert [f["id"] for f in ask.relevant(facts, "bermuda")] == ["bermuda:b", "a"]
    assert len(ask.relevant(facts, None)) == 3


def test_drop_advice_becomes_facts():
    advice = {
        "matches": [{"id": 1}, {"id": 2}, {"id": 3}],
        "drops": [
            {"place": "Refinery", "matches": [1, 2, 3], "team_matches": 6, "avg_placement": 4.5,
             "left_s": 195, "inside_s": {2: 400}, "advice": ["Teams that finished top 5 from"
             " here left by about 3:15 (median of 3)"]},
        ],
    }  # fmt: skip
    (f,) = ask.drop_facts(advice, "bermuda", "Bermuda")
    assert f["id"] == "rotate/bermuda/1" and f["map"] == "bermuda"
    assert "Refinery on Bermuda: average placement 4.5 over 6 team matches" in f["text"]


# -- The template answer -----------------------------------------------------------------------


def test_template_puts_plays_first_then_head_to_head():
    facts = [
        fact("slf/style.label", "Playstyle: aggressive", 4.0, 6, 6, [1, 2]),
        {**fact("slf/h2h", "Against SLF: ...", 1, 2, 2, [5]), "id": "slf/h2h"},
    ]
    plays = [{"title": "They start most fights", "why": [], "facts": ["slf/style.label"],
              "matches": [1, 2]}]  # fmt: skip
    points = ask.template_points(plays, facts, has_opponent=True)
    assert [p["text"] for p in points] == ["They start most fights", "Against SLF: ..."]
    assert points[0]["facts"] == ["slf/style.label"]


def test_a_question_about_ourselves_gets_our_strongest_facts():
    facts = [
        fact("us/rotation.z3.late", "Late into Zone 3 in 4 of 9", 0.44, 4, 9, [1]),
        fact("us/deaths.top1", "5 deaths at Mill, in 6 of 9", 5, 6, 9, [2]),
    ]
    points = ask.template_points([], facts, has_opponent=False)
    assert [p["facts"] for p in points] == [["us/deaths.top1"], ["us/rotation.z3.late"]]


# -- Checking AI points -----------------------------------------------------------------------

SOURCES = {
    "us/rotation.z3.late": fact("us/rotation.z3.late", "Got inside Zone 3 after it closed in 4 of"
                                " 9 matches", 0.44, 4, 9, [1, 2], zone=3),
    "k:7": {"id": "k:7", "title": "Zone 3", "body": "Zone 3 closes in 120 seconds", "data": {}},
}  # fmt: skip


def test_ai_points_must_cite_a_fact_and_only_use_its_numbers():
    good = {"text": "You were late to Zone 3 in 4 of 9 matches: leave earlier.",
            "cites": ["us/rotation.z3.late"]}  # fmt: skip
    assert ask.check_point(good, SOURCES) is None
    assert ask.check_point({**good, "text": "Late in 60% of games."}, SOURCES) == (
        "number 60 not in what it cites"
    )
    assert ask.check_point({**good, "text": "Late in 44% of games."}, SOURCES) is None
    assert ask.check_point({**good, "cites": ["k:7"]}, SOURCES) == "cites no fact"
    assert ask.check_point({**good, "cites": ["us/nope"]}, SOURCES) == "cites unknown us/nope"
    assert ask.check_point({**good, "text": "x" * 400}, SOURCES) == "too long"
    # Knowledge numbers count when the knowledge entry is cited.
    zone = {"text": "Zone 3 closes in 120 seconds, and you were late in 4 of 9.",
            "cites": ["us/rotation.z3.late", "k:7"]}  # fmt: skip
    assert ask.check_point(zone, SOURCES) is None


def test_failed_points_are_dropped_and_a_note_with_numbers_is_ignored():
    parsed = {
        "points": [
            {"text": "Leave earlier for Zone 3.", "cites": ["us/rotation.z3.late"]},
            {"text": "You lose 80% of fights.", "cites": ["us/rotation.z3.late"]},
        ],
        "not_covered": "We have 2 matches on Kalahari.",
    }
    points, note = ask.checked(parsed, SOURCES)
    assert [p["text"] for p in points] == ["Leave earlier for Zone 3."]
    assert points[0]["matches"] == [1, 2] and note == ""
    _, note = ask.checked({"points": [], "not_covered": "Nothing on weapons yet."}, SOURCES)
    assert note == "Nothing on weapons yet."


# -- API ---------------------------------------------------------------------------------------


@pytest.fixture
def teams(db):
    plan = Plan.objects.get(code="league_team")
    alpha = Team.objects.create(name="Alpha", slug="alpha", tag="ALP", plan=plan)
    bravo = Team.objects.create(name="Bravo Squad", slug="bravo-squad", tag="BRV", plan=plan)
    TeamAlias.objects.create(team=bravo, in_game_name="BRAVO ESP")
    return alpha, bravo


def _member(team, email):
    user = User.objects.create_user(email=email)
    Membership.objects.create(user=user, team=team)
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_asking_reads_the_opponent_and_map_and_keeps_the_question(teams):
    alpha, _ = teams
    a = _member(alpha, "a@tdl.test")
    resp = a.post(
        "/api/v1/coach/teams/alpha/ask", {"question": "How do we beat BRAVO ESP on Bermuda?"},
        format="json",
    )  # fmt: skip
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["opponents"] == [{"slug": "bravo-squad", "name": "Bravo Squad"}]
    assert body["map"] == {"slug": "bermuda", "name": "Bermuda"}
    # No matches recorded: nothing made up, just a note saying so.
    assert body["points"] == [] and "enough recorded data" in body["not_covered"]
    assert body["writer"] == "template" and body["question"].startswith("How do we beat")
    assert CoachQuestion.objects.filter(team=alpha).count() == 1
    history = a.get("/api/v1/coach/teams/alpha/ask").json()
    assert [q["question"] for q in history] == ["How do we beat BRAVO ESP on Bermuda?"]


def test_only_the_team_can_ask_and_questions_are_checked(teams):
    alpha, bravo = teams
    a, b = _member(alpha, "a@tdl.test"), _member(bravo, "b@tdl.test")
    url = "/api/v1/coach/teams/alpha/ask"
    assert b.post(url, {"question": "What about us?"}, format="json").status_code == 403
    assert b.get(url).status_code == 403
    assert APIClient().post(url, {"question": "hi there"}, format="json").status_code == 401
    assert a.post(url, {"question": " "}, format="json").status_code == 400
    assert a.post(url, {"question": "x" * 301}, format="json").status_code == 400


def test_questions_are_capped_per_team_per_day(teams):
    alpha, _ = teams
    a = _member(alpha, "a@tdl.test")
    with override_settings(COACH_ASK_PER_TEAM_DAILY=2):
        for _ in range(2):
            assert a.post("/api/v1/coach/teams/alpha/ask", {"question": "What do we do?"},
                          format="json").status_code == 201  # fmt: skip
        resp = a.post("/api/v1/coach/teams/alpha/ask", {"question": "And now?"}, format="json")
        assert resp.status_code == 429


@pytest.mark.django_db
def test_ai_answer_keeps_only_checked_points_and_records_usage(monkeypatch):
    facts = list(SOURCES.values())[:1]
    calls = []

    def fake(prompt, *, system, schema):
        calls.append((prompt, system))
        return (
            {
                "points": [
                    {"text": "Leave earlier: late in 4 of 9.", "cites": [facts[0]["id"]]},
                    {"text": "Made up: 99 kills.", "cites": [facts[0]["id"]]},
                ]
            },
            800,
            90,
        )

    monkeypatch.setattr(writer, "_gemini", fake)
    with override_settings(COACH_WRITER="gemini", GEMINI_API_KEY="k"):
        points, note = ask.ai_answer("When do we rotate?", "Alpha", facts, opponents=[],
                                     map_name="")  # fmt: skip
    assert [p["text"] for p in points] == ["Leave earlier: late in 4 of 9."]
    assert calls and calls[0][1] == ask.SYSTEM
    usage = AiUsage.objects.get()
    assert usage.feature == "ask" and usage.kept == 1 and usage.input_tokens == 800


@pytest.mark.django_db
def test_ai_off_means_no_call(monkeypatch):
    monkeypatch.setattr(writer, "_gemini", lambda *a, **k: pytest.fail("called"))
    with override_settings(COACH_WRITER="off"):
        assert ask.ai_answer("q", "Alpha", list(SOURCES.values())[:1], opponents=[],
                             map_name="") is None  # fmt: skip
    assert AiUsage.objects.count() == 0
