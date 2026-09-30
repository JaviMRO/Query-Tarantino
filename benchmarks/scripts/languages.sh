#!/usr/bin/env bash

export LC_ALL=C

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BENCHMARKS_DIR="${ROOT_DIR}/benchmarks"
SHARED_DIR="${TARANTINO_SHARED_DIR:-${ROOT_DIR}/shared}"
BOOK_IDS_FILE="${SHARED_DIR}/book_ids_benchmark.txt"
QUERIES_FILE="${SHARED_DIR}/queries.txt"

LANGUAGES="${BENCH_LANGUAGES:-python java cpp}"

PYTHON_CMD="${TARANTINO_PYTHON_CMD:-python -m tarantino}"
JAVA_CMD="${TARANTINO_JAVA_CMD:-}"
CPP_CMD="${TARANTINO_CPP_CMD:-}"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

module_dir() {
    case "$1" in
        python) echo "${ROOT_DIR}/Query_Tarantino_Python" ;;
        java) echo "${ROOT_DIR}/Query_Tarantino_Java" ;;
        cpp) echo "${ROOT_DIR}/Query_Tarantino_Cpp" ;;
        *) die "unknown language: $1" ;;
    esac
}

language_command() {
    case "$1" in
        python) echo "${PYTHON_CMD}" ;;
        java) echo "${JAVA_CMD}" ;;
        cpp) echo "${CPP_CMD}" ;;
        *) die "unknown language: $1" ;;
    esac
}

require_language_commands() {
    local language
    for language in ${LANGUAGES}; do
        [[ -n "$(language_command "${language}")" ]] \
            || die "no command for ${language}: set TARANTINO_$(echo "${language}" | tr '[:lower:]' '[:upper:]')_CMD"
    done
}

run_tarantino() {
    local language="$1"
    shift
    local prefix=()
    while [[ $# -gt 0 && "$1" != "--" ]]; do
        prefix+=("$1")
        shift
    done
    shift
    local command
    read -r -a command <<< "$(language_command "${language}")"
    (cd "$(module_dir "${language}")" && "${prefix[@]+"${prefix[@]}"}" "${command[@]}" "$@")
}
