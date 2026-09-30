# Query_Tarantino_Python

Módulo Python de la capa de datos (datalake, datamart y control) del motor de
búsqueda Query Tarantino. Implementa Arquitectura Hexagonal (Ports & Adapters):
`domain/` no depende de ninguna librería externa, `application/` orquesta los
casos de uso vía inyección de dependencias, e `infrastructure/` contiene los
adaptadores concretos (SQLite, MongoDB, JSON, HTTP).

## Requisitos

- Python 3.10+
- MongoDB, solo para `--index mongo` (sus tests se saltan si no hay servidor en `localhost:27017`).

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
ruff format --check . # formato (ruff format . lo aplica)
mypy src tests        # tipos: los adapters cumplen los ports
python -m pytest      # tests
```

Tests opcionales contra gutenberg.org real (unas 8 peticiones; nunca en el CI de cada push, porque Gutenberg
bloquea a los robots que abusan):

```bash
TARANTINO_LIVE_TESTS=1 python -m pytest tests/live
```

Los tests de MongoDB se saltan si no hay servidor en `localhost:27017`; en el CI se ejecutan contra un contenedor
`mongo:7`.

La configuración está en `pyproject.toml` y el CI en `.github/workflows/python.yml`.

`tests/` replica la estructura de `src/`: cada test va en la carpeta del módulo que prueba.

## Ejecución

Desde `Query_Tarantino_Python/`, la CLI de la SPEC 10:

```bash
python -m tarantino download 1342 --shared-dir ../shared
python -m tarantino index 1342 --shared-dir ../shared
python -m tarantino step [--ids FICHERO] --shared-dir ../shared
python -m tarantino run --steps K [--ids FICHERO] --shared-dir ../shared
python -m tarantino search "TEXTO" [--json] --shared-dir ../shared
python -m tarantino bench --experiment E --structure S --n N --run R --out FICHERO.csv --shared-dir ../shared
```

`bench` ejecuta una configuración de la SPEC 11.1 dentro de `<TARANTINO_DATA_DIR>/bench/` y añade sus filas al CSV
solo si pasan todas las comprobaciones de validez (código `2` si no). Su código está en
`src/infrastructure/entrypoints/bench/`: `configuration.py` (combinaciones válidas), `bench_area.py`, `measurement/`
(reloj, percentiles, almacenamiento y CSV) y `experiments/` (un módulo por experimento). La campaña completa la
lanza `benchmarks/run_all.sh`, descrito en el `README.md` de la raíz.

Cada opción de la SPEC 2 (`--data-dir`, `--lake`, `--index`, `--downloader`, `--corpus-dir`, `--mongo-url`,
`--shared-dir`) puede ir antes o después del comando y gana a su variable `TARANTINO_*`. Códigos de salida: `0`
éxito, `1` uso incorrecto, `2` error de ejecución. La tabla completa de configuración y el procedimiento de la
comprobación de equivalencia están en el `README.md` de la raíz.

Ejemplo sobre el corpus local, sin red:

```bash
python -m tarantino run --steps 40 --ids ../shared/book_ids_benchmark.txt \
    --downloader local --corpus-dir ../shared/sample_dataset --shared-dir ../shared
python -m tarantino search "white whale" --json --shared-dir ../shared
```

## Datos compartidos del benchmark

`corpus_tools build-corpus` y `build-queries` crean una única vez `shared/book_ids_benchmark.txt`,
`shared/sample_dataset/` y `shared/queries.txt` (SPEC 1.1, 1.2). El procedimiento está en el `README.md` de la raíz.

## Estructura

```
src/
├── domain/                # modelos, ports (Protocol) y búsqueda TF-IDF
│   └── text_processing/   # decodificación, split, tokenizer y parser del header (SPEC 3, 5, 6)
├── application/           # ControlPipeline (paso de control)
│   ├── use_cases/         # ingesta, indexado y búsqueda
│   └── corpus/            # selección del corpus y generación de queries (SPEC 1.1, 1.2)
└── infrastructure/        # adaptadores concretos, helpers de ficheros, lock y limpieza de .tmp
    ├── datalake/layouts/  # time, book y batch
    ├── corpus/            # corpus_raw/, lista de IDs y sample dataset
    └── entrypoints/       # CLI (cli.py, settings.py), corpus_tools.py, wiring/ (comandos y composición) y bench/
tarantino/                 # python -m tarantino
tests/                     # misma estructura que src/, más live/ (peticiones reales opcionales)
```

Las reglas compartidas por Python, Java y C++ están en `../shared/SPEC.md`.
