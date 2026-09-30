#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: run_with_peak_rss.sh PEAK_FILE COMMAND [ARGS...]" >&2
    echo "Runs the command under GNU time and writes its peak RSS in bytes to PEAK_FILE (SPEC 11.6)." >&2
    exit 1
fi

PEAK_FILE="$1"
shift
TIME_OUTPUT="$(mktemp)"
trap 'rm -f "${TIME_OUTPUT}"' EXIT

status=0
/usr/bin/time -v -o "${TIME_OUTPUT}" "$@" || status=$?

peak_kb="$(awk -F': ' '/Maximum resident set size/ { print $2; exit }' "${TIME_OUTPUT}")"
if [[ ! "${peak_kb}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: GNU time reported no peak RSS" >&2
    exit 2
fi
echo "$((peak_kb * 1024))" > "${PEAK_FILE}"
exit "${status}"
