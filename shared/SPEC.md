# SPEC · Shared rules for Stage 1

**Project:** Query Tarantino · Big Data, ULPGC
**Version:** 1.5 · 2026-09-29
**Scope:** the three Stage 1 modules (`Query_Tarantino_Java`, `Query_Tarantino_Python`, `Query_Tarantino_Cpp`), the shared repository layout (section 15) and, from phase 2 onwards, the Java version.

This document defines **what** each module must do, precisely enough for all three to produce exactly the same results. It does not say **how** to implement it: each language uses its own tools as long as it follows these rules.

The Stage 1 guide requires all implementations to use the same dataset and the same preprocessing rules, and to produce equivalent outputs. An implementation that does not comply with this document cannot be used for benchmarking. The guide also requires a README, a sample dataset and a Git history that shows the progression of the work; section 15 collects those requirements.

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

- It is done with the Python tool `python -m src.infrastructure.entrypoints.corpus_tools build-corpus`, which reuses the download, decoding, split and header rules of the pipeline.
- Project Gutenberg reserves its website for human users and asks automated clients to wait 2 seconds between requests. This one-off selection therefore waits **2 seconds** between the starts of two requests, which satisfies section 3.2. The `download` benchmark (section 11.5.5) is automated too and also waits 2 seconds; the pipeline keeps the 1-second minimum.
- A book's corpus file is written before its ID is appended to `book_ids_benchmark.txt`, so an interrupted selection resumes after the last listed ID.

### 1.2 How the queries are generated

Done once, with a Python script and fixed seed `42`, on the full index of the 1,000 books:

- 40 one-term queries, 30 two-term queries and 30 three-term queries, in this order: 190 term slots in total.
- The index is the `json` index of the 1,000 books (section 7.1). The document frequency `df` of a term is the number of books it appears in, and `N` is the number of indexed books (section 9.3).
- Bands, checked in this order with integer arithmetic:
  - frequent: `2 × df > N` (more than 50% of the books);
  - medium: `20 × df ≥ N` and not frequent (from 5% to 50%, both included);
  - rare: `2 ≤ df ≤ 5`;
  - any other term is never drawn.
- Term slot `i` (from 0, counted over all the queries in order) belongs to band `i mod 3`: frequent, medium, rare, frequent… This gives 64 frequent, 63 medium and 63 rare terms.
- The candidates of each band are sorted alphabetically. With a single `random.Random(42)`, each band draws all its terms at once with `sample(candidates, k)`, without replacement, in the order frequent, medium, rare. The slots of each band take its drawn terms in order. A term therefore never appears twice in the file.
- Each query is written as its terms in slot order, separated by a single space. If a band has fewer candidates than it needs, the generation fails.
- It is done with `python -m src.infrastructure.entrypoints.corpus_tools build-queries`. The result is saved to `queries.txt` and is never regenerated: the tool refuses to overwrite it.

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

- At most **one request per second**: at least 1 second must pass between the **start** of two consecutive requests, fallback URLs included. The wait applies only to the `http` downloader.
- Header `User-Agent: QueryTarantino/1.0 (ULPGC Big Data student project)`.
- Maximum wait per request: 30 seconds.
- **Network errors.** A timeout, or any other network error (DNS failure, connection refused or reset, TLS error, too many redirects), makes that URL count as failed, and the next one is tried. If it was the last URL, the book fails with `HTTP_ERROR`.
- Redirects are followed. Some HTTP clients do not follow them by default and must be configured to do so.
- Because of this limit, `http_throughput` can never exceed 1 book per second; the `download` benchmark waits 2 seconds, so there it never exceeds 0.5 (section 11.5.5).

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

**Copies of the same book.** In this structure a book can end up in two folders: if a run is interrupted after writing a book and before appending it to `downloaded_books.txt` (section 8), the book is downloaded again later and written to a later hour folder. The copy in the **most recent** folder counts, comparing the folder paths `YYYYMMDD/HH` as text; older copies are ignored by every reader and are never deleted automatically. In `book` and `batch` the path does not depend on the time, so the new copy simply replaces the old one.

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

The header is written first, then the body. A book exists in the datalake only if both final files exist.

