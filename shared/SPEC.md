# SPEC · Shared rules for Stage 1

**Project:** Query Tarantino · Big Data, ULPGC
**Version:** 1.2 · 2026-09-24
**Scope:** the three Stage 1 modules (`Query_Tarantino_Java`, `Query_Tarantino_Python`, `Query_Tarantino_Cpp`) and, from phase 2 onwards, the Java version.

This document defines **what** each module must do, precisely enough for all three to produce exactly the same results. It does not say **how** to implement it: each language uses its own tools as long as it follows these rules.

The Stage 1 guide requires all implementations to use the same dataset and the same preprocessing rules, and to produce equivalent outputs. An implementation that does not comply with this document cannot be used for benchmarking.

## How this document is changed

1. Nobody changes a rule directly in the code. It is changed here first.
2. The change goes in a *pull request* that must be approved by the owners of all three modules.
3. The version is bumped (1.0 → 1.1) and the change is recorded in the history at the end.
4. After the change, all three modules must pass the equivalence check again (section 12) before any measurement.

---

## 1. Shared files

All of them live in `shared/` at the repository root. They are data, not code. All in UTF-8 without BOM, with `\n` line endings.

| File | Content | Format |
|---|---|---|
| `SPEC.md` | This document | — |
| `stopwords_en.txt` | English stop words | One per line, lowercase, letters `a-z` only, alphabetically sorted, no blank lines or comments |
| `book_ids_benchmark.txt` | The 1,000 books of the benchmark corpus | One integer ID per line, ascending order |
| `queries.txt` | The 100 benchmark queries | One query per line, terms separated by a single space |
| `sample_dataset/` | The first 20 books of the benchmark corpus (section 1.1) | One `N.txt` per book, as in `corpus_raw/` (section 3.6) |

### 1.1 How the benchmark books are selected

Gutenberg IDs are traversed in ascending order starting at 1 and downloaded following section 3. A book is added to the list if the download is valid and its language, according to section 5, is `en`. The process stops at 1,000. The first 20 books of the list are copied, raw, to `sample_dataset/`.

This selection is done by one person, only once. The downloaded corpus is stored locally (section 3.6) and everyone works from it.

### 1.2 How the queries are generated

Done once, with a Python script and fixed seed `42`, on the full index of the 1,000 books:

- 40 one-term queries, 30 two-term queries and 30 three-term queries.
- Terms are drawn in equal parts from three bands, according to the number of books they appear in: frequent (in more than 50% of the books), medium (between 5% and 50%) and rare (between 2 and 5 books).
- The result is saved to `queries.txt` and is never regenerated.

---

## 2. Configuration

All modules read the same configuration, from an environment variable or from the equivalent command-line argument: the variable name without the `TARANTINO_` prefix, in lowercase and with hyphens (`TARANTINO_DATA_DIR` → `--data-dir`, `TARANTINO_LAKE` → `--lake`). The argument takes precedence.

| Variable | Values | Default | Purpose |
|---|---|---|---|
| `TARANTINO_DATA_DIR` | path | `./data` | Root folder where `datalake*/`, `datamarts/` and `control/` are created |
| `TARANTINO_LAKE` | `time` · `book` · `batch` | `time` | Datalake structure |
| `TARANTINO_INDEX` | `json` · `mongo` · `folders` | `json` | Index structure |
| `TARANTINO_DOWNLOADER` | `http` · `local` | `http` | Download from Gutenberg or read the local corpus |
| `TARANTINO_CORPUS_DIR` | path | `./corpus_raw` | Local corpus folder |
| `TARANTINO_MONGO_URL` | URL | `mongodb://localhost:27017` | MongoDB connection |
| `TARANTINO_SHARED_DIR` | path | `./shared` | Folder with the shared files |

---

## 3. Download

### 3.1 URLs

For a book with ID `N`, the following URLs are tried in this order until an HTTP 200 response is obtained:

