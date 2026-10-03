"""Course plan v2: knowledge points, schema versioning, and safe revision."""
import json

import pytest

from src.course_plan import (
    PLAN_SCHEMA_VERSION,
    CoursePlan,
    DailyPlan,
    KnowledgePoint,
    build_plan_from_days,
    get_today_plan,
    load_course_plan,
    plan_is_stale,
    revise_plan_tail,
)
from src.utils import read_json, write_json


def _day(n, **kw):
    base = dict(
        day=n, topic=f"Topic {n}", focus="focus",
        exercise_types=["free_writing"], vocab_theme="vt",
    )
    base.update(kw)
    return DailyPlan(**base)


def _plan(n=5, **kw):
    return CoursePlan(
        total_days=n,
        days=[_day(i) for i in range(1, n + 1)],
        schema_version=PLAN_SCHEMA_VERSION,
        **kw,
    )


# ---------------------------------------------------------------- schema v2 --

def test_knowledge_points_are_first_class():
    d = _day(1, knowledge_points=[
        {"id": "gram.pp", "title": "Present Perfect vs Past Simple",
         "detail": "choose with time markers", "example": "I have lived here 3 years."},
    ], extension="Try the past perfect.", estimated_minutes=30)

    assert d.knowledge_points[0].title == "Present Perfect vs Past Simple"
    assert d.extension == "Try the past perfect."
    assert d.estimated_minutes == 30


def test_new_fields_have_safe_defaults():
    d = _day(1)
    assert d.knowledge_points == []
    assert d.extension == ""
    assert d.estimated_minutes == 20
    assert d.revised is False


def test_build_plan_stamps_current_version():
    plan = build_plan_from_days([{"day": 1, "topic": "t", "focus": "f",
                                  "exercise_types": ["x"], "vocab_theme": "v"}])
    assert plan.schema_version == PLAN_SCHEMA_VERSION
    assert plan.is_current()


def test_build_plan_skips_malformed_days_instead_of_failing():
    plan = build_plan_from_days([
        {"day": 1, "topic": "t", "focus": "f", "exercise_types": ["x"], "vocab_theme": "v"},
        {"nonsense": True},
        {"day": 2, "topic": "t2", "focus": "f", "exercise_types": ["x"], "vocab_theme": "v"},
    ])
    assert [d.day for d in plan.days] == [1, 2]
    assert plan.total_days == 2


# ------------------------------------------------------------ version gate --

def test_v1_plan_is_stale_and_refuses_to_load(temp_data_dir):
    """A plan written before versioning has no schema_version key. It must be
    treated as stale so the app regenerates instead of half-reading it."""
    legacy = {"total_days": 14, "days": [
        {"day": i, "topic": "t", "focus": "f",
         "exercise_types": ["x"], "vocab_theme": "v"} for i in range(1, 15)]}
    write_json("course_plan.json", legacy)

    assert plan_is_stale() is True
    assert load_course_plan() is None


def test_v2_plan_loads(temp_data_dir):
    write_json("course_plan.json", _plan(3).model_dump())
    loaded = load_course_plan()
    assert loaded is not None and loaded.is_current()


def test_absent_plan_is_not_stale(temp_data_dir):
    assert plan_is_stale() is False
    assert load_course_plan() is None


def test_corrupt_plan_loads_as_none(temp_data_dir):
    write_json("course_plan.json", {"total_days": "not-an-int", "days": []})
    assert load_course_plan() is None


# ------------------------------------------------------------- day lookup --

def test_today_lookup_by_day_number(temp_data_dir):
    write_json("user_profile.json", {"last_completed_day": 1})
    assert get_today_plan(_plan(3)).day == 2


def test_today_lookup_survives_reordering(temp_data_dir):
    """After a mid-course revision positions shift; day numbers must win."""
    write_json("user_profile.json", {"last_completed_day": 1})
    plan = _plan(3)
    plan.days.insert(0, _day(99, topic="INSERTED"))

    assert get_today_plan(plan).day == 2, "positional lookup would return INSERTED"


def test_today_lookup_falls_back_when_numbers_missing(temp_data_dir):
    write_json("user_profile.json", {"last_completed_day": 1})
    plan = _plan(3)
    plan.days = [_day(0, topic="A"), _day(0, topic="B"), _day(0, topic="C")]

    assert get_today_plan(plan) is not None  # does not crash


# ------------------------------------------------------------ future days --

def test_future_days_sorted():
    plan = _plan(3)
    assert [d.day for d in plan.future_days(1)] == [1, 2, 3]
    assert [d.day for d in plan.future_days(2)] == [2, 3]
    assert [d.day for d in plan.future_days(9)] == []


# -------------------------------------------------------- revision safety --

class _FakeLLM:
    """Stands in for LLMClient; records the messages it was given."""

    def __init__(self, tool_calls):
        self._tool_calls = tool_calls
        self.messages = None

    async def chat(self, messages, tools=None):
        self.messages = messages
        return "", self._tool_calls