**Leftovers from an interrupted run.** On startup, right after acquiring the lock (section 13.1), every command that writes deletes all `.tmp` files under `datalake/`, `datalake_book/`, `datalake_batch/` and `datamarts/`. A reader never treats a `.tmp` file as data: it is not a book, it is not counted and it is not listed.

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
CREATE INDEX IF NOT EXISTS idx_books_title    ON books(title);
```

- Written with `INSERT OR REPLACE`: processing a book twice does not duplicate rows.
- `header_path` and `body_path`: paths relative to `TARANTINO_DATA_DIR`, using `/` as separator on every operating system. How to achieve this in each language is described in section 13.3.
- `indexed_at`: UTC timestamp in `YYYY-MM-DDTHH:MM:SSZ` format. Empty (`NULL`) if the book is not in English and has therefore not been indexed.
- The indexes on `lower(author)` and `title` serve the metadata queries named in the Stage 1 guide (books by author, path by title) and are measured in section 11.5.4.

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
- Book IDs are **strings** (`"1342"`, not `1342`), because JSON object keys are always strings. They are converted to strings **before** sorting and serializing. Sorting integer IDs and converting them afterwards gives numeric order (`5` before `12`), which is wrong (section 14.6).
- Keys sorted **lexicographically as text** at both levels, terms and book IDs alike. Note: as text, `"12"` comes before `"5"`.
- `tf` values are integers.

How to obtain it in each language:

- **Python:** every key must already be a `str` (`index[term][str(book_id)] = tf`), then `json.dumps(index, separators=(",", ":"), sort_keys=True)`. Warning: `sort_keys` sorts the keys *before* converting them to text, so integer keys would come out in numeric order. `json.dump` with the same arguments, writing directly to the file, produces the same bytes.
- **Java (Jackson):** `TreeMap<String, TreeMap<String, Integer>>`, never `TreeMap<Integer, …>`, and an `ObjectMapper` with the default serialization settings, without pretty printing. Disabling `AUTO_CLOSE_TARGET`, so that the final `\n` can be written to the same stream, does not change the bytes.
- **C++ (nlohmann):** `nlohmann::json` uses an ordered `std::map` by default and its object keys are always strings: `j[term][std::to_string(book_id)] = tf`. Output with `j.dump()` with no arguments, or `stream << j`, which produces the same bytes.
- In all three, the final `\n` is written explicitly after the object.

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
- `N`: number of indexed books, read from the metadata with `SELECT COUNT(*) FROM books WHERE indexed_at IS NOT NULL`. It is read once per search, not once per term. Taking it from SQLite gives the same value in every index structure, at the same cost; counting the distinct books of the `folders` index would require reading every file.
- `ln`: natural logarithm.
- `1` is added inside the second logarithm so that a term present in every book does not score zero.
- All computation is done in 64-bit floating point, and the summands are added **in alphabetical order of term**. Details in section 13.2.

### 9.4 Ordering and output

- Ordered by **score rounded to 9 decimals**, descending. Ties are broken by `book_id`, ascending. The rounded value is used, not the exact one, so that two mathematically equal scores that differ in the last bit are not ordered differently depending on the language.
- Each result includes `book_id`, `title`, `author`, `language` and `score`, taken from the metadata.
- `score` is displayed rounded to **6 decimals**, always with a decimal point, regardless of the system locale.
- When comparing languages, the displayed scores (already rounded to 6 decimals) are considered equal if they differ by at most `1e-6 + 1e-9` (section 12).

---

## 10. Command line

Same command and argument names in all three modules. The executable is called `tarantino` in the examples; in Java it will be `java -jar tarantino.jar` and in Python `python -m tarantino`.

```
tarantino download N                   Downloads and stores a book; appends it to downloaded_books.txt
tarantino index N                      Indexes an already downloaded book; appends it to indexed_books.txt
tarantino step [--ids FILE]            Runs one control step
tarantino run --steps K [--ids FILE]   Runs K control steps in a row
tarantino search "TEXT" [--json]       Searches and prints the results
tarantino bench --experiment E --structure S --n N --run R --out FILE.csv
```

Any variable of section 2 can be overridden with its argument (for example `--lake`, `--index` or `--downloader`). The valid combinations of `--experiment`, `--structure` and `--n` are those of section 11.1; any other combination is a usage error. `bench` is described in section 11.

**Exit codes:** `0` success, `1` usage error (invalid arguments), `2` runtime error (download failure, database unavailable…).

**`tarantino search --json`** writes a single line in canonical form (sorted keys, no spaces), so that the three languages can be compared:

```json
{"query":"car best","results":[{"author":"...","book_id":3,"language":"en","score":2.079442,"title":"..."}],"total":1}
```

Without `--json`, the output is free-form and intended for humans.

---

## 11. Benchmarks

The benchmark compares three languages and several storage structures. For the comparison to be valid, every number answers a single question and everything else stays fixed. This section defines what is measured, from which state and how; nothing in it is left to each implementation. If something is not covered here, it is clarified in this document before measuring (see the procedure at the top).

### 11.1 Experiments and configurations

| Experiment | What it compares | `structure` | `n_books` |
|---|---|---|---|
| `datalake` | Datalake structures: writing, lookup, incremental detection, storage overhead | `time` · `book` · `batch` | `100` · `250` · `500` · `1000` |
| `recovery` | Datalake structures: resuming after an interruption | `time` · `book` · `batch` | `100` · `250` · `500` · `1000` |
| `index` | Inverted-index structures: build, update, queries, storage | `json` · `mongo` · `folders` | `100` · `250` · `500` · `1000` |
| `metadata` | The SQLite metadata store as it grows | `sqlite` | `1000` · `10000` · `50000` |
| `download` | Real download from Gutenberg | `none` | `50` |
| `baseline` | Memory of the runtime alone, subtracted from `peak_rss` | `none` | `0` |

A **configuration** is one combination of language, experiment, structure and `n_books` from this table. A **run** is one execution of one configuration, in its own process.

The books of a configuration with `n_books = N` are the first N IDs of `shared/book_ids_benchmark.txt`, in file order. The queries are the 100 lines of `shared/queries.txt`, in file order.

### 11.2 Command and bench area

```
tarantino bench --experiment E --structure S --n N --run R --out FILE.csv
```

- **Bench area.** `bench` works only inside `<TARANTINO_DATA_DIR>/bench/`, which it empties right after acquiring the lock (section 13.1). It never touches anything else in the data folder, so a benchmark can never destroy real pipeline data. The lock is still `<TARANTINO_DATA_DIR>/control/.lock`.
- Inside the bench area, paths are those of sections 4, 5, 7 and 8, as if it were a data folder of its own: for example `bench/datalake_book/7/body.txt` or `bench/control/downloaded_books.txt`. When the `recovery` experiment runs the `.tmp` cleanup of section 4.3, it runs it over the same folders inside the bench area.
- **Downloader.** Every experiment except `download` reads books with `LocalCorpusDownloader` from `TARANTINO_CORPUS_DIR`, which must contain the whole benchmark corpus (the 1,000 books). `download` uses `HttpBookDownloader`.
- `--structure` selects the structure. The `--lake`, `--index` and `--downloader` settings are ignored by `bench`.
- **MongoDB.** Database `query_tarantino_bench`, never `query_tarantino`. It is dropped at the start of every run.
- **Output.** A run appends its rows to `--out` (writing the header of section 11.8 only if the file does not exist yet), and only after all its validity checks have passed (section 11.7). If a check fails, the run writes no rows and exits with code `2`.

### 11.3 Measurement rules

1. **Clock.** Monotonic, with nanosecond resolution: `time.perf_counter_ns()` in Python, `System.nanoTime()` in Java, `std::chrono::steady_clock` in C++.
2. **Timed region.** Only the operation named in the metric's definition. Preparing the state, validity checks, statistics, writing the CSV and printing are always outside it.
3. **Warm-up inside the process.** Before lookups, `detect_new_*` and queries are measured, one full unmeasured pass of exactly the same operations is run. Each run is a new process, so run 0 of section 11.6 warms the disk cache but not Java's JIT compiler; this in-process pass does. Write metrics (`write_throughput`, `build_time`, `update_50_time`, `recovery_time_*`, inserts) have no in-process warm-up: they measure work done for the first time.
4. **Short operations.** Lookups and `detect_new_*` are timed as a single region around all their repetitions, and the value is the total divided by the number of operations. Queries are timed one by one, because their percentiles are needed.
5. **Percentiles.** Nearest-rank method: with the n samples sorted in ascending order, percentile p (an integer between 1 and 100) is the sample at 1-based position `(p × n + 99) div 100`, computed with integer arithmetic. No interpolation. The mean is the arithmetic mean.
6. **No forced flushes.** No `fsync`, `fdatasync`, `FileChannel.force` or `FlushFileBuffers`, in the benchmark or in the pipeline (section 13.3). With them, write throughput would measure the disk's durability policy instead of the implementation.
7. **Garbage collectors** keep their default configuration. There are no explicit calls (`gc.collect()`, `System.gc()`).
8. **Page cache.** Measurements are taken with a warm operating-system cache: files written or read while preparing a run stay cached. It is the same for every language and structure, and it is stated as a limitation in the report.
9. **Values.** Times in milliseconds. Throughputs in items per second, computed with the elapsed time in seconds. Written as described in section 11.8.

### 11.4 Simulated clock

In `bench`, the `time` datalake does not use the real clock. Its clock is created with a start instant and, on its i-th call (i from 0), returns:

```
start + ⌊i / 50⌋ hours
```

The `time` datalake calls its clock exactly once per `save`. Unless a section says otherwise, `start` is `2026-01-01T00:00:00Z`.

- Calls 0–49 write to `datalake/20260101/00/`, call 50 to `20260101/01/`, and call 999 to `20260101/19/`.
- 1,000 books are spread over 20 hour folders, like a crawler running for most of a day. With the real clock, the local corpus would put every book into one or two folders, and each language would produce different folders depending on when it ran.

### 11.5 Definitions

#### 11.5.1 `datalake`

The sample of a run is the 50 books at positions `⌊j × N / 50⌋`, for j = 0…49, of the N books of the configuration (positions from 0).

1. **`write_throughput`** (`books_per_s`). From an empty bench area, `IngestBookUseCase` is executed for the N books, in order, with the structure under test and the control store of the bench area. Timed: the whole loop. Value: N divided by the elapsed seconds.
2. **Storage** (right after step 1, under the lake root only: `datalake/`, `datalake_book/` or `datalake_batch/`):
   - `disk_bytes` (`bytes`): sum of the sizes of all regular files.
   - `file_count` (`files`): number of regular files.
   - `dir_count` (`dirs`): number of directories below the root, the root excluded.
   - The space actually allocated on disk is measured by `run_all.sh` (section 11.6).
3. **`lookup_scan_mean`** (`ms`). For each sample book: `get_paths` of the structure, then check that both files exist. Only the lake is used: neither control files nor SQLite. After the warm-up pass, 20 passes over the sample (1,000 lookups) are timed as one region. Value: total divided by 1,000.
4. **`lookup_metadata_mean`** (`ms`).
   - Preparation (not timed): for each of the N books, `load` from the lake, `parse_header`, and `MetadataStorage.save` with the book's paths (`get_paths`), in `bench/datamarts/metadata.sqlite`.
   - Timed: for each sample book, `SELECT header_path, body_path FROM books WHERE book_id = ?` (statement prepared once), join both paths to the bench area and check that both files exist. Same repetitions and value as step 3.
5. **Incremental state** (not timed). The first N − 50 books are recorded as indexed (`record_indexing`), so the books pending indexing are exactly the last 50.
6. **`detect_new_control`** (`ms`). `get_downloaded_books()`, `get_indexed_books()` and their difference. After the warm-up pass, 20 repetitions are timed as one region. Value: total divided by 20.
7. **`detect_new_scan`** (`ms`). The pending books are found from the lake itself, as the guide's "incremental processing" describes.
   - The set of indexed books is read once, before timing (it is the same for every structure).
   - Timed: list the IDs of the complete books stored in the lake (both final files present; `.tmp` files ignored) and subtract the indexed set.
   - **Checkpoint.** In `time`, the listing only walks the hour folders whose name `YYYYMMDD/HH` is greater than or equal, as text, to the folder of the last indexed book (the book at position N − 51): every book in an earlier folder is already indexed. `book` and `batch` do not record when a book was written, so they list the whole lake. In the real pipeline the checkpoint would be stored after each indexing step; that is outside Stage 1.
   - Same repetitions and value as step 6.

#### 11.5.2 `recovery`

Each run executes two scenarios, each one from an empty bench area and in this order: `tmp_leftover` and `data_without_control`. In both, `c = N / 2` is the position of the interrupted book and `b` is the book at that position.

**Phase 1: the interrupted run** (not timed; simulated clock with the default start).

1. `IngestBookUseCase` for the books at positions 0 … c − 1.
2. Book `b` is left exactly as an interrupted run would leave it:
   - `tmp_leftover` (interrupted while writing the header): `b` is read with the downloader and saved with the structure's `save`. Then both final files are deleted, and `<header path>.tmp` is written with the first `⌊L / 2⌋` bytes of the header, where L is the length of the header in UTF-8 bytes. Nothing is appended to control.
   - `data_without_control` (interrupted after writing the data and before appending to control): `b` is saved with the structure's `save`. Nothing is appended to control.

**Phase 2: the restart.** New adapters are created, as a new process would do. The `time` datalake receives a new simulated clock whose start is one hour after the last hour used in phase 1: `2026-01-01T00:00:00Z + (⌊c / 50⌋ + 1)` hours, because a real restart always happens later.

- **`recovery_time_<scenario>`** (`ms`). Timed:
  1. the `.tmp` cleanup of section 4.3 over the bench area;
  2. `IngestBookUseCase` for the first book of the list that is not in `downloaded_books.txt`. It must be `b` (validity, section 11.7).

**Phase 3: completion and checks** (not timed). The books at positions c + 1 … N − 1 are ingested. Then:

- **`recovery_correct_<scenario>`** (`ok`): `1` if all of these hold, `0` otherwise:
  - there is no `.tmp` file in the bench area;
  - `downloaded_books.txt` contains each of the N IDs exactly once, and no other ID;
  - for each of the N books, `load` returns exactly the header and body obtained by reading its corpus file with the downloader.
- **`recovery_stale_copies_<scenario>`** (`count`): number of books with a complete copy in more than one place of the lake. It can only be non-zero in `time`, when a book is downloaded again at a later hour (section 4.1).

`<scenario>` is `tmp_leftover` or `data_without_control`, so each run writes six metrics.

#### 11.5.3 `index`

**Preparation** (not timed). Empty the bench area and drop the bench MongoDB database. Load the stop words. Ingest the N books with `IngestBookUseCase` into a `book` datalake of the bench area. The datalake structure is the same for every index structure, so it does not affect the result.

1. **`build_time`** and **`update_50_time`** (`ms`). `IndexBookUseCase` is executed for the N books, in order, with the structure under test, the SQLite store `bench/datamarts/metadata.sqlite` and the real clock (`indexed_at` is not compared). It is timed in two regions: the first N − 50 books and the last 50.
   - `update_50_time`: the second region, that is, the cost of adding 50 books to an existing index of N − 50 books.
   - `build_time`: the sum of both regions.
2. **Breakdown of `build_time`** (`ms`). The ports used by `IndexBookUseCase` are wrapped in timing decorators that implement the same port and accumulate the time spent inside the wrapped calls over the N books:
   - `index_write_time`: `write_book_terms`;
   - `metadata_write_time`: `save` and `update_indexed_at`;
   - `lake_read_time`: `load`.
   - The rest of `build_time` is processing: header parsing, tokenization and control. The analysis computes it by subtraction.
3. **Storage** (right after step 1):
   - `json`: `disk_bytes` is the size of `inverted_index.json`.
   - `folders`: `disk_bytes` is the sum of the sizes of the files under `datamarts/inverted_index/`; also `file_count` and `dir_count` (directories below `inverted_index/`, itself excluded).
   - `mongo`: after running the `fsync` admin command, so that the data has reached the disk, `disk_bytes` is `storageSize + totalIndexSize` from the storage statistics of the `postings` collection (`$collStats` with `storageStats`). This size is compressed by MongoDB, which the report must mention.
   - The space actually allocated for `json` and `folders` is measured by `run_all.sh` (section 11.6).
4. **Validity counts** (`count`), read from the structure after step 1: `index_terms` (distinct terms) and `index_postings` (distinct term-book pairs; in `folders`, the last line of each book counts, section 7.3). For the same N they must be equal in every language and structure (section 11.7).
5. **`open_time`** (`ms`). Time to make the index ready for queries from nothing:
   - in every structure, open the SQLite store and read N (section 9.3);
   - `json`: in addition, read and parse the whole file into memory;
   - `mongo`: in addition, create a new client and run the `ping` command;
   - `folders`: nothing else.
6. **Queries** (`ms`). With the index opened in step 5: the warm-up pass over the 100 queries, then 5 measured passes; each query is timed individually (500 samples). A query covers sections 9.1 to 9.4 up to the ordered list of `(book_id, score)`: tokenizing, reading the postings of each term, AND matching, TF-IDF and ordering. Fetching titles and authors and printing are excluded.
   - `query_mean`, `query_p50`, `query_p95`, `query_p99`: over the 500 samples.
   - `query_mean_t1`, `query_mean_t2`, `query_mean_t3`: mean over the samples of the queries with 1, 2 and 3 distinct terms after tokenization.
   - `query_results_total` (`count`): sum of the number of results of the 100 queries in the first measured pass. It must be equal in every language and structure (section 11.7).

#### 11.5.4 `metadata`

Measures the SQLite store of section 5.4 as the number of books grows, as recommended by the Stage 1 guide (insertion speed, common queries and scalability from hundreds to tens of thousands of books).

1. **Source rows** (not timed). For each of the 1,000 benchmark books, in list order: read it with `LocalCorpusDownloader`, apply `parse_header`, and use the paths of the `book` layout (`datalake_book/N/header.txt`, `datalake_book/N/body.txt`) and `indexed_at = 2026-01-01T00:00:00Z`. Nothing is written to the lake.
2. **Scaling.** For `n_books = K`, `K / 1000` copies of the source rows are generated. Copy `c` (starting at 0) keeps every column and replaces `book_id` with `book_id + 1,000,000 × c`. Example: book 1342 in copy 3 becomes `3001342`.
3. **Database.** `bench/datamarts/metadata_bench.sqlite`, created with the schema of section 5.4. It is deleted and created again before steps 4 and 5.
4. **`insert_throughput`** (`rows_per_s`). The K rows are inserted in order of copy and then of `book_id`, each with its own `INSERT OR REPLACE` in its own transaction, as the pipeline does. Value: K divided by the elapsed seconds.
5. **`bulk_insert_throughput`** (`rows_per_s`). The same K rows, inserted in a single transaction with a single prepared statement. Value: K divided by the elapsed seconds.
6. **Lookups** (`ms`), on the database of step 5. The sample is the source rows at positions 0, 20, 40, …, 980 (50 rows). Each statement is prepared once and every execution reads all the rows it returns. After the warm-up pass, 20 passes over the sample (1,000 executions) are timed as one region. Value: total divided by 1,000.
   - `query_author_mean`: `SELECT book_id FROM books WHERE lower(author) = lower(?) ORDER BY book_id`, with the sample's `author`.
   - `lookup_title_mean`: `SELECT header_path, body_path FROM books WHERE title = ?`, with the sample's `title`.
   - `lookup_id_mean`: `SELECT header_path, body_path FROM books WHERE book_id = ?`, with the sample's `book_id`.
7. **`disk_bytes`** (`bytes`). Size of `metadata_bench.sqlite` after step 6.

#### 11.5.5 `download`

`IngestBookUseCase` with `HttpBookDownloader` and a `book` datalake, for the first 50 books of the list. Like the corpus selection of section 1.1, it is an automated client, so it waits **2 seconds** between the starts of two requests, following Project Gutenberg's robot policy. **`http_throughput`** (`books_per_s`): 50 divided by the elapsed seconds, politeness waits included. The 2-second wait caps it at 0.5 books per second in every language, so it is reported but not used to compare languages. To limit the load on Project Gutenberg, it only runs in rounds 0 to 3 (section 11.6).

#### 11.5.6 `baseline`

Acquires the lock, empties the bench area, loads the stop words and exits. It times nothing and writes no rows of its own. `run_all.sh` records its `peak_rss` (section 11.6), and the analysis subtracts it from the `peak_rss` of the other experiments of the same language, so that the memory of the runtime itself (the JVM, the Python interpreter) is not attributed to the structures.

### 11.6 `run_all.sh`: environment, order and external measurements

**Machine.**

- A single machine for every run, running Linux: native, or WSL2 with the whole repository inside the Linux file system (never under `/mnt/c`). `peak_rss` requires GNU time (`/usr/bin/time -v`).
- SSD disk, at least 8 GB of RAM, and the MongoDB server running on the same machine.
- The repository outside folders synchronized to the cloud (OneDrive, Dropbox, iCloud) and excluded from antivirus scanning, which would slow down every small file.
- Laptop plugged in, no other heavy programs running, and the CPU frequency governor set to `performance` when the system allows it.

**Builds and runtimes**, identical in every run:

- C++: `cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release` and the resulting binary.
- Java: the packaged jar, run with `java -Xms256m -Xmx4g -jar`.
- Python: the CPython version stated in the README, run with `python -m tarantino`.

**Before measuring**, `run_all.sh`:

1. Runs the equivalence check of section 12 on the current commit and stops if it fails.
2. Writes `benchmarks/results/environment.txt`: date; CPU model and number of cores; RAM; disk model and type; file system of the repository; operating system and kernel; versions of Python, JDK, C++ compiler, CMake and MongoDB server; the commit hash, and whether there are uncommitted changes.

**Order of the runs.**

- Round 0 is the warm-up and is discarded; rounds 1 to 5 are the ones that count.
- In each round, every configuration of section 11.1 runs once (`download` only in rounds 0 to 3), in the order printed by `python benchmarks/plan.py --round R`: the list of all configurations, shuffled with `random.Random(R)`. Interleaving languages and structures spreads effects such as the machine heating up over all of them, instead of penalizing whatever runs last.
- Every run is a separate process, with `TARANTINO_DATA_DIR=benchmarks/work` and `TARANTINO_CORPUS_DIR` pointing to the full corpus.

**External measurements.** `run_all.sh` appends these rows to the same CSV as the run, with the same `language`, `experiment`, `structure`, `n_books` and `run`:

- `peak_rss` (`bytes`): "Maximum resident set size" reported by `/usr/bin/time -v`, multiplied by 1,024. For every experiment, `baseline` included. The memory of the MongoDB server is not included, because it is another process.
- `disk_bytes_allocated` (`bytes`): `du -sB1` of the same path measured in `disk_bytes`, right after the run: the lake root in `datalake`, and `inverted_index.json` or `datamarts/inverted_index/` in `index` with `json` or `folders`. Compared with `disk_bytes`, it shows the space lost to small files: a 20-byte file occupies a whole disk block.

**JSON index fingerprint.** After every `index` run with `json`, `run_all.sh` appends the SHA-256 of `bench/datamarts/inverted_index.json` to `benchmarks/results/json_index_sha256.csv`, with header `language,n_books,run,sha256`.

### 11.7 Validity

A measurement of a wrong result is worthless.

**Inside each run** (after the timed phases, not timed). If any check fails, the run writes no rows and exits with code `2`:

- `datalake`: the lake holds exactly the N books, complete and without `.tmp` files; every lookup found both files; both `detect_new_*` returned exactly the last 50 IDs.
- `recovery`: the book ingested first after the restart was `b`.
- `index`: `index_terms`, `index_postings` and `query_results_total` were computed.
- `metadata`: after each insertion step the table has exactly K rows, and every lookup of the sample returns at least one row.

**Across runs** (checked by `benchmarks/analyze.py`, section 11.9). For each N:

- `index_terms`, `index_postings` and `query_results_total` are equal in every language, structure and run;
- the SHA-256 in `json_index_sha256.csv` is the same in every language and run.

If anything differs, the results for that N are not valid: the discrepancy is found and fixed, and those configurations are measured again.

### 11.8 CSV format

Each run appends rows to `benchmarks/results/{language}_{experiment}.csv`, with this exact header:

```
language,experiment,structure,n_books,metric,value,unit,run
```

| Column | Values |
|---|---|
| `language` | `java` · `python` · `cpp` |
| `experiment` | `datalake` · `recovery` · `index` · `metadata` · `download` · `baseline` |
| `structure` | as in section 11.1 |
| `n_books` | as in section 11.1 |
| `metric` | see the next table |
| `value` | a number with a decimal point, six decimals and no thousands separator, written regardless of the system locale (`1000.000000`, `0.004213`; section 13.2) |
| `unit` | `books_per_s` · `rows_per_s` · `ms` · `bytes` · `files` · `dirs` · `ok` · `count` |
| `run` | `0` for the warm-up round, which is not used; `1` to `5` for the rounds that count |

| Experiment | `metric` | Unit |
|---|---|---|
| datalake | `write_throughput` | `books_per_s` |
| datalake | `lookup_scan_mean` · `lookup_metadata_mean` | `ms` |
| datalake | `detect_new_control` · `detect_new_scan` | `ms` |
| datalake | `disk_bytes` · `disk_bytes_allocated`\* | `bytes` |
| datalake | `file_count` · `dir_count` | `files` · `dirs` |
| recovery | `recovery_time_tmp_leftover` · `recovery_time_data_without_control` | `ms` |
| recovery | `recovery_correct_tmp_leftover` · `recovery_correct_data_without_control` | `ok` |
| recovery | `recovery_stale_copies_tmp_leftover` · `recovery_stale_copies_data_without_control` | `count` |
| index | `build_time` · `update_50_time` | `ms` |
| index | `index_write_time` · `metadata_write_time` · `lake_read_time` | `ms` |
| index | `open_time` | `ms` |
| index | `query_mean` · `query_p50` · `query_p95` · `query_p99` | `ms` |
| index | `query_mean_t1` · `query_mean_t2` · `query_mean_t3` | `ms` |
| index | `disk_bytes` · `disk_bytes_allocated`\* (not in `mongo`) | `bytes` |
| index | `file_count` · `dir_count` (only `folders`) | `files` · `dirs` |
| index | `index_terms` · `index_postings` · `query_results_total` | `count` |
| metadata | `insert_throughput` · `bulk_insert_throughput` | `rows_per_s` |
| metadata | `query_author_mean` · `lookup_title_mean` · `lookup_id_mean` | `ms` |
| metadata | `disk_bytes` | `bytes` |
| download | `http_throughput` | `books_per_s` |
| all | `peak_rss`\* | `bytes` |

\* Added by `run_all.sh` (section 11.6), not by the program.

### 11.9 Analysis

`benchmarks/analyze.py` (Python, with pandas and matplotlib listed in `benchmarks/requirements.txt`) reads every CSV in `benchmarks/results/` and writes its tables and figures to `benchmarks/report/`:

1. **Aggregation.** For each configuration and metric: median over rounds 1 to 5, and interquartile range (p25 to p75, nearest-rank as in section 11.3). A time or throughput metric whose coefficient of variation (sample standard deviation divided by the mean) exceeds 10 % is flagged; that configuration is run for 5 more rounds with the same procedure, and the report says so.
2. **Summary tables** at the largest N of each experiment: median [p25–p75] per language × structure, and the speedup relative to Python (ratio of medians).
3. **Scalability.** Each metric against N on log-log axes, one line per language and one panel per structure, with the slope of the least-squares line through the log-log points. A slope close to 1 means linear growth and close to 2 quadratic growth, which is expected for `build_time` with `json`, because the whole file is rewritten for every book.
4. **Build breakdown.** Stacked bars of `lake_read_time`, `metadata_write_time`, `index_write_time` and the rest, per language × structure. They show which part of the cost depends on the language (processing, bound by the CPU) and which on the structure (input/output).
5. **Query latency.** `query_p50`, `query_p95` and `query_p99` per language × structure, as grouped bars with the interquartile range as error bars, and `query_mean_t1`, `query_mean_t2` and `query_mean_t3`, which show how the cost grows with the number of terms.
6. **Memory.** `peak_rss` minus the `baseline` of the same language, per experiment and structure.
7. **Validity.** The cross-run checks of section 11.7 and `recovery_correct_*`, as a table.

The benchmark section of the report is built from these tables and figures. It discusses where the language matters and where the structure matters, the threats to validity (warm cache, a single machine, MongoDB on the same host, N small compared with a real system) and justifies the final choice of datalake and index structures.

---

## 12. Equivalence check

Before any measurement, and after any change to this document:

1. Each module processes the 20 books in `sample_dataset/` from scratch with `TARANTINO_DOWNLOADER=local`, `TARANTINO_CORPUS_DIR=shared/sample_dataset`, `TARANTINO_LAKE=time` and `TARANTINO_INDEX=json`. For example, `tarantino run --steps 40 --ids shared/book_ids_benchmark.txt`: each downloaded book is indexed in the next step, so 40 steps process exactly the first 20 books.
2. The three `inverted_index.json` files are compared by their SHA-256 hash. **They must be identical.**
3. The `books` tables of the three SQLite files are compared, sorted by `book_id` and without the `header_path`, `body_path` and `indexed_at` columns (which depend on when the run happened). They must be identical.
4. The first 10 queries of `queries.txt` are run with `tarantino search --json` in all three languages. Same books, in the same order, with scores differing by at most `1e-6 + 1e-9`. The scores are already rounded to 6 decimals: two unrounded scores that differ only in the last bits can fall on both sides of a rounding boundary and end up exactly `1e-6` apart, and the extra `1e-9` absorbs the binary representation of that difference.

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
3. If the file already exists, the command exits with code `2` and a message stating the PID found in the file and how to delete it if that process no longer exists. **It does not delete the existing file.**
4. Once the lock is acquired, the command deletes the `.tmp` leftovers of section 4.3 before doing anything else.
5. On exit, whether successful or not, the command deletes the lock file **it created**. A command that could not create it never deletes it.
6. `tarantino search` only reads and does not create the lock.

Real parallelism arrives in phase 2, with MongoDB and PostgreSQL, which do support multiple writers (book claiming with `FOR UPDATE SKIP LOCKED` and the unique term-book index).

### 13.2 Score arithmetic

- All computation in **64-bit** floating point: `double` in Java and C++, `float` in Python (which already is). Never 32-bit `float` in Java or C++.
- Integers (`tf`, `df`, `N`) are converted to floating point **before** dividing. `N / df` with integers would perform integer division and give a wrong result.
- Natural logarithm from the standard library: `Math.log` in Java, `math.log` in Python, `std::log` in C++.
- The summands of section 9.3 are added in **alphabetical order of term**. In floating point, adding in a different order can change the last decimals.
- Even so, each language's logarithm function may differ in the last bit. That is why ordering uses the score rounded to 9 decimals and cross-language comparison allows a difference of up to `1e-6 + 1e-9` (sections 9.4 and 12). With these two rules such tiny differences almost never change the visible result. The residual risk is a score that falls exactly on a rounding boundary: two books whose scores tie to 9 decimals in one language and not in another could swap places. It is accepted as extremely unlikely; if the equivalence check ever shows it, the case is documented in the report.

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

**No forced flushes.** Files are never forced to disk: no `fsync`, `fdatasync`, `FileChannel.force` or `FlushFileBuffers`. The safe write of section 4.3 protects against an interrupted process, not against a power cut; that limitation is stated in the report. The three languages must perform exactly the same input/output operations; otherwise the benchmark would compare durability policies instead of implementations (section 11.3).

---

## 14. Test cases

Every module implements these cases as automated tests with these exact results. Sections 14.1 to 14.6 and 14.9 have been verified with a reference implementation in Python; 14.7 and 14.8 follow directly from the rules above and must be verified the same way before this version is approved.

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

### 14.6 Order of book IDs in the JSON index

Two books whose bodies are:

| `book_id` | Body |
|---|---|
| 5 | `the car is nice` |
| 12 | `that car is mine` |

Expected `inverted_index.json`, byte by byte (plus a final `\n`):

```
{"car":{"12":1,"5":1},"mine":{"12":1},"nice":{"5":1}}
```

As text, `"12"` comes before `"5"`. An implementation that sorts integer IDs and converts them afterwards writes `"5"` first and fails this case. Section 14.3 does not detect the error because its IDs have a single digit.

### 14.7 Startup: lock and leftovers

| Situation | Expected result |
|---|---|
| `datalake_book/7/body.txt.tmp` exists and `tarantino step` is run | The `.tmp` file is deleted before the step does anything else |
| `control/.lock` exists and `tarantino step` is run | Exit code `2`; nothing is written or deleted, and `control/.lock` is still there |
| `control/.lock` exists and `tarantino search "car"` is run | The search runs normally, because it does not use the lock |
| `tarantino step` finishes, with or without errors | `control/.lock` no longer exists |

### 14.8 Time datalake with an old copy

Files present:

| File | Content |
|---|---|
| `datalake/20260101/00/7.header.txt` | `old header` |
| `datalake/20260101/00/7.body.txt` | `old body` |
| `datalake/20260101/03/7.header.txt` | `new header` |
| `datalake/20260101/03/7.body.txt` | `new body` |
| `datalake/20260101/05/7.header.txt` | `incomplete` (there is no `7.body.txt` in that folder) |

Expected result:

- `load(7)` returns header `new header` and body `new body`.
- `get_paths(7)` returns `datalake/20260101/03/7.header.txt` and `datalake/20260101/03/7.body.txt`.
- Folder `05` does not hold a copy, because only one of the two files is there; folder `00` holds an old copy, which is ignored (section 4.1).

### 14.9 Benchmark rules

**Simulated clock** (section 11.4), with start `2026-01-01T00:00:00Z`:

| Call | Instant | `time` folder |
|---|---|---|
| 0 | `2026-01-01T00:00:00Z` | `20260101/00` |
| 49 | `2026-01-01T00:00:00Z` | `20260101/00` |
| 50 | `2026-01-01T01:00:00Z` | `20260101/01` |
| 999 | `2026-01-01T19:00:00Z` | `20260101/19` |

**Percentiles** (section 11.3) of the samples `5, 1, 4, 2, 3, 10, 9, 8, 7, 6`: p25 = 3, p50 = 5, p75 = 8, p95 = 10, p99 = 10, mean = 5.5.

**Positions** (section 11.5):

| N | Lookup sample positions | Last indexed position and `time` checkpoint | Recovery `c` and restart clock start |
|---|---|---|---|
| 100 | 0, 2, 4, …, 98 | 49 → `20260101/00` | 50 → `2026-01-01T02:00:00Z` |
| 250 | 0, 5, 10, …, 245 | 199 → `20260101/03` | 125 → `2026-01-01T03:00:00Z` |
| 500 | 0, 10, 20, …, 490 | 449 → `20260101/08` | 250 → `2026-01-01T06:00:00Z` |
| 1000 | 0, 20, 40, …, 980 | 949 → `20260101/18` | 500 → `2026-01-01T11:00:00Z` |

---

## 15. Repository and delivery

These requirements come from the Stage 1 guide. They do not change what the modules do, but the repository is graded together with the report.

**Repository:** exactly `https://github.com/<group_name>/stage_1`.

