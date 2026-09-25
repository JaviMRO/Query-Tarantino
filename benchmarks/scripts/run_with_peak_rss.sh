#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: run_with_peak_rss.sh <output_csv> <command> [args...]" >&2
    exit 1
fi

OUTPUT_CSV="$1"
shift

TIME_OUTPUT="$(mktemp)"

cleanup() {
    rm -f "${TIME_OUTPUT}"
}

trap cleanup EXIT

/usr/bin/time -v -o "${TIME_OUTPUT}" "$@"

PEAK_KB="$(
    awk -F': ' '
        /Maximum resident set size/ {
            print $2
            exit
        }
    ' "${TIME_OUTPUT}"
)"

if [[ -z "${PEAK_KB}" ]]; then
    echo "ERROR: could not obtain peak RSS from /usr/bin/time" >&2
    exit 2
fi

if ! [[ "${PEAK_KB}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: invalid peak RSS value: ${PEAK_KB}" >&2
    exit 2
fi

PEAK_BYTES=$((PEAK_KB * 1024))

if [[ ! -f "${OUTPUT_CSV}" ]]; then
    echo "ERROR: benchmark did not create CSV:" >&2
    echo "  ${OUTPUT_CSV}" >&2
    exit 2
fi

printf '%s\n' "${PEAK_BYTES}" > "${OUTPUT_CSV}.peak_rss"