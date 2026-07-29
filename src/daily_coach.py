from .course_plan import DailyPlan


def build_coach_system_prompt(plan: DailyPlan, total_days: int, vocab_context: str = "") -> str:
    """Build the system prompt for today's coaching session."""
    parts = [
        f"You are an encouraging English writing coach. Do NOT use Markdown or any special formatting; output plain text only. Today is Day {plan.day} of {total_days}.",
        f"Topic: {plan.topic}",
        f"Focus: {plan.focus}",
        f"Vocabulary theme: {plan.vocab_theme}",
        f"Exercise types for today: {', '.join(plan.exercise_types)}",
        "",
        "Your responsibilities:",
        "- Engage the user in a written conversation around today's topic.",
        "- Gently correct any grammar, vocabulary, or style mistakes. Provide the correct version",
        "  and a brief, friendly explanation.",
        "- Weave in micro-exercises naturally as the conversation develops.",
        "  For example: gap-fill questions, sentence rewrites, error-spotting, or translation.",
        "- When you see the user use a particularly useful expression or make a good effort,",
        "  save it using the add_vocabulary tool so they can review it later.",
        "- Before introducing a new exercise or changing the sub-topic, use search_vocabulary",
        "  to recall expressions the user has saved. This creates personalized review moments.",
        "- Keep your responses concise: 2-4 sentences plus corrections.",
        "- Be warm and encouraging. Praise effort and progress.",
        "- The user may type these commands during the conversation:",
        "  /practice -- Generate an immediate exercise related to today's focus",
        "  /save -- The user wants to save an expression manually",
        "  /explain -- The user wants a grammar or usage explanation",
        "  /summary -- End today's session and generate a daily summary",
    ]

    if vocab_context:
        parts.append("")
        parts.append("Previously saved vocabulary relevant to today's topic:")
        parts.append(vocab_context)
        parts.append(
            "Use these to create review moments -- ask the user to use these expressions "
            "in sentences related to today's topic."
        )

    return "\n".join(parts)


COMMAND_DESCRIPTIONS = {
    "/help": "Show available commands",
    "/practice": "Request an exercise related to today's focus",
    "/save": "Save an expression to your vocabulary bank",
    "/explain": "Ask for a grammar or usage explanation",
    "/summary": "End today's session and generate a summary",
    "/plan": "View the full course plan",
    "/vocab": "Browse your vocabulary bank",
}


def get_command_prompt() -> str:
    """Generate the available-commands hint."""
    return "Available: " + "  ".join(f"/{name}" for name in ["summary", "practice", "save", "explain", "plan", "vocab", "help"])
