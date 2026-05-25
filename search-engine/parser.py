"""HTML parsing and URL normalization."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from config import MAX_BODY_CHARS, MAX_LINKS_PER_PAGE, SKIP_EXTENSIONS

_STRIP_TAGS = {"script", "style", "noscript", "svg", "iframe"}


def normalize_url(base: str, href: str) -> str | None:
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    joined = urljoin(base, href.strip())
    parsed = urlparse(joined)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None

    path_lower = (parsed.path or "").lower()
    for ext in SKIP_EXTENSIONS:
        if path_lower.endswith(ext):
            return None

    clean, _ = urldefrag(joined)
    # Drop common tracking params
    return clean.rstrip("/") or clean


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return unescape(soup.title.string.strip())[:500]
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return unescape(og["content"].strip())[:500]
    h1 = soup.find("h1")
    if h1:
        return unescape(h1.get_text(strip=True))[:500]
    return ""


def extract_body_text(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return unescape(text)[:MAX_BODY_CHARS]


def extract_links(soup: BeautifulSoup, page_url: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        norm = normalize_url(page_url, a["href"])
        if norm and norm not in seen:
            seen.add(norm)
            links.append(norm)
        if len(links) >= MAX_LINKS_PER_PAGE:
            break
    return links


def parse_html(html: str, page_url: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(html, "lxml")
    title = extract_title(soup)
    body = extract_body_text(soup)
    links = extract_links(soup, page_url)
    return title, body, links
