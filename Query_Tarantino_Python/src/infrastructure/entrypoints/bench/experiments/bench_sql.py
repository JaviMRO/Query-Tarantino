"""SQL statements that only the benchmark runs on the SPEC 5.4 schema (SPEC 11.5.1 step 4, 11.5.4)."""

SELECT_PATHS_BY_ID = "SELECT header_path, body_path FROM books WHERE book_id = ?"
SELECT_PATHS_BY_TITLE = "SELECT header_path, body_path FROM books WHERE title = ?"
SELECT_IDS_BY_AUTHOR = "SELECT book_id FROM books WHERE lower(author) = lower(?) ORDER BY book_id"
COUNT_ROWS = "SELECT COUNT(*) FROM books"
INSERT_ROW = """
INSERT OR REPLACE INTO books
(book_id, title, author, language, release_date, header_path, body_path, indexed_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""
