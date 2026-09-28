#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# Query Tarantino - Sprint 1
# Equivalence Check
#
# According to shared/SPEC.md:
#   1. Process the 20 books from sample_data from scratch.
#   2. Use datalake "time" and index "json".
#   3. Compare inverted_index.json using SHA-256.
#   4. Compare SQLite "books", ignoring:
#        - header_path
#        - body_path
#        - indexed_at
#   5. Run the first 10 queries from queries.txt.
#   6. Compare books, order, and scores (< 1e-6).
#
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SAMPLE_DATA_DIR="${PROJECT_ROOT}/sample_data"
QUERIES_FILE="${PROJECT_ROOT}/shared/queries.txt"

# ------------------------------------------------------------
# Commands for each implementation
#
# They can be overridden using environment variables.
# ------------------------------------------------------------

PYTHON_CMD="${TARANTINO_PYTHON_CMD:-python -m tarantino}"
JAVA_CMD="${TARANTINO_JAVA_CMD:-}"
CPP_CMD="${TARANTINO_CPP_CMD:-}"

# ------------------------------------------------------------
# Data directories for each implementation
#
# If the implementations use different paths, they can be changed
# using TARANTINO_*_DATA_DIR.
# ------------------------------------------------------------

PYTHON_DATA_DIR="${TARANTINO_PYTHON_DATA_DIR:-${PROJECT_ROOT}/data/python}"
JAVA_DATA_DIR="${TARANTINO_JAVA_DATA_DIR:-${PROJECT_ROOT}/data/java}"
CPP_DATA_DIR="${TARANTINO_CPP_DATA_DIR:-${PROJECT_ROOT}/data/cpp}"

# ------------------------------------------------------------
# SQLite paths
#
# IMPORTANT:
# When you know the official path, ONLY these three variables
# need to be changed.
#
# Example:
# TARANTINO_PYTHON_DB="${PROJECT_ROOT}/data/python/tarantino.db"
# ------------------------------------------------------------

PYTHON_DB="${TARANTINO_PYTHON_DB:-}"
JAVA_DB="${TARANTINO_JAVA_DB:-}"
CPP_DB="${TARANTINO_CPP_DB:-}"

# ------------------------------------------------------------
# Index paths
#
# They can be changed later if the implementation uses
# a different location.
# ------------------------------------------------------------

PYTHON_INDEX="${TARANTINO_PYTHON_INDEX:-${PYTHON_DATA_DIR}/inverted_index.json}"
JAVA_INDEX="${TARANTINO_JAVA_INDEX:-${JAVA_DATA_DIR}/inverted_index.json}"
CPP_INDEX="${TARANTINO_CPP_INDEX:-${CPP_DATA_DIR}/inverted_index.json}"

# ------------------------------------------------------------
# Temporary directory
# ------------------------------------------------------------

TMP_DIR="$(mktemp -d)"

cleanup() {
    rm -rf "${TMP_DIR}"
}

trap cleanup EXIT

PYTHON_RESULTS="${TMP_DIR}/python_results.jsonl"
JAVA_RESULTS="${TMP_DIR}/java_results.jsonl"
CPP_RESULTS="${TMP_DIR}/cpp_results.jsonl"

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

fail() {
    echo
    echo "ERROR: $1"
    exit 1
}