1. `https://www.gutenberg.org/cache/epub/N/pgN.txt`
2. `https://www.gutenberg.org/files/N/N-0.txt`
3. `https://www.gutenberg.org/files/N/N.txt`

If none returns 200, the book fails with reason `HTTP_ERROR`.

### 3.2 Politeness towards the source

- At most **one request per second**, fallback URLs included.
- Header `User-Agent: QueryTarantino/1.0 (ULPGC Big Data student project)`.
- Maximum wait per request: 30 seconds. On timeout, that URL counts as failed and the next one is tried.
- Redirects are followed.

### 3.3 Decoding and normalization

In this order:

1. Decode the bytes as UTF-8. If there is any invalid sequence, decode the whole file as ISO-8859-1 (Latin-1).
2. Remove the BOM (`U+FEFF`) if present at the start.
3. Convert every `\r\n` and `\r` line ending to `\n`.

From here on, all text is handled and stored in UTF-8 with `\n` line endings.

### 3.4 Splitting header and body

Markers are located with these regular expressions, **case-insensitive**. The dot does not match line breaks, which is the default behaviour in Python, Java and C++ `std::regex`:

```
Start:  \*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG E-?BOOK.*?\*\*\*
End:    \*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG E-?BOOK.*?\*\*\*
```

- The **first** occurrence of the start marker is used, and the **first** occurrence of the end marker **after** it.
- **Header:** all text before the beginning of the start marker.
- **Body:** all text between the end of the start marker and the beginning of the end marker.
- The footer, everything after the end marker, is discarded.
- Header and body are trimmed: ASCII whitespace (space, `\t`, `\n`, `\r`, `\f`, `\v`) is removed from both ends.

Failure reasons:

| Reason | When |
|---|---|
| `HTTP_ERROR` | No URL returned 200 |
| `NO_MARKERS` | The start or the end marker is missing |
| `EMPTY_BODY` | The body is empty after trimming |

A failed book writes nothing to the datalake.

### 3.5 Retries

A failed book may be retried in later control steps. After **3 failed attempts** it is never proposed again (section 8).

### 3.6 Local corpus

The benchmark corpus is stored only once, after the normalization of section 3.3 and before splitting header and body, in:

```
corpus_raw/N.txt
```

The `LocalCorpusDownloader` adapter reads from there instead of requesting Gutenberg, and applies the split of section 3.4. For the rest of the system there is no difference between both downloaders. If the file does not exist, it fails with reason `HTTP_ERROR`.

---

## 4. Datalake

### 4.1 Paths

Relative to `TARANTINO_DATA_DIR`. `N` is the ID without leading zeros.

**By date and hour (`time`)**, the one recommended by the guide:
```
datalake/YYYYMMDD/HH/N.header.txt
datalake/YYYYMMDD/HH/N.body.txt
```
`YYYYMMDD` and `HH` are the download date and hour **in UTC**, with the hour in 24-hour format and two digits. UTC is used so that every team machine produces the same folders.

**By book (`book`):**
```
datalake_book/N/header.txt
datalake_book/N/body.txt
```

**By batch (`batch`)**, in ranges of 1,000:
```
datalake_batch/AAAAAA-BBBBBB/N.header.txt
datalake_batch/AAAAAA-BBBBBB/N.body.txt
```
`AAAAAA` is `(N ÷ 1000) × 1000` using integer division, and `BBBBBB` is `AAAAAA + 999`, both zero-padded to six digits. Example: book 1342 goes in `001000-001999`; book 5 goes in `000000-000999`.

### 4.2 Content

- Exactly the header and body from section 3.4, in UTF-8 without BOM, with `\n` line endings and **no trailing newline added**.
- On Windows, files are opened so that `\n` is not converted to `\r\n` (section 13.3).

### 4.3 Safe writes

1. Write the content to a file with the same name plus `.tmp` (for example `1342.body.txt.tmp`).
2. Close the file.
3. Rename it to its final name.

