from .utils import daily_log_path
from .dynamic_profile import PROFILE_UPDATE_TOOLS, format_profile_for_prompt


SUMMARY_SYSTEM_PROMPT = (
    "You are a supportive English coach reviewing today's training session. "
    "Based on the entire conversation, generate a structured daily summary.\n\n"
    "You may use Markdown for structure. Use these sections:\n\n"
    "## Today's Topic\n"
    "[Briefly restate today's topic and focus]\n\n"
    "## Mistakes & Corrections\n"
    "For each mistake, use a bullet like:\n"
    "- **original:** the user's sentence -> **corrected:** the fixed sentence\n"
    "  *why:* one line explaining the rule\n\n"
    "## New Expressions\n"
    "- **expression** - meaning *(example)*\n\n"
    "## Coach's Note\n"
    "[A paragraph of encouragement, noting what the user did well, "
    "what to focus on next, and a preview of tomorrow's topic]\n\n"
    "## Practice Suggestions\n"
    "[1-2 specific suggestions for what the user can review or practise on their own]\n\n"
    "If there were no mistakes (unlikely but possible), note the user's accurate expression instead."
)


async def generate_summary(llm_client, conversation: list[dict], day: int, total_days: int, current_profile=None):
    """Generate a daily summary from the conversation history and save it."""
    from datetime import date

    # Extract user and assistant messages (exclude system prompt)
    history_text = _conversation_to_text(conversation)
    profile_text = ""
    if current_profile:
        profile_text = format_profile_for_prompt(current_profile)

    user_content = f"Here is the conversation from Day {day}/{total_days}.\n\n"
    if profile_text:
        user_content += (
            "=== Student Profile (update this by calling update_dynamic_profile) ===\n"
            f"{profile_text}\n\n"
        )
    user_content += ""
    if profile_text:
        user_content += (
            "---\n"
            "IMPORTANT: In a single response, FIRST output the student-facing summary as plain text. "
            "THEN call update_dynamic_profile with the adjusted profile. "
            "Both outputs are required.\n\n---\n\n"
        )
    user_content += history_text
    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        content, tool_calls = await llm_client.chat(messages, tools=PROFILE_UPDATE_TOOLS)
    except Exception:
        # Some API endpoints do not support function calling; keep summary working.
        content, tool_calls = await llm_client.chat(messages)
    profile_data = None
    for tc in tool_calls:
        if tc["name"] == "update_dynamic_profile":
            profile_data = tc["arguments"]
            profile_data["lessons_completed"] = (current_profile.lessons_completed if current_profile else 0) + 1

    # Add a header
    today = date.today()
    full_summary = (
        f"Daily Summary - Day {day}/{total_days}\n"
        f"{today.strftime('%A, %B %d, %Y')}\n\n"
        f"{content}"
    )

    # Save to file
    summary_path = daily_log_path()
    summary_path.write_text(full_summary, encoding="utf-8")

    return full_summary, profile_data


def _conversation_to_text(conversation: list[dict]) -> str:
    """Convert conversation history to readable text for summary generation."""
    lines = []
    for msg in conversation:
        role = msg["role"]
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"User: {content}")
        elif role == "assistant":
            lines.append(f"Coach: {content}")
    return "\n\n".join(lines)


def get_summary_dates() -> list[str]:
    """Get list of dates that have saved summaries."""
    import os
    from .utils import DATA_DIR

    log_dir = DATA_DIR / "daily_logs"
    if not log_dir.exists():
        return []

    files = sorted(log_dir.glob("*.md"), reverse=True)
    return [f.stem for f in files]


def load_summary(date_str: str) -> str | None:
    """Load a specific day's summary."""
    path = daily_log_path(date_str)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None
