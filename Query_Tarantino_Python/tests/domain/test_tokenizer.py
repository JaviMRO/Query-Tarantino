"""SPEC 14.1, with the official stopwords_en.txt."""

from src.domain.model import TermOccurrences
from src.domain.tokenizer import tokenize


def test_possessives_and_digits_close_terms(official_stopwords):
    assert tokenize("It's the Whale's 2 voyages", official_stopwords) == {
        "whale": TermOccurrences(1, (3,)),
        "voyages": TermOccurrences(1, (5,)),
    }


def test_uppercase_is_folded_and_positions_accumulate(official_stopwords):
    assert tokenize("Whale whale WHALE ship", official_stopwords) == {
        "whale": TermOccurrences(3, (0, 1, 2)),
        "ship": TermOccurrences(1, (3,)),
    }


def test_non_ascii_letters_close_terms(official_stopwords):
    assert tokenize("The café was naïve", official_stopwords) == {
        "caf": TermOccurrences(1, (1,)),
        "na": TermOccurrences(1, (3,)),
    }


def test_apostrophes_and_hyphens_close_terms(official_stopwords):
    assert tokenize("Don't stop-believing", official_stopwords) == {
        "stop": TermOccurrences(1, (2,)),
        "believing": TermOccurrences(1, (3,)),
    }


def test_empty_text(official_stopwords):
    assert tokenize("", official_stopwords) == {}
