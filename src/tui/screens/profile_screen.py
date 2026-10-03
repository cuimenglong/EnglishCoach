"""Skill profile dashboard.

This is the payoff for computing the profile in code: the numbers the coach
acts on are shown to the learner, instead of being invisible prompt text.
"""
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from src.coach_policy import SessionDirectives
from src.dynamic_profile import DynamicProfile

_DIMENSION_LABELS = {
    "grammar": "Grammar",
    "vocabulary": "Vocabulary",
    "sentence_structure": "Sentence structure",
    "fluency": "Fluency",
    "accuracy": "Accuracy",
}


def _bar(score: int, width: int = 20) -> Text:
    filled = max(0, min(width, round(score / 10 * width)))
    bar = Text()
    # Colour by band so a weak dimension is obvious at a glance.
    style = "green" if score >= 7 else "yellow" if score >= 5 else "red"
    bar.append("█" * filled, style=style)
    bar.append("░" * (width - filled), style="dim")
    return bar


class ProfileScreen(Screen):
    """Show the learner's skill profile and today's computed directives."""

    TITLE = "Your Profile"

    def __init__(self, profile: DynamicProfile, directives: SessionDirectives | None = None) -> None:
        super().__init__()
        self.profile = profile
        self.directives = directives

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="profile-container"):
            with Vertical():
                yield Static("Skill profile", id="profile-title")
                yield Static("", id="profile-skills")
                yield Static("", id="profile-summary")
                yield Static("", id="profile-directives")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#profile-title", Static).update(
            f"Skill profile  -  {self.profile.cefr_level} "
            f"(confidence: {self.profile.confidence_in_level})"
        )

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Skill", width=18)
        table.add_column("", width=22)
        table.add_column("Score", width=5)
        for name, score in self.profile.skill_scores.model_dump().items():
            table.add_row(_DIMENSION_LABELS.get(name, name), _bar(score), f"{score}/10")
        self.query_one("#profile-skills", Static).update(table)

        parts = [f"Lessons completed: {self.profile.lessons_completed}"]
        for label, values in (
            ("Strengths", self.profile.strengths),
            ("Focus areas", self.profile.weaknesses),
            ("Still challenging", self.profile.challenging_areas),
            ("Mastered", self.profile.mastered_topics),
            ("Common mistakes", self.profile.common_mistakes),
            ("Interests", self.profile.interests),
        ):
            if values:
                parts.append(f"{label}: " + ", ".join(values))
        self.query_one("#profile-summary", Static).update("\n".join(parts))

        if self.directives is not None:
            d = self.directives
            lines = [
                "Today the coach was set to:",
                f"  difficulty     {d.difficulty} (average {d.difficulty_score}/10)",
                f"  priority skill {d.priority_dimension.replace('_', ' ')} "
                f"({d.priority_score}/10)",
                f"  session target {d.target_exchanges} exchanges (~{d.target_minutes} min)",
            ]
            if d.due_vocabulary:
                lines.append(f"  due for review {len(d.due_vocabulary)} expression(s)")
            self.query_one("#profile-directives", Static).update("\n".join(lines))

    def key_escape(self) -> None:
        self.app.pop_screen()
