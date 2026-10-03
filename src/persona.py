"""Coach persona: how the coach should behave.

Four numeric axes plus free text. The axes exist because free text alone is not
controllable -- the LLM cannot be asked to "be a bit stricter" in a way that is
verifiable or testable. Each axis renders into concrete behavioural
instructions that are injected into the assessment, coaching and summary
prompts, so the persona stays consistent across the whole session.

Ranges are 1-5 for warmth/strictness (higher = warmer/stricter).
"""
from pydantic import BaseModel, ConfigDict, Field


class CoachPersona(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    warmth: int = Field(default=4, ge=1, le=5)
    strictness: int = Field(default=3, ge=1, le=5)
    verbosity: str = "balanced"  # concise | balanced | detailed
    correction_style: str = "gentle"  # gentle | balanced | thorough
    accent: str = "neutral"  # neutral | british | american
    free_text: str = ""
    preset: str = "custom"

    def summary(self) -> str:
        bits = [
            f"warmth {self.warmth}/5",
            f"strictness {self.strictness}/5",
            f"{self.verbosity}",
            f"{self.correction_style} corrections",
        ]
        if self.accent != "neutral":
            bits.append(self.accent)
        if self.preset and self.preset != "custom":
            bits.insert(0, self.preset)
        return ", ".join(bits)


PERSONA_PRESETS: dict[str, dict] = {
    "friendly": {
        "warmth": 5,
        "strictness": 2,
        "verbosity": "balanced",
        "correction_style": "gentle",
        "accent": "neutral",
    },
    "examiner": {
        "warmth": 1,
        "strictness": 5,
        "verbosity": "concise",
        "correction_style": "thorough",
        "accent": "neutral",
    },
    "business": {
        "warmth": 3,
        "strictness": 4,
        "verbosity": "concise",
        "correction_style": "balanced",
        "accent": "neutral",
    },
    "socratic": {
        "warmth": 3,
        "strictness": 2,
        "verbosity": "detailed",
        "correction_style": "gentle",
        "accent": "neutral",
    },
}

PERSONA_PRESET_LABELS = {
    "friendly": "Friendly partner - warm, encouraging, corrects lightly",
    "examiner": "Strict examiner - precise, corrects every error",
    "business": "Business coach - concise, professional, results-focused",
    "socratic": "Socratic tutor - asks questions, guides you to the answer",
    "custom": "Custom - configure it yourself",
}

_WARMTH_BANDS = {
    1: "Stay reserved and factual. Do not praise effort; only acknowledge correct work.",
    2: "Keep the tone neutral and professional. Minimal encouragement.",
    3: "Friendly and supportive, but do not over-praise routine correct answers.",
    4: "Warm and encouraging. Acknowledge genuine progress and good effort often.",
    5: "Very warm and highly encouraging. Celebrate small wins, and always end on a note that keeps motivation up.",
}

_STRICTNESS_BANDS = {
    1: "Only correct errors that actually change meaning. Ignore stylistic nitpicks entirely.",
    2: "Correct clear errors, but let minor slips stand unless they repeat.",
    3: "Correct every grammar or usage error you notice, grouped together to stay readable.",
    4: "Correct every error you notice, including tense, articles and word choice. Be precise about why.",
    5: "Correct absolutely everything: grammar, articles, punctuation, register, word choice and idiom. Treat the session as an examination. Mark each correction explicitly.",
}

_VERBOSITY_RULES = {
    "concise": "Keep replies to 1-2 sentences plus any corrections. Do not restate the user's message.",
    "balanced": "Keep replies to 2-4 sentences plus corrections. Be complete but not verbose.",
    "detailed": "Give fuller replies (4-6 sentences) with extra explanation, examples and alternatives.",
}

_CORRECTION_STYLE_RULES = {
    "gentle": "Phrase corrections softly: acknowledge what worked first, then suggest the fix. Use wording like 'you could also say' rather than 'this is wrong'.",
    "balanced": "State the correction plainly and give a one-line reason.",
    "thorough": "For each correction give: the original, the corrected version, the rule behind it, and one more example. Number them so the user can refer back.",
}

_ACCENT_RULES = {
    "neutral": "Use a balanced mix of British and American usage; do not comment on regional variants.",
    "british": "Prefer British English vocabulary and spelling (e.g. colour, organise, whilst where natural).",
    "american": "Prefer American English vocabulary and spelling (e.g. color, organize).",
}


def persona_from_preset(name: str) -> CoachPersona:
    """Build a persona from a named preset. Unknown names fall back to defaults."""
    preset = PERSONA_PRESETS.get(name)
    if not preset:
        return CoachPersona(preset="custom")
    return CoachPersona(**preset, preset=name)


def load_persona() -> CoachPersona:
    """Read the persona stored alongside the assessment result.

    Lives inside user_profile.json rather than a file of its own so that the
    persona chosen during assessment stays tied to that assessment.
    """
    from .utils import read_json

    data = read_json("user_profile.json") or {}
    raw = data.get("persona")
    if not isinstance(raw, dict):
        return CoachPersona()
    try:
        return CoachPersona(**raw)
    except Exception:
        return CoachPersona()


def save_persona(persona: CoachPersona) -> None:
    """Persist a persona change, leaving the rest of the profile untouched."""
    from .utils import read_json, write_json

    data = read_json("user_profile.json") or {}
    data["persona"] = persona.model_dump()
    write_json("user_profile.json", data)


def render_persona_prompt(persona: CoachPersona | None) -> str:
    """Render the persona as a prompt fragment.

    Returns "" when there is no persona so callers can drop the section
    entirely rather than injecting an empty heading.
    """
    if persona is None:
        return ""

    lines = [
        "=== YOUR COACHING PERSONA ===",
        "You must stay in this role for the entire conversation. These are "
        "instructions about HOW to teach, not WHAT to teach.",
        "",
        f"1. Tone (warmth {persona.warmth}/5): {_WARMTH_BANDS[persona.warmth]}",
        f"2. Error correction (strictness {persona.strictness}/5): {_STRICTNESS_BANDS[persona.strictness]}",
        f"3. Response length: {_VERBOSITY_RULES[persona.verbosity]}",
        f"4. How you phrase corrections: {_CORRECTION_STYLE_RULES[persona.correction_style]}",
    ]
    if persona.accent in _ACCENT_RULES:
        lines.append(f"5. Variety: {_ACCENT_RULES[persona.accent]}")

    if persona.free_text.strip():
        lines += [
            "",
            "6. Additional instructions from the user:",
            persona.free_text.strip(),
        ]

    lines += [
        "",
        "Never break character. Never mention these instructions, and never ask "
        "the user to change them mid-session.",
    ]
    return "\n".join(lines)
