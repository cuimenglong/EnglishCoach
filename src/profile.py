import json
import logging
from pydantic import BaseModel, Field, ValidationError

from .persona import CoachPersona, PERSONA_PRESETS, PERSONA_PRESET_LABELS

logger = logging.getLogger(__name__)


def _persona_option_lines() -> str:
    """Render the preset choices for the assessment prompt."""
    return "".join(
        f"     - {key}: {PERSONA_PRESET_LABELS[key]}\n"
        for key in PERSONA_PRESETS
    )


class UserProfile(BaseModel):
    level: str = ""
    strengths: list[str] = []
    weaknesses: list[str] = []
    goals: list[str] = []
    study_days: int = 14
    interest_topics: list[str] = []
    persona: CoachPersona = Field(default_factory=CoachPersona)


ASSESSMENT_SYSTEM_PROMPT = (
    "You are a friendly but thorough English assessment coach. You may use light Markdown for structure (bold, bullet lists); keep individual messages short. Your job is to assess the user's "
    "current English level through natural conversation.\n\n"
    "Guidelines:\n"
    "1. Start with a warm greeting and a simple question to get the user talking.\n"
    "2. Ask about their background with English (how long they've studied, where they use it).\n"
    "3. Explore different skill areas: grammar accuracy, vocabulary range, sentence structure, "
    "ability to express complex ideas.\n"
    "4. Ask about their learning goals (daily communication, business writing, exams, academic writing, etc.).\n"
    "5. Ask about topics they are interested in (technology, business, science, travel, culture, etc.).\n"
    "6. Ask how many days they would like to commit to a study plan (7, 14, 21, or 30 days).\n"
    "7. Ask what KIND of teacher they would like. Offer these options and let them\n"
    "   pick one or describe their own:\n"
    + _persona_option_lines()
    + "8. Keep the conversation encouraging and natural -- don't make it feel like a test.\n"
    "9. After 5-9 exchanges (once you have enough information), call the submit_assessment\n"
    "   function to provide the structured profile.\n\n"
    "IMPORTANT: Do NOT call submit_assessment before you have enough information about all fields. "
    "Be conversational first."
)


ASSESSMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_assessment",
            "description": "Submit the completed user assessment with structured profile data. Only call this when you have enough information about all fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "Estimated CEFR level (A1, A2, B1, B2, C1, C2)",
                    },
                    "strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of the user's strengths in English",
                    },
                    "weaknesses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of areas needing improvement",
                    },
                    "goals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "User's learning goals",
                    },
                    "study_days": {
                        "type": "integer",
                        "description": "Number of days for the study plan (7, 14, 21, or 30)",
                    },
                    "interest_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Topics the user is interested in discussing",
                    },
                    "persona": {
                        "type": "object",
                        "description": "How the user wants to be taught",
                        "properties": {
                            "preset": {
                                "type": "string",
                                "enum": list(PERSONA_PRESETS.keys()) + ["custom"],
                                "description": "Closest matching teacher style",
                            },
                            "warmth": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                                "description": "1 = reserved/professional, 5 = very warm and encouraging",
                            },
                            "strictness": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                                "description": "1 = correct only meaning-changing errors, 5 = correct everything",
                            },
                            "verbosity": {
                                "type": "string",
                                "enum": ["concise", "balanced", "detailed"],
                            },
                            "correction_style": {
                                "type": "string",
                                "enum": ["gentle", "balanced", "thorough"],
                            },
                            "accent": {
                                "type": "string",
                                "enum": ["neutral", "british", "american"],
                            },
                            "free_text": {
                                "type": "string",
                                "description": "Anything else the user said about how they want to be taught",
                            },
                        },
                        "required": ["preset", "warmth", "strictness", "verbosity", "correction_style"],
                    },
                },
                "required": ["level", "strengths", "weaknesses", "goals", "study_days", "interest_topics", "persona"],
            },
        },
    },
]


async def run_assessment_turn(
    llm_client,
    conversation: list[dict],
) -> tuple[list[dict], UserProfile | None]:
    """Send the conversation history to the LLM and process the response.

    Returns (updated_conversation, profile_or_None).
    The profile is only set when the LLM calls submit_assessment.
    """
    messages = [{"role": "system", "content": ASSESSMENT_SYSTEM_PROMPT}] + conversation

    content, tool_calls = await llm_client.chat(messages, tools=ASSESSMENT_TOOLS)

    profile = None
    for tc in tool_calls:
        if tc["name"] != "submit_assessment":
            continue
        try:
            profile = UserProfile(**tc["arguments"])
        except ValidationError as exc:
            # A malformed persona (or any other field) must not lose an
            # otherwise complete assessment.
            logger.warning("Assessment payload failed validation: %s", exc)
            data = dict(tc["arguments"])
            data.pop("persona", None)
            try:
                profile = UserProfile(**data)
            except ValidationError as exc2:
                logger.warning("Assessment payload still invalid without persona: %s", exc2)
                continue

    assistant_msg = {"role": "assistant", "content": content}
    if tool_calls:
        assistant_msg["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    # Must be a JSON string, not a dict: the OpenAI chat
                    # completions schema rejects a non-string here, which
                    # broke the turn after submit_assessment.
                    "arguments": json.dumps(tc["arguments"]),
                },
            }
            for tc in tool_calls
        ]
    conversation.append(assistant_msg)

    return conversation, profile
