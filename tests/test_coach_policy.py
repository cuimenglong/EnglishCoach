"""Session policy: the profile must produce real, computed instructions."""
import logging

import pytest

from src.coach_policy import (
    SessionDirectives,
    average_skill_score,
    build_session_directives,
    difficulty_for_score,
    weakest_dimension,
)
from src.course_plan import DailyPlan
from src.dynamic_profile import DynamicProfile, SkillScores


def _profile(**skills):
    return DynamicProfile(
        skill_scores=SkillScores(**{k: v for k, v in skills.items()}),
    )


def _plan(minutes=20):
    return DailyPlan(
        day=1, topic="T", focus="F",
        exercise_types=["free_writing"], vocab_theme="v",
        estimated_minutes=minutes,
    )


# --------------------------------------------------------------- difficulty --

@pytest.mark.parametrize("score,expected", [
    (1, "beginner"), (3.9, "beginner"),
    (4.0, "intermediate"), (6.4, "intermediate"),
    (6.5, "advanced"), (7.9, "advanced"),
    (8.0, "expert"), (10, "expert"),
])
def test_difficulty_bands(score, expected):
    assert difficulty_for_score(score) == expected


def test_average_is_computed_not_trusted():
    p = _profile(grammar=6, vocabulary=5, sentence_structure=6, fluency=5, accuracy=4)
    assert average_skill_score(p) == 5.2


def test_weakest_dimension_is_found():
    p = _profile(grammar=6, vocabulary=5, sentence_structure=6, fluency=5, accuracy=4)
    assert weakest_dimension(p) == ("accuracy", 4)


def test_weakest_dimension_tie_is_deterministic():
    p = _profile(grammar=3, vocabulary=3, sentence_structure=9, fluency=9, accuracy=9)
    assert weakest_dimension(p) == ("grammar", 3)
    p2 = _profile(grammar=9, vocabulary=3, sentence_structure=9, fluency=9, accuracy=9)
    assert weakest_dimension(p2) == ("vocabulary", 3)


def test_difficulty_overrides_the_models_own_suggestion(caplog):
    """The profile's recommended_difficulty used to be circular: we showed the
    model a value and it echoed it back. Scores must win."""
    p = DynamicProfile(
        skill_scores=SkillScores(grammar=6, vocabulary=5, sentence_structure=6,
                                 fluency=5, accuracy=4),
        recommended_difficulty="beginner",
    )
    with caplog.at_level(logging.INFO):
        d = build_session_directives(p, _plan())

    assert d.difficulty == "intermediate"  # average is 5.2
    assert any("difficulty" in r.message for r in caplog.records), "disagreement not logged"


# -------------------------------------------------------------------- pace --

@pytest.mark.parametrize("pace,expected_minutes", [
    ("slow", 12), ("normal", 20), ("fast", 28),
])
def test_pace_scales_session_length(pace, expected_minutes):
    p = _profile(grammar=6, vocabulary=6, sentence_structure=6, fluency=6, accuracy=6)
    p = p.model_copy(update={"recommended_pace": pace})
    d = build_session_directives(p, _plan(minutes=20))
    assert d.target_minutes == expected_minutes


def test_unknown_pace_falls_back_to_normal():
    p = _profile(grammar=6, vocabulary=6, sentence_structure=6, fluency=6, accuracy=6)
    p = p.model_copy(update={"recommended_pace": "turbo"})
    d = build_session_directives(p, _plan(minutes=20))
    assert d.target_minutes == 20


def test_exchanges_stay_within_bounds():
    p = _profile(grammar=6, vocabulary=6, sentence_structure=6, fluency=6, accuracy=6)
    for minutes in (1, 20, 500):
        d = build_session_directives(p, _plan(minutes=minutes))
        assert 4 <= d.target_exchanges <= 40


def test_missing_plan_uses_default_length():
    p = _profile(grammar=6, vocabulary=6, sentence_structure=6, fluency=6, accuracy=6)
    d = build_session_directives(p, None)
    assert d.target_minutes == 20


# ---------------------------------------------------------------- directives --

def test_rendered_directives_name_the_priority():
    p = _profile(grammar=6, vocabulary=5, sentence_structure=6, fluency=5, accuracy=4)
    text = build_session_directives(p, _plan()).render()

    assert "accuracy" in text
    assert "priority skill" in text
    assert "intermediate" in text


def test_every_dimension_has_a_playbook():
    """A dimension with no playbook would silently fall back to filler text."""
    from src.coach_policy import _PRIORITY_PLAYBOOK
    for dim in ("grammar", "vocabulary", "sentence_structure", "fluency", "accuracy"):
        p = _profile(**{dim: 2})
        d = build_session_directives(p, _plan())
        assert d.priority_dimension == dim
        text = d.render()
        assert _PRIORITY_PLAYBOOK[dim][:40] in text


def test_due_vocabulary_is_surfaced():
    p = _profile(grammar=6, vocabulary=6, sentence_structure=6, fluency=6, accuracy=6)
    due = [{"expression": "take off", "meaning": "to leave the ground"}]
    text = build_session_directives(p, _plan(), due_vocabulary=due).render()

    assert "due for review" in text
    assert "take off" in text


def test_no_vocabulary_section_when_nothing_due():
    p = _profile(grammar=6, vocabulary=6, sentence_structure=6, fluency=6, accuracy=6)
    assert "due for review" not in build_session_directives(p, _plan()).render()


def test_low_confidence_and_early_session_add_notes():
    p = DynamicProfile(
        skill_scores=SkillScores(grammar=6, vocabulary=6, sentence_structure=6,
                                 fluency=6, accuracy=6),
        confidence_in_level="low",
        lessons_completed=0,
        challenging_areas=["past perfect", "articles"],
    )
    text = build_session_directives(p, _plan()).render()
    assert "still uncertain" in text
    assert "early session" in text
    assert "past perfect" in text


def test_directives_render_with_default_instance():
    assert "difficulty" in SessionDirectives().render().lower()


def test_default_profile_produces_valid_directives():
    d = build_session_directives(DynamicProfile(), None)
    assert d.difficulty in ("beginner", "intermediate", "advanced", "expert")
    assert 4 <= d.target_exchanges <= 40
    assert d.priority_dimension in (
        "grammar", "vocabulary", "sentence_structure", "fluency", "accuracy")
