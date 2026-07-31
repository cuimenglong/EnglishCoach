from textual.message import Message
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Input, Button, RichLog, Footer
from textual.containers import Container, Horizontal, Vertical
from textual import work
from openai import AuthenticationError, APIError

from src.llm_client import LLMClient
from src.profile import run_assessment_turn, UserProfile
from src.tui.widgets.chat_widgets import (
    format_coach_message,
    format_user_message,
    format_system_message,
    format_error_message,
)


class AssessmentComplete(Message):
    """Posted when the LLM assessment finishes and a profile is ready."""
    def __init__(self, profile: UserProfile) -> None:
        super().__init__()
        self.profile = profile


class AssessmentScreen(Screen):
    """Screen for the initial LLM-based assessment."""

    TITLE = "English Assessment"

    def __init__(self, llm: LLMClient) -> None:
        super().__init__()
        self.llm = llm
        self.conversation: list[dict] = []
        self.profile: UserProfile | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="assessment-layout"):
            with Vertical(id="assessment-chat-panel"):
                yield RichLog(id="assessment-chat-log", wrap=True, highlight=False, markup=True, auto_scroll=True, min_width=1, max_lines=2000)
            with Horizontal(id="assessment-input-area"):
                yield Input(placeholder="Type your response here...", id="assessment-input")
                yield Button("Send", variant="primary", id="btn-assessment-send")
                yield Button("Settings", id="btn-assessment-settings")
        yield Footer()

    def on_mount(self) -> None:
        self._start_assessment()

    @work(thread=False)
    async def _start_assessment(self) -> None:
        chat_log = self.query_one("#assessment-chat-log", RichLog)
        chat_log.write(format_system_message("Starting your English level assessment..."))

        try:
            content, tool_calls = await self.llm.chat([{
                "role": "system",
                "content": "You are an English assessment coach. Start by greeting the user warmly "
                           "and asking a simple question to get them talking. Be casual and friendly.",
            }])
        except AuthenticationError:
            chat_log.write(format_error_message(
                "Authentication failed -- your API key is invalid. "
                "Please go back to Settings and check your key."
            ))
            chat_log.write(format_system_message("Press Escape to return to settings."))
            return
        except APIError as e:
            chat_log.write(format_error_message(f"API Error: {e.message}"))
            chat_log.write(format_system_message("Press Escape to return to settings."))
            return
        except Exception as e:
            chat_log.write(format_error_message(f"Connection error: {e}"))
            chat_log.write(format_system_message("Check your API key / model / base URL in Settings (press Escape)."))
            return

        self.conversation.append({"role": "assistant", "content": content})
        chat_log.write(format_coach_message(content))
        self.query_one("#assessment-input", Input).focus()

    def key_escape(self) -> None:
        """Escape returns to settings on first screen, or does nothing."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-assessment-send":
            self._handle_send()
        elif event.button.id == "btn-assessment-settings":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "assessment-input":
            self._handle_send()

    def _set_input_locked(self, locked: bool) -> None:
        self.query_one("#assessment-input", Input).disabled = locked
        self.query_one("#btn-assessment-send", Button).disabled = locked

    def _handle_send(self) -> None:
        user_input = self.query_one("#assessment-input", Input).value.strip()
        if not user_input:
            return

        self.query_one("#assessment-input", Input).value = ""
        chat_log = self.query_one("#assessment-chat-log", RichLog)
        chat_log.write(format_user_message(user_input))
        self.conversation.append({"role": "user", "content": user_input})
        self._set_input_locked(True)
        self._process_assessment_turn()

    @work(thread=False)
    async def _process_assessment_turn(self) -> None:
        chat_log = self.query_one("#assessment-chat-log", RichLog)
        try:
            self.conversation, self.profile = await run_assessment_turn(self.llm, self.conversation)

            if self.profile:
                chat_log.write(format_system_message("Assessment complete! Generating course plan..."))
                self.post_message(AssessmentComplete(self.profile))
                return

            last_msg = self.conversation[-1]
            if last_msg["role"] == "assistant":
                content = last_msg.get("content", "")
                if content:
                    chat_log.write(format_coach_message(content))

            self._set_input_locked(False)
            self.query_one("#assessment-input", Input).focus()

        except AuthenticationError:
            chat_log.write(format_error_message("Authentication failed. Your API key is invalid."))
            self._set_input_locked(False)
        except APIError as e:
            chat_log.write(format_error_message(f"API Error: {e.message}"))
            self._set_input_locked(False)
        except Exception as e:
            chat_log.write(format_error_message(f"Error: {e}"))
            chat_log.write(format_system_message("Press Escape to return to Settings."))
            self._set_input_locked(False)
