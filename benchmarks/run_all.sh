#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/scripts/languages.sh"

RESULTS_DIR="${BENCHMARKS_DIR}/results"
WORK_DIR="${BENCHMARKS_DIR}/work"
BENCH_DIR="${WORK_DIR}/bench"
CSV_HEADER="language,experiment,structure,n_books,metric,value,unit,run"
SHA_FILE="${RESULTS_DIR}/json_index_sha256.csv"
SHA_HEADER="language,n_books,run,sha256"
CORPUS_BOOKS=1000
FIRST_ROUND="${1:-0}"
LAST_ROUND="${2:-5}"
CONFIGURATIONS_FILE="${3:-}"

usage() {
    cat <<USAGE
Usage: benchmarks/run_all.sh [FIRST_ROUND LAST_ROUND [CONFIGURATIONS_FILE]]

Runs every round of SPEC 11.6 (by default 0 to 5; round 0 is the warm-up) in the order of plan.py, after the
equivalence check of SPEC 12, and adds peak_rss, disk_bytes_allocated and the JSON index fingerprint.
CONFIGURATIONS_FILE limits the runs to its lines "language experiment structure n_books", as written by
analyze.py in report/rerun_configurations.txt for the extra rounds of SPEC 11.9.

Environment: TARANTINO_CORPUS_DIR (the 1,000 books, required), BENCH_LANGUAGES (default "python java cpp"),
TARANTINO_PYTHON_CMD, TARANTINO_JAVA_CMD, TARANTINO_CPP_CMD, TARANTINO_MONGO_URL.
USAGE
}

check_prerequisites() {
    [[ -n "${TARANTINO_CORPUS_DIR:-}" ]] || die "TARANTINO_CORPUS_DIR must point to the full benchmark corpus"
    local corpus_books
    corpus_books="$(find "${TARANTINO_CORPUS_DIR}" -maxdepth 1 -name '*.txt' | wc -l | tr -d ' ')"
    [[ "${corpus_books}" -ge "${CORPUS_BOOKS}" ]] || die "${TARANTINO_CORPUS_DIR} holds ${corpus_books} books"
    [[ -f "${BOOK_IDS_FILE}" ]] || die "missing ${BOOK_IDS_FILE}"
    [[ -f "${QUERIES_FILE}" ]] || die "missing ${QUERIES_FILE}"
    /usr/bin/time -v true > /dev/null 2>&1 || die "GNU time (/usr/bin/time -v) is required"
    du -sB1 "${BENCHMARKS_DIR}" > /dev/null 2>&1 || die "GNU du (du -sB1) is required"
    require_language_commands
}

version_of() {
    if ! command -v "$1" > /dev/null 2>&1; then
        echo "unavailable"
        return
    fi
    "$@" 2>&1 | head -n 1
}

mongodb_server_version() {
    python -c 'import sys; from pymongo import MongoClient; print(MongoClient(sys.argv[1], serverSelectionTimeoutMS=2000).server_info()["version"])' \
        "${TARANTINO_MONGO_URL:-mongodb://localhost:27017}" 2> /dev/null || echo "unavailable"
}

write_environment() {
    {
        echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "cpu: $(lscpu 2>/dev/null | awk -F': +' '/Model name/ { print $2; exit }')"
        echo "cores: $(nproc 2>/dev/null || echo unavailable)"
        echo "ram_bytes: $(awk '/MemTotal/ { print $2 * 1024 }' /proc/meminfo 2>/dev/null || echo unavailable)"
        echo "disks: $(lsblk -d -n -o NAME,MODEL,ROTA 2>/dev/null | tr '\n' ';' || echo unavailable)"
        echo "file_system: $(df -T "${ROOT_DIR}" 2>/dev/null | awk 'NR == 2 { print $2 }')"
        echo "os: $(uname -srvm)"
        echo "python: $(version_of python --version)"
        echo "java: $(version_of java -version)"
        echo "cxx: $(version_of c++ --version)"
        echo "cmake: $(version_of cmake --version)"
        echo "mongodb_server: $(mongodb_server_version)"
        echo "python_packages: $(python -m pip freeze 2> /dev/null | tr '\n' ' ')"
        echo "commit: $(git -C "${ROOT_DIR}" rev-parse HEAD)"
        echo "uncommitted_changes: $([[ -n "$(git -C "${ROOT_DIR}" status --porcelain)" ]] && echo yes || echo no)"
    } > "${RESULTS_DIR}/environment.txt"
}

