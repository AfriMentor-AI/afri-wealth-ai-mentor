"""C2.1 — African English / local expression lexicon."""
from app.services.lexicon import EXPRESSION_LEXICON, expand_query, find_expressions


def test_find_expressions_detects_local_terms():
    assert find_expressions("how to grow my hustle") == ["hustle"]
    assert find_expressions("na wahala everywhere") == ["wahala"]
    assert find_expressions("nothing here") == []
    assert find_expressions("") == []


def test_find_expressions_prefers_longest_match():
    # "side hustle" must win over the bare "hustle" substring.
    assert "side hustle" in find_expressions("starting a side hustle")


def test_find_expressions_is_case_insensitive_and_deduped():
    assert find_expressions("Hustle and hustle and HUSTLE") == ["hustle"]


def test_find_expressions_respects_word_boundaries():
    # "ajo" must not fire inside an unrelated word.
    assert find_expressions("major projects") == []


def test_expand_query_adds_standard_english():
    out = expand_query("how to grow my hustle")
    assert out.startswith("how to grow my hustle")  # original preserved
    assert "business" in out


def test_expand_query_handles_informal_finance_terms():
    out = expand_query("how does esusu work")
    assert "rotating savings" in out
    assert "savings group" in out


def test_expand_query_noop_without_local_terms():
    q = "how to start a fashion business in Nigeria"
    assert expand_query(q) == q


def test_expand_query_multiple_expressions():
    out = expand_query("my oga said the wahala is too much")
    assert "boss" in out
    assert "problem" in out or "trouble" in out


def test_lexicon_entries_are_wellformed():
    for key, expansions in EXPRESSION_LEXICON.items():
        assert key == key.lower(), f"{key} must be lowercase"
        assert expansions, f"{key} has no expansions"
        assert len(set(expansions)) == len(expansions), f"{key} has duplicates"
