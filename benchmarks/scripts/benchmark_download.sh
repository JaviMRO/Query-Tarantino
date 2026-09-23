#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

RESULTS_DIR="${ROOT_DIR}/benchmarks/results"
BOOKS_FILE="${ROOT_DIR}/shared/book_ids_benchmark.txt"
PEAK_RSS_SCRIPT="${ROOT_DIR}/benchmarks/scripts/run_with_peak_rss.sh"

LANGUAGE="${LANGUAGE:-python}"
TARANTINO_CMD="${TARANTINO_CMD:-python -m tarantino}"

N_BOOKS=(100 250 500 1000)
RUNS=(0 1 2 3)

OUTPUT_FILE="${RESULTS_DIR}/${LANGUAGE}_download.csv"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_file() {
    local file="$1"
    [[ -f "${file}" ]] || die "required file does not exist: ${file}"
}

prepare_output() {
    rm -f "${OUTPUT_FILE}"
}

run_one() {
    local n_books="$1"
    local run="$2"

    local peak_file
    local peak_rss

    peak_file="${OUTPUT_FILE}.peak_rss"

    rm -f "${peak_file}"

    echo
    echo "----------------------------------------"
    echo "Download benchmark"
    echo "language:   ${LANGUAGE}"
    echo "structure:  none"
    echo "n_books:    ${n_books}"
    echo "run:        ${run}"
    echo "----------------------------------------"

    "${PEAK_RSS_SCRIPT}" \
        "${OUTPUT_FILE}" \
        bash -c "${TARANTINO_CMD} bench \
            --experiment download \
            --structure none \
            --books '${BOOKS_FILE}' \
            --n '${n_books}' \
            --run '${run}' \
            --out '${OUTPUT_FILE}'"

    [[ -f "${peak_file}" ]] \
        || die "peak RSS measurement was not produced"

    peak_rss="$(cat "${peak_file}")"

    [[ "${peak_rss}" =~ ^[0-9]+$ ]] \
        || die "invalid peak RSS value: ${peak_rss}"

    printf '%s,%s,%s,%s,peak_rss,%.1f,bytes,%s\n' \
        "${LANGUAGE}" \
        "download" \
        "none" \
        "${n_books}" \
        "${peak_rss}" \
        "${run}" \
        >> "${OUTPUT_FILE}"

    rm -f "${peak_file}"
}

main() {
    mkdir -p "${RESULTS_DIR}"

    require_file "${BOOKS_FILE}"
    require_file "${PEAK_RSS_SCRIPT}"

    prepare_output

    for n_books in "${N_BOOKS[@]}"; do
        for run in "${RUNS[@]}"; do
            run_one "${n_books}" "${run}"
        done
    done

    echo
    echo "Download benchmarks completed."
    echo "Results: ${OUTPUT_FILE}"
}

main "$@"