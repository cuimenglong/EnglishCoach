"""UI polish: Markdown rendering, typing indicator, sidebar affordances."""
import asyncio
import json

from textual.app import App
from textual.widgets import RichLog, Static

from src import knowledge as K
from src.course_plan import PLAN_SCHEMA_VERSION, CoursePlan, DailyPlan
from src.tui.widgets.chat_widgets import (
    COACH_MARK,
    format_coach_mark,
    format_coach_message,
    format_error_message,
    format_system_message,
    format_user_message,
)
from src.utils import write_json
from rich.markdown import Markdown


# ------------------------------------------------------------- formatting --

def test_coach_replies_render_as_markdown():
    """The prompts used to forbid Markdown, which flattened everything."""
    assert isinstance(format_coach_message("**Correction:** bad -> good"), Markdown)


def test_user_text_cannot_inject_markup():
    """User input is escaped; a learner typing [bold] must not get styled output."""
    out = format_user_message("I wrote [bold]hello[/bold]")
    # rich escapes the opening bracket of every tag, so both tags are inert
    assert out.count(r"\[") == 2, out
    assert "[bold]hello" not in out.replace(r"\[", "")


def test_system_and_error_text_stay_escaped():
    assert r"\[x]" in format_system_message("[x]")
    assert r"\[x]" in format_error_message("[x]")


def test_coach_mark_is_plain_ascii():
    """Windows terminals render many Unicode box characters as tofu."""
    assert COACH_MARK.isascii(), "coach mark must stay ASCII-only"
    assert max(len(line) for line in COACH_MARK.splitlines()) <= 14
    assert format_coach_mark().plain == COACH_MARK.strip("\n")


# ----------------------------------------------------------------- screen --

def _mount(tmp, body):
    from src import sessions as sessmod
    from src.llm_client import LLMClient
    from src.tui.screens.coach_screen import CoachScreen

    K.init_db()
    plan = CoursePlan(
        total_days=3, schema_version=PLAN_SCHEMA_VERSION,
        days=[DailyPlan(day=i, topic=f"Topic {i}", focus="f",
                        exercise_types=["free_writing"], vocab_theme="v",
                        knowledge_points=[{"title": f"KP{i}", "detail": "d"}])
              for i in range(1, 4)],
    )
    write_json("course_plan.json", plan.model_dump())
    write_json("user_profile.json", {"level": "B1", "last_completed_day": 0})

    async def scenario():
        app = App()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = CoachScreen(LLMClient("k", "http://x", "m"), sessmod.SessionManager())
            await app.push_screen(screen)
            await pilot.pause()
            return body(screen)

    return asyncio.run(scenario())


def test_typing_indicator_appears_and_stops(temp_data_dir):
    def body(screen):
        indicator = screen.query_one("#typing-indicator", Static)
        assert indicator.display is False, "must be hidden when idle"

        screen._set_typing(True)
        assert indicator.display is True
        assert "typing" in str(indicator.content).lower()

        screen._tick_typing()
        screen._set_typing(False)
        assert indicator.display is False
        assert screen._typing_timer is None, "timer must be stopped, not leaked"
        return True

    assert _mount(temp_data_dir, body)


def test_unlocking_input_also_stops_typing(temp_data_dir):
    """A finished turn must not leave the indicator spinning forever."""
    def body(screen):
        screen._set_typing(True)
        screen._set_input_locked(False)
        assert screen.query_one("#typing-indicator", Static).display is False
        return True

    assert _mount(temp_data_dir, body)


def test_sidebar_has_review_and_profile_buttons(temp_data_dir):
    from textual.widgets import Button

    def body(screen):
        ids = {b.id for b in screen.query(Button)}
        assert {"btn-review", "btn-profile", "btn-vocab", "btn-plan",
                "btn-history", "btn-settings"} <= ids
        return True

    assert _mount(temp_data_dir, body)


def test_sidebar_shows_day_and_coach_mark(temp_data_dir):
    def body(screen):
        day = str(screen.query_one("#sidebar-day", Static).content)
        assert "Day 1 of 3" in day
        mark = screen.query_one("#sidebar-mark", Static).content
        assert mark.plain == COACH_MARK.strip("\n")
        return True

    assert _mount(temp_data_dir, body)


def test_chat_log_accepts_markdown_renderables(temp_data_dir):
    def body(screen):
        screen._add_message(format_coach_message("**Corrections**\n\n- a -> b"))
        screen._add_message(format_system_message("saved"))
        log = screen.query_one("#chat-log", RichLog)
        assert len(log.lines) > 0
        return True

    assert _mount(temp_data_dir, body)


def test_prompts_no_longer_forbid_markdown():
    """Guard against the ban creeping back in."""
    from src import daily_coach, summary, profile, dynamic_profile
    for module in (daily_coach, summary, profile, dynamic_profile):
        blob = "".join(
            v for v in vars(module).values() if isinstance(v, str)
        )
        assert "Do NOT use Markdown" not in blob, f"{module.__name__} still bans Markdown"
