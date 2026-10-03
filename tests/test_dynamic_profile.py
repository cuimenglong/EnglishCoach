"""P0-1: the /summary profile update must not corrupt the model.

The old code did `setattr(self.profile, key, value)` for every key the LLM
returned. Pydantic v2 does not validate on assignment by default, so
`skill_scores` -- which arrives from json.loads as a plain dict -- replaced the
SkillScores model in place. The next line, format_profile_for_prompt, then died
with `AttributeError: 'dict' object has no attribute 'grammar'` on the first
/summary of every session.
"""
import pytest
from pydantic import ValidationError

from src.dynamic_profile import (
    DynamicProfile,
    SkillScores,
    apply_profile_update,
    format_profile_for_prompt,
    load_dynamic_profile,
    save_dynamic_profile,
)


def _llm_update(**overrides):
    """Exactly the shape llm_client.chat() hands back (plain JSON, not models)."""
    data = {
        "cefr_level": "B1",
        "confidence_in_level": "medium",
        "skill_scores": {
            "grammar": 6,
            "vocabulary": 5,
            "sentence_structure": 6,
            "fluency": 5,
            "accuracy": 4,
        },
        "strengths": ["fluent in daily conversation"],
        "weaknesses": ["article usage", "tense consistency"],
        "common_mistakes": ["missing articles"],
        "mastered_topics": ["present simple"],
        "challenging_areas": ["past perfect"],
        "interests": ["technology"],
        "preferred_exercises": ["gap_fill"],
        "recommended_difficulty": "intermediate",
        "recommended_pace": "normal",
        "lessons_completed": 1,
    }
    data.update(overrides)
    return data


def test_update_revalidates_nested_model():
    profile = apply_profile_update(DynamicProfile(), _llm_update())

    assert isinstance(profile.skill_scores, SkillScores)
    assert profile.skill_scores.grammar == 6
    assert profile.cefr_level == "B1"


def test_format_profile_after_update_does_not_crash():
    """The exact call that used to raise AttributeError on the first /summary."""
    profile = apply_profile_update(DynamicProfile(), _llm_update())

    text = format_profile_for_prompt(profile)  # must not raise

    assert "Grammar: 6" in text
    assert "B1" in text


def test_update_drops_unknown_keys():
    profile = apply_profile_update(DynamicProfile(), _llm_update(junk_field="nope"))

    assert not hasattr(profile, "junk_field")


def test_update_salvages_valid_fields_when_one_is_invalid():
    """A single bad nested value must not discard the rest of the update."""
    profile = apply_profile_update(
        DynamicProfile(),
        _llm_update(skill_scores={"grammar": "not-an-int"}),
    )

    # The unusable field keeps its default, the other update fields still land.
    assert isinstance(profile.skill_scores, SkillScores)
    assert profile.skill_scores.grammar == 5
    assert profile.cefr_level == "B1"
    assert profile.weaknesses == ["article usage", "tense consistency"]


def test_update_preserves_fields_the_llm_omitted():
    profile = DynamicProfile(recommended_pace="slow")
    update = _llm_update()
    del update["recommended_pace"]

    merged = apply_profile_update(profile, update)

    assert merged.recommended_pace == "slow"


def test_update_ignores_non_dict():
    profile = DynamicProfile(cefr_level="B2")

    assert apply_profile_update(profile, None) is profile
    assert apply_profile_update(profile, ["not", "a", "dict"]) is profile


def test_update_increments_lessons_completed():
    profile = DynamicProfile(lessons_completed=4)

    merged = apply_profile_update(profile, _llm_update(lessons_completed=5))

    assert merged.lessons_completed == 5


def test_saved_profile_round_trips_as_a_model():
    """Regression: the corrupted dict used to be written to disk."""
    profile = apply_profile_update(DynamicProfile(), _llm_update())
    save_dynamic_profile(profile)

    reloaded = load_dynamic_profile()

    assert isinstance(reloaded.skill_scores, SkillScores)
    format_profile_for_prompt(reloaded)


def test_assignment_guardrail_rejects_bad_values():
    """validate_assignment should stop corruption at the source."""
    profile = DynamicProfile()

    with pytest.raises(ValidationError):
        profile.skill_scores = {"grammar": "not-an-int"}