append_csv_row() {
    local file="$1" header="$2" row="$3"
    [[ -f "${file}" ]] || echo "${header}" > "${file}"
    echo "${row}" >> "${file}"
}

allocated_path() {
    local experiment="$1" structure="$2"
    case "${experiment}:${structure}" in
        datalake:time) echo "${BENCH_DIR}/datalake" ;;
        datalake:book) echo "${BENCH_DIR}/datalake_book" ;;
        datalake:batch) echo "${BENCH_DIR}/datalake_batch" ;;
        index:json) echo "${BENCH_DIR}/datamarts/inverted_index.json" ;;
        index:folders) echo "${BENCH_DIR}/datamarts/inverted_index" ;;
        *) echo "" ;;
    esac
}

record_external_measurements() {
    local language="$1" experiment="$2" structure="$3" n_books="$4" round="$5" peak_bytes="$6"
    local out="${RESULTS_DIR}/${language}_${experiment}.csv"
    local row_prefix="${language},${experiment},${structure},${n_books}"
    append_csv_row "${out}" "${CSV_HEADER}" "${row_prefix},peak_rss,$(printf '%.6f' "${peak_bytes}"),bytes,${round}"
    local allocated
    allocated="$(allocated_path "${experiment}" "${structure}")"
    if [[ -n "${allocated}" ]]; then
        local allocated_bytes
        allocated_bytes="$(du -sB1 "${allocated}" | cut -f1)"
        append_csv_row "${out}" "${CSV_HEADER}" \
            "${row_prefix},disk_bytes_allocated,$(printf '%.6f' "${allocated_bytes}"),bytes,${round}"
    fi
    if [[ "${experiment}:${structure}" == "index:json" ]]; then
        local sha
        sha="$(sha256sum "${BENCH_DIR}/datamarts/inverted_index.json" | cut -d ' ' -f1)"
        append_csv_row "${SHA_FILE}" "${SHA_HEADER}" "${language},${n_books},${round},${sha}"
    fi
}

run_configuration() {
    local language="$1" experiment="$2" structure="$3" n_books="$4" round="$5"
    local peak_file
    peak_file="$(mktemp)"
    echo "== round ${round}: ${language} ${experiment} ${structure} ${n_books}"
    run_tarantino "${language}" env TARANTINO_DATA_DIR="${WORK_DIR}" TARANTINO_SHARED_DIR="${SHARED_DIR}" \
        "${BENCHMARKS_DIR}/scripts/run_with_peak_rss.sh" "${peak_file}" \
        -- bench --experiment "${experiment}" --structure "${structure}" --n "${n_books}" --run "${round}" \
        --out "${RESULTS_DIR}/${language}_${experiment}.csv" < /dev/null \
        || die "invalid run: ${language} ${experiment} ${structure} ${n_books} round ${round}"
    record_external_measurements "${language}" "${experiment}" "${structure}" "${n_books}" "${round}" \
        "$(cat "${peak_file}")"
    rm -f "${peak_file}"
}

is_selected() {
    local language="$1" configuration="$2"
    [[ " ${LANGUAGES} " == *" ${language} "* ]] || return 1
    [[ -z "${CONFIGURATIONS_FILE}" ]] || grep -qxF "${configuration}" "${CONFIGURATIONS_FILE}"
}

run_round() {
    local round="$1" plan language experiment structure n_books
    plan="$(python3 "${BENCHMARKS_DIR}/plan.py" --round "${round}")"
    while read -r language experiment structure n_books; do
        if is_selected "${language}" "${language} ${experiment} ${structure} ${n_books}"; then
            run_configuration "${language}" "${experiment}" "${structure}" "${n_books}" "${round}"
        fi
    done <<< "${plan}"
}

main() {
    if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        usage
        exit 0
    fi
    check_prerequisites
    mkdir -p "${RESULTS_DIR}" "${WORK_DIR}"
    "${BENCHMARKS_DIR}/equivalence_check.sh"
    write_environment
    local round
    for ((round = FIRST_ROUND; round <= LAST_ROUND; round++)); do
        run_round "${round}"
    done
    python3 "${BENCHMARKS_DIR}/scripts/validate_csv.py" "${RESULTS_DIR}"
    echo "All rounds finished. Next: python3 benchmarks/analyze.py"
}

main "$@"
