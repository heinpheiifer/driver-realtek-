# Private Search Engine

A **self-hosted, private web search engine** that crawls the public web and indexes pages on your own machine. No Google, no Microsoft, no third-party search APIs — your queries never leave your computer.

## What you get

| Piece | Technology | Purpose |
|-------|------------|---------|
| **Crawler** | Python + httpx | Discovers pages by following links from seed URLs |
| **Index** | SQLite FTS5 | Full-text search stored locally in `data/index.db` |
| **API** | FastAPI | Serves search results to the UI |
| **UI** | Static HTML/CSS/JS | Simple search page at `http://127.0.0.1:8787` |

## Privacy

- All crawling, indexing, and searching runs **on your machine**
- No telemetry, ads, or external search backends
- Uses only open-source Python libraries (httpx, BeautifulSoup, FastAPI, SQLite)
- Respects `robots.txt` and rate-limits requests per domain

## Quick start

```bash
cd search-engine
chmod +x start.sh crawl.sh

# 1. Crawl the web (starts from seeds.txt, follows links)
./crawl.sh --max-pages 50

# 2. Start the search UI
./start.sh
```

Open **http://127.0.0.1:8787** and search your index.

## Configuration

Edit `seeds.txt` to add starting URLs (one per line). The crawler discovers new sites by following links on each page.

Adjust limits in `config.py`:

- `MAX_TOTAL_PAGES` — cap on total indexed pages
- `MAX_PAGES_PER_DOMAIN` — per-site limit
- `DELAY_BETWEEN_REQUESTS_SEC` — politeness delay

## Manual usage

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Initialize DB and seed queue
python3 crawler.py --seed-only

# Crawl (example: 100 pages)
python3 crawler.py --max-pages 100

# Check stats
python3 crawler.py --stats

# Run search server
python3 api.py
```

Search API: `GET /api/search?q=your+query`

## How discovery works

1. You provide **seed URLs** in `seeds.txt`
2. The crawler fetches each page, extracts text and outbound links
3. New links are queued and fetched later (breadth-first)
4. Indexed content is searchable immediately via FTS5

To cover more of the web, run the crawler regularly (e.g. via cron) or increase `MAX_TOTAL_PAGES`.

## Limitations (honest expectations)

This is a **personal / small-scale** search engine, not a Google replacement:

- Coverage depends on what you crawl — start with good seeds
- Ranking is BM25 via SQLite FTS5 (good, but not Google-level)
- JavaScript-heavy sites may not index well (static HTML only)
- You must respect site policies and applicable law

For a larger index, consider running the crawler on a home server with more disk space and scheduling long crawl sessions.

## Stack (no Google / Microsoft)

- Python 3.10+
- httpx, BeautifulSoup, lxml
- SQLite FTS5 (built into Python)
- FastAPI + uvicorn

No Bing API, no Google Custom Search, no Azure, no Google Cloud.
