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
```

Exit codes: `0` success, `1` usage error, `2` runtime error (failed download, missing data, lock held…).
`download`, `index`, `step` and `run` hold `control/.lock` while they run; if another process holds it they exit
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

Process the 20 books of `shared/sample_dataset/` from scratch with the local downloader, the `time` datalake and
the `json` index:

```bash
cd Query_Tarantino_Python
export TARANTINO_DATA_DIR=./data/equivalence TARANTINO_DOWNLOADER=local TARANTINO_CORPUS_DIR=../shared/sample_dataset \
       TARANTINO_LAKE=time TARANTINO_INDEX=json TARANTINO_SHARED_DIR=../shared
python -m tarantino run --steps 40 --ids ../shared/book_ids_benchmark.txt
shasum -a 256 data/equivalence/datamarts/inverted_index.json
head -n 10 ../shared/queries.txt | while read -r query; do python -m tarantino search "$query" --json; done
```

Then compare, across the three languages, the SHA-256 of `inverted_index.json`, the `books` table without
`header_path`, `body_path` and `indexed_at`, and the output of the first 10 queries.

## Benchmarks (SPEC 11)

Maintained by the benchmarks owner in `benchmarks/`.
