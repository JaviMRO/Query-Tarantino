import math

import pytest

from src.domain.search import query_terms, rank_books

SPEC_14_3_POSTINGS = {"best": {3: 1}, "car": {1: 1, 2: 1, 3: 1}, "mine": {2: 1}, "nice": {1: 1}}


def ranked(query: str, stopwords: frozenset[str]) -> list[tuple[int, str]]:
    terms = query_terms(query, stopwords)
    postings = {term: SPEC_14_3_POSTINGS.get(term, {}) for term in terms}
    return [(hit.book_id, f"{hit.score:.6f}") for hit in rank_books(terms, postings, 3)]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("car", [(1, "0.693147"), (2, "0.693147"), (3, "0.693147")]),
        ("car best", [(3, "2.079442")]),
        ("Best CAR", [(3, "2.079442")]),
        ("nice mine", []),
        ("the", []),
    ],
)
def test_spec_14_3_searches(query: str, expected: list[tuple[int, str]], official_stopwords: frozenset[str]) -> None:
    assert ranked(query, official_stopwords) == expected


def test_query_terms_are_distinct_and_alphabetical(official_stopwords: frozenset[str]) -> None:
    assert query_terms("whale Ship WHALE ahab", official_stopwords) == ["ahab", "ship", "whale"]


def test_a_term_without_postings_matches_nothing() -> None:
    assert rank_books(["car", "zebra"], {"car": {1: 1}, "zebra": {}}, 3) == []


def test_higher_scores_come_first_and_ties_are_broken_by_book_id() -> None:
    postings = {"car": {9: 1, 4: 5, 2: 1}}

    hits = rank_books(["car"], postings, 10)

    assert [hit.book_id for hit in hits] == [4, 2, 9]


def test_scores_equal_to_nine_decimals_are_ordered_by_book_id() -> None:
    postings = {"car": {8: 1, 3: 1}, "ship": {8: 1, 3: 1}}

    hits = rank_books(["car", "ship"], postings, 2)

    assert [hit.book_id for hit in hits] == [3, 8]


def test_the_score_follows_the_tf_idf_formula() -> None:
    hits = rank_books(["whale"], {"whale": {1: 4, 2: 1}}, 5)

    assert hits[0].book_id == 1
    assert hits[0].score == (1.0 + math.log(4.0)) * math.log(1.0 + 5.0 / 2.0)
