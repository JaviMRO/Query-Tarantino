# Query-Tarantino

Stage 1 of the Query Tarantino search engine (Big Data, ULPGC): the data layer — download from Project Gutenberg,
datalake, SQLite metadata, inverted index, control layer and TF-IDF search — implemented three times, in Python,
Java and C++, with equivalent outputs. The shared rules are in [`shared/SPEC.md`](shared/SPEC.md).

```
stage_1/
├── shared/                   SPEC, stop words, benchmark IDs, queries, sample dataset
├── Query_Tarantino_Python/
├── Query_Tarantino_Java/
├── Query_Tarantino_Cpp/
└── benchmarks/
```

## Requirements

- **MongoDB** (only for `--index mongo`): a server reachable at `TARANTINO_MONGO_URL`
  (default `mongodb://localhost:27017`), for example `docker run -d -p 27017:27017 mongo`.
- **Python:** CPython 3.10 or later. Details in [`Query_Tarantino_Python/README.md`](Query_Tarantino_Python/README.md).
- **Java** and **C++:** see the README of each module.

## Build and install

### Python

```bash
cd Query_Tarantino_Python
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # requirements-dev.txt to run the checks and tests
```

There is nothing to compile. Every command below is run from `Query_Tarantino_Python/`.

## Configuration (SPEC 2)

Each setting is read from its `--argument` or, if absent, from its environment variable; the argument wins.
Settings are accepted before or after the command.

| Variable | Argument | Values | Default |
|---|---|---|---|
| `TARANTINO_DATA_DIR` | `--data-dir` | path | `./data` |
| `TARANTINO_LAKE` | `--lake` | `time` · `book` · `batch` | `time` |
| `TARANTINO_INDEX` | `--index` | `json` · `mongo` · `folders` | `json` |
| `TARANTINO_DOWNLOADER` | `--downloader` | `http` · `local` | `http` |
| `TARANTINO_CORPUS_DIR` | `--corpus-dir` | path | `./corpus_raw` |
| `TARANTINO_MONGO_URL` | `--mongo-url` | URL | `mongodb://localhost:27017` |
| `TARANTINO_SHARED_DIR` | `--shared-dir` | path | `./shared` |

Relative paths are resolved from the current directory, so from a module folder the shared files are in `../shared`.

## Commands (SPEC 10)

In Python the executable is `python -m tarantino`:

```bash
python -m tarantino download 1342 --shared-dir ../shared      # download and store one book
python -m tarantino index 1342 --shared-dir ../shared         # index a downloaded book
python -m tarantino step --shared-dir ../shared               # one control step, 10 random candidates
python -m tarantino run --steps 40 --ids ../shared/book_ids_benchmark.txt --shared-dir ../shared
python -m tarantino search "white whale" --shared-dir ../shared
python -m tarantino search "white whale" --json --shared-dir ../shared
python -m tarantino bench --experiment datalake --structure book --n 100 --run 1 --out ../benchmarks/results/python_datalake.csv \
    --data-dir ../benchmarks/work --corpus-dir ../corpus_raw --shared-dir ../shared   # one benchmark run (SPEC 11)
```

Exit codes: `0` success, `1` usage error, `2` runtime error (failed download, missing data, lock held…).
`download`, `index`, `step`, `run` and `bench` hold `control/.lock` while they run; if another process holds it they exit
with code `2` and print its PID. If that process no longer exists, delete the file and run the command again.
`search` never uses the lock.

## Shared benchmark data (SPEC 1.1, 1.2)

`shared/book_ids_benchmark.txt`, `shared/sample_dataset/` and `shared/queries.txt` are created **once, by one
person**, and then versioned. The Python module provides the tools:

```bash
cd Query_Tarantino_Python
# 1. Select the first 1,000 valid English books from Gutenberg (2 s between requests, about 1 hour).
#    Writes ../corpus_raw/N.txt and ../shared/book_ids_benchmark.txt, then copies the first 20 books
#    to ../shared/sample_dataset/. If it is interrupted, run it again: it resumes after the last listed ID.
python -m src.infrastructure.entrypoints.corpus_tools build-corpus --corpus-dir ../corpus_raw --shared-dir ../shared

# 2. Index the 1,000 books with the json index.
python -m tarantino run --steps 2000 --ids ../shared/book_ids_benchmark.txt --data-dir ./data/corpus \
    --downloader local --corpus-dir ../corpus_raw --lake book --index json --shared-dir ../shared

# 3. Generate the 100 queries; it refuses to overwrite an existing queries.txt.
python -m src.infrastructure.entrypoints.corpus_tools build-queries --data-dir ./data/corpus --shared-dir ../shared
```

