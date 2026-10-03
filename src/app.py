from textual import work
from textual.app import App
from textual.binding import Binding
from datetime import date
import logging

from src.config import load_config, Config
from src.llm_client import LLMClient
from src.sessions import SessionManager
from src.profile import UserProfile
from src.course_plan import generate_course_plan, CoursePlan, DailyPlan
from src.knowledge import init_db
from src.utils import read_json, write_json

from src.tui.screens.settings_screen import SettingsScreen
from src.tui.screens.assessment_screen import AssessmentScreen, AssessmentComplete
from src.tui.screens.coach_screen import CoachScreen

logger = logging.getLogger(__name__)


class EnglishCoachApp(App):
    """The English Expression Coach application."""

    TITLE = "English Expression Coach"
    SUB_TITLE = "Your personal AI-powered writing coach"

    CSS = """
    Screen { background: $surface; }
    #settings-container { padding: 1 2; height: auto; }
    .section-title { text-style: bold; color: $accent; padding: 1 0; }
    .field-label { padding: 0 0; margin-top: 1; }
    .button-row { margin: 1 0; align: center middle; }
    .button-row Button { margin: 0 1; }
    #settings-status { text-align: center; padding: 1 0; }
    #assessment-layout, #coach-body { height: 1fr; }
    #assessment-chat-panel, #chat-panel {
        height: 1fr; border: solid $primary;
    }
    #assessment-chat-log, #chat-log {
        height: 1fr; overflow-y: auto; padding: 0 1;
    }
    #assessment-chat-log {
    overflow-x: hidden;
}
#assessment-input-area, #input-area {
        height: 3; dock: bottom; padding: 0 1;
    }
    #assessment-input, #chat-input { width: 1fr; }
    #btn-assessment-send, #btn-send { width: 10; }
    #btn-assessment-settings { width: 12; }
    #sidebar {
        width: 28; height: 1fr; border: solid $secondary;
        padding: 0 1; background: $surface;
    }
    #sidebar .sidebar-title { text-style: bold; color: $accent; margin-top: 1; }
    #sidebar .sidebar-section { margin: 0 0 1 0; }
    #sidebar Button { width: 100%; margin: 0 0 1 0; }
    #command-hints { height: 1; dock: bottom; color: $text-disabled; text-align: center; }
    #vocab-container, #plan-container, #history-container { padding: 1 2; height: 1fr; }
    #vocab-title, #plan-title, #history-title { text-style: bold; color: $accent; padding: 1 0; }
    #vocab-search { width: 1fr; }
    #vocab-list, #plan-list, #history-list { height: 1fr; }
    #history-content {
        height: 1fr; overflow-y: auto; border: solid $primary;
        padding: 0 1; margin-top: 1;
    }
    #vocab-count { padding: 0 0 1 0; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.llm: LLMClient | None = None
        self.session = SessionManager()

    def _get_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient(
                api_key=self.config.openai_api_key,
                base_url=self.config.base_url,
                model=self.config.model_name,
                temperature=self.config.temperature,
            )
        return self.llm

    def on_mount(self) -> None:
        init_db()
        self._navigate()

    def _navigate(self) -> None:
        if not self.config.openai_api_key:
            self.push_screen(SettingsScreen(self.config), self._on_settings_dismissed)
        elif self.session.stage == SessionManager.STAGE_ASSESSMENT:
            self.push_screen(
                AssessmentScreen(self._get_llm()),
                self._on_assessment_dismissed,
            )
        elif self.session.stage == SessionManager.STAGE_PLANNING:
            self._do_plan_generation()
        elif self.session.stage == SessionManager.STAGE_TRAINING:
            self.push_screen(CoachScreen(self._get_llm(), self.session))

    def _on_settings_dismissed(self, config: Config | None) -> None:
        if config is not None:
            self.config = config
            self.llm = None
        self._navigate()

    def _on_assessment_dismissed(self, result: None) -> None:
        """Called when assessment screen is dismissed without completing (e.g. Escape)."""
        self.push_screen(SettingsScreen(self.config), self._on_settings_dismissed)

    def on_assessment_complete(self, event: AssessmentComplete) -> None:
        """Assessment finished successfully with a profile."""
        profile = event.profile
        profile_dict = profile.model_dump()
        profile_dict["created_at"] = date.today().isoformat()
        write_json("user_profile.json", profile_dict)

        # Pop assessment screen (no callback triggered since we use pop_screen, not dismiss)
        self.pop_screen()
        self._do_plan_generation()

    @work(thread=False)
    async def _do_plan_generation(self) -> None:
        profile_data = read_json("user_profile.json")
        if not profile_data:
            self.push_screen(
                AssessmentScreen(self._get_llm()),
                self._on_assessment_dismissed,
            )
            return

        profile = UserProfile(**profile_data)

        try:
            plan = await generate_course_plan(self._get_llm(), profile)
        except Exception as exc:
            # Previously this was a bare "except Exception" that silently built a
            # generic placeholder plan, so an invalid API key, a wrong model
            # name or a network failure all looked like success. Log it, tell
            # the user, and only then fall back so they can still practise.
            logger.exception("Course plan generation failed")
            self.notify(
                f"Course plan generation failed: {exc}",
                title="LLM error",
                severity="error",
                timeout=15,
            )
            plan = self._fallback_plan(profile)
            write_json("course_plan.json", plan.model_dump())

        self.session.stage = SessionManager.STAGE_TRAINING
        self.session.total_days = plan.total_days
        self.session.save()
        self.push_screen(CoachScreen(self._get_llm(), self.session))

    def _fallback_plan(self, profile: UserProfile) -> CoursePlan:
        """Generic plan used when the LLM is unreachable. Never overwrites a
        previously generated plan -- the caller writes it only after a failure."""
        days = [
            DailyPlan(
                day=d,
                topic=f"Day {d}: Building Your Expression Skills",
                focus="General writing improvement",
                exercise_types=["free_writing", "sentence_rewriting"],
                vocab_theme="Daily expressions",
            )
            for d in range(1, profile.study_days + 1)
        ]
        return CoursePlan(total_days=len(days), days=days)


if __name__ == "__main__":
    app = EnglishCoachApp()
    app.run()
