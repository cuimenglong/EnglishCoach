import re
import sqlite3
import logging
from pathlib import Path

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
        conn.commit()


def add_vocabulary(expression: str, meaning: str = "", example: str = "", tags: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO vocabulary (expression, meaning, example_sentence, tags) VALUES (?, ?, ?, ?)",
            (expression.strip(), meaning.strip(), example.strip(), tags.strip()),
        )
        conn.commit()
        return cur.lastrowid


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
    vid = add_vocabulary(expression, meaning, example_sentence, tags)
    return f"Saved expression #{vid}: '{expression}'"


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
