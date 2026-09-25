#!/usr/bin/env python3

"""
Query Tarantino - Sprint 1

Compara los resultados de:
    tarantino search "TEXT" --json

según el contrato de equivalencia del SPEC.

Se comprueba:

    - mismo número de resultados
    - mismos libros
    - mismo orden
    - diferencia absoluta de score < 1e-6
"""

import json
import math
import sys
from pathlib import Path


SCORE_TOLERANCE = 1e-6


def load_results(path: str):
    """
    Carga los resultados JSON producidos por una implementación.

    Se espera un objeto JSON por línea.
    """

    results = []

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo de resultados: {path}"
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
                f"{path}: JSON inválido en la línea "
                f"{line_number}: {exc}"
            ) from exc

        results.append(result)

    return results


def get_book_id(result):
    """
    Obtiene el identificador del libro.

    Se acepta 'id' y 'book_id' para que la comprobación no dependa
    de una elección interna de nombre mientras se integran las
    implementaciones.
    """

    if not isinstance(result, dict):
        raise ValueError(
            f"El resultado no es un objeto JSON: {result!r}"
        )

    if "id" in result:
        return result["id"]

    if "book_id" in result:
        return result["book_id"]

    raise ValueError(
        f"No se encuentra el identificador del libro "
        f"en el resultado: {result!r}"
    )


def get_score(result):
    """
    Obtiene y valida el score.
    """

    if not isinstance(result, dict):
        raise ValueError(
            f"El resultado no es un objeto JSON: {result!r}"
        )

    if "score" not in result:
        raise ValueError(
            f"El resultado no contiene 'score': {result!r}"
        )

    try:
        score = float(result["score"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Score inválido: {result!r}"
        ) from exc

    if not math.isfinite(score):
        raise ValueError(
            f"Score no finito: {result!r}"
        )

    return score


def compare_query_results(
    reference,
    candidate,
    reference_name,
    candidate_name,
):
    """
    Compara dos conjuntos de resultados.
    """

    if len(reference) != len(candidate):
        raise AssertionError(
            f"{reference_name} y {candidate_name} devuelven "
            f"un número diferente de resultados: "
            f"{len(reference)} != {len(candidate)}"
        )

    for position, (reference_result, candidate_result) in enumerate(
        zip(reference, candidate)
    ):
        reference_id = get_book_id(reference_result)
        candidate_id = get_book_id(candidate_result)

        # Mismo libro y mismo orden.
        if reference_id != candidate_id:
            raise AssertionError(
                f"Libro diferente en posición {position}: "
                f"{reference_name}={reference_id!r}, "
                f"{candidate_name}={candidate_id!r}"
            )

        reference_score = get_score(reference_result)
        candidate_score = get_score(candidate_result)

        difference = abs(reference_score - candidate_score)

        # SPEC: diferencia de score < 1e-6
        if difference >= SCORE_TOLERANCE:
            raise AssertionError(
                f"Score diferente en posición {position}, "
                f"libro {reference_id!r}: "
                f"{reference_name}={reference_score}, "
                f"{candidate_name}={candidate_score}, "
                f"diferencia={difference}"
            )


def main():
    if len(sys.argv) != 4:
        print(
            "Uso:",
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

        # Python se utiliza como referencia.
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