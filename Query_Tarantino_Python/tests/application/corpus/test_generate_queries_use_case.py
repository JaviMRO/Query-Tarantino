import random

import pytest

from src.application.corpus.generate_queries_use_case import QUERY_SEED, GenerateQueriesUseCase
from tests.application.fakes import FakeBookCatalog, FakeTermStatistics

TOTAL_BOOKS = 1000
FREQUENT = {f"frequent{index:03d}": 600 for index in range(80)}
MEDIUM = {f"medium{index:03d}": 50 + index for index in range(80)}
RARE = {f"rare{index:03d}": 2 + index % 4 for index in range(80)}
OUTSIDE_EVERY_BAND = {"single": 1, "fortynine": 49, "six": 6, "half": 500}


def generate(frequencies: dict[str, int], seed: int = QUERY_SEED) -> list[str]:
    catalog = FakeBookCatalog({}, indexed_count=TOTAL_BOOKS)
    return GenerateQueriesUseCase(FakeTermStatistics(frequencies), catalog, random.Random(seed)).execute()


def all_frequencies() -> dict[str, int]:
    return {**FREQUENT, **MEDIUM, **RARE, **OUTSIDE_EVERY_BAND}


def test_generates_40_one_term_30_two_term_and_30_three_term_queries() -> None:
    queries = generate(all_frequencies())

    assert [len(query.split(" ")) for query in queries] == [1] * 40 + [2] * 30 + [3] * 30


def test_term_slots_take_the_bands_in_turns() -> None:
    queries = generate(all_frequencies())

    terms = [term for query in queries for term in query.split(" ")]
    assert [term.rstrip("0123456789") for term in terms[:6]] == ["frequent", "medium", "rare"] * 2


def test_only_terms_inside_a_band_are_drawn_and_never_twice() -> None:
    terms = [term for query in generate(all_frequencies()) for term in query.split(" ")]

    assert len(terms) == len(set(terms)) == 190
    assert not set(terms) & set(OUTSIDE_EVERY_BAND)


def test_the_same_seed_gives_the_same_queries_whatever_the_input_order() -> None:
    reversed_frequencies = dict(reversed(list(all_frequencies().items())))

    assert generate(all_frequencies()) == generate(reversed_frequencies)


def test_another_seed_gives_other_queries() -> None:
    assert generate(all_frequencies()) != generate(all_frequencies(), seed=7)


def test_a_band_with_too_few_terms_raises() -> None:
    with pytest.raises(ValueError, match="rare"):
        generate({**FREQUENT, **MEDIUM, "rare000": 3})
