"""Profile dashboard: the computed numbers must be visible to the learner."""
import asyncio
import io

from rich.console import Console
from textual.app import App
from textual.widgets import Static

from src.coach_policy import build_session_directives
from src.course_plan import DailyPlan
from src.dynamic_profile import DynamicProfile, SkillScores
from src.tui.screens.profile_screen import ProfileScreen


def _profile(**kw):
    base = dict(
        cefr_level="B1", confidence_in_level="medium", lessons_completed=7,
        skill_scores=SkillScores(grammar=6, vocabulary=5, sentence_structure=6,
                                 fluency=5, accuracy=4),
        strengths=["daily conversation"],
        weaknesses=["article usage"],
        challenging_areas=["past perfect"],
        mastered_topics=["present simple"],
        common_mistakes=["missing articles"],
        interests=["technology"],
    )
    base.update(kw)
    return DynamicProfile(**base)


def _run(body, profile=None, directives=True):
    profile = profile or _profile()
    plan = DailyPlan(day=2, topic="T", focus="F",
                     exercise_types=["free_writing"], vocab_theme="v",
                     estimated_minutes=20)
    d = build_session_directives(profile, plan) if directives else None

    class H(App):
        CSS = "Screen { background: $surface; }"

        def on_mount(self):
            self.s = ProfileScreen(profile, d)
            self.push_screen(self.s)

    async def scenario():
        app = H()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            return body(app)
    return asyncio.run(scenario())


def _t(app, sel):
    """Widget content as text; the skills pane holds a rich Table, not a str."""
    content = app.s.query_one(sel, Static).content
    if isinstance(content, str):
        return content
    buffer = io.StringIO()
    Console(width=200, no_color=True, file=buffer, legacy_windows=False).print(content)
    return buffer.getvalue()


def test_shows_all_five_skill_dimensions():
    def body(app):
        out = _t(app, "#profile-skills")
        for label in ("Grammar", "Vocabulary", "Sentence structure", "Fluency", "Accuracy"):
            assert label in out, f"{label} missing from the dashboard"
        return out

    assert "5/10" in _run(body)


def test_shows_scores():
    assert "4/10" in _run(lambda app: _t(app, "#profile-skills"))


def test_shows_level_and_confidence():
    out = _run(lambda app: _t(app, "#profile-title"))
    assert "B1" in out
    assert "medium" in out


def test_shows_learner_context():
    out = _run(lambda app: _t(app, "#profile-summary"))
    assert "Lessons completed: 7" in out
    assert "article usage" in out
    assert "past perfect" in out
    assert "technology" in out


def test_shows_todays_computed_directives():
    """The dashboard is the visible half of what the decision engine computes."""
    out = _run(lambda app: _t(app, "#profile-directives"))
    assert "accuracy" in out
    assert "intermediate" in out
    assert "exchanges" in out


def test_works_without_directives():
    out = _run(lambda app: _t(app, "#profile-skills"), directives=False)
    assert "Grammar" in out


def test_weak_dimension_is_visually_distinct():
    """A 4/10 must not render the same as a 6/10."""
    out = _run(lambda app: _t(app, "#profile-skills"))
    assert "█" in out and "░" in out
