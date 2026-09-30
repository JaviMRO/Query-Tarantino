# Query_Tarantino_Python

Python module of the data layer (datalake, datamart and control) of the Query Tarantino search engine. It follows a
hexagonal architecture (ports and adapters): `domain/` depends on no external library, `application/` orchestrates
the use cases through dependency injection, and `infrastructure/` holds the concrete adapters (SQLite, MongoDB,
JSON, HTTP).

## Requirements

- Python 3.10 or later; the benchmarks run with CPython 3.12 (root `README.md`).
- MongoDB, only for `--index mongo` (its tests are skipped if there is no server at `localhost:27017`).

## Installing the dependencies

```bash
python -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # or requirements.txt if you will not run the tests
```

## Checks

From `Query_Tarantino_Python/`, the same ones CI runs on every push:

```bash
ruff check .          # errors and style (ruff check . --fix applies the automatic fixes)
ruff format --check . # formatting (ruff format . applies it)
mypy src tests        # types: the adapters satisfy the ports
python -m pytest      # tests
```

Optional tests against the real gutenberg.org (about 8 requests; never in the CI run of every push, because
Gutenberg blocks robots that abuse it):

```bash
TARANTINO_LIVE_TESTS=1 python -m pytest tests/live
```

The MongoDB tests are skipped if there is no server at `localhost:27017`; in CI they run against a `mongo:7`
container.

The configuration is in `pyproject.toml` and CI in `.github/workflows/python.yml`.

`tests/` mirrors the structure of `src/`: each test goes in the folder of the module it tests.

## Running

From `Query_Tarantino_Python/`, the command line of SPEC 10:

```bash
python -m tarantino download 1342 --shared-dir ../shared
python -m tarantino index 1342 --shared-dir ../shared
python -m tarantino step [--ids FILE] --shared-dir ../shared
python -m tarantino run --steps K [--ids FILE] --shared-dir ../shared
python -m tarantino search "TEXT" [--json] --shared-dir ../shared
python -m tarantino bench --experiment E --structure S --n N --run R --out FILE.csv --shared-dir ../shared
```

`bench` runs one configuration of SPEC 11.1 inside `<TARANTINO_DATA_DIR>/bench/` and appends its rows to the CSV
only if every validity check passed (exit code `2` otherwise). Its code is in
`src/infrastructure/entrypoints/bench/`: `configuration.py` (valid combinations), `bench_area.py`, `measurement/`
(clock, percentiles, storage and CSV) and `experiments/` (one module per experiment). The whole campaign is run by
`benchmarks/run_all.sh`, described in the root `README.md`.

Every SPEC 2 option (`--data-dir`, `--lake`, `--index`, `--downloader`, `--corpus-dir`, `--mongo-url`,
`--shared-dir`) can go before or after the command and takes precedence over its `TARANTINO_*` variable. Exit codes:
`0` success, `1` usage error, `2` runtime error. The full configuration table and the equivalence check procedure
are in the root `README.md`.

Example on the local corpus, without network access:

```bash
python -m tarantino run --steps 40 --ids ../shared/book_ids_benchmark.txt \
    --downloader local --corpus-dir ../shared/sample_dataset --shared-dir ../shared
python -m tarantino search "white whale" --json --shared-dir ../shared
```

## Shared benchmark data

`corpus_tools build-corpus` and `build-queries` create `shared/book_ids_benchmark.txt`, `shared/sample_dataset/`
and `shared/queries.txt` once (SPEC 1.1, 1.2). The procedure is in the root `README.md`.

## Structure

```
src/
├── domain/                # models, ports (Protocol) and TF-IDF search
│   └── text_processing/   # decoding, split, tokenizer and header parser (SPEC 3, 5, 6)
├── application/           # ControlPipeline (control step)
│   ├── use_cases/         # ingestion, indexing and search
│   └── corpus/            # corpus selection and query generation (SPEC 1.1, 1.2)
└── infrastructure/        # concrete adapters, file helpers, lock and .tmp cleanup
    ├── datalake/layouts/  # time, book and batch
    ├── corpus/            # corpus_raw/, the id list and the sample dataset
    └── entrypoints/       # CLI (cli.py, settings.py), corpus_tools.py, wiring/ (commands and composition) and bench/
tarantino/                 # python -m tarantino
tests/                     # same structure as src/, plus live/ (optional real requests)
```

## Design decisions and known limitations

For the report. Java and C++ follow the same decisions.

- **`json` index with `json.dumps`:** the index is serialized in one go with the C encoder (about 3 times faster than
  `json.dump`, same bytes), at the cost of an O(I) memory peak, of the same order as the index that SPEC 7.1 already
  requires to be loaded.
- **`time` datalake, double lookup when indexing:** `IndexBookUseCase` calls `load` and then `get_paths`, and in
  `time` each call walks the `YYYYMMDD/HH` folders (O(D)). The real cost is minimal: D grows by about one folder per
  hour of downloading, and the benchmark's `index` experiment uses the `book` datalake. Avoiding it would require
  changing the `DatalakeStorage` port in the three languages, so it is kept.
- **Benchmark helper functions inside the adapters:** the ones that list the datalake, count the index or measure
  MongoDB (`stored_*_book_ids`, `count_*_index`, `count_stale_copies`, `hour_folder_of`, `mongo_disk_bytes`) live
  next to their adapter because they need to know its internal format, which is thus kept in a single place. Only
  the `bench` command uses them, and their docstrings say so.
- **Metadata of the search results, one query per book:** `SqliteBookCatalog.get_books` runs one prepared
  `SELECT … WHERE book_id = ?` per result, the per-book lookups the Stage 1 guide lists as the common metadata
  queries (by author, title or ID). A single `IN` would mean building the SQL with one placeholder per id or
  relying on SQLite's JSON extension in the three languages; it is only used by `search`, never by the benchmark.
- **2-second wait in `build-corpus` and in the `download` benchmark:** Project Gutenberg asks automated clients for
  2 seconds between requests; the pipeline keeps the 1-second minimum of SPEC 3.2.
- **`folders` index, slow build:** SPEC 7.3 requires appending one line to a file for every term of every book, so
  there are U open-and-write operations per book.

The rules shared by Python, Java and C++ are in `../shared/SPEC.md`.
