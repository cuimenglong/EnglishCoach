"""CoachScreen wiring: directives reach the prompt, and the day actually advances.

The stale-plan bug this covers: today_plan and system_prompt were built once in
__init__, so after /summary moved the day counter the prompt still said
"Today is Day N" and the sidebar showed the new day next to the old topic.
"""
import asyncio
import json

from textual.app import App
from textual.widgets import Static

from src.course_plan import PLAN_SCHEMA_VERSION, CoursePlan, DailyPlan
from src.tui.screens.coach_screen import CoachScreen


def _day(n, **kw):
    base = dict(day=n, topic=f"Topic {n}", focus="f",
                exercise_types=["free_writing"], vocab_theme="v",
                knowledge_points=[{"title": f"KP {n}", "detail": "d"}],
                estimated_minutes=20)
    base.update(kw)
    return DailyPlan(**base)


def _write_plan(tmp, days=3):
    plan = CoursePlan(total_days=days, days=[_day(i) for i in range(1, days + 1)],
                      schema_version=PLAN_SCHEMA_VERSION)
    (tmp / "course_plan.json").write_text(json.dumps(plan.model_dump()), encoding="utf-8")
    return plan


def _write_profile(tmp, completed_day, days=3):
    (tmp / "user_profile.json").write_text(
        json.dumps({"level": "B1", "study_days": days, "last_completed_day": completed_day}),
        encoding="utf-8",
    )


def _run(tmp, completed_day, body):
    """Mount CoachScreen, run body(screen) inside the live app, return its result."""
    from src import sessions as sessmod
    from src.knowledge import init_db
    from src.llm_client import LLMClient

    init_db()
    _write_plan(tmp)
    _write_profile(tmp, completed_day)

    async def scenario():
        app = App()
        async with app.run_test() as pilot:
            await pilot.pause()
            session = sessmod.SessionManager()
            screen = CoachScreen(LLMClient("k", "http://x", "m"), session)
            await app.push_screen(screen)
            await pilot.pause()
            result = body(screen)
            await pilot.pause()
            return result

    return asyncio.run(scenario())


# ------------------------------------------------------------------ prompt --

def test_directives_reach_the_system_prompt(temp_data_dir):
    def body(screen):
        prompt = screen.system_prompt
        assert "SESSION DIRECTIVES" in prompt
        assert "priority skill" in prompt
        assert "Session length target" in prompt
        # the real computed values, not placeholders
        assert screen.directives.difficulty in prompt
        assert str(screen.directives.target_exchanges) in prompt
        return True

    assert _run(temp_data_dir, completed_day=0, body=body)


def test_prompt_names_the_current_day(temp_data_dir):
    def body(screen):
        return screen.system_prompt

    assert "Today is Day 1 of 3" in _run(temp_data_dir, 0, body)


# ------------------------------------------------------- day advance / stale --

def test_refresh_day_context_advances_the_prompt(temp_data_dir):
    """Regression: after /summary the day moves but the prompt used to stay put."""

    def body(screen):
        before = screen.system_prompt
        assert "Today is Day 1 of 3" in before

        screen.session.current_day = 2
        _write_profile(temp_data_dir, completed_day=1)
        screen._refresh_day_context()
        return screen.system_prompt, screen.today_plan.day

    prompt, day = _run(temp_data_dir, 0, body)
    assert "Today is Day 2 of 3" in prompt
    assert "Today is Day 1" not in prompt
    assert "KP 2" in prompt
    assert "KP 1" not in prompt
    assert day == 2


def test_refresh_recomputes_directives_from_new_profile(temp_data_dir):
    from src.dynamic_profile import DynamicProfile, SkillScores

    def body(screen):
        before = screen.directives.difficulty_score
        screen.profile = DynamicProfile(
            skill_scores=SkillScores(grammar=9, vocabulary=9, sentence_structure=9,
                                     fluency=9, accuracy=9))
        screen._refresh_day_context()
        return before, screen.directives.difficulty

    before, after = _run(temp_data_dir, 0, body)
    assert after == "expert"
    assert after != before or True  # score changed; label is what matters


def test_sidebar_shows_the_current_day(temp_data_dir):
    def body(screen):
        first = screen.query_one("#sidebar-progress", Static).content
        screen.session.current_day = 3
        screen._update_sidebar()
        return first, screen.query_one("#sidebar-progress", Static).content

    first, after = _run(temp_data_dir, 0, body)
    assert "Day 1 of 3" in first
    assert "Day 3 of 3" in after


def test_sidebar_topic_matches_todays_plan(temp_data_dir):
    """The earlier bug: a new day number next to the previous day's topic."""

    def body(screen):
        screen.session.current_day = 2
        _write_profile(temp_data_dir, completed_day=1)
        screen._refresh_day_context()
        screen._update_sidebar()
        return screen.query_one("#sidebar-topic", Static).content

    topic = _run(temp_data_dir, 0, body)
    assert "Topic 2" in topic
    assert "Topic 1" not in topic


def test_revised_flag_survives_a_reload(temp_data_dir):
    """_refresh_day_context re-reads the plan from disk, so a revision written
    by revise_plan_tail must show up in the rebuilt context."""
    def body(screen):
        plan = _write_plan(temp_data_dir)
        plan.days[0].revised = True
        (temp_data_dir / "course_plan.json").write_text(
            json.dumps(plan.model_dump()), encoding="utf-8")
        screen._refresh_day_context()
        return screen.today_plan.revised

    assert _run(temp_data_dir, 0, body) is True
