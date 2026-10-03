"""P0-3: LLM-supplied search text must not be able to crash the coaching turn.

FTS5 treats its input as a query language, not a plain string. Before the fix,
search_vocabulary passed the raw tool argument straight into MATCH, so a
model-authored query containing a quote or a bare operator raised
sqlite3.OperationalError, which bubbled up and aborted the whole turn.
"""
import pytest

from src import knowledge as K


@pytest.mark.parametrize(
    "hostile",
    [
        '"unbalanced',
        "a AND OR",
        "NOT",
        "x(",
        "*",
        '""',
        "NEAR(",
        "^foo",
        "col:val",
        "-minus",
        "OR OR OR",
        "AND",
    ],
)
def test_hostile_fts_queries_do_not_raise(temp_data_dir, hostile):
    K.init_db()
    K.add_vocabulary("take off", "to leave the ground", "", "phrasal verb")

    results = K.search_vocabulary(hostile)  # must not raise

    assert isinstance(results, list)


@pytest.mark.parametrize(
    "hostile",
    ['"unbalanced', "a AND OR", "NOT", "x(", "*", "NEAR(", "col:val"],
)
def test_hostile_fts_queries_do_not_escape_through_the_tool_handler(temp_data_dir, hostile):
    """The LLM-facing handler must always return a string, never propagate."""
    K.init_db()
    K.add_vocabulary("take off", "to leave the ground", "", "phrasal verb")

    result = K._handle_search(hostile)

    assert isinstance(result, str)
    assert result


def test_punctuation_only_query_short_circuits(temp_data_dir):
    K.init_db()
    K.add_vocabulary("take off", "to leave the ground", "", "")

    assert K.search_vocabulary("!!! ???") == []


def test_search_still_finds_real_matches(temp_data_dir):
    """Sanitising must not break ordinary search."""
    K.init_db()
    K.add_vocabulary("take off", "to leave the ground", "", "phrasal verb")
    K.add_vocabulary("run down", "to criticize", "", "idiom")

    hits = K.search_vocabulary("take off")
    assert [h["expression"] for h in hits] == ["take off"]


def test_search_matches_meaning_and_tags(temp_data_dir):
    K.init_db()
    K.add_vocabulary("take off", "to leave the ground", "", "aviation")

    assert K.search_vocabulary("aviation")
    assert K.search_vocabulary("ground")


def test_build_fts_query_quotes_each_token():
    assert K.build_fts_query("take off") == '"take" "off"'
    assert K.build_fts_query("a AND OR") == '"a" "AND" "OR"'
    assert K.build_fts_query("") == ""
    assert K.build_fts_query("!!!") == ""


def test_build_fts_query_handles_cjk():
    assert K.build_fts_query("学习 单词") == '"学习" "单词"'