The header is written first, then the body. A book exists in the datalake only if both final files exist. On startup, any `.tmp` files left over from an interrupted run are deleted.

---

## 5. Metadata

### 5.1 Header extraction

The header is processed **line by line**. Each of these regular expressions is applied to each line, case-insensitive:

| Field | Expression | Group stored |
|---|---|---|
| `title` | `^Title:\s*(.*)$` | 1 |
| `author` | `^Author:\s*(.*)$` | 1 |
| `language` | `^Language:\s*(.*)$` | 1 |
| `release_date` | `^Release date:\s*([^\[]*)` | 1 |

Rules:

- Only the **first** line matching each field counts.
- The captured value is trimmed (ASCII whitespace at both ends).
- **Multi-line titles:** if the line following the title line starts with a space or a tab and is not blank, it is appended to the title with a single space in between, after trimming it. This repeats with the following lines until one does not meet the condition. This rule applies only to the title.
- **Missing field:** stored as an empty string `""`. A book never fails because of a missing field.

### 5.2 Language normalization

1. If the value contains commas, only the part before the first comma is kept, trimmed.
2. It is converted with this table, case-insensitive:

| Value | Code |
|---|---|
| English | `en` |
| French | `fr` |
| German | `de` |
| Spanish | `es` |
| Italian | `it` |
| Portuguese | `pt` |
| Dutch | `nl` |
| Finnish | `fi` |
| Latin | `la` |
| Chinese | `zh` |

3. Any other value is stored as is, converted to lowercase (A–Z only).

Only books with language `en` are indexed. The others are recorded in the metadata but not in the index (section 8).

### 5.3 Meaning of `release_date`

It is the publication date **on Project Gutenberg**, not that of the original book. It is stored as text, exactly as it appears. It is neither parsed nor converted to a date.

### 5.4 Database

File `datamarts/metadata.sqlite`:

```sql
CREATE TABLE IF NOT EXISTS books (
  book_id      INTEGER PRIMARY KEY,
  title        TEXT NOT NULL,
  author       TEXT NOT NULL,
  language     TEXT NOT NULL,
  release_date TEXT NOT NULL,
  header_path  TEXT NOT NULL,
  body_path    TEXT NOT NULL,
  indexed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_books_author   ON books(lower(author));
CREATE INDEX IF NOT EXISTS idx_books_language ON books(language);
```

- Written with `INSERT OR REPLACE`: processing a book twice does not duplicate rows.
- `header_path` and `body_path`: paths relative to `TARANTINO_DATA_DIR`, using `/` as separator on every operating system. How to achieve this in each language is described in section 13.3.
- `indexed_at`: UTC timestamp in `YYYY-MM-DDTHH:MM:SSZ` format. Empty (`NULL`) if the book is not in English and has therefore not been indexed.

---

## 6. Tokenization

Applied to the book **body** and, with the same rules, to queries.

### 6.1 Algorithm

The text is traversed **byte by byte** in its UTF-8 encoding:

1. If the byte is an ASCII uppercase letter (`A`–`Z`, values 65 to 90), it is converted to lowercase by adding 32.
2. If the byte, after step 1, is an ASCII lowercase letter (`a`–`z`, values 97 to 122), it is appended to the current term.
3. Any other byte **closes** the current term, if there is one. This includes spaces, punctuation, digits, apostrophes, hyphens and every byte of non-ASCII characters, such as accented letters.
4. At the end of the text, the last term is closed, if any.

Each closed term receives a **position**, starting at 0 and increasing by 1 for every closed term, **including those that are discarded afterwards**.

After the position is assigned, the term is discarded if:

- it has a single letter, or
- it appears in `stopwords_en.txt`.

### 6.2 Result per book

For each surviving term:

- `tf`: number of occurrences in the book.
- `positions`: list of its positions, in ascending order.

### 6.3 Language-specific notes

