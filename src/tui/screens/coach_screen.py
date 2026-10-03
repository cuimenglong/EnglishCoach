from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Input, Button, Static, Footer, RichLog
from textual.containers import Container, Horizontal, Vertical
from textual import work
import json
import logging

from src.utils import read_json, write_json

from src.llm_client import LLMClient, TextChunk, FunctionCall, Done, Error
from src.knowledge import TOOL_DEFINITIONS, TOOL_FUNCTION_MAP, get_vocabulary_count
from src.daily_coach import build_coach_system_prompt, get_command_prompt, COMMAND_DESCRIPTIONS
from src.course_plan import (
    CoursePlan,
    DailyPlan,
    load_course_plan,
    get_today_plan,
    revise_plan_tail,
)
from src.sessions import SessionManager
from src.summary import generate_summary
from src.tui.widgets.chat_widgets import (
    format_coach_mark,
    format_coach_message,
    format_user_message,
    format_system_message,
    format_error_message,
)
from src.persona import load_persona, render_persona_prompt
from src.coach_policy import SessionDirectives, build_session_directives
from src.dynamic_profile import (
    apply_profile_update,
    load_dynamic_profile,
    save_dynamic_profile,
    format_profile_for_prompt,
)

logger = logging.getLogger(__name__)


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

    #sidebar-mark {
        height: auto;
        margin-top: 0;
    }

    #sidebar-day {
        text-align: center;
        margin-top: 0;
    }

    .sidebar-section {
        margin: 0 0 1 0;
        width: 100%;
    }

    #sidebar Button {
        width: 100%;
        margin: 0 0 1 0;
    }

    #typing-indicator {
        height: 1; dock: bottom; color: $text-muted; padding: 0 2;
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
        self.persona = load_persona()
        self.persona_context = render_persona_prompt(self.persona)
        self._session_note_source: list[dict] = []
        self._typing_timer = None
        self._typing_frame = 0

        if self.plan:
            self.today_plan = get_today_plan(self.plan)

        # Difficulty, priority skill and session length are computed from the
        # profile here rather than left to the model, which would otherwise just
        # echo back whatever difficulty string we showed it. Due vocabulary is
        # passed in so review is proactive instead of waiting for the model to
        # decide to call search_vocabulary.
        self.due_vocabulary = self._load_due_vocabulary()
        self.directives: SessionDirectives = build_session_directives(
            self.profile, self.today_plan, due_vocabulary=self.due_vocabulary
        )

        if self.today_plan:
            self.system_prompt = build_coach_system_prompt(
                self.today_plan,
                self.plan.total_days if self.plan else session.total_days,
                profile_context=self.profile_context,
                persona_context=self.persona_context,
                session_directives=self.directives.render(),
            )
        else:
            self.system_prompt = (
                "You are an encouraging English writing coach. "
                f"=== Student Profile ===\n{self.profile_context}"
                + (f"\n\n{self.persona_context}" if self.persona_context else "")
            )

    @staticmethod
    def _load_due_vocabulary(limit: int = 5) -> list[dict]:
        """Expressions due for review, shaped for the directives fragment."""
        try:
            from src.knowledge import get_due_cards
            return [
                {"expression": c.expression, "meaning": c.meaning}
                for c in get_due_cards(limit=limit)
            ]
        except Exception as exc:
            # Review is an enhancement; never let it stop a training session.
            logger.warning("Could not load due vocabulary: %s", exc)
            return []

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
                yield Static(format_coach_mark(), id="sidebar-mark", classes="sidebar-title")
                yield Static(f"Day {self.session.current_day} of {self.session.total_days}",
                             id="sidebar-day", classes="sidebar-title")
                yield Static("Today's Plan", classes="sidebar-title")
                yield Static(id="sidebar-topic", classes="sidebar-section")
                yield Static("Progress", classes="sidebar-title")
                yield Static(id="sidebar-progress", classes="sidebar-section")
                yield Static("Vocabulary", classes="sidebar-title")
                yield Static(id="sidebar-vocab", classes="sidebar-section")
                yield Static("Quick Access", classes="sidebar-title")
                yield Button("Vocabulary Bank", id="btn-vocab", classes="sidebar-btn")
                yield Button("Course Plan", id="btn-plan", classes="sidebar-btn")
                yield Button("Review Cards", id="btn-review", classes="sidebar-btn")
                yield Button("My Profile", id="btn-profile", classes="sidebar-btn")
                yield Button("History", id="btn-history", classes="sidebar-btn")
                yield Button("Settings", id="btn-settings", classes="sidebar-btn")
        with Horizontal(id="input-area"):
            yield Input(placeholder="Type your message or /command...", id="chat-input")
            yield Button("Send", variant="primary", id="btn-send")
        yield Static("", id="typing-indicator")
        yield Static(get_command_prompt(), id="command-hints")
        yield Footer()

    def on_mount(self) -> None:
        self._set_typing(False)
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

    def _add_message(self, renderable) -> None:
        """Append to the chat log. Accepts a str or any Rich renderable."""
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
        due = self._due_count()
        text = f"Saved expressions: [bold]{self.vocab_count}[/]"
        if due:
            text += f"\nDue for review: [bold yellow]{due}[/]  (/review)"
        self.query_one("#sidebar-vocab", Static).update(text)

    @staticmethod
    def _due_count() -> int:
        try:
            from src.knowledge import get_due_count
            return get_due_count()
        except Exception as exc:
            logger.warning("Could not read due count: %s", exc)
            return 0

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
        elif btn_id == "btn-review":
            from src.tui.screens.review_screen import ReviewScreen
            self.app.push_screen(ReviewScreen())
        elif btn_id == "btn-profile":
            from src.tui.screens.profile_screen import ProfileScreen
            self.app.push_screen(ProfileScreen(self.profile, self.directives))
        elif btn_id == "btn-settings":
            from src.tui.screens.settings_screen import SettingsScreen
            from src.config import load_config
            from src.llm_client import LLMClient

            def _on_settings_dismissed(config):
                if config is not None:
                    self.llm = LLMClient(
                        api_key=config.openai_api_key,
                        base_url=config.base_url,
                        model=config.model_name,
                        temperature=config.temperature,
                    )

            self.app.push_screen(SettingsScreen(load_config()), _on_settings_dismissed)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            self._handle_send()

    def _set_input_locked(self, locked: bool) -> None:
        self._streaming = locked
        self.query_one("#chat-input", Input).disabled = locked
        self.query_one("#btn-send", Button).disabled = locked
        if not locked:
            self._set_typing(False)

    _TYPING_FRAMES = ("Coach is typing", "Coach is typing.", "Coach is typing..",
                      "Coach is typing...")

    def _set_typing(self, active: bool) -> None:
        """Show progress while an LLM call is in flight.

        Without this the UI is simply silent for 5-20 seconds, which reads as a
        hang rather than as waiting.
        """
        indicator = self.query_one("#typing-indicator", Static)
        indicator.display = active
        if active:
            indicator.update(self._TYPING_FRAMES[0])
            if not self._typing_timer:
                self._typing_frame = 0
                self._typing_timer = self.set_interval(
                    0.45, self._tick_typing, name="typing-indicator"
                )
        else:
            indicator.update("")
            if self._typing_timer is not None:
                self._typing_timer.stop()
                self._typing_timer = None

    def _tick_typing(self) -> None:
        self._typing_frame = (self._typing_frame + 1) % len(self._TYPING_FRAMES)
        self.query_one("#typing-indicator", Static).update(
            self._TYPING_FRAMES[self._typing_frame]
        )

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
        elif cmd == "/review":
            from src.tui.screens.review_screen import ReviewScreen
            self.app.push_screen(ReviewScreen())
        elif cmd == "/profile":
            from src.tui.screens.profile_screen import ProfileScreen
            self.app.push_screen(ProfileScreen(self.profile, self.directives))
        else:
            self._add_message(format_system_message(f"Unknown command: {cmd}. Type /help for commands."))

    @work(thread=False)
    async def _stream_response(self) -> None:
        self._set_typing(True)
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
        finally:
            self._set_typing(False)

    @work(thread=False)
    async def _generate_summary(self) -> None:
        if not self.conversation:
            self._add_message(format_system_message(
                "No conversation yet for today. Chat a little first, then use /summary."
            ))
            return

        self._add_message(format_system_message("Generating your daily summary..."))
        self._set_input_locked(True)
        self._set_typing(True)
        try:
            summary, profile_data = await generate_summary(
                self.llm,
                self.conversation,
                self.session.current_day,
                self.plan.total_days if self.plan else self.session.total_days,
                current_profile=self.profile,
            )
            self._add_message(format_coach_message("Today's session is complete! Here is your summary:"))
            self._add_message(format_coach_message(summary))
            # Update profile from the same LLM call that generated the summary.
            # Go through apply_profile_update so nested models are re-validated
            # instead of being replaced by raw dicts.
            if profile_data:
                self.profile = apply_profile_update(self.profile, profile_data)
                save_dynamic_profile(self.profile)
                self.profile_context = format_profile_for_prompt(self.profile)
                self._add_message(format_system_message("Student profile updated for next session."))
            
            self._add_message(format_system_message(
                "Progress saved. Restart the app to open the next day's lesson."
            ))

            completed_day = self.session.current_day
            # Snapshot before clearing: the plan revision needs to see what was
            # actually practised today.
            self._session_note_source = list(self.conversation)
            self.conversation = []
            self.session.training_history = []

            user_data = read_json("user_profile.json") or {}
            user_data["last_completed_day"] = completed_day
            write_json("user_profile.json", user_data)

            next_day = min(completed_day + 1, self.session.total_days)
            self.session.current_day = next_day
            self.session.save()

            # Adapt the remaining days to how the session actually went. This
            # only rewrites days from next_day onward; completed days are
            # out of scope by construction.
            await self._revise_remaining_plan(next_day)

            # Rebuild the day context. Without this the prompt would still say
            # "Today is Day N" after the day counter moved on.
            self._refresh_day_context()
            self._update_sidebar()
        except Exception as e:
            self._add_message(format_error_message(f"Error generating summary: {e}"))
        finally:
            self._set_typing(False)
            self._set_input_locked(False)
            self.query_one("#chat-input", Input).focus()

    def _session_note(self, max_chars: int = 1500) -> str:
        """A short digest of the finished session, for the plan revision prompt."""
        parts = []
        for msg in self.session_note_source or []:
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            role = "Learner" if msg.get("role") == "user" else "Coach"
            parts.append(f"{role}: {content[:300]}")
        note = "\n".join(parts)
        return note[:max_chars]

    async def _revise_remaining_plan(self, next_day: int) -> None:
        if not self.plan or next_day > self.session.total_days:
            return
        try:
            result = await revise_plan_tail(
                self.llm,
                self.plan,
                from_day=next_day,
                profile_context=format_profile_for_prompt(self.profile),
                session_note=self._session_note(),
            )
        except Exception as exc:
            # A failed revision must never block the summary that already
            # succeeded; the existing plan simply stays as it is.
            logger.warning("Plan revision failed: %s", exc)
            return

        if result is None:
            return
        self.plan, reason = result
        message = "Course plan updated to match your progress."
        if reason:
            message += f" Reason: {reason}"
        self._add_message(format_system_message(message))

    def _refresh_day_context(self) -> None:
        """Reload plan, directives and system prompt for the current day."""
        self.plan = load_course_plan() or self.plan
        self.today_plan = get_today_plan(self.plan) if self.plan else None
        self.profile_context = format_profile_for_prompt(self.profile)
        self.directives = build_session_directives(self.profile, self.today_plan)

        if self.today_plan:
            self.system_prompt = build_coach_system_prompt(
                self.today_plan,
                self.plan.total_days if self.plan else self.session.total_days,
                profile_context=self.profile_context,
                persona_context=self.persona_context,
                session_directives=self.directives.render(),
            )
        else:
            self.system_prompt = (
                "You are an encouraging English writing coach. "
                f"=== Student Profile ===\n{self.profile_context}"
                + (f"\n\n{self.persona_context}" if self.persona_context else "")
            )
