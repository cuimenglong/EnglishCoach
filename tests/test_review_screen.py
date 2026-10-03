"""Review screen behaviour, and due cards reaching the coach prompt."""
import asyncio

from textual.app import App
from textual.widgets import Static

from src import knowledge as K
from src.srs import RATING_AGAIN, RATING_EASY, RATING_GOOD
from src.tui.screens.review_screen import ReviewScreen


class _Harness(App):
    def __init__(self):
        super().__init__()
        self.screen_instance = None

    def on_mount(self) -> None:
        self.screen_instance = ReviewScreen()
        self.push_screen(self.screen_instance)


def _run(body):
    async def scenario():
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            result = body(app, pilot)
            await pilot.pause()
            return result

    return asyncio.run(scenario())


def _seed_due(n=3):
    K.init_db()
    for i in range(n):
        K.add_vocabulary(f"expression {i}", f"meaning {i}", f"e.g. example {i}",
                         "tag", source="manual")


def _text(screen, selector):
    return str(screen.query_one(selector, Static).content)


# ------------------------------------------------------------- happy path --

def test_shows_a_card_and_hides_the_answer_initially(temp_data_dir):
    _seed_due(2)

    def body(app, pilot):
        s = app.screen_instance
        assert len(s.queue) == 2
        assert "expression 0" in _text(s, "#review-card")
        assert "meaning 0" not in _text(s, "#review-detail")
        return True

    assert _run(body)


def test_reveal_shows_meaning_and_example(temp_data_dir):
    _seed_due(1)

    def body(app, pilot):
        s = app.screen_instance
        s.action_reveal()
        detail = _text(s, "#review-detail")
        assert "meaning 0" in detail
        assert "e.g. example 0" in detail
        return True

    assert _run(body)


def test_rating_moves_to_the_next_card_and_persists(temp_data_dir):
    _seed_due(2)

    def body(app, pilot):
        s = app.screen_instance
        first_id = s.queue[0].id
        s.action_reveal()
        s._rate(RATING_GOOD)

        assert s.index == 1
        assert "expression 1" in _text(s, "#review-card")
        assert "meaning 0" not in _text(s, "#review-detail"), "must re-hide after grading"
        # the graded card left the due queue
        assert K.get_review_card(first_id).reps == 1
        return True

    assert _run(body)


def test_again_keeps_the_card_in_the_queue(temp_data_dir):
    _seed_due(1)

    def body(app, pilot):
        s = app.screen_instance
        card_id = s.queue[0].id
        s._rate(RATING_AGAIN)

        assert K.get_review_card(card_id).state == "relearning"
        assert K.get_due_count() == 1, "a failed card must still be due today"
        return True

    assert _run(body)


def test_easy_also_records_the_review(temp_data_dir):
    _seed_due(1)

    def body(app, pilot):
        s = app.screen_instance
        card_id = s.queue[0].id
        s._rate(RATING_EASY)
        assert K.get_review_card(card_id).reps == 1
        return True

    assert _run(body)


def test_finishing_shows_a_summary(temp_data_dir):
    _seed_due(1)

    def body(app, pilot):
        s = app.screen_instance
        s._rate(RATING_GOOD)
        assert "Review complete" in _text(s, "#review-progress")
        assert "All done" in _text(s, "#review-card")
        assert "good 1" in _text(s, "#review-detail")
        return True

    assert _run(body)


def test_empty_queue_is_handled(temp_data_dir):
    K.init_db()

    def body(app, pilot):
        s = app.screen_instance
        assert s.queue == []
        assert "Review complete" in _text(s, "#review-progress")
        return True

    assert _run(body)


def test_falls_back_to_unenrolled_cards(temp_data_dir):
    """A learner with saved expressions but no schedule should not see an empty screen."""
    K.init_db()
    K.add_vocabulary("auto saved", "a meaning", "", "", source="coach")

    def body(app, pilot):
        s = app.screen_instance
        assert len(s.queue) == 1
        assert "auto saved" in _text(s, "#review-card")
        return True

    assert _run(body)


def test_rating_a_new_card_enrols_it(temp_data_dir):
    K.init_db()
    K.add_vocabulary("auto saved", "a meaning", "", "", source="coach")

    def body(app, pilot):
        s = app.screen_instance
        card_id = s.queue[0].id
        s._rate(RATING_GOOD)
        assert K.get_review_card(card_id).state in ("learning", "review")
        return True

    assert _run(body)


# ---------------------------------------------------- proactive injection --

def test_due_expressions_reach_the_coach_prompt(temp_data_dir):
    """The whole point of the review queue: the coach surfaces due items without
    being asked, instead of only when it feels like calling search_vocabulary."""
    from src import sessions as sessmod
    from src.course_plan import PLAN_SCHEMA_VERSION, CoursePlan, DailyPlan
    from src.llm_client import LLMClient
    from src.tui.screens.coach_screen import CoachScreen
    from src.utils import write_json
    import json

    K.init_db()
    K.add_vocabulary("take off", "to leave the ground", "", "", source="manual")
    K.add_vocabulary("run down", "to criticize", "", "", source="manual")

    plan = CoursePlan(
        total_days=3, schema_version=PLAN_SCHEMA_VERSION,
        days=[DailyPlan(day=i, topic=f"T{i}", focus="f",
                        exercise_types=["free_writing"], vocab_theme="v")
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
            return screen.system_prompt

    prompt = asyncio.run(scenario())
    assert "due for review" in prompt
    assert "take off" in prompt


def test_no_due_items_means_no_section(temp_data_dir):
    from src import sessions as sessmod
    from src.course_plan import PLAN_SCHEMA_VERSION, CoursePlan, DailyPlan
    from src.llm_client import LLMClient
    from src.tui.screens.coach_screen import CoachScreen
    from src.utils import write_json

    K.init_db()
    plan = CoursePlan(
        total_days=3, schema_version=PLAN_SCHEMA_VERSION,
        days=[DailyPlan(day=i, topic=f"T{i}", focus="f",
                        exercise_types=["free_writing"], vocab_theme="v")
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
            return screen.system_prompt

    assert "due for review" not in asyncio.run(scenario())


def test_sidebar_shows_due_badge(temp_data_dir):
    from src import sessions as sessmod
    from src.course_plan import PLAN_SCHEMA_VERSION, CoursePlan, DailyPlan
    from src.llm_client import LLMClient
    from src.tui.screens.coach_screen import CoachScreen
    from src.utils import write_json

    K.init_db()
    K.add_vocabulary("take off", "", "", "", source="manual")
    plan = CoursePlan(
        total_days=2, schema_version=PLAN_SCHEMA_VERSION,
        days=[DailyPlan(day=i, topic=f"T{i}", focus="f",
                        exercise_types=["free_writing"], vocab_theme="v")
              for i in range(1, 3)],
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
            return str(screen.query_one("#sidebar-vocab", Static).content)

    assert "Due for review" in asyncio.run(scenario())
