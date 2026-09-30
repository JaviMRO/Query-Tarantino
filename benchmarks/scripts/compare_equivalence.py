"""
Comparison step of the equivalence check (SPEC 12): each language is compared with the first one.

Usage: compare_equivalence.py WORK_DIR LANGUAGE [LANGUAGE...]
where WORK_DIR/<language>/ holds datamarts/ and search_results.jsonl.
"""

import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

INDEX_FILE = Path("datamarts") / "inverted_index.json"
METADATA_FILE = Path("datamarts") / "metadata.sqlite"
SEARCH_RESULTS_FILE = "search_results.jsonl"
COMPARED_BOOK_COLUMNS = "SELECT book_id, title, author, language, release_date FROM books ORDER BY book_id"
SCORE_TOLERANCE = 1e-6 + 1e-9


def index_sha256(data_dir: Path) -> str:
    """SHA-256 of the inverted_index.json of a language (SPEC 12 step 2)."""
    return hashlib.sha256((data_dir / INDEX_FILE).read_bytes()).hexdigest()


def books_table(data_dir: Path) -> list[tuple[object, ...]]:
    """The books table sorted by book_id, without the paths and indexed_at (SPEC 12 step 3)."""
    with closing(sqlite3.connect(data_dir / METADATA_FILE)) as connection:
        return connection.execute(COMPARED_BOOK_COLUMNS).fetchall()


@dataclass(frozen=True, slots=True)
class SearchOutput:
    """One line of search --json: the query and its (book_id, score) results in order."""

    query: str
    hits: list[tuple[int, float]]


def search_outputs(data_dir: Path) -> list[SearchOutput]:
    """The search --json lines of a language, in query order."""
    lines = (data_dir / SEARCH_RESULTS_FILE).read_text(encoding="utf-8").splitlines()
    return [parse_search_output(line) for line in lines if line]


def parse_search_output(line: str) -> SearchOutput:
    """The query and the ordered (book_id, score) pairs of one search --json line."""
    output = json.loads(line)
    return SearchOutput(output["query"], [(result["book_id"], result["score"]) for result in output["results"]])


def query_differences(number: int, reference: SearchOutput, candidate: SearchOutput) -> list[str]:
    """Differences in one query: text, books and order, or a score beyond the tolerance (SPEC 12 step 4)."""
    if reference.query != candidate.query:
        return [f"query {number}: different query text"]
    if [book_id for book_id, _ in reference.hits] != [book_id for book_id, _ in candidate.hits]:
        return [f"query {number} ({reference.query!r}): books or order differ"]
    return [
        f"query {number}: book {book_id} scores {first} and {second}"
        for (book_id, first), (_, second) in zip(reference.hits, candidate.hits, strict=True)
        if abs(first - second) > SCORE_TOLERANCE
    ]


def differences(reference_dir: Path, candidate_dir: Path) -> list[str]:
    """Everything that differs between two languages: index, books table and searches."""
    found = []
    if index_sha256(reference_dir) != index_sha256(candidate_dir):
        found.append("inverted_index.json differs (SHA-256)")
    if books_table(reference_dir) != books_table(candidate_dir):
        found.append("the books tables differ")
    reference_searches, candidate_searches = search_outputs(reference_dir), search_outputs(candidate_dir)
    if len(reference_searches) != len(candidate_searches):
        found.append("a different number of search outputs")
    for number, (first, second) in enumerate(zip(reference_searches, candidate_searches, strict=False), start=1):
        found.extend(query_differences(number, first, second))
    return found


def main(work_dir: Path, languages: list[str]) -> int:
    """Compares every language with the first one; exit code 1 if any of them differs."""
    reference = languages[0]
    for language in languages:
        print(f"{language}: inverted_index.json sha256 {index_sha256(work_dir / language)}")
    if len(languages) == 1:
        print(f"PARTIAL: only {reference} was run, so nothing was compared across languages (SPEC 12 needs all three)")
        return 0
    failures = 0
    for language in languages[1:]:
        for difference in differences(work_dir / reference, work_dir / language):
            print(f"MISMATCH {reference} vs {language}: {difference}")
            failures += 1
    print("EQUIVALENCE CHECK FAILED" if failures else f"EQUIVALENCE CHECK PASSED: {', '.join(languages)}")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    raise SystemExit(main(Path(sys.argv[1]), sys.argv[2:]))
