import re
import sqlite3
import logging
from datetime import date
from pathlib import Path

from . import srs
from .srs import ReviewCard, DEFAULT_EASE, get_scheduler
from .utils import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "knowledge.db"

# Word characters only: keeps CJK and accented letters, drops every FTS5
# operator character.
_FTS_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def build_fts_query(query: str) -> str:
    """Turn free-form text into a safe FTS5 MATCH expression.

    FTS5 has its own query language: an unbalanced quote, a bare AND/OR/NOT, or
    a stray operator all raise ``sqlite3.OperationalError``. Since the query text
    originates from LLM tool arguments, those inputs reached the database
    verbatim and could abort the whole coaching turn.

    Quoting every token keeps plain AND-of-terms matching and makes it
    impossible for the caller to inject FTS5 syntax. Returns "" when the input
    has no usable tokens, so the caller can skip the query entirely.
    """
    tokens = _FTS_TOKEN_RE.findall(query or "")
    if not tokens:
        return ""
    return " ".join(f'"{token}"' for token in tokens)


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expression TEXT NOT NULL,
                meaning TEXT DEFAULT '',
                example_sentence TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS vocab_fts
            USING fts5(expression, meaning, tags, content='vocabulary', content_rowid='id');

            CREATE TRIGGER IF NOT EXISTS vocab_ai AFTER INSERT ON vocabulary BEGIN
                INSERT INTO vocab_fts(rowid, expression, meaning, tags)
                VALUES (new.id, new.expression, new.meaning, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS vocab_ad AFTER DELETE ON vocabulary BEGIN
                INSERT INTO vocab_fts(vocab_fts, rowid, expression, meaning, tags)
                VALUES ('delete', old.id, old.expression, old.meaning, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS vocab_au AFTER UPDATE ON vocabulary BEGIN
                INSERT INTO vocab_fts(vocab_fts, rowid, expression, meaning, tags)
                VALUES ('delete', old.id, old.expression, old.meaning, old.tags);
                INSERT INTO vocab_fts(rowid, expression, meaning, tags)
                VALUES (new.id, new.expression, new.meaning, new.tags);
            END;
        """)
        # Idempotent upgrade for databases created before SRS existed.
        srs.migrate(conn)
        conn.commit()


def _ensure_srs_columns(conn: sqlite3.Connection) -> None:
    """Make sure SRS columns exist even if init_db() has not run this session."""
    srs.migrate(conn)


def add_vocabulary(
    expression: str,
    meaning: str = "",
    example: str = "",
    tags: str = "",
    source: str = "manual",
) -> int:
    """Insert an expression.

    Manual /save entries enter the review queue immediately; entries the coach
    auto-saves start as state='new' with no due date so they only come back once
    the learner has deliberately enrolled them.
    """
    from datetime import date

    with get_connection() as conn:
        _ensure_srs_columns(conn)
        cur = conn.execute(
            """INSERT INTO vocabulary
               (expression, meaning, example_sentence, tags, state, source, due_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                expression.strip(), meaning.strip(), example.strip(), tags.strip(),
                "review" if source == "manual" else "new",
                source,
                date.today().isoformat() if source == "manual" else None,
            ),
        )
        conn.commit()
        return cur.lastrowid


def _select_card_sql(where: str, order: str = "") -> str:
    return f"""SELECT id, expression, meaning, example_sentence, tags,
                       reps, lapses, ease, interval_days, due_at, state, last_reviewed_at
                FROM vocabulary {where} {order}"""


def get_review_card(vocab_id: int) -> ReviewCard | None:
    with get_connection() as conn:
        _ensure_srs_columns(conn)
        row = conn.execute(_select_card_sql("WHERE id = ?"), (vocab_id,)).fetchone()
    return _to_card(row) if row else None


def get_due_cards(on: date | None = None, limit: int = 20) -> list[ReviewCard]:
    """Cards due for review, most overdue first.

    state='new' rows with no due date are excluded: an expression the coach
    auto-saved has never been consciously studied, so surfacing it would be
    noise.
    """
    on = on or date.today()
    with get_connection() as conn:
        _ensure_srs_columns(conn)
        rows = conn.execute(
            _select_card_sql(
                "WHERE due_at IS NOT NULL AND due_at <= ?",
                "ORDER BY due_at ASC, reps ASC LIMIT ?",
            ),
            (on.isoformat(), limit),
        ).fetchall()
    return [_to_card(r) for r in rows]


def get_due_count(on: date | None = None) -> int:
    on = on or date.today()
    with get_connection() as conn:
        _ensure_srs_columns(conn)
        return conn.execute(
            "SELECT COUNT(*) FROM vocabulary WHERE due_at IS NOT NULL AND due_at <= ?",
            (on.isoformat(),),
        ).fetchone()[0]


def get_learning_cards(limit: int = 50) -> list[ReviewCard]:
    """Cards still in 'new' state, so the learner can opt into reviewing them."""
    with get_connection() as conn:
        _ensure_srs_columns(conn)
        rows = conn.execute(
            _select_card_sql("WHERE state = 'new'", "ORDER BY created_at DESC LIMIT ?"),
            (limit,),
        ).fetchall()
    return [_to_card(r) for r in rows]


def enroll_in_review(vocab_id: int) -> bool:
    """Move a 'new' card into the review queue starting today."""
    with get_connection() as conn:
        _ensure_srs_columns(conn)
        cur = conn.execute(
            """UPDATE vocabulary
               SET state = 'review', due_at = COALESCE(due_at, ?)
               WHERE id = ? AND state = 'new'""",
            (date.today().isoformat(), vocab_id),
        )
        conn.commit()
        return cur.rowcount > 0


def apply_review(vocab_id: int, rating: int, on: date | None = None) -> dict | None:
    """Record a review result and reschedule the card."""
    card = get_review_card(vocab_id)
    if card is None:
        return None
    update = get_scheduler().review(card, rating, on=on)
    assignments = ", ".join(f"{k} = ?" for k in update)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE vocabulary SET {assignments} WHERE id = ?",
            (*update.values(), vocab_id),
        )
        conn.commit()
    return update


