"""Persona model, presets and prompt rendering."""
import pytest
from pydantic import ValidationError

from src.persona import (
    CoachPersona,
    PERSONA_PRESETS,
    persona_from_preset,
    render_persona_prompt,
    load_persona,
    save_persona,
)


def test_every_preset_renders():
    for name in PERSONA_PRESETS:
        persona = persona_from_preset(name)
        fragment = render_persona_prompt(persona)
        assert fragment
        assert "COACHING PERSONA" in fragment


def test_preset_is_remembered():
    assert persona_from_preset("examiner").preset == "examiner"
    assert persona_from_preset("nope").preset == "custom"


def test_warmth_and_strictness_actually_change_the_prompt():
    cold = render_persona_prompt(CoachPersona(warmth=1, strictness=5))
    warm = render_persona_prompt(CoachPersona(warmth=5, strictness=1))

    assert cold != warm
    assert "Correct absolutely everything" in cold
    assert "warm and highly encouraging" in warm.lower()
    assert "actually change meaning" in warm  # strictness 1


@pytest.mark.parametrize("axis,low,high", [
    ("verbosity", "concise", "detailed"),
    ("correction_style", "gentle", "thorough"),
    ("accent", "neutral", "british"),
])
def test_each_axis_changes_the_prompt(axis, low, high):
    a = render_persona_prompt(CoachPersona(**{axis: low}))
    b = render_persona_prompt(CoachPersona(**{axis: high}))
    assert a != b


def test_out_of_range_is_rejected():
    with pytest.raises(ValidationError):
        CoachPersona(warmth=9)
    with pytest.raises(ValidationError):
        CoachPersona(strictness=0)


def test_free_text_is_included():
    fragment = render_persona_prompt(
        CoachPersona(free_text="Never use idioms, keep it plain")
    )
    assert "Never use idioms" in fragment


def test_none_persona_renders_empty():
    """Callers drop the section entirely rather than inject an empty heading."""
    assert render_persona_prompt(None) == ""


def test_save_and_load_round_trip(temp_data_dir):
    persona = persona_from_preset("business")
    save_persona(persona)
    assert load_persona() == persona


def test_load_without_profile_returns_default(temp_data_dir):
    assert load_persona() == CoachPersona()


def test_load_ignores_corrupt_persona(temp_data_dir):
    from src.utils import write_json
    write_json("user_profile.json", {"level": "B1", "persona": "not-a-dict"})
    assert load_persona() == CoachPersona()


def test_load_ignores_invalid_persona_fields(temp_data_dir):
    from src.utils import write_json
    write_json("user_profile.json", {"persona": {"warmth": 99}})
    assert load_persona() == CoachPersona()


def test_save_preserves_other_profile_fields(temp_data_dir):
    from src.utils import read_json, write_json
    write_json("user_profile.json", {"level": "B2", "last_completed_day": 3})

    save_persona(persona_from_preset("socratic"))

    data = read_json("user_profile.json")
    assert data["level"] == "B2"
    assert data["last_completed_day"] == 3
    assert data["persona"]["preset"] == "socratic"