`corpus_raw/` is not versioned; share it with the team outside Git so nobody has to download it again.

## Sample dataset and equivalence check (SPEC 12)

`benchmarks/equivalence_check.sh` processes the 20 books of `shared/sample_dataset/` from scratch in every language
(local downloader, `time` datalake, `json` index, `run --steps 40 --ids shared/book_ids_benchmark.txt`), runs the
first 10 queries of `shared/queries.txt` with `search --json`, and compares the SHA-256 of `inverted_index.json`,
the `books` tables without `header_path`, `body_path` and `indexed_at`, and the results: same books in the same
order, with scores differing by at most `1e-6 + 1e-9`.

```bash
source Query_Tarantino_Python/.venv/bin/activate
export TARANTINO_JAVA_CMD="java -jar /absolute/path/to/tarantino.jar" TARANTINO_CPP_CMD="/absolute/path/to/tarantino"
benchmarks/equivalence_check.sh                          # the three languages; exit code 1 on any mismatch
BENCH_LANGUAGES=python benchmarks/equivalence_check.sh   # one language only: prints PARTIAL, compares nothing
```

Each language works in `benchmarks/work/equivalence/<language>/`, which is not versioned. The Python command
defaults to `python -m tarantino`, run from `Query_Tarantino_Python/`; Java and C++ are run from their module folder.

## Benchmarks (SPEC 11)

Each module provides `tarantino bench --experiment E --structure S --n N --run R --out FILE.csv`, which runs one
configuration of SPEC 11.1 inside `<TARANTINO_DATA_DIR>/bench/` (emptied at the start of every run; nothing else in
the data folder is touched) and appends its rows to `FILE.csv` only if every validity check passed (exit code `2`
otherwise). Every experiment except `download` reads the books with the local downloader, so `TARANTINO_CORPUS_DIR`
must hold the whole corpus; `download` requests Gutenberg with 2 seconds between requests. MongoDB runs use the
database `query_tarantino_bench`, never `query_tarantino`.

The whole campaign, on one Linux machine (native or WSL2, with GNU `time` and GNU `du`) and with MongoDB running:

```bash
source Query_Tarantino_Python/.venv/bin/activate
export TARANTINO_CORPUS_DIR="$PWD/corpus_raw" TARANTINO_JAVA_CMD="..." TARANTINO_CPP_CMD="..."
benchmarks/run_all.sh                       # equivalence check, environment.txt, then rounds 0 to 5
pip install -r benchmarks/requirements.txt  # pandas and matplotlib, for the analysis only
python benchmarks/analyze.py                # tables and figures in benchmarks/report/
benchmarks/run_all.sh 6 10 benchmarks/report/rerun_configurations.txt   # 5 extra rounds for flagged configurations
```

| File | Purpose |
|---|---|
| `benchmarks/run_all.sh` | Runs the equivalence check, writes `results/environment.txt`, then every configuration of each round in the order of `plan.py`; appends `peak_rss`, `disk_bytes_allocated` and `results/json_index_sha256.csv`, and validates the CSV files |
| `benchmarks/plan.py` | `python benchmarks/plan.py --round R`: every configuration of SPEC 11.1 for the three languages, shuffled with `random.Random(R)`; `download` only in rounds 0 to 3 |
| `benchmarks/equivalence_check.sh` | SPEC 12, described above |
| `benchmarks/analyze.py` | SPEC 11.9: medians and interquartile ranges, flagged configurations (coefficient of variation over 10 %), summary tables with the speedup relative to Python, log-log scalability with slopes, build breakdown, query latency, memory over the baseline and the cross-run validity checks (exit code `1` if one fails) |
| `benchmarks/scripts/` | `languages.sh` (how each module is run), `run_with_peak_rss.sh`, `compare_equivalence.py` and `validate_csv.py` (SPEC 11.8) |
| `benchmarks/results/`, `benchmarks/report/` | Versioned: the CSV files and the generated tables and figures |

`BENCH_LANGUAGES` (default `python java cpp`) limits the languages, for example to try the scripts while a module
does not have `bench` yet; results measured that way are not a valid comparison.
