#!/usr/bin/env python3

"""
Query Tarantino - Sprint 1

Compares the results of:
    tarantino search "TEXT" --json

according to the equivalence contract defined in the SPEC.

The following are checked:

    - same number of results
    - same books
    - same order
    - absolute score difference < 1e-6
"""

import json
import math
import sys
from pathlib import Path


SCORE_TOLERANCE = 1e-6


def load_results(path: str):
    """
    Loads the JSON results produced by an implementation.

    One JSON object is expected per line.
    """

    results = []

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Results file does not exist: {path}"
        )

    for line_number, line in enumerate(
        file_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = line.strip()

        if not line:
            continue

        try:
            result = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}: invalid JSON on line "
                f"{line_number}: {exc}"
            ) from exc

        results.append(result)

    return results


def get_book_id(result):
    """
    Retrieves the book identifier.

    Both 'id' and 'book_id' are accepted so that the check does not
    depend on an internal naming choice while the implementations
    are being integrated.
    """

    if not isinstance(result, dict):
        raise ValueError(
            f"Result is not a JSON object: {result!r}"
        )

    if "id" in result:
        return result["id"]

    if "book_id" in result:
        return result["book_id"]

    raise ValueError(
        f"Book identifier not found "
        f"in result: {result!r}"
    )


def get_score(result):
    """
    Retrieves and validates the score.
    """

    if not isinstance(result, dict):
        raise ValueError(
            f"Result is not a JSON object: {result!r}"
        )

    if "score" not in result:
        raise ValueError(
            f"Result does not contain 'score': {result!r}"
        )

    try:
        score = float(result["score"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid score: {result!r}"
        ) from exc

    if not math.isfinite(score):
        raise ValueError(
            f"Non-finite score: {result!r}"
        )

    return score


def compare_query_results(
    reference,
    candidate,
    reference_name,
    candidate_name,
):
    """
    Compares two sets of results.
    """

    if len(reference) != len(candidate):
        raise AssertionError(
            f"{reference_name} and {candidate_name} return "
            f"a different number of results: "
            f"{len(reference)} != {len(candidate)}"
        )

    for position, (reference_result, candidate_result) in enumerate(
        zip(reference, candidate)
    ):
        reference_id = get_book_id(reference_result)
        candidate_id = get_book_id(candidate_result)

        # Same book and same order.
        if reference_id != candidate_id:
            raise AssertionError(
                f"Different book at position {position}: "
                f"{reference_name}={reference_id!r}, "
                f"{candidate_name}={candidate_id!r}"
            )

        reference_score = get_score(reference_result)
        candidate_score = get_score(candidate_result)

        difference = abs(reference_score - candidate_score)

        # SPEC: score difference < 1e-6
        if difference >= SCORE_TOLERANCE:
            raise AssertionError(
                f"Different score at position {position}, "
                f"book {reference_id!r}: "
                f"{reference_name}={reference_score}, "
                f"{candidate_name}={candidate_score}, "
                f"difference={difference}"
            )


def main():
    if len(sys.argv) != 4:
        print(
            "Usage:",
            file=sys.stderr,
        )
        print(
            "  compare_search_results.py "
            "PYTHON_RESULTS JAVA_RESULTS CPP_RESULTS",
            file=sys.stderr,
        )
        return 1

    python_file = sys.argv[1]
    java_file = sys.argv[2]
    cpp_file = sys.argv[3]

    try:
        python_results = load_results(python_file)
        java_results = load_results(java_file)
        cpp_results = load_results(cpp_file)

        # Python is used as the reference implementation.
        compare_query_results(
            python_results,
            java_results,
            "Python",
            "Java",
        )

        compare_query_results(
            python_results,
            cpp_results,
            "Python",
            "C++",
        )

    except (AssertionError, ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("OK: search results are equivalent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())