def review_stats() -> dict:
    """Counts for the sidebar/dashboard."""
    with get_connection() as conn:
        _ensure_srs_columns(conn)
        total = conn.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0]
        learning = conn.execute(
            "SELECT COUNT(*) FROM vocabulary WHERE state = 'new'").fetchone()[0]
        scheduled = conn.execute(
            "SELECT COUNT(*) FROM vocabulary WHERE due_at IS NOT NULL").fetchone()[0]
    return {
        "total": total,
        "new": learning,
        "scheduled": scheduled,
        "due": get_due_count(),
    }


def _to_card(row) -> ReviewCard:
    return ReviewCard(
        id=row["id"],
        expression=row["expression"],
        meaning=row["meaning"] or "",
        example_sentence=row["example_sentence"] or "",
        tags=row["tags"] or "",
        reps=row["reps"] or 0,
        lapses=row["lapses"] or 0,
        ease=row["ease"] or DEFAULT_EASE,
        interval_days=row["interval_days"] or 0.0,
        due_at=row["due_at"] or "",
        state=row["state"] or "new",
        last_reviewed_at=row["last_reviewed_at"] or "",
    )


def search_vocabulary(query: str, limit: int = 5) -> list[dict]:
    match_expr = build_fts_query(query)
    if not match_expr:
        return []
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT v.id, v.expression, v.meaning, v.example_sentence, v.tags, v.created_at
                   FROM vocab_fts f JOIN vocabulary v ON f.rowid = v.id
                   WHERE vocab_fts MATCH ? ORDER BY rank LIMIT ?""",
                (match_expr, limit),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        # Never let a malformed query kill the surrounding coaching turn.
        logger.warning("Vocabulary search failed for %r: %s", query, exc)
        return []


def get_all_vocabulary(limit: int = 100, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM vocabulary ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def get_vocabulary_count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0]


def delete_vocabulary(vocab_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM vocabulary WHERE id = ?", (vocab_id,))
        conn.commit()


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "add_vocabulary",
            "description": "Save a useful English expression, phrase, or corrected sentence to the user's personal vocabulary bank for later review and practice.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The English expression, phrase, or sentence to save",
                    },
                    "meaning": {
                        "type": "string",
                        "description": "Brief meaning or explanation in simple English",
                    },
                    "example_sentence": {
                        "type": "string",
                        "description": "An example sentence using this expression correctly",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags for categorization (e.g., grammar, phrasal verb, idiom)",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_vocabulary",
            "description": "Search the user's vocabulary bank for previously saved expressions. Call this to recall what the user has learned and create personalized review opportunities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keywords to find matching expressions",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


TOOL_FUNCTION_MAP = {
    "add_vocabulary": lambda **kw: _handle_add(**kw),
    "search_vocabulary": lambda **kw: _handle_search(**kw),
}


def _handle_add(expression: str, meaning: str = "", example_sentence: str = "", tags: str = ""):
    vid = add_vocabulary(
        expression, meaning, example_sentence, tags, source="coach"
    )
    return (
        f"Saved expression #{vid}: '{expression}'. It is available in the "
        "vocabulary bank and can be added to the review schedule."
    )


def _handle_search(query: str):
    try:
        results = search_vocabulary(query)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("search_vocabulary tool call failed: %s", exc)
        return "Vocabulary search is temporarily unavailable."
    if not results:
        return "No matching expressions found in your vocabulary bank."
    lines = ["Found these expressions from your vocabulary bank:"]
    for r in results:
        lines.append(f"- {r['expression']} ({r['meaning']}) [tags: {r['tags']}]")
    return "\n".join(lines)