info() {
    echo
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

# ------------------------------------------------------------
# Initial checks
# ------------------------------------------------------------

info "Checking project files"

[[ -d "${SAMPLE_DATA_DIR}" ]] \
    || fail "sample_data/ does not exist: ${SAMPLE_DATA_DIR}"

[[ -f "${QUERIES_FILE}" ]] \
    || fail "shared/queries.txt does not exist: ${QUERIES_FILE}"

SAMPLE_COUNT="$(find "${SAMPLE_DATA_DIR}" -type f | wc -l)"

if [[ "${SAMPLE_COUNT}" -ne 20 ]]; then
    fail "Exactly 20 files were expected in sample_data/, found ${SAMPLE_COUNT}"
fi

[[ -n "${JAVA_CMD}" ]] \
    || fail "TARANTINO_JAVA_CMD is not configured."

[[ -n "${CPP_CMD}" ]] \
    || fail "TARANTINO_CPP_CMD is not configured."

# ------------------------------------------------------------
# Function to run index
# ------------------------------------------------------------

run_index() {
    local language="$1"
    local command="$2"

    info "Indexing 20 sample books - ${language}"

    (
        cd "${PROJECT_ROOT}"

        # CLI defined in SPEC:
        # tarantino index N
        #
        # For equivalence, we use N=20.
        #
        # shellcheck disable=SC2086
        ${command} index 20
    )
}

# ------------------------------------------------------------
# Function to run the first 10 queries
# ------------------------------------------------------------

run_queries() {
    local language="$1"
    local command="$2"
    local output="$3"

    info "Running first 10 queries - ${language}"

    : > "${output}"

    head -n 10 "${QUERIES_FILE}" | while IFS= read -r query; do

        # Ignore empty lines.
        [[ -z "${query}" ]] && continue

        (
            cd "${PROJECT_ROOT}"

            # Python is used only to correctly escape
            # the query before passing it to the shell.
            quoted_query="$(
                python -c \
                'import shlex,sys; print(shlex.quote(sys.argv[1]))' \
                "${query}"
            )"

            # CLI defined in SPEC:
            # tarantino search "TEXT" --json

            # shellcheck disable=SC2086
            eval "${command} search ${quoted_query} --json"
        )

    done > "${output}"
}

# ------------------------------------------------------------
# PYTHON
# ------------------------------------------------------------

info "PYTHON"

rm -rf "${PYTHON_DATA_DIR}"
mkdir -p "${PYTHON_DATA_DIR}"

run_index "python" "${PYTHON_CMD}"

# ------------------------------------------------------------
# JAVA
# ------------------------------------------------------------

info "JAVA"

rm -rf "${JAVA_DATA_DIR}"
mkdir -p "${JAVA_DATA_DIR}"

run_index "java" "${JAVA_CMD}"

# ------------------------------------------------------------
# C++
# ------------------------------------------------------------

info "C++"

rm -rf "${CPP_DATA_DIR}"
mkdir -p "${CPP_DATA_DIR}"

run_index "cpp" "${CPP_CMD}"

# ------------------------------------------------------------
# COMPARISON OF inverted_index.json
# ------------------------------------------------------------

info "Comparing inverted indexes"

[[ -f "${PYTHON_INDEX}" ]] \
    || fail "Python index does not exist: ${PYTHON_INDEX}"

[[ -f "${JAVA_INDEX}" ]] \
    || fail "Java index does not exist: ${JAVA_INDEX}"

[[ -f "${CPP_INDEX}" ]] \
    || fail "C++ index does not exist: ${CPP_INDEX}"

PYTHON_SHA="$(sha256sum "${PYTHON_INDEX}" | awk '{print $1}')"
JAVA_SHA="$(sha256sum "${JAVA_INDEX}" | awk '{print $1}')"
CPP_SHA="$(sha256sum "${CPP_INDEX}" | awk '{print $1}')"

echo "Python SHA-256: ${PYTHON_SHA}"
echo "Java   SHA-256: ${JAVA_SHA}"
echo "C++    SHA-256: ${CPP_SHA}"

if [[ "${PYTHON_SHA}" != "${JAVA_SHA}" ]]; then
    fail "Python and Java produce different inverted_index.json files."
fi

if [[ "${PYTHON_SHA}" != "${CPP_SHA}" ]]; then
    fail "Python and C++ produce different inverted_index.json files."
fi

echo
echo "OK: all three inverted_index.json files are identical."

# ------------------------------------------------------------
# COMPARISON OF SQLITE
#
# The paths are configurable.
#
# Once you have the official paths, simply set them above:
#
#   PYTHON_DB="..."
#   JAVA_DB="..."
#   CPP_DB="..."
#
# ------------------------------------------------------------

