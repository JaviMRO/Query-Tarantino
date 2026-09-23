#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RESULTS_DIR="${ROOT_DIR}/benchmarks/results"
SCRIPTS_DIR="${ROOT_DIR}/benchmarks/scripts"
BOOKS_FILE="${ROOT_DIR}/shared/book_ids_benchmark.txt"

PYTHON_CMD="${TARANTINO_PYTHON_CMD:-python -m tarantino}"
JAVA_CMD="${TARANTINO_JAVA_CMD:-}"
CPP_CMD="${TARANTINO_CPP_CMD:-}"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_file() {
    local file="$1"

    [[ -f "${file}" ]] \
        || die "required file does not exist: ${file}"
}

require_executable() {
    local file="$1"

    [[ -x "${file}" ]] \
        || die "required executable does not exist or is not executable: ${file}"
}

check_prerequisites() {
    require_file "${BOOKS_FILE}"

    require_executable "${SCRIPTS_DIR}/benchmark_datalake.sh"
    require_executable "${SCRIPTS_DIR}/benchmark_index.sh"
    require_executable "${SCRIPTS_DIR}/benchmark_download.sh"
    require_executable "${SCRIPTS_DIR}/run_with_peak_rss.sh"

    require_file "${SCRIPTS_DIR}/validate_csv.py"

    command -v python >/dev/null 2>&1 \
        || die "python is required"

    [[ -x "/usr/bin/time" ]] \
        || die "/usr/bin/time is required"
}

run_language_benchmarks() {
    local language="$1"
    local command="$2"

    echo
    echo "========================================"
    echo "Running ${language} benchmarks"
    echo "========================================"

    LANGUAGE="${language}" \
    TARANTINO_CMD="${command}" \
        "${SCRIPTS_DIR}/benchmark_datalake.sh"

    LANGUAGE="${language}" \
    TARANTINO_CMD="${command}" \
        "${SCRIPTS_DIR}/benchmark_index.sh"

    LANGUAGE="${language}" \
    TARANTINO_CMD="${command}" \
        "${SCRIPTS_DIR}/benchmark_download.sh"
}

validate_results() {
    local language="$1"

    for experiment in datalake index download; do
        local output_file="${RESULTS_DIR}/${language}_${experiment}.csv"

        require_file "${output_file}"

        python "${SCRIPTS_DIR}/validate_csv.py" \
            "${output_file}"
    done
}

main() {
    mkdir -p "${RESULTS_DIR}"

    check_prerequisites

    # Python
    run_language_benchmarks \
        "python" \
        "${PYTHON_CMD}"

    # Java
    [[ -n "${JAVA_CMD}" ]] \
        || die "TARANTINO_JAVA_CMD is not set"

    run_language_benchmarks \
        "java" \
        "${JAVA_CMD}"

    # C++
    [[ -n "${CPP_CMD}" ]] \
        || die "TARANTINO_CPP_CMD is not set"

    run_language_benchmarks \
        "cpp" \
        "${CPP_CMD}"

    echo
    echo "========================================"
    echo "Validating benchmark results"
    echo "========================================"

    validate_results "python"
    validate_results "java"
    validate_results "cpp"

    echo
    echo "========================================"
    echo "All benchmarks completed successfully."
    echo "========================================"
}

main "$@"