- **Java:** do not use `String.toLowerCase()` without arguments, because it depends on the system locale (in Turkish, `I` is not converted to `i`). Traverse the bytes of `getBytes(StandardCharsets.UTF_8)` and apply the rules manually.
- **Python:** do not use `str.lower()` or `str.isalpha()`, which accept non-ASCII letters. Traverse `text.encode("utf-8")`.
- **C++:** traverse the `std::string` as `unsigned char`. Do not use `std::tolower` or `std::isalpha`, which depend on the locale.

### 6.4 Accepted consequences

These follow from the rules and are accepted. They are not fixed case by case:

- "don't" produces `don` and `t`, which are discarded.
- "café" produces `caf`. "naïve" produces `na` and `ve`, and `ve` is a stop word.
- "stop-believing" produces `stop` and `believing`.
- Numbers are not indexed.

---

## 7. Inverted index

All three structures store the same information: for each term, the books it appears in and its frequency. MongoDB also stores positions.

### 7.1 Single file (`json`)

File `datamarts/inverted_index.json`, the path required by the guide.

Format:

```json
{"term":{"book_id":tf,"book_id":tf},"term":{...}}
```

**Mandatory** canonical form, which makes byte-by-byte comparison across the three languages possible:

- A single JSON object on one line, without spaces, followed by a final `\n`.
- Book IDs are **strings** (`"1342"`, not `1342`), because JSON object keys are always strings.
- Keys sorted **lexicographically as text** at both levels, terms and book IDs alike. Note: as text, `"12"` comes before `"5"`.
- `tf` values are integers.

How to obtain it in each language:

- **Python:** `json.dumps(index, separators=(",", ":"), sort_keys=True)`.
- **Java (Jackson):** `TreeMap<String, TreeMap<String, Integer>>` and the default `ObjectMapper`, without pretty printing.
- **C++ (nlohmann):** `nlohmann::json` uses an ordered `std::map` by default; `j.dump()` with no arguments.

**Updates:** to add a book, the file is read, that book's entries are written or overwritten, and the whole file is rewritten using the safe write of section 4.3.

### 7.2 MongoDB (`mongo`)

- Database `query_tarantino`, collection `postings`.
- **One document per term-book pair:**

```json
{ "term": "whale", "book_id": 2701, "tf": 1685, "pos": [12, 88, 341] }
```

- `book_id`, `tf` and the elements of `pos` are 32-bit integers. `pos` is in ascending order.
- Indexes, created on startup if missing:
  - unique on `{ term: 1, book_id: 1 }`
  - on `{ book_id: 1 }`
- **Writes:** for each book, a single batch write (`bulkWrite`) with one `replaceOne` operation per term, filtering by `{ term, book_id }` with `upsert: true`. Indexing a book again overwrites its documents without duplicating them.
- **Reading** several terms: a single query with `{ term: { $in: [...] } }`.

**Why not one document per term**, as the guide suggests: a term that is frequent across thousands of books, with all its positions, exceeds MongoDB's 16 MB document limit, and two processes indexing at the same time clash when modifying the same documents. This decision is justified in the report.

### 7.3 Folders (`folders`)

- One file per term: `datamarts/inverted_index/X/term.txt`, where `X` is the first letter of the term **in uppercase**. Example: `datamarts/inverted_index/W/whale.txt`.
- Each line: `book_id tf`, separated by a single space and terminated by `\n`.
- **Writes:** when a book is indexed, one line is **appended** to the file of each of its terms. The file is created if it does not exist.
- **Reads:** if the same `book_id` appears on several lines, **the last one** counts. This way, a book indexed twice because of an interruption does not change the result.
- **Concurrency:** appending lines to the same file from two threads or processes at once can interleave or corrupt them. This does not happen in Stage 1 because only one process with one thread writes (section 13.1).

---

## 8. Control

Files in `control/`, relative to `TARANTINO_DATA_DIR`. All in UTF-8, one entry per line terminated by `\n`, and **append-only**: they are never rewritten.

