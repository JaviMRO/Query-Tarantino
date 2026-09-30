import json
import sqlite3
from pathlib import Path

from compare_equivalence import SearchOutput, differences, main, query_differences

BOOKS_SCHEMA = (
    "CREATE TABLE books (book_id INTEGER PRIMARY KEY, title TEXT, author TEXT, language TEXT, release_date TEXT, "
    "header_path TEXT, body_path TEXT, indexed_at TEXT)"
)


def output(*hits: tuple[int, float], query: str = "car best") -> SearchOutput:
    return SearchOutput(query, list(hits))


def write_language(
    work_dir: Path, language: str, index: str = '{"car":{"1":1}}\n', score: float = 0.693147, title: str = "Book 1"
) -> Path:
    data_dir = work_dir / language
    (data_dir / "datamarts").mkdir(parents=True)
    (data_dir / "datamarts" / "inverted_index.json").write_text(index, encoding="utf-8")
    with sqlite3.connect(data_dir / "datamarts" / "metadata.sqlite") as connection:
        connection.execute(BOOKS_SCHEMA)
        row = (1, title, "Jane Doe", "en", "", f"{language}/header.txt", f"{language}/body.txt", language)
        connection.execute("INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)
    connection.close()
    search = {"query": "car", "results": [{"book_id": 1, "score": score}], "total": 1}
    (data_dir / "search_results.jsonl").write_text(json.dumps(search) + "\n", encoding="utf-8")
    return data_dir


def test_equal_outputs_have_no_differences() -> None:
    assert query_differences(1, output((3, 2.079442)), output((3, 2.079442))) == []


def test_scores_one_millionth_apart_are_equal() -> None:
    assert query_differences(1, output((3, 2.079442)), output((3, 2.079443))) == []


def test_scores_two_millionths_apart_are_reported() -> None:
    assert query_differences(1, output((3, 2.079442)), output((3, 2.079444))) != []


def test_a_different_order_of_books_is_reported() -> None:
    assert query_differences(1, output((1, 1.0), (2, 1.0)), output((2, 1.0), (1, 1.0))) != []


def test_a_different_query_text_is_reported() -> None:
    assert query_differences(1, output(query="car"), output(query="best")) != []


def test_paths_and_indexed_at_are_not_compared(tmp_path: Path) -> None:
    reference = write_language(tmp_path, "python")
    candidate = write_language(tmp_path, "java")

    assert differences(reference, candidate) == []


def test_a_different_index_and_books_table_are_reported(tmp_path: Path) -> None:
    reference = write_language(tmp_path, "python")
    candidate = write_language(tmp_path, "java", index='{"car":{"1":2}}\n', title="Another title")

    assert len(differences(reference, candidate)) == 2


def test_main_fails_when_a_language_differs(tmp_path: Path) -> None:
    write_language(tmp_path, "python")
    write_language(tmp_path, "cpp", score=0.7)

    assert main(tmp_path, ["python", "cpp"]) == 1


def test_main_passes_when_every_language_matches(tmp_path: Path) -> None:
    write_language(tmp_path, "python")
    write_language(tmp_path, "java")

    assert main(tmp_path, ["python", "java"]) == 0
