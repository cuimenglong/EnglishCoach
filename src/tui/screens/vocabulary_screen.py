from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Input, Button, Static, ListView, ListItem, Footer
from textual.containers import Container, Horizontal
from src.knowledge import get_all_vocabulary, search_vocabulary, delete_vocabulary, get_vocabulary_count


class VocabularyScreen(Screen):
    """Screen for browsing and managing the vocabulary bank."""

    TITLE = "Vocabulary Bank"

    def __init__(self) -> None:
        super().__init__()
        # Row ids of the entries currently rendered, in display order. Delete
        # resolves against this list instead of re-querying the unfiltered table,
        # which used to remove a different expression after a search.
        self._visible_ids: list[int] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="vocab-container"):
            yield Static("Your Vocabulary Bank", id="vocab-title")
            with Horizontal():
                yield Input(placeholder="Search expressions...", id="vocab-search")
                yield Button("Search", variant="primary", id="btn-vocab-search")
                yield Button("Show All", id="btn-vocab-all")
            yield Static("", id="vocab-count")
            yield ListView(id="vocab-list")
            with Horizontal(classes="button-row"):
                yield Button("Delete Selected", variant="error", id="btn-vocab-delete")
                yield Button("Close", variant="default", id="btn-vocab-close")
        yield Footer()

    def on_mount(self) -> None:
        self._load_all()

    def _load_all(self) -> None:
        items = get_all_vocabulary(limit=200)
        self._populate_list(items)
        self.query_one("#vocab-count", Static).update(f"Total: {get_vocabulary_count()} expressions")

    def _populate_list(self, items: list[dict]) -> None:
        vocab_list = self.query_one("#vocab-list", ListView)
        vocab_list.clear()
        self._visible_ids: list[int] = []
        for item in items:
            label = f"{item['expression']}"
            if item['meaning']:
                label += f"  --  {item['meaning']}"
            if item['tags']:
                label += f" [{item['tags']}]"
            self._visible_ids.append(item["id"])
            vocab_list.append(ListItem(Static(label)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-vocab-search":
            query = self.query_one("#vocab-search", Input).value.strip()
            if query:
                results = get_all_vocabulary(limit=200)
                filtered = [r for r in results if query.lower() in r['expression'].lower() or query.lower() in (r['meaning'] or '').lower()]
                self._populate_list(filtered if filtered else results)
                self.query_one("#vocab-count", Static).update(f"Results: {len(filtered) if filtered else len(results)} expressions")
        elif btn_id == "btn-vocab-all":
            self._load_all()
        elif btn_id == "btn-vocab-delete":
            vocab_list = self.query_one("#vocab-list", ListView)
            idx = vocab_list.index
            if idx is None:
                self.query_one("#vocab-count", Static).update("Select an entry to delete first.")
                return
            if idx < 0 or idx >= len(self._visible_ids):
                self.query_one("#vocab-count", Static).update("Nothing selected.")
                return
            vocab_id = self._visible_ids[idx]
            delete_vocabulary(vocab_id)
            self._load_all()
        elif btn_id == "btn-vocab-close":
            self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "vocab-search":
            self.query_one("#btn-vocab-search", Button).press()

    def key_escape(self) -> None:
        self.app.pop_screen()