| File | Line format | Meaning |
|---|---|---|
| `downloaded_books.txt` | `N` | Book stored in the datalake |
| `indexed_books.txt` | `N` | Book processed by the indexer: indexed if it is in English, or only recorded in the metadata otherwise |
| `failed_books.txt` | `N;REASON;ATTEMPTS` | Each failed attempt appends a line; `ATTEMPTS` is the cumulative count |

Rules:

- When reading, repeated lines for the same ID change nothing: what counts is that the ID appears. In `failed_books.txt`, the line with the highest `ATTEMPTS` counts.
- A line is appended **only after** the data it refers to has been completely written. Therefore, after an interruption, the control files are never ahead of the data.
- Only one process may use a given `TARANTINO_DATA_DIR` folder at a time (section 13.1).

### 8.1 One control step

1. **Pending indexing** = IDs in `downloaded_books.txt` that are not in `indexed_books.txt`.
2. If there are any, the **lowest** one is taken, indexed (section 8.2) and appended to `indexed_books.txt`. End of step.
3. If there are none, a new book to download is searched for. A candidate is **valid** if it has not been downloaded and has fewer than 3 failures.
   - **With `--ids FILE`** (the benchmark case): the whole file is traversed in its order and the first valid ID is taken. There is no limit on how many IDs are checked.
   - **Without a list:** exactly 10 random IDs between 1 and 75,000 (both included) are drawn, and the first valid one, in the order they were drawn, is taken. The limit of 10 only applies here, so a step can never loop forever when most IDs are already downloaded.
   - If no candidate is valid, the step ends without downloading anything.
4. The book is downloaded (section 3) and stored (section 4). On success, it is appended to `downloaded_books.txt`. On failure, a line is appended to `failed_books.txt`. End of step.

### 8.2 Indexing a book

In this order:

1. Read header and body from the datalake.
2. Extract the metadata (section 5) and write it to SQLite, with `indexed_at` empty.
3. If the language is not `en`, stop here.
4. Tokenize the body (section 6) and write to the index (section 7).
5. Update `indexed_at` in SQLite.

---

## 9. Search

### 9.1 Query processing

1. Tokenize the query text following section 6.
2. Keep the distinct terms. Order and positions do not matter.
3. If no term remains, the result is empty.

### 9.2 Matching

AND mode: a book is a result if it contains **all** the query terms.

### 9.3 TF-IDF score

For each result book `d`:

```
score(d) = Σ over each query term t:  (1 + ln(tf(t, d))) × ln(1 + N / df(t))
```

- `tf(t, d)`: frequency of the term in the book.
- `df(t)`: number of books in the index containing the term.
- `N`: number of distinct books in the index.
- `ln`: natural logarithm.
- `1` is added inside the second logarithm so that a term present in every book does not score zero.
- All computation is done in 64-bit floating point, and the summands are added **in alphabetical order of term**. Details in section 13.2.

### 9.4 Ordering and output

- Ordered by **score rounded to 9 decimals**, descending. Ties are broken by `book_id`, ascending. The rounded value is used, not the exact one, so that two mathematically equal scores that differ in the last bit are not ordered differently depending on the language.
- Each result includes `book_id`, `title`, `author`, `language` and `score`, taken from the metadata.
- `score` is displayed rounded to **6 decimals**, always with a decimal point, regardless of the system locale.
- When comparing languages, unrounded scores are considered equal if they differ by less than `1e-6`.

---

## 10. Command line

Same command and argument names in all three modules. The executable is called `tarantino` in the examples; in Java it will be `java -jar tarantino.jar` and in Python `python -m tarantino`.

```
tarantino download N                   Downloads and stores a book; appends it to downloaded_books.txt
tarantino index N                      Indexes an already downloaded book; appends it to indexed_books.txt
tarantino step [--ids FILE]            Runs one control step
tarantino run --steps K [--ids FILE]   Runs K control steps in a row
tarantino search "TEXT" [--json]       Searches and prints the results
tarantino bench --experiment E --structure S --books FILE --n K --run R --out FILE.csv
```

