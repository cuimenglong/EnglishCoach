"""Spaced-repetition scheduling for the vocabulary bank.

SM-2 behind a small Scheduler interface. SM-2 is chosen over FSRS deliberately:
it has one number to tune (ease) instead of a dozen, so it behaves predictably
for a single user, and swapping in FSRS later only means a new Scheduler
implementation -- callers already go through get_scheduler().

The review queue is what makes the coach proactive: session directives include
whatever is due, so a learner sees expressions for revision without having to
ask for it.
"""
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Ratings the learner gives. The numeric values are part of the stored history,
# so they must stay stable.
RATING_AGAIN = 1
RATING_HARD = 2
RATING_GOOD = 3
RATING_EASY = 4
RATING_LABELS = {RATING_AGAIN: "Again", RATING_HARD: "Hard",
                 RATING_GOOD: "Good", RATING_EASY: "Easy"}

DEFAULT_EASE = 2.5
MIN_EASE = 1.3
MAX_EASE = 3.0
MAX_INTERVAL_DAYS = 180

# A card the learner just failed comes back the same day. A first success steps
# out by 1/3/7 days, or further if the learner rated it easy.
_FIRST_INTERVAL = {1: 1.0, 2: 3.0, 3: 7.0}


@dataclass
class ReviewCard:
    id: int
    expression: str
    meaning: str
    example_sentence: str
    tags: str
    reps: int
    lapses: int
    ease: float
    interval_days: float
    due_at: str
    state: str
    last_reviewed_at: str = ""

    def is_due(self, on: date | None = None) -> bool:
        on = on or date.today()
        try:
            return date.fromisoformat(self.due_at) <= on
        except (TypeError, ValueError):
            # An unreadable due date should not silently hide the card.
            return True


def compute_review(
    *,
    reps: int,
    lapses: int,
    ease: float,
    interval_days: float,
    rating: int,
    on: date | None = None,
) -> dict:
    """Advance one card by `rating`. Pure: takes state, returns new state.

    This is the single place interval arithmetic happens. Returns the column
    values to persist.
    """
    if rating not in RATING_LABELS:
        raise ValueError(f"rating must be one of {sorted(RATING_LABELS)}")

    on = on or date.today()
    ease = float(ease or DEFAULT_EASE)
    interval = float(interval_days or 0.0)
    new_lapses = lapses

    if rating == RATING_AGAIN:
        # Failed. Keep it in rotation today and make future cards slightly harder.
        ease = max(MIN_EASE, ease - 0.20)
        new_lapses = lapses + 1
        return {
            "reps": reps + 1,
            "lapses": new_lapses,
            "ease": round(ease, 2),
            "interval_days": 0.0,
            "due_at": on.isoformat(),
            "state": "relearning",
            "last_reviewed_at": on.isoformat(),
        }

    if rating == RATING_HARD:
        ease = max(MIN_EASE, ease - 0.15)
        # Barely grows; this is the "I knew it but it was hard" button.
        new_interval = max(1.0, (interval or 1.0) * 1.2)
        state = "review" if reps >= 2 else "learning"
    elif rating == RATING_EASY:
        ease = min(MAX_EASE, ease + 0.15)
        new_interval = (interval or 1.0) * ease * 1.3
        state = "review"
    else:  # GOOD
        if reps <= 0:
            new_interval = _FIRST_INTERVAL[1]
        elif reps == 1:
            new_interval = _FIRST_INTERVAL[2]
        elif reps == 2:
            new_interval = _FIRST_INTERVAL[3]
        else:
            new_interval = interval * ease
        state = "learning" if reps < 2 else "review"

    new_interval = min(MAX_INTERVAL_DAYS, max(1.0, round(new_interval, 2)))
    return {
        "reps": reps + 1,
        "lapses": new_lapses,
        "ease": round(ease, 2),
        "interval_days": new_interval,
        "due_at": (on + timedelta(days=new_interval)).isoformat(),
        "state": state,
        "last_reviewed_at": on.isoformat(),
    }


def next_due(interval_days: float, on: date | None = None) -> str:
    on = on or date.today()
    return (on + timedelta(days=max(0.0, float(interval_days)))).isoformat()


# -------------------------------------------------------------- migrations --

# Column name -> DDL. Kept in one place so migrate() and the knowledge layer
# stay in sync.
SRS_COLUMNS = [
    ("state", "TEXT NOT NULL DEFAULT 'new'"),
    ("reps", "INTEGER NOT NULL DEFAULT 0"),
    ("lapses", "INTEGER NOT NULL DEFAULT 0"),
    ("ease", f"REAL NOT NULL DEFAULT {DEFAULT_EASE}"),
    ("interval_days", "REAL NOT NULL DEFAULT 0"),
    ("due_at", "TEXT"),
    ("last_reviewed_at", "TEXT"),
    ("source", "TEXT NOT NULL DEFAULT 'manual'"),
]


def migrate(conn: sqlite3.Connection) -> None:
    """Add SRS columns to an existing vocabulary table. Idempotent.

    Existing rows keep their content and get state='new' with no due date, so
    they stay out of the review queue until the learner opts in. A database
    created before this ran has no 'state' column at all, which is the case
    this exists for.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)").fetchall()}
    if not existing:
        return  # table does not exist yet; CREATE TABLE will make it properly
    for name, ddl in SRS_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE vocabulary ADD COLUMN {name} {ddl}")
    conn.execute("UPDATE vocabulary SET state = 'new' WHERE state IS NULL")
    conn.execute("UPDATE vocabulary SET source = 'manual' WHERE source IS NULL")
    conn.commit()


class Scheduler:
    """Indirection so the algorithm can be replaced without touching callers."""

    def review(self, card: ReviewCard, rating: int, on: date | None = None) -> dict:
        return compute_review(
            reps=card.reps,
            lapses=card.lapses,
            ease=card.ease,
            interval_days=card.interval_days,
            rating=rating,
            on=on,
        )


def get_scheduler() -> Scheduler:
    return Scheduler()
