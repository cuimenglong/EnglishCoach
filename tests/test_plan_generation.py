"""P0-4: a failed course-plan call must be visible, not silently swallowed.

The old handler was a bare `except Exception` that built a generic placeholder
plan. An invalid API key, a wrong model name and a network failure all produced
a plan that looked exactly like a successful one, so the user had no way to
tell the product was broken.
"""
import asyncio
import logging

import pytest
from textual.app import App

from src import app as app_module
from src.app import EnglishCoachApp
from src.profile import UserProfile


def test_fallback_plan_shape():
    profile = UserProfile(level="B1", study_days=7)

    plan = EnglishCoachApp._fallback_plan(None, profile)

    assert plan.total_days == 7
    assert [d.day for d in plan.days] == [1, 2, 3, 4, 5, 6, 7]
    assert all(d.topic and d.focus and d.exercise_types for d in plan.days)


def test_fallback_plan_respects_requested_length():
    for days in (7, 14, 21, 30):
        plan = EnglishCoachApp._fallback_plan(None, UserProfile(study_days=days))
        assert plan.total_days == days


def test_plan_generation_failure_is_logged_and_notifies(temp_data_dir, monkeypatch, caplog):
    """The whole point of P0-4: the error must surface."""
    import src.utils as utils
    import src.course_plan as course_plan
    import src.knowledge as knowledge
    import src.sessions as sessions

    utils.write_json(
        "user_profile.json",
        {"level": "B1", "study_days": 3, "last_completed_day": None},
    )

    async def boom(*_args, **_kwargs):
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(app_module, "generate_course_plan", boom)

    seen = {}

    class _App(EnglishCoachApp):
        def notify(self, message, **kwargs):  # capture instead of rendering a toast
            seen["message"] = message
            seen["severity"] = kwargs.get("severity")

    async def scenario():
        application = _App()
        application.config = app_module.Config(openai_api_key="sk-test")
        async with application.run_test() as pilot:
            await pilot.pause()
            await asyncio.sleep(0.3)
            await pilot.pause()

    with caplog.at_level(logging.ERROR):
        _run(scenario())

    assert "401 Unauthorized" in seen.get("message", ""), "user was never told"
    assert seen.get("severity") == "error"
    assert any("Course plan generation failed" in r.message for r in caplog.records), (
        "failure was not logged"
    )


def test_successful_generation_does_not_notify(temp_data_dir, monkeypatch):
    """Guard against the opposite bug: no spurious error on the happy path."""
    import src.utils as utils
    from src.course_plan import CoursePlan, DailyPlan

    utils.write_json(
        "user_profile.json",
        {"level": "B1", "study_days": 2, "last_completed_day": None},
    )

    async def ok(_llm, _profile):
        return CoursePlan(
            total_days=2,
            days=[
                DailyPlan(day=1, topic="T1", focus="f",
                          exercise_types=["free_writing"], vocab_theme="v"),
                DailyPlan(day=2, topic="T2", focus="f",
                          exercise_types=["free_writing"], vocab_theme="v"),
            ],
        )

    monkeypatch.setattr(app_module, "generate_course_plan", ok)

    seen = {}

    class _App(EnglishCoachApp):
        def notify(self, message, **kwargs):
            seen["message"] = message

    async def scenario():
        application = _App()
        application.config = app_module.Config(openai_api_key="sk-test")
        async with application.run_test() as pilot:
            await pilot.pause()
            await asyncio.sleep(0.3)
            await pilot.pause()

    _run(scenario())

    assert "message" not in seen


def _run(coro):
    return asyncio.run(coro)