Any variable of section 2 can be overridden with its argument (for example `--lake`, `--index` or `--downloader`).

**Exit codes:** `0` success, `1` usage error (invalid arguments), `2` runtime error (download failure, database unavailable…).

**`tarantino search --json`** writes a single line in canonical form (sorted keys, no spaces), so that the three languages can be compared:

```json
{"query":"car best","results":[{"author":"...","book_id":3,"language":"en","score":2.079442,"title":"..."}],"total":1}
```

Without `--json`, the output is free-form and intended for humans.

---

## 11. Benchmark results

Each `tarantino bench` run appends rows to a CSV with this exact header:

```
language,experiment,structure,n_books,metric,value,unit,run
```

| Column | Values |
|---|---|
| `language` | `java` · `python` · `cpp` |
| `experiment` | `datalake` · `index` · `download` |
| `structure` | `time` · `book` · `batch` · `json` · `mongo` · `folders` · `none` |
| `n_books` | `100` · `250` · `500` · `1000` |
| `metric` | see the next table |
| `value` | number with a decimal point |
| `unit` | `books_per_s` · `ms` · `bytes` · `files` · `dirs` · `ok` |
| `run` | `0` for the warm-up, which is not used; `1`, `2` and `3` for the runs that count |

| Experiment | `metric` | Unit |
|---|---|---|
| datalake | `write_throughput` | `books_per_s` |
| datalake | `lookup_scan_mean` · `lookup_metadata_mean` | `ms` |
| datalake | `detect_new` | `ms` |
| datalake | `recovery_correct` (1 or 0) · `recovery_time` | `ok` · `ms` |
| datalake | `disk_bytes` · `file_count` · `dir_count` | `bytes` · `files` · `dirs` |
| index | `build_time` | `ms` |
| index | `query_mean` · `query_p95` | `ms` |
| index | `update_50_time` | `ms` |
| index | `disk_bytes` | `bytes` |
| download | `http_throughput` | `books_per_s` |

Peak memory is not measured by the program: `run_all.sh` measures it externally with `/usr/bin/time -v` and adds it with `metric = peak_rss` and `unit = bytes`.

File names: `benchmarks/results/{language}_{experiment}.csv`.

---

## 12. Equivalence check

Before any measurement, and after any change to this document:

1. Each module processes the 20 books in `sample_dataset/` from scratch with `TARANTINO_DOWNLOADER=local`, `TARANTINO_LAKE=time` and `TARANTINO_INDEX=json`.
2. The three `inverted_index.json` files are compared by their SHA-256 hash. **They must be identical.**
3. The `books` tables of the three SQLite files are compared, sorted by `book_id` and without the `header_path`, `body_path` and `indexed_at` columns (which depend on when the run happened). They must be identical.
4. The first 10 queries of `queries.txt` are run with `tarantino search --json` in all three languages. Same books, in the same order, with scores differing by less than `1e-6`.

If anything does not match, the difference is located and the implementation that deviates from this document is fixed. If the cause is an ambiguity in the document, the document is clarified following the procedure at the top.

---

## 13. Implementation rules

Details that do not change what the system does but that, if ignored, make the three languages produce different results or corrupt the data.

### 13.1 One process, one thread

In Stage 1, **all writes are performed by a single process with a single thread**: control steps run one after another, and within each step books and terms are written sequentially.

Reasons:

- The file-based structures do not support concurrent writers without locking: the folder index appends lines to files shared across books, the single-file index is read, modified and rewritten in full, and the control files grow on every step. Two writers at once would interleave lines or lose updates.
- The benchmark compares languages and structures on equal terms. If one language used several threads and another did not, something else would be measured.

To prevent anyone from accidentally running two processes on the same folder:

