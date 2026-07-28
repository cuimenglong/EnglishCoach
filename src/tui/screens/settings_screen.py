from textual.message import Message

from textual.app import ComposeResult, Screen
from textual.widgets import Header, Input, Button, Label, Static, Footer
from textual.containers import Container, Horizontal
from src.config import load_config, save_config, Config


class SettingsSaved(Message):
    """Posted when settings have been saved."""
    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config


class SettingsScreen(Screen[Config]):
    """Screen for configuring API settings."""

    TITLE = "Settings"

    def __init__(self, config: Config | None = None) -> None:
        super().__init__()
        self._config = config or load_config()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="settings-container"):
            yield Label("API Configuration", classes="section-title")
            yield Label("OpenAI API Key", classes="field-label")
            yield Input(
                value=self._config.openai_api_key,
                placeholder="sk-...",
                password=True,
                id="api-key-input",
            )
            yield Label("Model Name", classes="field-label")
            yield Input(
                value=self._config.model_name,
                placeholder="gpt-4o, deepseek-chat, etc.",
                id="model-input",
            )
            yield Label("Base URL", classes="field-label")
            yield Input(
                value=self._config.base_url,
                placeholder="https://api.openai.com/v1",
                id="base-url-input",
            )
            yield Label("Temperature", classes="field-label")
            yield Input(
                value=str(self._config.temperature),
                placeholder="0.7",
                id="temperature-input",
            )
            with Horizontal(classes="button-row"):
                yield Button("Save", variant="primary", id="btn-save-settings")
                yield Button("Cancel", variant="default", id="btn-cancel-settings")
            yield Static("", id="settings-status")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-settings":
            self._save()
        elif event.button.id == "btn-cancel-settings":
            self.dismiss(None)

    def _save(self) -> None:
        api_key = self.query_one("#api-key-input", Input).value.strip()
        model = self.query_one("#model-input", Input).value.strip() or "gpt-4o"
        base_url = self.query_one("#base-url-input", Input).value.strip() or "https://api.openai.com/v1"
        temp_str = self.query_one("#temperature-input", Input).value.strip() or "0.7"
        try:
            temp = max(0.0, min(2.0, float(temp_str)))
        except ValueError:
            temp = 0.7

        config = Config(
            openai_api_key=api_key,
            model_name=model,
            base_url=base_url,
            temperature=temp,
        )
        save_config(config)
        self.dismiss(config)
from textual.screen import Screen
