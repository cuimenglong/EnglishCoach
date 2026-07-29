from .utils import daily_log_path


SUMMARY_SYSTEM_PROMPT = (
    "You are a supportive English coach reviewing today's training session. "
    "Based on the entire conversation, generate a structured daily summary.\n\n"
    "Include the following sections:\n\n"
    "## Today's Topic\n"
    "[Briefly restate today's topic and focus]\n\n"
    "## Mistakes & Corrections\n"
    "- Original sentence: ... -> Corrected: ... (reason)\n"
    "[List each mistake the user made with the correction and a brief explanation]\n\n"
    "## New Expressions\n"
    "- Expression: meaning (example)\n"
    "[List any useful expressions or vocabulary that came up today]\n\n"
    "## Coach's Note\n"
    "[A paragraph of encouragement, noting what the user did well, "
    "what to focus on next, and a preview of tomorrow's topic]\n\n"
    "## Practice Suggestions\n"
    "[1-2 specific suggestions for what the user can review or practice on their own]\n\n"
    "Do NOT use Markdown formatting. Use plain text only.

Format the output in plain text. If there were no mistakes (unlikely but possible), "
    "note the user's accurate expression instead."
)


async def generate_summary(llm_client, conversation: list[dict], day: int, total_days: int) -> str:
    """Generate a daily summary from the conversation history and save it."""
    from datetime import date

    # Extract user and assistant messages (exclude system prompt)
    history_text = _conversation_to_text(conversation)

    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Here is the conversation from Day {day}/{total_days}. "
                f"Please generate a structured daily summary.\n\n{history_text}"
            ),
        },
    ]

    content, _ = await llm_client.chat(messages)

    # Add a header
    today = date.today()
    full_summary = f"# Daily Summary - Day {day}/{total_days}\n## {today.strftime('%A, %B %d, %Y')}\n\n{content}"

    # Save to file
    summary_path = daily_log_path()
    summary_path.write_text(full_summary, encoding="utf-8")

    return full_summary


def _conversation_to_text(conversation: list[dict]) -> str:
    """Convert conversation history to readable text for summary generation."""
    lines = []
    for msg in conversation:
        role = msg["role"]
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"**User**: {content}")
        elif role == "assistant":
            lines.append(f"**Coach**: {content}")
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
