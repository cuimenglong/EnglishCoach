"""Session policy: turn the learner's profile into concrete instructions.

The dynamic profile used to be rendered as prose and pasted into the system
prompt, where the model was free to ignore it. Here the numbers are turned into
*constraints* by code, and the model executes them:

  - difficulty is computed from the skill scores rather than trusted from the
    profile's own `recommended_difficulty`, which used to be circular (we showed
    the model a value and it echoed the same value back);
  - the weakest skill dimension becomes today's explicit priority;
  - session length comes from the day's estimate adjusted by the recommended pace;
  - due vocabulary from the SRS queue is surfaced proactively instead of waiting
    for the model to decide to call search_vocabulary.

Everything here is a pure function so it can be unit tested without an LLM.
"""
import logging
from dataclasses import dataclass, field

from .course_plan import DailyPlan
from .dynamic_profile import DynamicProfile

logger = logging.getLogger(__name__)

# How to coach each skill dimension when it is the weakest one. Keys must match
# SkillScores field names.
_PRIORITY_PLAYBOOK = {
    "grammar": (
        "Prioritise sentence-level accuracy: verb tense agreement, articles, "
        "plural forms, prepositions and word order."
    ),
    "vocabulary": (
        "Prioritise word choice: collocations, precise verbs, avoiding repetition, "
        "and upgrading overly basic words."
    ),
    "sentence_structure": (
        "Prioritise structure: clause order, combining short sentences, varied "
        "sentence lengths, and clear linking."
    ),
    "fluency": (
        "Prioritise natural flow: reduce hesitation fillers, vary sentence openings, "
        "and keep momentum without over-editing."
    ),
    "accuracy": (
        "Prioritise error-free output over speed. Ask the learner to re-read before "
        "sending, and name each error precisely."
    ),
}

_DIFFICULTY_BANDS = [
    (4.0, "beginner", "Use short sentences, one idea at a time, and heavy scaffolding."),
    (6.5, "intermediate", "Use full sentences with light scaffolding; correct and continue."),
    (8.0, "advanced", "Push for nuance and precision; minimal scaffolding."),
    (10.1, "expert", "Discuss abstract topics; challenge register and style, not just grammar."),
]

_PACE_MULTIPLIER = {"slow": 0.6, "normal": 1.0, "fast": 1.4}


def difficulty_for_score(score: float) -> str:
    for ceiling, label, _rule in _DIFFICULTY_BANDS:
        if score < ceiling:
            return label
    return "expert"


def average_skill_score(profile: DynamicProfile) -> float:
    scores = profile.skill_scores.model_dump().values()
    return round(sum(scores) / len(scores), 2) if scores else 5.0


def weakest_dimension(profile: DynamicProfile) -> tuple[str, int]:
    """Return (dimension, score) for the lowest-scoring skill.

    Ties break in model field order so the result is deterministic.
    """
    items = profile.skill_scores.model_dump().items()
    return min(items, key=lambda kv: kv[1])


@dataclass
class SessionDirectives:
    difficulty: str = "intermediate"
    difficulty_score: float = 5.0
    difficulty_rule: str = ""
    priority_dimension: str = "accuracy"
    priority_score: int = 5
    target_minutes: int = 20
    target_exchanges: int = 12
    due_vocabulary: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Prompt fragment the coach must follow today."""
        lines = [
            f"- Today's difficulty: {self.difficulty} "
            f"(computed from the learner's skill scores, average {self.difficulty_score}/10).",
            f"  {self.difficulty_rule}",
            f"- Today's priority skill: {self.priority_dimension.replace('_', ' ')} "
            f"(weakest dimension, {self.priority_score}/10).",
            f"  {_PRIORITY_PLAYBOOK.get(self.priority_dimension, 'Work on the weakest dimension.')}",
            f"- Session length target: about {self.target_exchanges} exchanges "
            f"(~{self.target_minutes} minutes). Wrap up gracefully near the target;",
            "  do not pad with filler and do not cut off mid-exercise.",
        ]

        if self.due_vocabulary:
            lines.append(
                f"- {len(self.due_vocabulary)} saved expression(s) are due for review. "
                "Weave the first one or two in as a natural review moment early in the "
                "session; do not turn it into a test."
            )
            for item in self.due_vocabulary[:3]:
                lines.append(f"    * {item['expression']} -- {item.get('meaning', '')}".rstrip(" -"))

        for note in self.notes:
            lines.append(f"- {note}")

        lines.append(
            "These directives come from the learner's measured progress. Follow them "
            "even if today's plan suggests something else; mention the plan's knowledge "
            "points as the content, but let these directives set the difficulty and pace."
        )
        return "\n".join(lines)


def build_session_directives(
    profile: DynamicProfile,
    plan: DailyPlan | None,
    due_vocabulary: list[dict] | None = None,
) -> SessionDirectives:
    """Compute today's directives from the profile."""
    average = average_skill_score(profile)
    difficulty = difficulty_for_score(average)
    rule = next(r for ceiling, label, r in _DIFFICULTY_BANDS if label == difficulty)

    dimension, score = weakest_dimension(profile)

    base_minutes = plan.estimated_minutes if plan and plan.estimated_minutes else 20
    pace = profile.recommended_pace if profile.recommended_pace in _PACE_MULTIPLIER else "normal"
    multiplier = _PACE_MULTIPLIER[pace]
    target_minutes = max(5, int(round(base_minutes * multiplier)))
    # ~1 exchange per minute is a reasonable exchange for written practice.
    target_exchanges = max(4, min(40, target_minutes))

    notes: list[str] = []
    if profile.confidence_in_level == "low":
        notes.append("The learner's level estimate is still uncertain; keep a wide range available.")
    if profile.lessons_completed <= 1:
        notes.append("This is an early session, so gather more evidence before adjusting anything.")
    if profile.challenging_areas:
        notes.append(
            "Still challenging for this learner: " + ", ".join(profile.challenging_areas[:3]) + "."
        )

    # The profile's own difficulty call is advisory only. Disagreement is worth
    # a log line because it usually means the model's read of the session is off.
    llm_suggestion = profile.recommended_difficulty
    if llm_suggestion and llm_suggestion != difficulty:
        logger.info(
            "Profile suggested difficulty %r but skill scores average %.2f -> using %r",
            llm_suggestion, average, difficulty,
        )

    return SessionDirectives(
        difficulty=difficulty,
        difficulty_score=average,
        difficulty_rule=rule,
        priority_dimension=dimension,
        priority_score=score,
        target_minutes=target_minutes,
        target_exchanges=target_exchanges,
        due_vocabulary=list(due_vocabulary or []),
        notes=notes,
    )