def _revised(day_numbers, **extra):
    days = [{
        "day": n, "topic": f"REVISED {n}", "focus": "new focus",
        "knowledge_points": [{"title": f"NEW KP {n}", "detail": "d"}],
        "extension": "stretch", "exercise_types": ["gap_fill"],
        "vocab_theme": "vt", "estimated_minutes": 20,
    } for n in day_numbers]
    return [{"id": "submit_revised_plan", "name": "submit_revised_plan",
             "arguments": {"reason": "student struggled with articles", "days": days, **extra}}]


async def test_revision_never_touches_completed_days(temp_data_dir):
    plan = _plan(5)
    write_json("course_plan.json", plan.model_dump())
    llm = _FakeLLM(_revised([3, 4, 5]))

    result = await revise_plan_tail(llm, plan, from_day=3, profile_context="p", session_note="n")

    assert result is not None
    new_plan, reason = result
    assert [d.topic for d in new_plan.days[:2]] == ["Topic 1", "Topic 2"], "completed days changed!"
    assert [d.topic for d in new_plan.days[2:]] == ["REVISED 3", "REVISED 4", "REVISED 5"]
    assert "articles" in reason
    assert new_plan.days[2].revised is True


async def test_revision_rejects_wrong_day_count(temp_data_dir):
    plan = _plan(5)
    llm = _FakeLLM(_revised([3, 4]))  # one day short

    assert await revise_plan_tail(llm, plan, 3, "p", "n") is None


async def test_revision_rejects_wrong_day_numbers(temp_data_dir):
    plan = _plan(5)
    llm = _FakeLLM(_revised([2, 4, 5]))  # gap, and starts too early

    assert await revise_plan_tail(llm, plan, 3, "p", "n") is None


async def test_revision_rejects_duplicate_days(temp_data_dir):
    plan = _plan(5)
    llm = _FakeLLM(_revised([3, 3, 5]))

    assert await revise_plan_tail(llm, plan, 3, "p", "n") is None


async def test_revision_is_a_noop_when_nothing_is_left(temp_data_dir):
    plan = _plan(3)
    llm = _FakeLLM(_revised([3]))

    assert await revise_plan_tail(llm, plan, 4, "p", "n") is None


async def test_revision_survives_llm_error(temp_data_dir):
    class _Boom:
        async def chat(self, messages, tools=None):
            raise RuntimeError("network down")

    plan = _plan(5)
    assert await revise_plan_tail(_Boom(), plan, 3, "p", "n") is None


async def test_revision_survives_missing_tool_call(temp_data_dir):
    plan = _plan(5)
    llm = _FakeLLM([{"id": "1", "name": "something_else", "arguments": {}}])
    assert await revise_plan_tail(llm, plan, 3, "p", "n") is None


async def test_revision_persists_and_timestamps(temp_data_dir):
    plan = _plan(5, created_at="2026-01-01")
    write_json("course_plan.json", plan.model_dump())
    llm = _FakeLLM(_revised([3, 4, 5]))

    new_plan, _ = await revise_plan_tail(llm, plan, 3, "p", "n")

    saved = read_json("course_plan.json")
    assert saved["created_at"] == "2026-01-01"
    assert saved["revised_at"]
    assert saved["schema_version"] == PLAN_SCHEMA_VERSION
    assert load_course_plan().is_current()


async def test_revision_prompt_shows_completed_days_forbidden(temp_data_dir):
    plan = _plan(5)
    llm = _FakeLLM(_revised([3, 4, 5]))

    await revise_plan_tail(llm, plan, 3, "PROFILE_CTX", "SESSION_NOTE")

    body = llm.messages[1]["content"]
    assert "PROFILE_CTX" in body
    assert "SESSION_NOTE" in body
    assert "Already completed" in body
    assert "Topic 1" in body and "Topic 2" in body
    assert "Produce exactly 3 revised days starting at day 3" in body


async def test_malformed_day_in_revision_is_skipped_and_good_ones_apply(temp_data_dir):
    """One junk day must not throw away an otherwise good revision."""
    plan = _plan(5)
    calls = _revised([3, 4, 5])
    calls[0]["arguments"]["days"].insert(1, {"garbage": True})
    llm = _FakeLLM(calls)

    result = await revise_plan_tail(llm, plan, 3, "p", "n")

    assert result is not None
    new_plan, _ = result
    assert [d.topic for d in new_plan.days[2:]] == ["REVISED 3", "REVISED 4", "REVISED 5"]


async def test_revision_rejected_when_bad_days_leave_a_short_list(temp_data_dir):
    """If skipping malformed days changes the count, the revision is refused."""
    plan = _plan(5)
    calls = _revised([3, 4, 5])
    calls[0]["arguments"]["days"] = [
        {"garbage": True},
        calls[0]["arguments"]["days"][0],
        calls[0]["arguments"]["days"][1],
    ]  # 2 valid days for 3 slots
    llm = _FakeLLM(calls)

    assert await revise_plan_tail(llm, plan, 3, "p", "n") is None
