from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Input, Button, Static, Footer, RichLog
from textual.containers import Container, Horizontal, Vertical
from textual import work
import json
from src.utils import read_json, write_json

from src.llm_client import LLMClient, TextChunk, FunctionCall, Done, Error
from src.knowledge import TOOL_DEFINITIONS, TOOL_FUNCTION_MAP, get_vocabulary_count
from src.daily_coach import build_coach_system_prompt, get_command_prompt, COMMAND_DESCRIPTIONS
from src.course_plan import CoursePlan, DailyPlan, load_course_plan, get_today_plan
from src.sessions import SessionManager
from src.summary import generate_summary
from src.tui.widgets.chat_widgets import (
    format_coach_message,
    format_user_message,
    format_system_message,
    format_error_message,
)
from src.summary import _conversation_to_text
from src.dynamic_profile import (
    load_dynamic_profile,
    save_dynamic_profile,
    format_profile_for_prompt,
    PROFILE_UPDATE_SYSTEM_PROMPT,
    PROFILE_UPDATE_TOOLS,
)


class CoachScreen(Screen):
    """Main daily training screen."""

    TITLE = "English Coach"

    CSS = """
    CoachScreen {
        layout: vertical;
    }

    #coach-body {
        height: 1fr;
        layout: horizontal;
    }

    #chat-panel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    #chat-log {
        width: 100%;
        height: 1fr;
        overflow-x: hidden;
        overflow-y: auto;
        scrollbar-size-horizontal: 0;
    }

    #sidebar {
        width: 28;
        height: 1fr;
        border: solid $secondary;
        padding: 0 1;
        background: $surface;
    }

    .sidebar-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }

    .sidebar-section {
        margin: 0 0 1 0;
        width: 100%;
    }

    #sidebar Button {
        width: 100%;
        margin: 0 0 1 0;
    }

    #input-area {
        height: 3;
        dock: bottom;
        padding: 0 1;
    }

    #chat-input {
        width: 1fr;
    }

    #btn-send {
        width: 10;
    }

    #command-hints {
        height: 1;
        dock: bottom;
        color: $text-disabled;
        text-align: center;
    }
    """

    def __init__(self, llm: LLMClient, session: SessionManager) -> None:
        super().__init__()
        self.llm = llm
        self.session = session
        self.conversation: list[dict] = list(session.training_history)
        self.plan: CoursePlan | None = load_course_plan()
        self.today_plan: DailyPlan | None = None
        self.vocab_count: int = get_vocabulary_count()
        self._streaming = False
        self._awaiting_save = False
        self.profile = load_dynamic_profile()
        self.profile_context = format_profile_for_prompt(self.profile)

        if self.plan:
            self.today_plan = get_today_plan(self.plan)

        if self.today_plan:
            self.system_prompt = build_coach_system_prompt(
                self.today_plan,
                self.plan.total_days if self.plan else session.total_days,
                profile_context=self.profile_context,
            )
        else:
            self.system_prompt = "You are an encouraging English writing coach."

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="coach-body"):
            with Vertical(id="chat-panel"):
                yield RichLog(
                    id="chat-log",
                    wrap=True,
                    highlight=False,
                    markup=True,
                    auto_scroll=True,
                    min_width=1,
                    max_lines=2000,
                )
            with Vertical(id="sidebar"):
                yield Static("Today's Plan", classes="sidebar-title")
                yield Static(id="sidebar-topic", classes="sidebar-section")
                yield Static("Progress", classes="sidebar-title")
                yield Static(id="sidebar-progress", classes="sidebar-section")
                yield Static("Vocabulary", classes="sidebar-title")
                yield Static(id="sidebar-vocab", classes="sidebar-section")
                yield Static("Quick Access", classes="sidebar-title")
                yield Button("Vocabulary Bank", id="btn-vocab", classes="sidebar-btn")
                yield Button("Course Plan", id="btn-plan", classes="sidebar-btn")
                yield Button("History", id="btn-history", classes="sidebar-btn")
                yield Button("Settings", id="btn-settings", classes="sidebar-btn")
        with Horizontal(id="input-area"):
            yield Input(placeholder="Type your message or /command...", id="chat-input")
            yield Button("Send", variant="primary", id="btn-send")
        yield Static(get_command_prompt(), id="command-hints")
        yield Footer()

    def on_mount(self) -> None:
        self._update_sidebar()
        self._restore_conversation()
        if not self.conversation:
            if self.today_plan:
                self._add_message(
                    format_system_message(
                        f"Day {self.session.current_day}: {self.today_plan.topic}. "
                        f"Focus: {self.today_plan.focus}. Type a message to begin, or use /practice."
                    )
                )
            else:
                self._add_message(
                    format_system_message(
                        "Course complete or no daily plan found. You can still practice freely, "
                        "or review History / Vocabulary."
                    )
                )
        self.query_one("#chat-input", Input).focus()

    def _restore_conversation(self) -> None:
        for msg in self.conversation:
            role = msg["role"]
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                self._add_message(format_user_message(content))
            elif role == "assistant":
                self._add_message(format_coach_message(content))
            elif role == "tool":
                self._add_message(format_system_message(content))

    def _add_message(self, renderable: str) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(renderable)
        chat_log.write("")

    def _update_sidebar(self) -> None:
        if self.today_plan:
            self.query_one("#sidebar-topic", Static).update(
                f"[bold]{self.today_plan.topic}[/]\n"
                f"Focus: {self.today_plan.focus}\n"
                f"Exercises: {', '.join(self.today_plan.exercise_types[:3])}"
            )
        else:
            self.query_one("#sidebar-topic", Static).update("No active day plan.")

        plan = self.plan
        if plan:
            filled = min(self.session.current_day, plan.total_days)
            empty = max(plan.total_days - filled, 0)
            self.query_one("#sidebar-progress", Static).update(
                f"Day {self.session.current_day} of {plan.total_days}\n"
                + "#" * filled
                + "." * empty
            )
        else:
            self.query_one("#sidebar-progress", Static).update("No course plan loaded.")

        self.vocab_count = get_vocabulary_count()
        self.query_one("#sidebar-vocab", Static).update(
            f"Saved expressions: [bold]{self.vocab_count}[/]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-send":
            self._handle_send()
        elif btn_id == "btn-vocab":
            from src.tui.screens.vocabulary_screen import VocabularyScreen
            self.app.push_screen(VocabularyScreen())
        elif btn_id == "btn-plan":
            from src.tui.screens.course_plan_screen import CoursePlanScreen
            if self.plan:
                self.app.push_screen(CoursePlanScreen(self.plan))
        elif btn_id == "btn-history":
            from src.tui.screens.history_screen import HistoryScreen
            self.app.push_screen(HistoryScreen())
        elif btn_id == "btn-settings":
            from src.tui.screens.settings_screen import SettingsScreen
            from src.config import load_config
            self.app.push_screen(SettingsScreen(load_config()))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            self._handle_send()

    def _set_input_locked(self, locked: bool) -> None:
        self._streaming = locked
        self.query_one("#chat-input", Input).disabled = locked
        self.query_one("#btn-send", Button).disabled = locked

    def _handle_send(self) -> None:
        user_input = self.query_one("#chat-input", Input).value.strip()
        if not user_input or self._streaming:
            return

        if self._awaiting_save and not user_input.startswith("/"):
            self._awaiting_save = False
            self.query_one("#chat-input", Input).value = ""
            self._add_message(format_user_message(user_input))
            from src.knowledge import add_vocabulary
            vid = add_vocabulary(user_input)
            self._add_message(
                format_system_message(
                    f"Saved expression #{vid}: '{user_input}'. You can browse it in Vocabulary Bank."
                )
            )
            self._update_sidebar()
            return

        if user_input.startswith("/"):
            self._handle_command(user_input)
            return

        self.query_one("#chat-input", Input).value = ""
        self._add_message(format_user_message(user_input))
        self.conversation.append({"role": "user", "content": user_input})
        self._set_input_locked(True)
        self._stream_response()

    def _handle_command(self, cmd: str) -> None:
        cmd = cmd.strip().lower()
        self.query_one("#chat-input", Input).value = ""

        if cmd == "/help":
            help_text = "\n".join(f"{k}: {v}" for k, v in COMMAND_DESCRIPTIONS.items())
            self._add_message(format_system_message(help_text))
        elif cmd == "/practice":
            self.conversation.append({
                "role": "user",
                "content": "Please give me a practice exercise related to today's focus area.",
            })
            self._add_message(format_user_message("/practice"))
            self._set_input_locked(True)
            self._stream_response()
        elif cmd == "/save":
            self._awaiting_save = True
            self._add_message(format_system_message(
                "Type the expression you would like to save. It will be added to your vocabulary bank."
            ))
        elif cmd == "/explain":
            self.conversation.append({
                "role": "user",
                "content": "Could you explain a grammar or usage point that would help me improve?",
            })
            self._add_message(format_user_message("/explain"))
            self._set_input_locked(True)
            self._stream_response()
        elif cmd == "/summary":
            self._generate_summary()
        elif cmd == "/plan":
            from src.tui.screens.course_plan_screen import CoursePlanScreen
            if self.plan:
                self.app.push_screen(CoursePlanScreen(self.plan))
            else:
                self._add_message(format_system_message("No course plan is available yet."))
        elif cmd == "/vocab":
            from src.tui.screens.vocabulary_screen import VocabularyScreen
            self.app.push_screen(VocabularyScreen())
        else:
            self._add_message(format_system_message(f"Unknown command: {cmd}. Type /help for commands."))

    @work(thread=False)
    async def _stream_response(self) -> None:
        try:
            messages = [{"role": "system", "content": self.system_prompt}] + self.conversation

            while True:
                full_content = ""
                pending_calls: list[FunctionCall] = []

                async for event in self.llm.chat_stream(messages, tools=TOOL_DEFINITIONS):
                    if isinstance(event, TextChunk):
                        full_content += event.content
                    elif isinstance(event, FunctionCall):
                        pending_calls.append(event)
                    elif isinstance(event, Error):
                        self._add_message(format_error_message(f"Error: {event.message}"))
                        self._set_input_locked(False)
                        return

                if full_content:
                    self._add_message(format_coach_message(full_content))

                assistant_msg: dict = {"role": "assistant", "content": full_content}
                if pending_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": fc.id,
                            "type": "function",
                            "function": {
                                "name": fc.name,
                                "arguments": json.dumps(fc.arguments),
                            },
                        }
                        for fc in pending_calls
                    ]

                self.conversation.append(assistant_msg)

                if not pending_calls:
                    break

                for fc in pending_calls:
                    handler = TOOL_FUNCTION_MAP.get(fc.name)
                    if handler:
                        result = handler(**fc.arguments)
                        self._add_message(format_system_message(result))
                        self.conversation.append({
                            "role": "tool",
                            "tool_call_id": fc.id,
                            "content": result,
                        })
                    else:
                        result = f"Unknown tool: {fc.name}"
                        self.conversation.append({
                            "role": "tool",
                            "tool_call_id": fc.id,
                            "content": result,
                        })

                self._update_sidebar()
                messages = [{"role": "system", "content": self.system_prompt}] + self.conversation

            self.session.training_history = list(self.conversation)
            self.session.save()
            self._set_input_locked(False)
            self.query_one("#chat-input", Input).focus()

        except Exception as e:
            self._add_message(format_error_message(f"Error: {e}"))
            self._set_input_locked(False)
            self.query_one("#chat-input", Input).focus()

    @work(thread=False)
    async def _generate_summary(self) -> None:
        if not self.conversation:
            self._add_message(format_system_message(
                "No conversation yet for today. Chat a little first, then use /summary."
            ))
            return

        self._add_message(format_system_message("Generating your daily summary..."))
        self._set_input_locked(True)
        try:
            summary, profile_data = await generate_summary(
                self.llm,
                self.conversation,
                self.session.current_day,
                self.plan.total_days if self.plan else self.session.total_days,
                current_profile=self.profile,
            )
            self._add_message(format_coach_message("Today's session is complete! Here is your summary:"))
            self._add_message(summary)
            # Update profile from the same LLM call that generated the summary
            if profile_data:
                for key, value in profile_data.items():
                    if hasattr(self.profile, key):
                        setattr(self.profile, key, value)
                save_dynamic_profile(self.profile)
                self.profile_context = format_profile_for_prompt(self.profile)
                self._add_message(format_system_message("Student profile updated for next session."))
            
            self._add_message(format_system_message(
                "Progress saved. Restart the app to open the next day's lesson."
            ))

            completed_day = self.session.current_day
            self.conversation = []
            self.session.training_history = []

            user_data = read_json("user_profile.json") or {}
            user_data["last_completed_day"] = completed_day
            write_json("user_profile.json", user_data)

            next_day = min(completed_day + 1, self.session.total_days)
            self.session.current_day = next_day
            self.session.save()
            self._update_sidebar()
        except Exception as e:
            self._add_message(format_error_message(f"Error generating summary: {e}"))
        finally:
            self._set_input_locked(False)
            self.query_one("#chat-input", Input).focus()
