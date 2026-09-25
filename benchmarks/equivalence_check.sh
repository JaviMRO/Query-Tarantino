#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# Query Tarantino - Sprint 1
# Equivalence Check
#
# Según shared/SPEC.md:
#   1. Procesar los 20 libros de sample_data desde cero.
#   2. Usar datalake "time" e índice "json".
#   3. Comparar inverted_index.json mediante SHA-256.
#   4. Comparar SQLite "books", ignorando:
#        - header_path
#        - body_path
#        - indexed_at
#   5. Ejecutar las primeras 10 queries de queries.txt.
#   6. Comparar libros, orden y scores (< 1e-6).
#
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SAMPLE_DATA_DIR="${PROJECT_ROOT}/sample_data"
QUERIES_FILE="${PROJECT_ROOT}/shared/queries.txt"

# ------------------------------------------------------------
# Comandos de cada implementación
#
# Se pueden sobrescribir mediante variables de entorno.
# ------------------------------------------------------------

PYTHON_CMD="${TARANTINO_PYTHON_CMD:-python -m tarantino}"
JAVA_CMD="${TARANTINO_JAVA_CMD:-}"
CPP_CMD="${TARANTINO_CPP_CMD:-}"

# ------------------------------------------------------------
# Directorios de datos de cada implementación
#
# Si las implementaciones usan otras rutas, se pueden cambiar
# mediante TARANTINO_*_DATA_DIR.
# ------------------------------------------------------------

PYTHON_DATA_DIR="${TARANTINO_PYTHON_DATA_DIR:-${PROJECT_ROOT}/data/python}"
JAVA_DATA_DIR="${TARANTINO_JAVA_DATA_DIR:-${PROJECT_ROOT}/data/java}"
CPP_DATA_DIR="${TARANTINO_CPP_DATA_DIR:-${PROJECT_ROOT}/data/cpp}"

# ------------------------------------------------------------
# Rutas de SQLite
#
# IMPORTANTE:
# Cuando sepáis la ruta oficial, SOLO hay que cambiar estas
# tres variables.
#
# Ejemplo:
# TARANTINO_PYTHON_DB="${PROJECT_ROOT}/data/python/tarantino.db"
# ------------------------------------------------------------

PYTHON_DB="${TARANTINO_PYTHON_DB:-}"
JAVA_DB="${TARANTINO_JAVA_DB:-}"
CPP_DB="${TARANTINO_CPP_DB:-}"

# ------------------------------------------------------------
# Rutas de los índices
#
# Se pueden cambiar posteriormente si la implementación utiliza
# otra ubicación.
# ------------------------------------------------------------

PYTHON_INDEX="${TARANTINO_PYTHON_INDEX:-${PYTHON_DATA_DIR}/inverted_index.json}"
JAVA_INDEX="${TARANTINO_JAVA_INDEX:-${JAVA_DATA_DIR}/inverted_index.json}"
CPP_INDEX="${TARANTINO_CPP_INDEX:-${CPP_DATA_DIR}/inverted_index.json}"

# ------------------------------------------------------------
# Directorio temporal
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
# Funciones auxiliares
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
# Comprobaciones iniciales
# ------------------------------------------------------------

info "Checking project files"

[[ -d "${SAMPLE_DATA_DIR}" ]] \
    || fail "sample_data/ no existe: ${SAMPLE_DATA_DIR}"

[[ -f "${QUERIES_FILE}" ]] \
    || fail "shared/queries.txt no existe: ${QUERIES_FILE}"

SAMPLE_COUNT="$(find "${SAMPLE_DATA_DIR}" -type f | wc -l)"

if [[ "${SAMPLE_COUNT}" -ne 20 ]]; then
    fail "Se esperaban exactamente 20 archivos en sample_data/, encontrados ${SAMPLE_COUNT}"
fi

[[ -n "${JAVA_CMD}" ]] \
    || fail "TARANTINO_JAVA_CMD no está configurado."

[[ -n "${CPP_CMD}" ]] \
    || fail "TARANTINO_CPP_CMD no está configurado."

# ------------------------------------------------------------
# Función para ejecutar index
# ------------------------------------------------------------

run_index() {
    local language="$1"
    local command="$2"

    info "Indexing 20 sample books - ${language}"

    (
        cd "${PROJECT_ROOT}"

        # El CLI definido en SPEC es:
        # tarantino index N
        #
        # Para la equivalencia usamos N=20.
        #
        # shellcheck disable=SC2086
        ${command} index 20
    )
}

# ------------------------------------------------------------
# Función para ejecutar las primeras 10 queries
# ------------------------------------------------------------

