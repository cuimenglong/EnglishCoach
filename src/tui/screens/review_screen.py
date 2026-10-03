"""Flashcard review screen: keyboard-driven spaced repetition.

Deliberately minimal. The learner sees the expression, reveals it, then rates
recall with 1-4. That loop is the whole point of SRS, so the screen has exactly
one job and no navigation chrome to get in the way.
"""
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from src.knowledge import (
    apply_review,
    enroll_in_review,
    get_due_cards,
    get_learning_cards,
    review_stats,
)
from src.srs import RATING_AGAIN, RATING_EASY, RATING_GOOD, RATING_HARD, RATING_LABELS


class ReviewScreen(Screen):
    """Review due expressions, one card at a time."""

    TITLE = "Review"

    BINDINGS = [
        Binding("space", "reveal", "Reveal", show=True),
        Binding("1", "rate('1')", "Again", show=True),
        Binding("2", "rate('2')", "Hard", show=True),
        Binding("3", "rate('3')", "Good", show=True),
        Binding("4", "rate('4')", "Easy", show=True),
        Binding("escape", "quit_review", "Back", show=True, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.queue: list = []
        self.index = 0
        self.revealed = False
        self.graded = {"again": 0, "hard": 0, "good": 0, "easy": 0}
        self.started_with = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="review-container"):
            yield Static("", id="review-progress")
            yield Static("", id="review-card")
            yield Static("", id="review-detail")
            with Horizontal(id="review-buttons"):
                yield Button("1 Again", id="rate-1", variant="error")
                yield Button("2 Hard", id="rate-2", variant="warning")
                yield Button("3 Good", id="rate-3", variant="primary")
                yield Button("4 Easy", id="rate-4", variant="success")
            yield Static("", id="review-hint")
        yield Footer()

    def on_mount(self) -> None:
        self.started_with = review_stats()["due"]
        # Fall back to un-enrolled cards so the screen is never mysteriously
        # empty for someone who has expressions but no schedule yet.
        self.queue = get_due_cards(limit=25) or get_learning_cards(limit=25)
        self.index = 0
        self.revealed = False
        self._render_card()

    def _current(self):
        if 0 <= self.index < len(self.queue):
            return self.queue[self.index]
        return None

    # NOTE: deliberately not named _render -- that name is Textual's private
    # Widget._render(), which must return a Visual. Shadowing it with a helper
    # that returns None made every frame of this screen fail to draw.
    def _render_card(self) -> None:
        card = self._current()
        if card is None:
            self._render_finished()
            return

        self.query_one("#review-progress", Static).update(
            f"Card {self.index + 1} of {len(self.queue)}"
            f"   |   reviewed {self.started_with} due"
            if self.started_with else f"Card {self.index + 1} of {len(self.queue)}"
        )

        self.query_one("#review-card", Static).update(
            Text(card.expression, style="bold")
        )

        if self.revealed:
            lines = []
            if card.meaning:
                lines.append(card.meaning)
            if card.example_sentence:
                lines.append(f"e.g. {card.example_sentence}")
            if card.tags:
                lines.append(f"[{card.tags}]")
            self.query_one("#review-detail", Static).update("\n".join(lines))
            self.query_one("#review-hint", Static).update(
                "Rate how well you recalled it:  1 Again   2 Hard   3 Good   4 Easy"
            )
        else:
            self.query_one("#review-detail", Static).update("press Space to reveal")
            self.query_one("#review-hint", Static).update(
                "Try to recall the meaning before revealing."
            )

    def _render_finished(self) -> None:
        self.query_one("#review-progress", Static).update("Review complete")
        self.query_one("#review-card", Static).update(Text("All done", style="bold green"))
        self.query_one("#review-detail", Static).update(
            f"again {self.graded['again']}  |  hard {self.graded['hard']}  |  "
            f"good {self.graded['good']}  |  easy {self.graded['easy']}"
        )
        self.query_one("#review-hint", Static).update("Press Escape to go back.")

    def action_reveal(self) -> None:
        if self._current() is None:
            return
        self.revealed = True
        self._render_card()

    def action_rate(self, value: str) -> None:
        self._rate(int(value))

    def _rate(self, rating: int) -> None:
        card = self._current()
        if card is None:
            return
        # An un-enrolled ("new") card is enrolled on its first rating, so a
        # learner can start a schedule straight from this screen.
        if card.state == "new":
            enroll_in_review(card.id)
        try:
            apply_review(card.id, rating)
        except Exception:
            pass
        self.graded[RATING_LABELS[rating].lower()] += 1

        # A card rated "Again" comes back later in this same sitting.
        self.index += 1
        if rating == RATING_AGAIN and self.index >= len(self.queue):
            remaining = get_due_cards(limit=25)
            if remaining:
                self.queue = remaining
                self.index = 0
        self.revealed = False
        self._render_card()

    def action_quit_review(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("rate-"):
            self._rate(int(btn_id.split("-")[1]))