1. On startup, every command that writes (`download`, `index`, `step`, `run`, `bench`) creates the file `control/.lock` in **exclusive-create** mode, which fails if the file already exists:
   - Java: `Files.createFile(path)`
   - Python: `open(path, "x")`
   - C++: `open(path, O_CREAT | O_EXCL | O_WRONLY)` on Linux and macOS, or `CreateFile` with `CREATE_NEW` on Windows
2. It writes the process PID and the start time in UTC into the file.
3. If the file already exists, the command exits with code `2` and a message stating the PID found in the file and how to delete it if that process no longer exists.
4. On exit, whether successful or not, the command deletes the file.
5. `tarantino search` only reads and does not create the lock.

Real parallelism arrives in phase 2, with MongoDB and PostgreSQL, which do support multiple writers (book claiming with `FOR UPDATE SKIP LOCKED` and the unique term-book index).

### 13.2 Score arithmetic

- All computation in **64-bit** floating point: `double` in Java and C++, `float` in Python (which already is). Never 32-bit `float` in Java or C++.
- Integers (`tf`, `df`, `N`) are converted to floating point **before** dividing. `N / df` with integers would perform integer division and give a wrong result.
- Natural logarithm from the standard library: `Math.log` in Java, `math.log` in Python, `std::log` in C++.
- The summands of section 9.3 are added in **alphabetical order of term**. In floating point, adding in a different order can change the last decimals.
- Even so, each language's logarithm function may differ in the last bit. That is why ordering uses the score rounded to 9 decimals and cross-language comparison allows a difference of up to `1e-6` (section 9.4). With these two rules, such tiny differences never change the visible result.

How to display the score with 6 decimals and a decimal point on any system:

| Language | Correct form | Typical mistake it avoids |
|---|---|---|
| Java | `String.format(Locale.ROOT, "%.6f", score)` | With a Spanish system locale, `String.format("%.6f", …)` writes `0,693147` with a comma |
| Python | `f"{score:.6f}"` | — |
| C++ | `std::snprintf(buf, sizeof buf, "%.6f", score)` without changing the locale | A call to `setlocale` with a locale that uses a decimal comma |

In `--json` output, `score` is written as a JSON number with the value already rounded to 6 decimals.

### 13.3 Files, encoding and paths

These rules matter mostly to whoever develops on Windows. On Linux and macOS most of them hold by default.

**Encoding.** Every text file is read and written with UTF-8 specified explicitly. The system default encoding, often `cp1252` on Windows, is never relied upon.

- Java: `StandardCharsets.UTF_8` on every read and write.
- Python: `encoding="utf-8"` on every `open`.
- C++: files are handled as bytes; the text is already UTF-8 in memory.

**Line endings.** Always write `\n`, never `\r\n`. On Windows, Python and C++ convert `\n` to `\r\n` when writing in text mode, which would break the byte-by-byte comparison of the index and the datalake.

- Python: `open(path, "w", encoding="utf-8", newline="")`.
- C++: `std::ofstream(path, std::ios::binary)`.
- Java: write `"\n"` explicitly; never `System.lineSeparator()` or `println` to a file.

**Stored paths.** Paths stored in SQLite (`header_path`, `body_path`) are **relative to `TARANTINO_DATA_DIR`** and use **`/`** as separator on every operating system. They are normalized right before the `INSERT`:

| Language | How to get the relative path with `/` |
|---|---|
| Java | `dataDir.relativize(path).toString().replace('\\', '/')` |
| Python | `path.relative_to(data_dir).as_posix()` |
| C++ | `std::filesystem::relative(path, data_dir).generic_string()` |

When reading a path from SQLite, it is joined to `TARANTINO_DATA_DIR` with the language's path functions, which also accept `/` on Windows. An absolute path is never stored.

**File names.** Every name the system generates (IDs, terms in `a-z`, folder letters in `A-Z`) is ASCII, so there are no case or special-character issues on any file system.

---

## 14. Test cases

Every module implements these cases as automated tests with these exact results. They have been verified with a reference implementation in Python.

