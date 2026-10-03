"""SM-2 scheduling, migration, and the review queue."""
import sqlite3
from datetime import date, timedelta

import pytest

from src import knowledge as K
from src import srs
from src.srs import (
    RATING_AGAIN, RATING_EASY, RATING_GOOD, RATING_HARD,
    ReviewCard, Scheduler, compute_review, get_scheduler,
)

TODAY = date(2026, 10, 3)


def _card(**kw):
    base = dict(
        id=1, expression="take off", meaning="leave the ground",
        example_sentence="The plane took off.", tags="phrasal",
        reps=0, lapses=0, ease=2.5, interval_days=0.0,
        due_at=TODAY.isoformat(), state="new",
    )
    base.update(kw)
    return ReviewCard(**base)


def _step(rating, reps=0, ease=2.5, interval=0.0, on=TODAY):
    return compute_review(reps=reps, lapses=0, ease=ease,
                          interval_days=interval, rating=rating, on=on)


# ------------------------------------------------------------- pure SM-2 --

def test_again_keeps_card_due_today():
    r = _step(RATING_AGAIN)
    assert r["due_at"] == TODAY.isoformat()
    assert r["interval_days"] == 0.0
    assert r["lapses"] == 1
    assert r["state"] == "relearning"


def test_again_lowers_ease_but_not_below_floor():
    ease = srs.MIN_EASE
    assert _step(RATING_AGAIN, reps=5, ease=ease)["ease"] == srs.MIN_EASE


def test_first_good_pushes_one_day():
    r = _step(RATING_GOOD)
    assert r["reps"] == 1
    assert r["due_at"] == (TODAY + timedelta(days=1)).isoformat()
    assert r["state"] == "learning"


def test_second_good_pushes_three_days():
    r = _step(RATING_GOOD, reps=1)
    assert r["due_at"] == (TODAY + timedelta(days=3)).isoformat()


def test_third_good_pushes_seven_days():
    r = _step(RATING_GOOD, reps=2)
    assert r["due_at"] == (TODAY + timedelta(days=7)).isoformat()


def test_later_good_multiplies_by_ease():
    r = _step(RATING_GOOD, reps=5, ease=2.5, interval=10.0)
    assert r["interval_days"] == 25.0


def test_hard_grows_slowly_and_lowers_ease():
    r = _step(RATING_HARD, reps=4, ease=2.5, interval=10.0)
    assert r["interval_days"] == 12.0
    assert r["ease"] == 2.35


def test_easy_raises_ease_and_jumps_further_than_good():
    easy = _step(RATING_EASY, reps=4, ease=2.5, interval=10.0)
    good = _step(RATING_GOOD, reps=4, ease=2.5, interval=10.0)
    assert easy["interval_days"] > good["interval_days"]
    assert easy["ease"] > 2.5


def test_interval_is_capped():
    r = _step(RATING_EASY, reps=20, ease=3.0, interval=1000.0)
    assert r["interval_days"] == srs.MAX_INTERVAL_DAYS


def test_interval_never_below_one_on_success():
    for rating in (RATING_HARD, RATING_GOOD, RATING_EASY):
        r = _step(rating, reps=0, interval=0.0)
        assert r["interval_days"] >= 1.0


def test_every_rating_records_the_review_date():
    for rating in (RATING_AGAIN, RATING_HARD, RATING_GOOD, RATING_EASY):
        assert _step(rating)["last_reviewed_at"] == TODAY.isoformat()


@pytest.mark.parametrize("bad", [0, 5, -1, "good", None])
def test_invalid_rating_is_rejected(bad):
    with pytest.raises(ValueError):
        _step(bad)


def test_state_reaches_review():
    assert _step(RATING_GOOD, reps=3)["state"] == "review"


def test_scheduler_matches_pure_function():
    card = _card(reps=3, ease=2.4, interval_days=6.0, state="review")
    via_scheduler = get_scheduler().review(card, RATING_GOOD, on=TODAY)
    direct = compute_review(reps=3, lapses=0, ease=2.4, interval_days=6.0,
                            rating=RATING_GOOD, on=TODAY)
    assert via_scheduler == direct


def test_is_due_handles_bad_dates():
    assert _card(due_at="not-a-date").is_due(TODAY)
    assert _card(due_at="").is_due(TODAY)
    assert _card(due_at=TODAY.isoformat()).is_due(TODAY)
    assert not _card(due_at=(TODAY + timedelta(days=1)).isoformat()).is_due(TODAY)


# -------------------------------------------------------------- migration --

def test_migrate_adds_columns_to_legacy_table():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE vocabulary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expression TEXT NOT NULL, meaning TEXT DEFAULT '',
        example_sentence TEXT DEFAULT '', tags TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("INSERT INTO vocabulary (expression) VALUES ('legacy row')")

    srs.migrate(conn)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(vocabulary)")}
    for name, _ in srs.SRS_COLUMNS:
        assert name in cols
    row = conn.execute("SELECT state, due_at, source FROM vocabulary").fetchone()
    assert row[0] == "new"
    assert row[1] is None, "legacy rows must not appear in the review queue unasked"
    conn.close()


def test_migrate_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE vocabulary (id INTEGER PRIMARY KEY, expression TEXT)")
    srs.migrate(conn)
    srs.migrate(conn)  # must not raise
    conn.close()


def test_migrate_tolerates_missing_table():
    conn = sqlite3.connect(":memory:")
    srs.migrate(conn)  # no vocabulary table at all
    conn.close()