**Layout:**

```
stage_1/
├── README.md
├── .gitignore
├── shared/                   section 1: SPEC, stop words, benchmark IDs, queries, sample dataset
├── Query_Tarantino_Java/
├── Query_Tarantino_Python/
├── Query_Tarantino_Cpp/
└── benchmarks/
    ├── run_all.sh            runs every round of section 11.6 and the external measurements
    ├── plan.py               order of the configurations in each round (section 11.6)
    ├── analyze.py            aggregation, validity checks, tables and figures (section 11.9)
    ├── requirements.txt      Python packages of analyze.py
    ├── results/              CSV files, environment.txt and json_index_sha256.csv (section 11)
    └── report/               tables and figures generated by analyze.py
```

**Not versioned:** `data/`, `corpus_raw/`, `benchmarks/work/` and build outputs. They are listed in `.gitignore`. `benchmarks/results/` and `benchmarks/report/` **are** versioned, because the report is built from them. The sample dataset in `shared/sample_dataset/` **is** versioned, so that instructors can test the pipeline without downloading anything.

**`README.md`**, at the root, with detailed setup and execution instructions:

- Requirements and installation for each language, including MongoDB.
- How to build each module (C++ in Release for benchmarks).
- Every command of section 10, with an example.
- The configuration of section 2.
- How to run the pipeline on the sample dataset, the equivalence check (section 12) and the benchmarks (section 11).

