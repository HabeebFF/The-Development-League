from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.coach import writer
from apps.coach.models import AiUsage, KnowledgeEntry

FACTS = [
    {"id": "deaths.top1", "topic": "deaths", "text": "5 player deaths at Clock Tower, in 3 of 6"
     " matches", "value": 5, "n": 3, "of": 6, "matches": [2, 3, 4], "map": "bermuda",
     "data": {"place": "Clock Tower"}},
    {"id": "rotation.z3.late", "topic": "rotation", "text": "Got inside Zone 3 after it closed"
     " in 4 of 9 matches", "value": 0.44, "n": 4, "of": 9, "matches": [1, 2], "map": None,
     "data": {"zone": 3}},
]  # fmt: skip
ITEMS = [
    {"title": "Stop dying at Clock Tower", "why": [FACTS[0]["text"]], "facts": ["deaths.top1"],
     "matches": [2, 3, 4]},
    {"title": "Move to Zone 3 earlier", "why": [FACTS[1]["text"]], "facts": ["rotation.z3.late"],
     "matches": [1, 2]},
]  # fmt: skip
ON = {"COACH_WRITER": "gemini", "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-2.5-flash"}


def fake_gemini(answer, tokens=(900, 120)):
    calls = []

    def call(prompt):
        calls.append(prompt)
        if isinstance(answer, Exception):
            raise answer
        return answer, *tokens

    call.calls = calls
    return call


SOURCES = {f["id"]: f for f in FACTS}


def test_numbers_must_come_from_what_is_cited():
    item = ITEMS[0]
    good = {"title": "Leave Clock Tower", "advice": "5 deaths there in 3 of 6 matches.",
            "cites": ["deaths.top1"]}  # fmt: skip
    assert writer.check(item, good, SOURCES) is None
    made_up = {**good, "advice": "You lose 80% of fights there."}
    assert writer.check(item, made_up, SOURCES) == "number 80 not in what it cites"
    # A share is allowed as a percentage: 0.44 → 44%.
    late = {"title": "Rotate early", "advice": "Late into Zone 3 in 44% of games.",
            "cites": ["rotation.z3.late"]}  # fmt: skip
    assert writer.check(ITEMS[1], late, SOURCES) is None


def test_answers_must_cite_the_items_own_facts_and_nothing_unknown():
    item = ITEMS[0]
    base = {"title": "Leave Clock Tower", "advice": "Pick a quieter drop."}
    assert writer.check(item, {**base, "cites": ["rotation.z3.late"]}, SOURCES) == (
        "cites none of the item's facts"
    )
    assert writer.check(item, {**base, "cites": ["deaths.top1", "k:999"]}, SOURCES) == (
        "cites unknown k:999"
    )
    assert writer.check(item, {**base, "advice": "x" * 400, "cites": ["deaths.top1"]}, SOURCES)
    assert writer.check(item, {"title": "", "advice": "", "cites": []}, SOURCES) == "empty"


@pytest.mark.django_db
def test_off_or_without_a_key_keeps_the_template_and_calls_nothing(monkeypatch):
    fake = fake_gemini({"items": []})
    monkeypatch.setattr(writer, "_gemini", fake)
    with override_settings(COACH_WRITER="off", GEMINI_API_KEY="k"):
        assert writer.rewrite("report", ITEMS, FACTS, team="Alpha") == (ITEMS, 0)
    with override_settings(COACH_WRITER="gemini", GEMINI_API_KEY=""):
        assert writer.rewrite("report", ITEMS, FACTS, team="Alpha") == (ITEMS, 0)
    assert fake.calls == [] and AiUsage.objects.count() == 0


@pytest.mark.django_db
@override_settings(**ON)
def test_items_that_pass_are_rewritten_and_the_rest_keep_the_template(monkeypatch):
    zone = KnowledgeEntry.objects.create(
        kind="ZONE", title="Zone timings in our matches", body="Zone 3 shrinks at about 680 s."
    )
    answer = {
        "items": [
            {"n": 1, "title": "Drop away from Clock Tower", "advice": "It cost 5 deaths in 3"
             " of 6 matches; land on the edge instead.", "cites": ["deaths.top1"]},
            {"n": 2, "title": "Leave by 680 s", "advice": "You were late 9 times out of 10.",
             "cites": ["rotation.z3.late", f"k:{zone.pk}"]},
        ]
    }  # fmt: skip
    fake = fake_gemini(answer)
    monkeypatch.setattr(writer, "_gemini", fake)

    out, kept = writer.rewrite("report", ITEMS, FACTS, team="Alpha")

    assert kept == 1
    assert out[0]["title"] == "Drop away from Clock Tower"
    assert out[0]["advice"].startswith("It cost 5 deaths")
    assert out[0]["why"] == ITEMS[0]["why"] and out[0]["facts"] == ["deaths.top1"]
    assert out[0]["knowledge"] == []
    assert out[1] == ITEMS[1]  # "10" isn't in anything it cited
    assert f"k:{zone.pk}" in fake.calls[0]  # rotation items get the zone knowledge
    usage = AiUsage.objects.get()
    assert (usage.feature, usage.ok, usage.items, usage.kept) == ("report", True, 2, 1)
    assert (usage.input_tokens, usage.output_tokens, usage.cost_usd) == (900, 120, 0)


@pytest.mark.django_db
@override_settings(**ON)
def test_a_failed_call_is_recorded_and_keeps_the_template(monkeypatch):
    monkeypatch.setattr(writer, "_gemini", fake_gemini(writer.WriterError("Gemini answered 429")))
    assert writer.rewrite("counter", ITEMS, FACTS, team="Alpha", opponent="Bravo") == (ITEMS, 0)
    usage = AiUsage.objects.get()
    assert not usage.ok and usage.error == "Gemini answered 429"


