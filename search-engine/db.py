"""SQLite storage and FTS5 full-text search."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urlparse

from config import DB_PATH, DATA_DIR


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                domain TEXT NOT NULL DEFAULT '',
                fetched_at REAL NOT NULL DEFAULT 0
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
                title,
                body,
                url,
                content='pages',
                content_rowid='id'
            );

            CREATE TABLE IF NOT EXISTS crawl_queue (
                url TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                depth INTEGER NOT NULL DEFAULT 0,
                added_at REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS crawl_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pages_domain ON pages(domain);
            CREATE INDEX IF NOT EXISTS idx_queue_domain ON crawl_queue(domain);

            -- FTS sync triggers
            CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
                INSERT INTO pages_fts(rowid, title, body, url)
                VALUES (new.id, new.title, new.body, new.url);
            END;

            CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
                INSERT INTO pages_fts(pages_fts, rowid, title, body, url)
                VALUES ('delete', old.id, old.title, old.body, old.url);
            END;

            CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
                INSERT INTO pages_fts(pages_fts, rowid, title, body, url)
                VALUES ('delete', old.id, old.title, old.body, old.url);
                INSERT INTO pages_fts(rowid, title, body, url)
                VALUES (new.id, new.title, new.body, new.url);
            END;
            """
        )


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    score: float


def domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc or "").lower()


def upsert_page(url: str, title: str, body: str) -> None:
    domain = domain_from_url(url)
    now = time.time()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO pages (url, title, body, domain, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                body = excluded.body,
                fetched_at = excluded.fetched_at
            """,
            (url, title, body, domain, now),
        )


def enqueue_url(url: str, depth: int = 0) -> bool:
    domain = domain_from_url(url)
    if not domain:
        return False
    with connect() as conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO crawl_queue (url, domain, depth, added_at) VALUES (?, ?, ?, ?)",
                (url, domain, depth, time.time()),
            )
            return conn.total_changes > 0
        except sqlite3.Error:
            return False


def dequeue_url() -> tuple[str, str, int] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT url, domain, depth FROM crawl_queue ORDER BY added_at LIMIT 1"
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM crawl_queue WHERE url = ?", (row["url"],))
        return row["url"], row["domain"], row["depth"]


def page_count() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM pages").fetchone()
        return int(row["c"]) if row else 0


def queue_count() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM crawl_queue").fetchone()
        return int(row["c"]) if row else 0


def domain_page_count(domain: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM pages WHERE domain = ?", (domain,)
        ).fetchone()
        return int(row["c"]) if row else 0


def url_already_indexed(url: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM pages WHERE url = ? LIMIT 1", (url,)).fetchone()
        return row is not None


def search(query: str, limit: int = 20) -> list[SearchResult]:
    if not query.strip():
        return []

    # FTS5 prefix matching on terms
    terms = [t for t in query.split() if t.strip()]
    if not terms:
        return []

    fts_query = " ".join(f'"{t}"*' if " " not in t else t for t in terms)

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                p.url,
                p.title,
                snippet(pages_fts, 1, '<b>', '</b>', '…', 32) AS snippet,
                bm25(pages_fts) AS score
            FROM pages_fts
            JOIN pages p ON p.id = pages_fts.rowid
            WHERE pages_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()

    results: list[SearchResult] = []
    for row in rows:
        snippet = row["snippet"] or ""
        results.append(
            SearchResult(
                url=row["url"],
                title=row["title"] or row["url"],
                snippet=snippet,
                score=float(row["score"] or 0),
            )
        )
    return results


def stats() -> dict:
    with connect() as conn:
        pages = conn.execute("SELECT COUNT(*) AS c FROM pages").fetchone()["c"]
        queued = conn.execute("SELECT COUNT(*) AS c FROM crawl_queue").fetchone()["c"]
        domains = conn.execute(
            "SELECT COUNT(DISTINCT domain) AS c FROM pages"
        ).fetchone()["c"]
    return {"pages": pages, "queued": queued, "domains": domains}
