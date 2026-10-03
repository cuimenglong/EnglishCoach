from pydantic import BaseModel, ConfigDict, Field
from .profile import UserProfile
from .llm_client import LLMClient
from .utils import read_json, write_json

# Bump when the persisted plan shape changes. CoursePlan.is_current() compares
# against it and callers regenerate the plan when it does not match, so an old
# plan file can never be read into the new model.
PLAN_SCHEMA_VERSION = 2


class KnowledgePoint(BaseModel):
    """One concrete, teachable thing for a day.

    Deliberately small: the point is that the LLM has to commit to a specific
    rule or structure rather than a vague theme like "tense practice".
    """
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    title: str
    detail: str = ""
    example: str = ""


class DailyPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day: int
    topic: str
    focus: str
    exercise_types: list[str]
    vocab_theme: str
    # --- added in schema v2 ---
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
    # Stretch material: optional, may be skipped without falling behind.
    extension: str = ""
    estimated_minutes: int = 20
    # Set when the plan is rewritten mid-course so the UI can show it changed.
    revised: bool = False


class CoursePlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_days: int
    days: list[DailyPlan]
    # Default is deliberately 1, NOT the current version: a plan file written
    # before versioning existed has no such key, so it must load as stale and
    # trigger regeneration rather than silently passing is_current().
    schema_version: int = 1
    created_at: str = ""
    revised_at: str = ""

    def is_current(self) -> bool:
        return self.schema_version == PLAN_SCHEMA_VERSION

    def day_by_number(self, day: int) -> DailyPlan | None:
        for d in self.days:
            if d.day == day:
                return d
        return None

    def future_days(self, from_day: int) -> list[DailyPlan]:
        """Days not yet completed, in day order.

        This is the ONLY part a revision may touch. Sorting keeps the revision
        prompt and the merge deterministic.
        """
        return sorted((d for d in self.days if d.day >= from_day), key=lambda d: d.day)



COURSE_PLAN_SYSTEM_PROMPT = (
    "You are a curriculum designer specialized in English language learning.\n\n"
    "Create a structured {total_days}-day course plan for the user profile below.\n\n"
    "The plan must:\n"
    "- Progress naturally from foundational to more advanced skills\n"
    "- Be tailored to the user's level, goals, and interests\n"
    "- Name CONCRETE knowledge points, not vague themes\n\n"
    "CRITICAL - knowledge point quality:\n"
    "A knowledge point is one specific, teachable idea: a grammar structure, a\n"
    "word-formation pattern, a discourse marker, a collocation family, a register\n"
    "distinction. Every day must have at least 1 and at most 3.\n"
    "  GOOD: 'Present Perfect vs Past Simple', 'Countable vs uncountable nouns with quantifiers',\n"
    "        'Hedging language (might / tend to / arguably)', 'Collocations: make vs do'\n"
    "  BAD:  'Tenses', 'Vocabulary building', 'Grammar practice'\n"
    "Each knowledge point needs a short id (snake_case), a title, one sentence of\n"
    "detail explaining what the learner will be able to do, and a short example.\n"
    "Knowledge points must not repeat across days.\n\n"
    "Each day also needs:\n"
    "- extension: one optional stretch idea that goes beyond the core point. The\n"
    "  learner may skip it without falling behind, so keep it genuinely optional.\n"
    "- estimated_minutes: realistic time for the day's practice (15-35).\n\n"
    "Available exercise types (mix them throughout the plan):\n"
    "- free_writing: Open-ended conversation on a topic with coach corrections\n"
    "- gap_fill: Complete sentences with missing words targeting specific grammar/vocab\n"
    "- sentence_rewriting: Rewrite sentences using target structures\n"
    "- error_finding: Find and correct errors in sentences or a short paragraph\n"
    "- translation_challenge: Translate sentences from your native language to English\n"
    "- paragraph_writing: Write a short paragraph (4-6 sentences) on a given topic\n"
    "- role_play: Practice a real-life scenario (job interview, ordering food, etc.)\n"
    "- vocabulary_in_context: Use target vocabulary in your own sentences\n"
    "- opinion_expression: Express and support an opinion on a topic\n"
    "- summary_writing: Read a short passage and write a summary\n\n"
    "Call the submit_course_plan function with the complete plan."
)