info "Comparing SQLite databases"

if [[ -z "${PYTHON_DB}" || -z "${JAVA_DB}" || -z "${CPP_DB}" ]]; then

    echo
    echo "SQLite is not configured yet."
    echo
    echo "Once you have the official paths, configure:"
    echo
    echo "PYTHON_DB=\"...\""
    echo "JAVA_DB=\"...\""
    echo "CPP_DB=\"...\""
    echo
    echo "The SQLite check will run automatically."
    echo

else

    [[ -f "${PYTHON_DB}" ]] \
        || fail "Python SQLite database does not exist: ${PYTHON_DB}"

    [[ -f "${JAVA_DB}" ]] \
        || fail "Java SQLite database does not exist: ${JAVA_DB}"

    [[ -f "${CPP_DB}" ]] \
        || fail "C++ SQLite database does not exist: ${CPP_DB}"

    python - \
        "${PYTHON_DB}" \
        "${JAVA_DB}" \
        "${CPP_DB}" <<'PY'
import sqlite3
import sys


IGNORED_COLUMNS = {
    "header_path",
    "body_path",
    "indexed_at",
}


def load_books(database):
    connection = sqlite3.connect(database)

    try:
        cursor = connection.cursor()

        # The books table is part of the persistence defined
        # for the equivalence check.
        cursor.execute("PRAGMA table_info(books)")
        columns_info = cursor.fetchall()

        if not columns_info:
            raise RuntimeError(
                f"Table 'books' was not found in {database}"
            )

        columns = [
            row[1]
            for row in columns_info
            if row[1] not in IGNORED_COLUMNS
        ]

        if not columns:
            raise RuntimeError(
                f"No comparable columns found in books: {database}"
            )

        # Quoted identifiers to correctly support column names.
        quoted_columns = ", ".join(
            '"' + column.replace('"', '""') + '"'
            for column in columns
        )

        query = (
            f'SELECT {quoted_columns} '
            f'FROM "books" '
            f'ORDER BY "id"'
        )

        cursor.execute(query)
        rows = cursor.fetchall()

        return columns, rows

    finally:
        connection.close()


def compare(reference_name, reference, candidate_name, candidate):
    reference_columns, reference_rows = reference
    candidate_columns, candidate_rows = candidate

    if reference_columns != candidate_columns:
        raise AssertionError(
            f"Different columns between "
            f"{reference_name} and {candidate_name}: "
            f"{reference_columns} != {candidate_columns}"
        )

    if reference_rows != candidate_rows:
        raise AssertionError(
            f"The books table differs between "
            f"{reference_name} and {candidate_name}"
        )


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "Usage: compare sqlite python java cpp"
        )

    python_db, java_db, cpp_db = sys.argv[1:]

    python_books = load_books(python_db)
    java_books = load_books(java_db)
    cpp_books = load_books(cpp_db)

    compare(
        "Python",
        python_books,
        "Java",
        java_books,
    )

    compare(
        "Python",
        python_books,
        "C++",
        cpp_books,
    )

    print("OK: SQLite books tables are equivalent.")


if __name__ == "__main__":
    main()
PY

fi

# ------------------------------------------------------------
# SEARCH --json
# ------------------------------------------------------------

run_queries "python" "${PYTHON_CMD}" "${PYTHON_RESULTS}"
run_queries "java" "${JAVA_CMD}" "${JAVA_RESULTS}"
run_queries "cpp" "${CPP_CMD}" "${CPP_RESULTS}"

info "Comparing search results"

python "${SCRIPT_DIR}/scripts/compare_search_results.py" \
    "${PYTHON_RESULTS}" \
    "${JAVA_RESULTS}" \
    "${CPP_RESULTS}"

# ------------------------------------------------------------
# RESULT
# ------------------------------------------------------------

echo
echo "============================================================"
echo "EQUIVALENCE CHECK PASSED"
echo "============================================================"
echo
echo "All available equivalence checks have passed."
echo
