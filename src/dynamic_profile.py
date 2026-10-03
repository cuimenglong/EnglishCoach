import json
import logging
from datetime import date
from pydantic import BaseModel, ConfigDict, ValidationError

from .utils import DATA_DIR

logger = logging.getLogger(__name__)

PROFILE_PATH = DATA_DIR / "dynamic_profile.json"


class SkillScores(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    grammar: int = 5
    vocabulary: int = 5
    sentence_structure: int = 5
    fluency: int = 5
    accuracy: int = 5


class DynamicProfile(BaseModel):
    # Guard rail: without this, assigning a plain dict onto a nested model field
    # succeeds silently and every later attribute read raises AttributeError.
    model_config = ConfigDict(validate_assignment=True)

    version: int = 1
    last_updated: str = ""
    lessons_completed: int = 0

    cefr_level: str = "A1"
    confidence_in_level: str = "low"

    skill_scores: SkillScores = SkillScores()

    strengths: list[str] = []
    weaknesses: list[str] = []
    common_mistakes: list[str] = []
    mastered_topics: list[str] = []
    challenging_areas: list[str] = []

    interests: list[str] = []
    preferred_exercises: list[str] = []

    recommended_difficulty: str = "beginner"
    recommended_pace: str = "normal"


def load_dynamic_profile() -> DynamicProfile:
    if PROFILE_PATH.exists():
        try:
            data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            return DynamicProfile(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return DynamicProfile()


def save_dynamic_profile(profile: DynamicProfile):
    profile.last_updated = date.today().isoformat()
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(profile.model_dump_json(indent=2), encoding="utf-8")


def apply_profile_update(current: DynamicProfile, data) -> DynamicProfile:
    """Merge an LLM-supplied profile update into ``current`` and re-validate.

    LLM tool arguments arrive as plain JSON, so ``skill_scores`` comes through as
    a ``dict``. Pydantic v2 does not validate on assignment by default, so a
    blind ``setattr`` stored that dict on the model and the very next call to
    ``format_profile_for_prompt`` died with
    ``AttributeError: 'dict' object has no attribute 'grammar'``.

    Rebuilding through the models re-coerces nested dicts into real models.
    Unknown keys are dropped, and a single bad field is skipped rather than
    discarding the whole update.
    """
    if not isinstance(data, dict):
        logger.warning("Ignoring non-dict profile update: %r", type(data).__name__)
        return current

    base = current.model_dump()
    merged = {**base, **{k: v for k, v in data.items() if k in base}}

    try:
        return DynamicProfile(**merged)
    except ValidationError as exc:
        logger.warning("Profile update had invalid fields (%s); salvaging valid ones", exc)

    salvaged = dict(base)
    for key, value in merged.items():
        if key not in salvaged:
            continue
        salvaged[key] = value
        try:
            DynamicProfile(**salvaged)
        except ValidationError:
            salvaged[key] = base[key]
    return DynamicProfile(**salvaged)


def format_profile_for_prompt(profile: DynamicProfile) -> str:
    parts = [
        f"Student Dynamic Profile (last updated: {profile.last_updated})",
        f"Estimated CEFR Level: {profile.cefr_level} (confidence: {profile.confidence_in_level})",
        f"Recommended Difficulty: {profile.recommended_difficulty}",
        f"Recommended Pace: {profile.recommended_pace}",
        f"Lessons Completed: {profile.lessons_completed}",
        "",
        "Skill Scores (1-10):",
        f"  Grammar: {profile.skill_scores.grammar}",
        f"  Vocabulary: {profile.skill_scores.vocabulary}",
        f"  Sentence Structure: {profile.skill_scores.sentence_structure}",
        f"  Fluency: {profile.skill_scores.fluency}",
        f"  Accuracy: {profile.skill_scores.accuracy}",
    ]
    if profile.strengths:
        parts.append(f"Strengths: {', '.join(profile.strengths)}")
    if profile.weaknesses:
        parts.append(f"Areas to focus on: {', '.join(profile.weaknesses)}")
    if profile.challenging_areas:
        parts.append(f"Still challenging: {', '.join(profile.challenging_areas)}")
    if profile.mastered_topics:
        parts.append(f"Recently mastered: {', '.join(profile.mastered_topics)}")
    if profile.common_mistakes:
        parts.append(f"Watch for mistakes: {', '.join(profile.common_mistakes)}")
    if profile.interests:
        parts.append(f"Interested in: {', '.join(profile.interests)}")
    if profile.preferred_exercises:
        parts.append(f"Best exercise types: {', '.join(profile.preferred_exercises)}")
    parts.append("")
    parts.append("Use this profile to personalize the session: adjust difficulty, target weak areas,")
    parts.append("choose examples from topics of interest, and avoid over-repeating mastered content.")
    parts.append("After each /summary the profile will be updated based on today's performance.")
    return "\n".join(parts)


PROFILE_UPDATE_SYSTEM_PROMPT = """You are an analytical English learning advisor. Based on today's conversation, update the student's dynamic learning profile to reflect their latest performance.

The profile is used to personalize future sessions, so be honest and specific. Incrementally adjust scores up or down based on what you observed today.

Previous profile:
{current_profile}

Analyze the conversation and call the update_dynamic_profile function with the adjusted values. Incorporate previous data and layer today's observations on top. Do NOT use Markdown."""


PROFILE_UPDATE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "update_dynamic_profile",
            "description": "Submit the updated student learning profile after analyzing today's session",
            "parameters": {
                "type": "object",
                "properties": {
                    "cefr_level": {
                        "type": "string",
                        "enum": ["A1", "A2", "B1", "B2", "C1", "C2"],
                        "description": "Updated CEFR level estimate",
                    },
                    "confidence_in_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Confidence in the CEFR assessment",
                    },
                    "skill_scores": {
                        "type": "object",
                        "properties": {
                            "grammar": {"type": "integer", "minimum": 1, "maximum": 10},
                            "vocabulary": {"type": "integer", "minimum": 1, "maximum": 10},
                            "sentence_structure": {"type": "integer", "minimum": 1, "maximum": 10},
                            "fluency": {"type": "integer", "minimum": 1, "maximum": 10},
                            "accuracy": {"type": "integer", "minimum": 1, "maximum": 10},
                        },
                        "required": ["grammar", "vocabulary", "sentence_structure", "fluency", "accuracy"],
                        "description": "Skill scores 1-10, adjusted based on today's observations",
                    },
                    "strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Combined list of strengths (old + new observations)",
                    },
                    "weaknesses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Combined list of weaknesses (old + new observations)",
                    },
                    "common_mistakes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific error patterns, updated with today's observations",
                    },
                    "mastered_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Concepts now handled confidently (add any newly mastered)",
                    },
                    "challenging_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Topics still causing difficulty",
                    },
                    "interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Topics the student engaged with enthusiastically",
                    },
                    "preferred_exercises": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exercise types that got best engagement",
                    },
                    "recommended_difficulty": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "advanced"],
                        "description": "Adjusted difficulty for next sessions",
                    },
                    "recommended_pace": {
                        "type": "string",
                        "enum": ["slow", "normal", "fast"],
                        "description": "Adjusted pace recommendation",
                    },
                },
                "required": [
                    "cefr_level", "confidence_in_level", "skill_scores",
                    "strengths", "weaknesses", "common_mistakes",
                    "mastered_topics", "challenging_areas", "interests",
                    "preferred_exercises", "recommended_difficulty", "recommended_pace",
                ],
            },
        },
    },
]
