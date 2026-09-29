from pathlib import Path

from src.infrastructure.corpus.file_corpus_store import FileCorpusStore, copy_sample_dataset

TEXT = "Title: Café\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nbody\n*** END OF THE PROJECT GUTENBERG EBOOK X ***"


def test_save_text_writes_the_exact_text_with_a_safe_write(tmp_path: Path) -> None:
    store = FileCorpusStore(tmp_path / "corpus_raw", tmp_path / "shared" / "book_ids_benchmark.txt")

    store.save_text(1342, TEXT)

    assert (tmp_path / "corpus_raw" / "1342.txt").read_bytes() == TEXT.encode()
    assert list(tmp_path.rglob("*.tmp")) == []


def test_selected_ids_are_appended_one_per_line_and_read_back(tmp_path: Path) -> None:
    ids_path = tmp_path / "shared" / "book_ids_benchmark.txt"
    FileCorpusStore(tmp_path / "corpus_raw", ids_path).record_selected(1)
    FileCorpusStore(tmp_path / "corpus_raw", ids_path).record_selected(12)

    store = FileCorpusStore(tmp_path / "corpus_raw", ids_path)

    assert ids_path.read_bytes() == b"1\n12\n"
    assert store.get_selected_books() == [1, 12]


def test_a_missing_id_list_means_nothing_selected(tmp_path: Path) -> None:
    store = FileCorpusStore(tmp_path / "corpus_raw", tmp_path / "shared" / "book_ids_benchmark.txt")

    assert store.get_selected_books() == []


def test_copy_sample_dataset_copies_only_the_first_20_books_byte_for_byte(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus_raw"
    store = FileCorpusStore(corpus_dir, tmp_path / "ids.txt")
    book_ids = list(range(1, 26))
    for book_id in book_ids:
        store.save_text(book_id, f"{TEXT} {book_id}")

    copy_sample_dataset(corpus_dir, tmp_path / "sample_dataset", book_ids)

    copied = sorted(int(path.stem) for path in (tmp_path / "sample_dataset").iterdir())
    assert copied == list(range(1, 21))
    assert (tmp_path / "sample_dataset" / "7.txt").read_bytes() == (corpus_dir / "7.txt").read_bytes()