COURSE_PLAN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_course_plan",
            "description": "Submit the generated course plan",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "day": {"type": "integer"},
                                "topic": {"type": "string", "description": "Day topic title"},
                                "focus": {"type": "string", "description": "Specific skill focus for the day"},
                                "knowledge_points": {
                                    "type": "array",
                                    "description": "1-3 concrete knowledge points for this day",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {
                                                "type": "string",
                                                "description": "Short snake_case identifier",
                                            },
                                            "title": {
                                                "type": "string",
                                                "description": "The specific structure or concept",
                                            },
                                            "detail": {
                                                "type": "string",
                                                "description": "One sentence: what the learner will be able to do",
                                            },
                                            "example": {
                                                "type": "string",
                                                "description": "A short example sentence or two",
                                            },
                                        },
                                        "required": ["title", "detail"],
                                    },
                                },
                                "extension": {
                                    "type": "string",
                                    "description": "Optional stretch idea beyond the core point; safe to skip",
                                },
                                "exercise_types": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of exercise types for this day",
                                },
                                "vocab_theme": {
                                    "type": "string",
                                    "description": "Vocabulary theme for the day",
                                },
                                "estimated_minutes": {
                                    "type": "integer",
                                    "description": "Realistic minutes for the day (15-35)",
                                },
                            },
                            "required": [
                                "day", "topic", "focus", "knowledge_points",
                                "exercise_types", "vocab_theme",
                            ],
                        },
                    },
                },
                "required": ["days"],
            },
        },
    },
]


async def generate_course_plan(llm: LLMClient, profile: UserProfile) -> CoursePlan:
    """Generate a complete course plan based on the user profile."""
    from datetime import date

    profile_json = profile.model_dump_json(indent=2)
    system_prompt = COURSE_PLAN_SYSTEM_PROMPT.format(total_days=profile.study_days)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Here is the user's profile:\n{profile_json}\n\n"
                f"Please create a {profile.study_days}-day course plan tailored to this user."
            ),
        },
    ]

    content, tool_calls = await llm.chat(messages, tools=COURSE_PLAN_TOOLS)

    for tc in tool_calls:
        if tc["name"] == "submit_course_plan":
            plan = build_plan_from_days(tc["arguments"]["days"])
            plan.created_at = date.today().isoformat()
            write_json("course_plan.json", plan.model_dump())
            return plan

    raise RuntimeError("LLM did not return a valid course plan.")


def build_plan_from_days(days_data) -> CoursePlan:
    """Build a plan from raw LLM day dicts, skipping days that fail validation.

    One malformed day should not throw away an otherwise good 14-day plan.
    """
    days: list[DailyPlan] = []
    for raw in days_data or []:
        try:
            days.append(DailyPlan(**raw))
        except (TypeError, ValueError):
            continue
    return CoursePlan(
        total_days=len(days),
        days=days,
        schema_version=PLAN_SCHEMA_VERSION,
    )


def load_course_plan() -> CoursePlan | None:
    """Load the plan, or None if absent / written by an older schema.

    Returning None on a version mismatch is what triggers regeneration: callers
    already treat "no plan" as "needs planning".
    """
    data = read_json("course_plan.json")
    if not data:
        return None
    try:
        plan = CoursePlan(**data)
    except (TypeError, ValueError):
        return None
    if not plan.is_current():
        return None
    if not plan.days:
        return None
    return plan


def plan_is_stale() -> bool:
    """True when a plan file exists but predates the current schema."""
    data = read_json("course_plan.json")
    if not data:
        return False
    try:
        return CoursePlan(**data).schema_version != PLAN_SCHEMA_VERSION
    except (TypeError, ValueError):
        return True


PLAN_REVISION_SYSTEM_PROMPT = """You are a curriculum designer revising an in-progress English course.

The student has just finished a session. Using their updated profile and what
you observed, rewrite the REMAINING days of the course so the course adapts to
how they are actually doing.

Rules you must follow:
- Only output the days from {from_day} onward. Days before {from_day} are already
  completed and must not appear in your output.
- Keep exactly the same number of remaining days so the course length is unchanged.
- Day numbers must start at {from_day} and increase by 1, with no gaps or duplicates.
- Make knowledge points specific and non-repeating, in the same style as before.
- If the student is doing well, keep the plan broadly intact and only refine it.
- If the student is struggling on something, bring that into the next few days.
- Do not repeat knowledge points from days that were already completed.

Call submit_revised_plan with the revised days."""


