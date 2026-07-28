from pydantic import BaseModel
from .profile import UserProfile
from .llm_client import LLMClient
from .utils import read_json, write_json


class DailyPlan(BaseModel):
    day: int
    topic: str
    focus: str
    exercise_types: list[str]
    vocab_theme: str


class CoursePlan(BaseModel):
    total_days: int
    days: list[DailyPlan]


COURSE_PLAN_SYSTEM_PROMPT = (
    "You are a curriculum designer specialized in English language learning. "
    "Based on the user's profile below, create a structured {total_days}-day course plan.\n\n"
    "The plan should:\n"
    "- Progress naturally from foundational to more advanced skills\n"
    "- Cover a variety of exercise types to keep learning engaging\n"
    "- Be tailored to the user's level, goals, and interests\n"
    "- Include specific, actionable focus areas for each day\n\n"
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
                                "exercise_types": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of exercise types for this day",
                                },
                                "vocab_theme": {
                                    "type": "string",
                                    "description": "Vocabulary theme for the day",
                                },
                            },
                            "required": ["day", "topic", "focus", "exercise_types", "vocab_theme"],
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
            days_data = tc["arguments"]["days"]
            plan = CoursePlan(total_days=len(days_data), days=[DailyPlan(**d) for d in days_data])
            write_json("course_plan.json", plan.model_dump())
            return plan

    raise RuntimeError("LLM did not return a valid course plan.")


def load_course_plan() -> CoursePlan | None:
    data = read_json("course_plan.json")
    if data:
        return CoursePlan(**data)
    return None


def get_today_plan(plan: CoursePlan) -> DailyPlan | None:
    """Get the active day plan from last_completed_day (completion-based, not calendar)."""
    profile = read_json("user_profile.json") or {}
    if not plan.days:
        return None

    last_completed = profile.get("last_completed_day")
    if last_completed is None:
        day_index = 0
    else:
        try:
            day_index = int(last_completed)
        except (TypeError, ValueError):
            day_index = 0

    if day_index < 0:
        return plan.days[0]
    if day_index >= len(plan.days):
        return None
    return plan.days[day_index]
