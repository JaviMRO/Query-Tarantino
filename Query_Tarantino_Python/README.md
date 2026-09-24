# Query_Tarantino_Python

Módulo Python de la capa de datos (datalake, datamart y control) del motor de
búsqueda Query Tarantino. Implementa Arquitectura Hexagonal (Ports & Adapters):
`domain/` no depende de ninguna librería externa, `application/` orquesta los
casos de uso vía inyección de dependencias, e `infrastructure/` contiene los
adaptadores concretos (SQLite, MongoDB, JSON, HTTP).

## Requisitos

- Python 3.10+

## Instalación de dependencias

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # o requirements.txt si no vas a lanzar tests
```

## Comprobaciones

Desde `Query_Tarantino_Python/`, las mismas que ejecuta el CI en cada push:

```bash
ruff check .          # errores y estilo (ruff check . --fix corrige lo automático)
ruff format .         # formatea el código
mypy src tests        # tipos: los adapters cumplen los ports
python -m pytest      # tests
```

La configuración está en `pyproject.toml` y el CI en `.github/workflows/python.yml`.

`tests/` replica la estructura de `src/`: cada test va en la carpeta del módulo que prueba.

## Ejecución

```bash
python -m src.infrastructure.entrypoints.<futuro_entrypoint>
```

## Estructura

```
src/
├── domain/            # reglas de la SPEC (tokenizer, parser, split) y ports (Protocol)
├── application/       # casos de uso (orquestación)
└── infrastructure/    # adaptadores concretos + entrypoints (futuro CLI)
tests/                 # misma estructura que src/
```

Las reglas compartidas por Python, Java y C++ están en `../shared/SPEC.md`.