PLAN_REVISION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_revised_plan",
            "description": "Submit the revised plan for the remaining days",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "One sentence on why the plan changed",
                    },
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "day": {"type": "integer"},
                                "topic": {"type": "string"},
                                "focus": {"type": "string"},
                                "knowledge_points": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "title": {"type": "string"},
                                            "detail": {"type": "string"},
                                            "example": {"type": "string"},
                                        },
                                        "required": ["title", "detail"],
                                    },
                                },
                                "extension": {"type": "string"},
                                "exercise_types": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "vocab_theme": {"type": "string"},
                                "estimated_minutes": {"type": "integer"},
                            },
                            "required": [
                                "day", "topic", "focus", "knowledge_points",
                                "exercise_types", "vocab_theme",
                            ],
                        },
                    },
                },
                "required": ["days"],
            },
        },
    },
]


async def revise_plan_tail(
    llm: LLMClient,
    plan: CoursePlan,
    from_day: int,
    profile_context: str,
    session_note: str,
) -> tuple[CoursePlan, str] | None:
    """Rewrite the remaining days of a plan based on how the student is doing.

    Safety rules enforced here, not just in the prompt:
      - completed days (day < from_day) are never touched;
      - the number of remaining days must stay the same;
      - a failed or malformed revision returns None and the plan is left alone.

    Returns (new_plan, reason) or None if nothing changed.
    """
    from datetime import date

    remaining = plan.future_days(from_day)
    if not remaining:
        return None

    system_prompt = PLAN_REVISION_SYSTEM_PROMPT.format(from_day=from_day)
    completed = [d for d in plan.days if d.day < from_day]
    completed_brief = "\n".join(
        f"  Day {d.day}: {d.topic} ({', '.join(kp.title for kp in d.knowledge_points) or d.focus})"
        for d in completed
    ) or "  (none yet)"

    user_content = (
        f"Current remaining plan (days {from_day}-{plan.days[-1].day}):\n"
        + "\n".join(
            f"  Day {d.day}: {d.topic} | {d.focus} | "
            f"knowledge: {', '.join(kp.title for kp in d.knowledge_points) or 'none'}"
            for d in remaining
        )
        + f"\n\nAlready completed (do NOT repeat these knowledge points):\n{completed_brief}"
        + f"\n\n=== Updated student profile ===\n{profile_context}"
        + f"\n\n=== What happened in the session just finished ===\n{session_note}"
        + f"\n\nProduce exactly {len(remaining)} revised days starting at day {from_day}."
    )

    try:
        _content, tool_calls = await llm.chat(
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": user_content}],
            tools=PLAN_REVISION_TOOLS,
        )
    except Exception:
        return None

    for tc in tool_calls:
        if tc["name"] != "submit_revised_plan":
            continue
        new_days_data = tc["arguments"].get("days") or []
        new_days: list[DailyPlan] = []
        for raw in new_days_data:
            try:
                new_days.append(DailyPlan(**raw))
            except (TypeError, ValueError):
                continue

        # Structural guard: wrong length, or day numbers that do not line up.
        if len(new_days) != len(remaining):
            return None
        expected = [d.day for d in remaining]
        if [d.day for d in new_days] != expected:
            return None

        for d in new_days:
            d.revised = True

        merged = list(plan.days)
        index_by_day = {d.day: i for i, d in enumerate(merged)}
        for d in new_days:
            merged[index_by_day[d.day]] = d

        new_plan = CoursePlan(
            total_days=plan.total_days,
            days=merged,
            schema_version=PLAN_SCHEMA_VERSION,
            created_at=plan.created_at,
            revised_at=date.today().isoformat(),
        )
        write_json("course_plan.json", new_plan.model_dump())
        return new_plan, tc["arguments"].get("reason", "")

    return None


def get_today_plan(plan: CoursePlan) -> DailyPlan | None:
    """Get the active day plan.

    Looks the day up by number rather than by list position, because a mid-course
    revision can insert or reorder days and position would then drift.
    """
    if not plan.days:
        return None

    profile = read_json("user_profile.json") or {}
    last_completed = profile.get("last_completed_day")
    if last_completed is None:
        target = 1
    else:
        try:
            target = int(last_completed) + 1
        except (TypeError, ValueError):
            target = 1

    found = plan.day_by_number(target)
    if found is not None:
        return found

    # Fall back to positional lookup for plans whose day numbers drifted.
    index = max(target - 1, 0)
    if index < len(plan.days):
        return plan.days[index]
    return None
