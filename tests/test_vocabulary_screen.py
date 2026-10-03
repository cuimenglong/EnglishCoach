"""P0-2: deleting a search result must delete the row the user actually saw.

VocabularyScreen used to re-query get_all_vocabulary(limit=200) on delete and
use the highlighted ListView index against that *unfiltered* list. After any
search, index 0 pointed at a completely different expression, so the delete
destroyed the wrong row (verified: selecting "expression_5" deleted "take off").
"""
import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, ListView, Static

from src import knowledge as K
from src.tui.screens.vocabulary_screen import VocabularyScreen


class _Harness(App):
    def on_mount(self) -> None:
        self.push_screen(VocabularyScreen())


class _Button:
    def __init__(self, id_: str) -> None:
        self.id = id_


class _Pressed:
    """Minimal stand-in for Button.Pressed."""

    def __init__(self, id_: str) -> None:
        self.button = _Button(id_)


def _seed() -> None:
    K.init_db()
    K.add_vocabulary("take off", "to leave the ground", "", "phrasal verb")
    K.add_vocabulary("run down", "to criticize", "", "idiom")
    K.add_vocabulary("expression_1", "m1", "", "")
    K.add_vocabulary("expression_2", "m2", "", "")
    K.add_vocabulary("expression_5", "m5", "", "")


def _run(coro):
    return asyncio.run(coro)


def test_delete_after_search_removes_the_selected_row(temp_data_dir):
    _seed()

    async def scenario():
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, VocabularyScreen)

            # User searches, narrowing the list to a single row.
            screen.query_one("#vocab-search", Input).value = "expression_5"
            screen.on_button_pressed(_Pressed("btn-vocab-search"))
            await pilot.pause()

            visible = [r["expression"] for r in _displayed(screen)]
            assert visible == ["expression_5"], f"expected one row, got {visible}"

            # Highlight the only row and delete it.
            screen.query_one("#vocab-list", ListView).index = 0
            screen.on_button_pressed(_Pressed("btn-vocab-delete"))
            await pilot.pause()

    _run(scenario())

    remaining = {r["expression"] for r in K.get_all_vocabulary(limit=200)}
    assert "expression_5" not in remaining, "the selected expression should be gone"
    # The real regression: the other rows must survive untouched.
    assert remaining == {"take off", "run down", "expression_1", "expression_2"}


def test_delete_without_search_still_works(temp_data_dir):
    _seed()

    async def scenario():
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            displayed = _displayed(screen)
            first = displayed[0]["expression"]
            screen.query_one("#vocab-list", ListView).index = 0
            screen.on_button_pressed(_Pressed("btn-vocab-delete"))
            await pilot.pause()
            return first

    removed = _run(scenario())

    remaining = {r["expression"] for r in K.get_all_vocabulary(limit=200)}
    assert removed not in remaining


def test_delete_with_nothing_highlighted_is_a_noop(temp_data_dir):
    _seed()
    before = {r["expression"] for r in K.get_all_vocabulary(limit=200)}

    async def scenario():
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.query_one("#vocab-list", ListView).index = None
            screen.on_button_pressed(_Pressed("btn-vocab-delete"))
            await pilot.pause()

    _run(scenario())

    assert {r["expression"] for r in K.get_all_vocabulary(limit=200)} == before


def test_desynced_visible_ids_never_deletes_the_wrong_row(temp_data_dir):
    """Guard rail: if the rendered rows and _visible_ids ever disagree, the
    handler must bail out rather than fall back to an unfiltered lookup.

    (Textual clamps ListView.index, so an out-of-range index is not reachable
    through the reactive; the risk is a desync between the two structures.)
    """
    _seed()
    before = {r["expression"] for r in K.get_all_vocabulary(limit=200)}

    async def scenario():
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # Simulate desync: list shows rows, but we have no id mapping.
            screen._visible_ids = []
            screen.query_one("#vocab-list", ListView).index = 0
            screen.on_button_pressed(_Pressed("btn-vocab-delete"))
            await pilot.pause()

    _run(scenario())

    assert {r["expression"] for r in K.get_all_vocabulary(limit=200)} == before


def _displayed(screen):
    """Recover the rows the screen is currently rendering."""
    vocab_list = screen.query_one("#vocab-list", ListView)
    by_id = {r["id"]: r for r in K.get_all_vocabulary(limit=200)}
    return [by_id[i] for i in screen._visible_ids if i in by_id]
