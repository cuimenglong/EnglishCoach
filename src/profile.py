from pydantic import BaseModel


class UserProfile(BaseModel):
    level: str = ""
    strengths: list[str] = []
    weaknesses: list[str] = []
    goals: list[str] = []
    study_days: int = 14
    interest_topics: list[str] = []


ASSESSMENT_SYSTEM_PROMPT = (
    "You are a friendly but thorough English assessment coach. Do NOT use Markdown formatting; output plain text only. Your job is to assess the user's "
    "current English level through natural conversation.\n\n"
    "Guidelines:\n"
    "1. Start with a warm greeting and a simple question to get the user talking.\n"
    "2. Ask about their background with English (how long they've studied, where they use it).\n"
    "3. Explore different skill areas: grammar accuracy, vocabulary range, sentence structure, "
    "ability to express complex ideas.\n"
    "4. Ask about their learning goals (daily communication, business writing, exams, academic writing, etc.).\n"
    "5. Ask about topics they are interested in (technology, business, science, travel, culture, etc.).\n"
    "6. Ask how many days they would like to commit to a study plan (7, 14, 21, or 30 days).\n"
    "7. Keep the conversation encouraging and natural -- don't make it feel like a test.\n"
    "8. After 5-8 exchanges (once you have enough information), call the submit_assessment function "
    "to provide the structured profile.\n\n"
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
                },
                "required": ["level", "strengths", "weaknesses", "goals", "study_days", "interest_topics"],
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
        if tc["name"] == "submit_assessment":
            profile = UserProfile(**tc["arguments"])

    assistant_msg = {"role": "assistant", "content": content}
    if tool_calls:
        assistant_msg["tool_calls"] = [
            {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
            for tc in tool_calls
        ]
    conversation.append(assistant_msg)

    return conversation, profile
