from pathlib import Path

from src.domain.model import TermOccurrences
from src.domain.text_processing.tokenizer import tokenize
from src.infrastructure.index.monolithic_json_adapter import JsonPostingsReader, MonolithicJsonAdapter

INDEX_FILE = Path("datamarts/inverted_index.json")


def index_books(data_dir: Path, bodies: dict[int, str], stopwords: frozenset[str]) -> None:
    adapter = MonolithicJsonAdapter(data_dir)
    for book_id, body in bodies.items():
        adapter.write_book_terms(book_id, tokenize(body, stopwords))


def test_three_books_produce_the_spec_14_3_file_byte_by_byte(
    tmp_path: Path, official_stopwords: frozenset[str]
) -> None:
    index_books(tmp_path, {1: "the car is nice", 2: "that car is mine", 3: "the car is the best"}, official_stopwords)

    assert (tmp_path / INDEX_FILE).read_bytes() == (
        b'{"best":{"3":1},"car":{"1":1,"2":1,"3":1},"mine":{"2":1},"nice":{"1":1}}\n'
    )


def test_book_ids_are_sorted_as_text_as_in_spec_14_6(tmp_path: Path, official_stopwords: frozenset[str]) -> None:
    index_books(tmp_path, {5: "the car is nice", 12: "that car is mine"}, official_stopwords)

    assert (tmp_path / INDEX_FILE).read_bytes() == b'{"car":{"12":1,"5":1},"mine":{"12":1},"nice":{"5":1}}\n'


def test_the_file_is_created_if_it_does_not_exist(tmp_path: Path) -> None:
    MonolithicJsonAdapter(tmp_path).write_book_terms(1, {"whale": TermOccurrences(2, (0, 4))})

    assert (tmp_path / INDEX_FILE).read_bytes() == b'{"whale":{"1":2}}\n'


def test_reindexing_a_book_overwrites_its_entries(tmp_path: Path) -> None:
    adapter = MonolithicJsonAdapter(tmp_path)
    adapter.write_book_terms(1, {"whale": TermOccurrences(2, (0, 4))})

    adapter.write_book_terms(1, {"whale": TermOccurrences(3, (0, 4, 9))})

    assert (tmp_path / INDEX_FILE).read_bytes() == b'{"whale":{"1":3}}\n'


def test_writing_leaves_no_tmp_file(tmp_path: Path) -> None:
    MonolithicJsonAdapter(tmp_path).write_book_terms(1, {"whale": TermOccurrences(1, (0,))})

    assert list(tmp_path.rglob("*.tmp")) == []


def test_reader_returns_int_ids_and_empty_postings_for_unknown_terms(tmp_path: Path) -> None:
    adapter = MonolithicJsonAdapter(tmp_path)
    adapter.write_book_terms(12, {"whale": TermOccurrences(2, (0, 4))})
    adapter.write_book_terms(5, {"whale": TermOccurrences(1, (3,))})

    postings = JsonPostingsReader(tmp_path).read_postings(["whale", "ship"])

    assert postings == {"whale": {5: 1, 12: 2}, "ship": {}}


def test_reader_of_a_missing_file_has_no_postings(tmp_path: Path) -> None:
    assert JsonPostingsReader(tmp_path).read_postings(["whale"]) == {"whale": {}}


def test_document_frequencies_count_the_books_of_every_term(tmp_path: Path, official_stopwords: frozenset[str]) -> None:
    index_books(tmp_path, {1: "the car is nice", 2: "that car is mine", 3: "the car is the best"}, official_stopwords)

    frequencies = JsonPostingsReader(tmp_path).document_frequencies()

    assert frequencies == {"best": 1, "car": 3, "mine": 1, "nice": 1}