# ------------------------------------------------------------ review queue --

def test_manual_save_enters_the_queue_immediately(temp_data_dir):
    K.init_db()
    vid = K.add_vocabulary("take off", "leave the ground", "", "phrasal", source="manual")

    assert [c.id for c in K.get_due_cards(on=TODAY)] == [vid]
    assert K.get_due_count(on=TODAY) == 1


def test_coach_save_stays_out_until_enrolled(temp_data_dir):
    """An expression the coach auto-saved has never been consciously studied;
    surfacing it on day one would be noise."""
    K.init_db()
    vid = K.add_vocabulary("run down", "to criticize", "", "idiom", source="coach")

    assert K.get_due_cards(on=TODAY) == []
    assert [c.id for c in K.get_learning_cards()] == [vid]

    assert K.enroll_in_review(vid) is True
    assert [c.id for c in K.get_due_cards(on=TODAY)] == [vid]


def test_enroll_is_not_repeatable(temp_data_dir):
    K.init_db()
    vid = K.add_vocabulary("x", "", "", "", source="coach")
    assert K.enroll_in_review(vid) is True
    assert K.enroll_in_review(vid) is False


def test_failed_card_returns_today(temp_data_dir):
    K.init_db()
    vid = K.add_vocabulary("take off", "", "", "", source="manual")
    K.apply_review(vid, RATING_GOOD, on=TODAY)

    result = K.apply_review(vid, RATING_AGAIN, on=TODAY)

    assert result["due_at"] == TODAY.isoformat()
    assert [c.id for c in K.get_due_cards(on=TODAY)] == [vid]


def test_successful_card_leaves_the_queue(temp_data_dir):
    K.init_db()
    vid = K.add_vocabulary("take off", "", "", "", source="manual")
    K.apply_review(vid, RATING_GOOD, on=TODAY)

    assert K.get_due_cards(on=TODAY) == []
    assert K.get_due_count(on=TODAY) == 0
    assert K.get_due_count(on=TODAY + timedelta(days=1)) == 1


def test_apply_review_persists_all_fields(temp_data_dir):
    K.init_db()
    vid = K.add_vocabulary("take off", "", "", "", source="manual")

    K.apply_review(vid, RATING_AGAIN, on=TODAY)
    card = K.get_review_card(vid)

    assert card.reps == 1
    assert card.lapses == 1
    assert card.state == "relearning"
    assert card.last_reviewed_at == TODAY.isoformat()
    assert card.ease < 2.5


def test_apply_review_unknown_id_returns_none(temp_data_dir):
    K.init_db()
    assert K.apply_review(9999, RATING_GOOD) is None


def test_due_cards_are_most_overdue_first(temp_data_dir):
    K.init_db()
    early = K.add_vocabulary("early", "", "", "", source="manual")
    late = K.add_vocabulary("late", "", "", "", source="manual")
    # both are due, but 'early' has been waiting longer
    K.apply_review(early, RATING_GOOD, on=TODAY - timedelta(days=5))
    K.apply_review(late, RATING_GOOD, on=TODAY - timedelta(days=1))

    ids = [c.id for c in K.get_due_cards(on=TODAY)]
    assert len(ids) == 2, f"expected both cards due, got {ids}"
    assert ids.index(early) < ids.index(late)


def test_due_cards_respect_limit(temp_data_dir):
    K.init_db()
    for i in range(5):
        K.add_vocabulary(f"expr {i}", "", "", "", source="manual")
    assert len(K.get_due_cards(on=TODAY, limit=3)) == 3


def test_review_stats(temp_data_dir):
    K.init_db()
    K.add_vocabulary("manual one", "", "", "", source="manual")
    K.add_vocabulary("coach one", "", "", "", source="coach")

    stats = K.review_stats()
    assert stats["total"] == 2
    assert stats["new"] == 1
    assert stats["scheduled"] == 1
    assert stats["due"] == 1


def test_srs_columns_survive_an_existing_database(temp_data_dir):
    """The upgrade path: a DB created by the previous release has no SRS columns.

    Built the way the old release would have built it, triggers included --
    dropping the table would also drop them and leave the FTS index orphaned.
    """
    import src.knowledge as knowledge
    conn = knowledge.get_connection()
    conn.executescript("DROP TABLE IF EXISTS vocabulary;")
    conn.executescript("""
        CREATE TABLE vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT, expression TEXT NOT NULL,
            meaning TEXT DEFAULT '', example_sentence TEXT DEFAULT '',
            tags TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE VIRTUAL TABLE vocab_fts
            USING fts5(expression, meaning, tags, content='vocabulary', content_rowid='id');
        CREATE TRIGGER vocab_ai AFTER INSERT ON vocabulary BEGIN
            INSERT INTO vocab_fts(rowid, expression, meaning, tags)
            VALUES (new.id, new.expression, new.meaning, new.tags);
        END;
    """)
    conn.execute("INSERT INTO vocabulary (expression, meaning) VALUES ('old entry', 'old meaning')")
    conn.commit()
    conn.close()

    K.init_db()  # should migrate in place

    cols = {r[1] for r in knowledge.get_connection().execute(
        "PRAGMA table_info(vocabulary)").fetchall()}
    assert {"state", "reps", "ease", "interval_days", "due_at", "source"} <= cols

    # old content still searchable, and not dumped into the review queue unasked
    assert [r["expression"] for r in K.search_vocabulary("old entry")] == ["old entry"]
    assert K.get_due_count(on=TODAY) == 0
    assert K.review_stats()["new"] == 1