@pytest.mark.django_db
@override_settings(**ON, COACH_AI_DAILY_REQUESTS=2, COACH_AI_PER_MINUTE=100)
def test_daily_limit_stops_calls(monkeypatch):
    fake = fake_gemini({"items": []})
    monkeypatch.setattr(writer, "_gemini", fake)
    for _ in range(3):
        writer.rewrite("report", ITEMS, FACTS, team="Alpha")
    assert len(fake.calls) == 2
    assert writer.unavailable() == "Today's limit of 2 requests is used up."


@pytest.mark.django_db
@override_settings(**ON, COACH_AI_PER_MINUTE=1)
def test_per_minute_limit_skips_or_waits(monkeypatch):
    fake = fake_gemini({"items": []})
    monkeypatch.setattr(writer, "_gemini", fake)
    slept = []
    monkeypatch.setattr(writer.time, "sleep", slept.append)
    writer.rewrite("report", ITEMS, FACTS, team="Alpha")
    writer.rewrite("report", ITEMS, FACTS, team="Alpha")
    assert len(fake.calls) == 1  # a web request doesn't wait
    writer.rewrite("report", ITEMS, FACTS, team="Alpha", wait=True)
    assert len(fake.calls) == 2 and slept and slept[0] > 50


@pytest.mark.django_db
@override_settings(**ON, COACH_AI_MONTHLY_CAP_USD=0.01, COACH_AI_PER_MINUTE=100)
def test_monthly_cap_prices_calls_and_stops_at_the_cap(monkeypatch):
    fake = fake_gemini({"items": []}, tokens=(10_000, 2_000))
    monkeypatch.setattr(writer, "_gemini", fake)
    writer.rewrite("report", ITEMS, FACTS, team="Alpha")
    # 10k in at $0.30/M + 2k out at $2.50/M = $0.008
    assert AiUsage.objects.get().cost_usd == Decimal("0.008")
    writer.rewrite("report", ITEMS, FACTS, team="Alpha")
    writer.rewrite("report", ITEMS, FACTS, team="Alpha")
    assert len(fake.calls) == 2
    assert writer.unavailable() == "This month's $0.01 cap is reached."


@pytest.mark.django_db
@override_settings(**ON)
def test_staff_see_usage(monkeypatch):
    AiUsage.objects.create(feature="report", provider="gemini", model="gemini-2.5-flash",
                           items=3, kept=2, input_tokens=100, output_tokens=50)  # fmt: skip
    user = User.objects.create_user(email="staff@tdl.test", password="pass-12345")
    StaffProfile.objects.create(user=user, role=StaffProfile.Role.ANALYST)
    staff = APIClient()
    staff.force_authenticate(user)
    data = staff.get("/api/v1/coach/ai-usage").json()
    assert data["on"] and data["blocked"] is None and data["today"] == 1
    assert data["recent"][0]["kept"] == 2 and data["recent"][0]["tokens"] == 150
    player = APIClient()
    player.force_authenticate(User.objects.create_user(email="p@tdl.test"))
    assert player.get("/api/v1/coach/ai-usage").status_code == 403


@pytest.mark.django_db
@override_settings(**ON)
def test_reports_record_the_ai_writer_only_when_it_wrote_something(monkeypatch):
    from apps.accounts.models import Plan
    from apps.coach import reports
    from apps.coach.models import CoachReport
    from apps.league.models import Team

    plan = Plan.objects.get(code="league_team")
    team = Team.objects.create(name="Alpha", slug="alpha", plan=plan, is_league_member=True)

    class Game:
        teams = {team.pk}

    monkeypatch.setattr("apps.coach.engine.load_games", lambda *a: [Game()])
    content = {"matches": [], "facts": FACTS, "tasks": [ITEMS[0]], "changes": []}
    monkeypatch.setattr(reports, "build", lambda *a: {**content, "tasks": [ITEMS[0]]})
    answer = {"items": [{"n": 1, "title": "Leave Clock Tower", "advice": "Pick another drop.",
                         "cites": ["deaths.top1"]}]}  # fmt: skip
    monkeypatch.setattr(writer, "_gemini", fake_gemini(answer))
    week = date(2026, 9, 28)
    reports.write_reports(week)
    report = CoachReport.objects.get()
    assert report.writer == "gemini:gemini-2.5-flash"
    assert report.tasks[0]["advice"] == "Pick another drop."

    monkeypatch.setattr(writer, "_gemini", fake_gemini({"items": []}))
    reports.write_reports(week)
    assert CoachReport.objects.get().writer == "template"


@override_settings(**ON)
def test_gemini_request_sends_the_key_in_a_header_and_reads_json(monkeypatch):
    import io
    import json

    sent = {}

    def urlopen(req, timeout):
        sent.update(url=req.full_url, key=req.get_header("X-goog-api-key"),
                    body=json.loads(req.data))  # fmt: skip
        reply = {"candidates": [{"content": {"parts": [{"text": '{"items": []}'}]}}],
                 "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3}}  # fmt: skip
        return io.BytesIO(json.dumps(reply).encode())

    monkeypatch.setattr(writer.urllib.request, "urlopen", urlopen)
    assert writer._gemini("hello") == ({"items": []}, 7, 3)
    assert sent["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert "test-key" not in sent["url"] and sent["key"] == "test-key"
    assert sent["body"]["generationConfig"]["responseMimeType"] == "application/json"
