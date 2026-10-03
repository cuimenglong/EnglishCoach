from .course_plan import DailyPlan


def build_coach_system_prompt(
    plan: DailyPlan,
    total_days: int,
    vocab_context: str = "",
    profile_context: str = "",
    persona_context: str = "",
    session_directives: str = "",
) -> str:
    """Build the system prompt for today's coaching session.

    Order matters: today's concrete target first, then the persona that shapes
    HOW to teach, then the profile, then optional vocabulary context.
    """
    parts = [
        f"You are an English writing coach. Today is Day {plan.day} of {total_days}.",
        f"Topic: {plan.topic}",
        f"Focus: {plan.focus}",
    ]

    if plan.knowledge_points:
        points = "\n".join(
            f"  {i}. {kp.title}"
            + (f" -- {kp.detail}" if kp.detail else "")
            + (f"  e.g. {kp.example}" if kp.example else "")
            for i, kp in enumerate(plan.knowledge_points, 1)
        )
        parts += [
            "",
            "TODAY'S KNOWLEDGE POINTS (these are the concrete things to cover):",
            points,
            "",
            "Teach these specific points. Do not drift into unrelated grammar or",
            "vocabulary, and do not cover all of them in the first message.",
        ]

    parts += [
        f"Vocabulary theme: {plan.vocab_theme}",
        f"Exercise types for today: {', '.join(plan.exercise_types)}",
    ]

    if plan.extension:
        parts += [
            "",
            f"OPTIONAL STRETCH (do not force it): {plan.extension}",
            "Only bring this in at the end, and only if the learner is keeping up.",
        ]

    parts += [
        "",
        "Your responsibilities:",
        "- Engage the user in a written conversation around today's topic.",
        "- Gently correct any grammar, vocabulary, or style mistakes. Provide the correct version",
        "  and a brief, friendly explanation.",
        "- Weave in micro-exercises naturally as the conversation develops.",
        "  For example: gap-fill questions, sentence rewrites, error-spotting, or translation.",
        "- When you see the user use a particularly useful expression or make a good effort,",
        "  save it using the add_vocabulary tool so they can review it later.",
        "- Use search_vocabulary to recall expressions the user has saved. This creates",
        "  personalized review moments.",
        "- The user may type these commands during the conversation:",
        "  /practice -- Generate an immediate exercise related to today's focus",
        "  /save -- The user wants to save an expression manually",
        "  /explain -- The user wants a grammar or usage explanation",
        "  /review -- Start flashcard review of saved expressions",
        "  /profile -- Show the learner's skill profile",
        "  /summary -- End today's session and generate a daily summary",
    ]

    if session_directives:
        parts += ["", "=== SESSION DIRECTIVES (follow these today) ===", session_directives]

    if persona_context:
        parts += ["", persona_context]

    if profile_context:
        parts += ["", "=== Student Profile ===", profile_context]

    if vocab_context:
        parts += ["", "Previously saved vocabulary relevant to today's topic:"]
        parts += [vocab_context]
        parts += [
            "Use these to create review moments -- ask the user to use these expressions "
            "in sentences related to today's topic."
        ]

    return "\n".join(parts)


COMMAND_DESCRIPTIONS = {
    "/help": "Show available commands",
    "/practice": "Request an exercise related to today's focus",
    "/save": "Save an expression to your vocabulary bank",
    "/explain": "Ask for a grammar or usage explanation",
    "/summary": "End today's session and generate a summary",
    "/plan": "View the full course plan",
    "/vocab": "Browse your vocabulary bank",
    "/review": "Flashcard review of saved expressions",
    "/profile": "Show your skill profile",
}


def get_command_prompt() -> str:
    """Generate the available-commands hint."""
    return "Available: " + "  ".join(
        f"/{name}" for name in ["summary", "practice", "save", "explain", "review", "profile", "plan", "vocab", "help"]
    )
