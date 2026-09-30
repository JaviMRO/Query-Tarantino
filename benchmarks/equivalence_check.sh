#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/scripts/languages.sh"

WORK_DIR="${BENCHMARKS_DIR}/work/equivalence"
SAMPLE_DIR="${SHARED_DIR}/sample_dataset"
STEPS=40
COMPARED_QUERIES=10

process_sample() {
    local language="$1"
    local data_dir="${WORK_DIR}/${language}"
    rm -rf "${data_dir}"
    mkdir -p "${data_dir}"
    echo "== ${language}: ${STEPS} control steps over the sample dataset"
    run_tarantino "${language}" env \
        TARANTINO_DATA_DIR="${data_dir}" TARANTINO_DOWNLOADER=local TARANTINO_CORPUS_DIR="${SAMPLE_DIR}" \
        TARANTINO_LAKE=time TARANTINO_INDEX=json TARANTINO_SHARED_DIR="${SHARED_DIR}" \
        -- run --steps "${STEPS}" --ids "${BOOK_IDS_FILE}" > "${data_dir}/run.log" < /dev/null
}

run_queries() {
    local language="$1"
    local data_dir="${WORK_DIR}/${language}"
    local query
    echo "== ${language}: first ${COMPARED_QUERIES} queries"
    head -n "${COMPARED_QUERIES}" "${QUERIES_FILE}" | while IFS= read -r query; do
        run_tarantino "${language}" env TARANTINO_DATA_DIR="${data_dir}" TARANTINO_INDEX=json \
            TARANTINO_SHARED_DIR="${SHARED_DIR}" -- search "${query}" --json < /dev/null
    done > "${data_dir}/search_results.jsonl"
}

main() {
    [[ -d "${SAMPLE_DIR}" ]] || die "missing ${SAMPLE_DIR}"
    [[ -f "${BOOK_IDS_FILE}" ]] || die "missing ${BOOK_IDS_FILE}"
    [[ -f "${QUERIES_FILE}" ]] || die "missing ${QUERIES_FILE}"
    require_language_commands
    local language
    for language in ${LANGUAGES}; do
        process_sample "${language}"
        run_queries "${language}"
    done
    local compared_languages
    read -r -a compared_languages <<< "${LANGUAGES}"
    python3 "${BENCHMARKS_DIR}/scripts/compare_equivalence.py" "${WORK_DIR}" "${compared_languages[@]}"
}

main "$@"