### 14.1 Tokenization

With `stopwords_en.txt` version 1.0:

| Input | Result: term → (tf, positions) |
|---|---|
| `It's the Whale's 2 voyages` | `whale` → (1, [3]) · `voyages` → (1, [5]) |
| `Whale whale WHALE ship` | `whale` → (3, [0, 1, 2]) · `ship` → (1, [3]) |
| `The café was naïve` | `caf` → (1, [1]) · `na` → (1, [3]) |
| `Don't stop-believing` | `stop` → (1, [2]) · `believing` → (1, [3]) |
| *(empty text)* | *(no terms)* |

### 14.2 Split and header

Input (with BOM and `\r\n` line endings, not visible here):

```
The Project Gutenberg eBook of Moby Dick; Or, The Whale

Title: Moby Dick;
       Or, The Whale

Author: Herman Melville

Release date: July 1, 2001 [eBook #2701]
                Most recently updated: August 18, 2021

Language: English

*** START OF THE PROJECT GUTENBERG EBOOK MOBY DICK; OR, THE WHALE ***

Call me Ishmael.

*** END OF THE PROJECT GUTENBERG EBOOK MOBY DICK; OR, THE WHALE ***

License text
```

Result:

| Field | Value |
|---|---|
| body | `Call me Ishmael.` |
| `title` | `Moby Dick; Or, The Whale` |
| `author` | `Herman Melville` |
| `language` | `en` |
| `release_date` | `July 1, 2001` |

The "Most recently updated" line is not appended to any field: the continuation rule only applies to the title.

Failure cases:

| Input | Result |
|---|---|
| Text without a `START` marker | Failure `NO_MARKERS` |
| Markers present, only whitespace between them | Failure `EMPTY_BODY` |
| Lowercase marker: `*** start of this project gutenberg ebook x ***` | Recognized as the start marker |

### 14.3 Index and search

Three books whose bodies are:

| `book_id` | Body |
|---|---|
| 1 | `the car is nice` |
| 2 | `that car is mine` |
| 3 | `the car is the best` |

Expected `inverted_index.json`, byte by byte (plus a final `\n`):

```
{"best":{"3":1},"car":{"1":1,"2":1,"3":1},"mine":{"2":1},"nice":{"1":1}}
```

Searches (with `N = 3`):

| Query | Result (`book_id`: score) |
|---|---|
| `car` | 1: 0.693147 · 2: 0.693147 · 3: 0.693147 (tie, ordered by ID) |
| `car best` | 3: 2.079442 |
| `Best CAR` | 3: 2.079442 |
| `nice mine` | *(empty: no book has both)* |
| `the` | *(empty: it is a stop word and the query has no terms left)* |

Computation of `car best` for book 3: `(1 + ln 1) × ln(1 + 3/3) + (1 + ln 1) × ln(1 + 3/1) = ln 2 + ln 4 = 0.693147 + 1.386294 = 2.079442`.

### 14.4 Batch datalake

| ID | Folder |
|---|---|
| 5 | `000000-000999` |
| 999 | `000000-000999` |
| 1000 | `001000-001999` |
| 1342 | `001000-001999` |
| 70001 | `070000-070999` |

### 14.5 Folder index with a repeated book

File `datamarts/inverted_index/C/car.txt` after indexing book 1, then book 2, and then book 1 again because of an interruption:

```
1 1
2 1
1 1
```

Expected reading: `{1: 1, 2: 1}`. The third line replaces the first one and the result does not change.

---

## History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-09-21 | Initial version |
| 1.1 | 2026-09-24 | `sample_data/` renamed to `sample_dataset/` and listed in section 1. `stopwords_en.txt` 1.0 defined as the NLTK English list keeping only `a-z` entries (153 words) |
| 1.2 | 2026-09-24 | Section 8.1 step 3: the limit of 10 candidates applies only to random IDs; with `--ids` the whole file is traversed; a step with no valid candidate downloads nothing |
