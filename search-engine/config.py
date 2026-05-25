"""Configuration for the private search engine."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "index.db"
SEEDS_FILE = ROOT / "seeds.txt"

# Crawler identity (required by many sites' robots.txt)
USER_AGENT = "PrivateSearchBot/1.0 (+https://github.com/local/private-search; contact=local)"

# Politeness
REQUEST_TIMEOUT_SEC = 15
DELAY_BETWEEN_REQUESTS_SEC = 1.0
MAX_PAGES_PER_DOMAIN = 500
MAX_TOTAL_PAGES = 10_000
MAX_BODY_CHARS = 100_000
MAX_LINKS_PER_PAGE = 200

# Only crawl http(s); skip common non-page extensions
SKIP_EXTENSIONS = {
    ".pdf", ".zip", ".gz", ".tar", ".rar", ".7z",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".mp3", ".mp4", ".avi", ".mov", ".wmv",
    ".css", ".js", ".json", ".xml", ".rss",
    ".exe", ".dmg", ".deb", ".rpm",
}

# API
API_HOST = "127.0.0.1"
API_PORT = 8787
