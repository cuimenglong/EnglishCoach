from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Static, ListView, ListItem, Footer
from textual.containers import Container, Vertical
from src.summary import get_summary_dates, load_summary


class HistoryScreen(Screen):
    """Screen for viewing past daily summaries."""

    TITLE = "History"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="history-container"):
            yield Static("Daily Summaries", id="history-title")
            with Vertical():
                yield ListView(id="history-list")
                yield Static("", id="history-content")
        yield Footer()

    def on_mount(self) -> None:
        dates = get_summary_dates()
        history_list = self.query_one("#history-list", ListView)
        if dates:
            for date_str in dates:
                history_list.append(ListItem(Static(date_str)))
        else:
            history_list.append(ListItem(Static("No summaries yet. Complete a day to see it here.")))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_text = event.item.children[0].renderable if hasattr(event.item.children[0], "renderable") else ""
        date_str = item_text.strip()
        if date_str and "No summaries yet" not in date_str:
            summary = load_summary(date_str)
            if summary:
                self.query_one("#history-content", Static).update(summary)

    def key_escape(self) -> None:
        self.app.pop_screen()