run_queries() {
    local language="$1"
    local command="$2"
    local output="$3"

    info "Running first 10 queries - ${language}"

    : > "${output}"

    head -n 10 "${QUERIES_FILE}" | while IFS= read -r query; do

        # Ignorar líneas vacías.
        [[ -z "${query}" ]] && continue

        (
            cd "${PROJECT_ROOT}"

            # Python se utiliza únicamente para escapar correctamente
            # la query antes de pasarla al shell.
            quoted_query="$(
                python -c \
                'import shlex,sys; print(shlex.quote(sys.argv[1]))' \
                "${query}"
            )"

            # CLI definido en SPEC:
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
# COMPARACIÓN DE inverted_index.json
# ------------------------------------------------------------

info "Comparing inverted indexes"

[[ -f "${PYTHON_INDEX}" ]] \
    || fail "No existe el índice Python: ${PYTHON_INDEX}"

[[ -f "${JAVA_INDEX}" ]] \
    || fail "No existe el índice Java: ${JAVA_INDEX}"

[[ -f "${CPP_INDEX}" ]] \
    || fail "No existe el índice C++: ${CPP_INDEX}"

PYTHON_SHA="$(sha256sum "${PYTHON_INDEX}" | awk '{print $1}')"
JAVA_SHA="$(sha256sum "${JAVA_INDEX}" | awk '{print $1}')"
CPP_SHA="$(sha256sum "${CPP_INDEX}" | awk '{print $1}')"

echo "Python SHA-256: ${PYTHON_SHA}"
echo "Java   SHA-256: ${JAVA_SHA}"
echo "C++    SHA-256: ${CPP_SHA}"

if [[ "${PYTHON_SHA}" != "${JAVA_SHA}" ]]; then
    fail "Python y Java producen inverted_index.json diferentes."
fi

if [[ "${PYTHON_SHA}" != "${CPP_SHA}" ]]; then
    fail "Python y C++ producen inverted_index.json diferentes."
fi

echo
echo "OK: los tres inverted_index.json son idénticos."

# ------------------------------------------------------------
# COMPARACIÓN DE SQLITE
#
# Las rutas se dejan configurables.
#
# Cuando tengáis las rutas oficiales, solo hay que ponerlas
# arriba en:
#
#   PYTHON_DB="..."
#   JAVA_DB="..."
#   CPP_DB="..."
#
# ------------------------------------------------------------

info "Comparing SQLite databases"

if [[ -z "${PYTHON_DB}" || -z "${JAVA_DB}" || -z "${CPP_DB}" ]]; then

    echo
    echo "SQLite todavía no está configurado."
    echo
    echo "Cuando tengáis las rutas oficiales, configurar:"
    echo
    echo "PYTHON_DB=\"...\""
    echo "JAVA_DB=\"...\""
    echo "CPP_DB=\"...\""
    echo
    echo "La comprobación SQLite se ejecutará automáticamente."
    echo

else

    [[ -f "${PYTHON_DB}" ]] \
        || fail "No existe SQLite Python: ${PYTHON_DB}"

    [[ -f "${JAVA_DB}" ]] \
        || fail "No existe SQLite Java: ${JAVA_DB}"

    [[ -f "${CPP_DB}" ]] \
        || fail "No existe SQLite C++: ${CPP_DB}"

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

        # La tabla books forma parte de la persistencia definida
        # para la equivalencia.
        cursor.execute("PRAGMA table_info(books)")
        columns_info = cursor.fetchall()

        if not columns_info:
            raise RuntimeError(
                f"No se encontró la tabla 'books' en {database}"
            )

        columns = [
            row[1]
            for row in columns_info
            if row[1] not in IGNORED_COLUMNS
        ]

        if not columns:
            raise RuntimeError(
                f"No hay columnas comparables en books: {database}"
            )

        # quoted identifiers para soportar nombres de columnas
        # correctamente.
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
            f"Columnas diferentes entre "
            f"{reference_name} y {candidate_name}: "
            f"{reference_columns} != {candidate_columns}"
        )

    if reference_rows != candidate_rows:
        raise AssertionError(
            f"La tabla books es diferente entre "
            f"{reference_name} y {candidate_name}"
        )


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "Uso: compare sqlite python java cpp"
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

    print("OK: SQLite books es equivalente.")


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
# RESULTADO
# ------------------------------------------------------------

echo
echo "============================================================"
echo "EQUIVALENCE CHECK PASSED"
echo "============================================================"
echo
echo "Las comprobaciones de equivalencia disponibles han pasado."
echo