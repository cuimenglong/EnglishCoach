from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Static, ListView, ListItem, Footer
from textual.containers import Container
from src.course_plan import CoursePlan


class CoursePlanScreen(Screen):
    """Screen for viewing the full course plan."""

    TITLE = "Course Plan"

    def __init__(self, plan: CoursePlan):
        super().__init__()
        self.plan = plan

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="plan-container"):
            yield Static(f"Your {self.plan.total_days}-Day Course Plan", id="plan-title")
            yield ListView(id="plan-list")
        yield Footer()

    def on_mount(self) -> None:
        plan_list = self.query_one("#plan-list", ListView)
        for day_plan in self.plan.days:
            exercises = ", ".join(day_plan.exercise_types)
            label = (
                f"Day {day_plan.day}: {day_plan.topic}\n"
                f"  Focus: {day_plan.focus}\n"
                f"  Exercises: {exercises}\n"
                f"  Vocabulary Theme: {day_plan.vocab_theme}"
            )
            plan_list.append(ListItem(Static(label)))

    def key_escape(self) -> None:
        self.app.pop_screen()