The README is updated in the same pull request that changes any of these points.

**Git history:** it must show the progression of the work. The size of a commit does not matter, as long as its message explains everything it changes and why: what was added, changed or removed, and which sections of this document it covers. The history is never squashed or rewritten.

**Report:** a single PDF, uploaded by one member of the group, with the structure required by the guide (cover page with the repository URL, introduction, architecture, design decisions, benchmarks, conclusions). Its benchmark section is built from `benchmarks/report/` (section 11.9) and discusses both the datalake structures and the inverted-index structures across the three languages. It justifies which datalake structure is chosen for the final implementation, and the deviations from the guide listed in this document (for example, section 7.2).

---

## History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-09-21 | Initial version |
| 1.1 | 2026-09-24 | `sample_data/` renamed to `sample_dataset/` and listed in section 1. `stopwords_en.txt` 1.0 defined as the NLTK English list keeping only `a-z` entries (153 words) |
| 1.2 | 2026-09-24 | Section 8.1 step 3: the limit of 10 candidates applies only to random IDs; with `--ids` the whole file is traversed; a step with no valid candidate downloads nothing |
| 1.3 | 2026-09-28 | 3.2: politeness measured between request starts; any network error counts as a failed URL; redirects must be enabled where the client does not follow them. 4.3 and 13.1: `.tmp` leftovers deleted right after acquiring the lock; a command that cannot acquire the lock never deletes it. 4.1: rule for old copies of a book in the `time` datalake. 5.4: index on `title`. 7.1: book IDs converted to strings before sorting, with per-language notes. 9.3: `N` read from SQLite. 10: `bench` arguments. 11: benchmark methodology rewritten: experiments and configurations, bench area, measurement rules, simulated clock, exact definition of every metric, new `recovery` and `baseline` experiments, `metadata` experiment up to 50,000 rows, `run_all.sh` environment and order, validity checks, CSV format and analysis. 12: corpus folder and example command. 13.3: no forced flushes. 14.6 to 14.9: new cases. 15: repository and delivery requirements from the guide |
| 1.4 | 2026-09-29 | 1.1: selection tool, 2-second wait between requests following Project Gutenberg's robot policy, resumable order of writes. 1.2: exact query generation rules (index, bands with integer limits, slot-to-band assignment, alphabetical candidates, sampling without replacement with seed 42, query format) |
| 1.5 | 2026-09-29 | 3.2, 11.5.5 and 1.1: the `download` benchmark waits 2 seconds between requests, like the corpus selection. 9.4, 12 and 13.2: displayed scores compared with a tolerance of `1e-6 + 1e-9`; residual risk of a tie on a rounding boundary stated. 15: the size of a commit does not matter as long as its message explains every change |
