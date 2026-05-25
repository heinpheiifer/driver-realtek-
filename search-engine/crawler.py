#!/usr/bin/env python3
"""Web crawler for the private search engine."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

from config import (
    DELAY_BETWEEN_REQUESTS_SEC,
    MAX_PAGES_PER_DOMAIN,
    MAX_TOTAL_PAGES,
    REQUEST_TIMEOUT_SEC,
    SEEDS_FILE,
    USER_AGENT,
)
from db import (
    dequeue_url,
    domain_page_count,
    enqueue_url,
    init_db,
    page_count,
    queue_count,
    stats,
    upsert_page,
    url_already_indexed,
)
from parser import parse_html
from robots import can_fetch


def load_seeds() -> list[str]:
    if not SEEDS_FILE.exists():
        return []
    lines = SEEDS_FILE.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def seed_queue(seeds: list[str]) -> int:
    added = 0
    for url in seeds:
        if enqueue_url(url, depth=0):
            added += 1
    return added


def crawl(max_pages: int | None = None, verbose: bool = True) -> None:
    init_db()
    seeds = load_seeds()
    if seeds:
        added = seed_queue(seeds)
        if verbose and added:
            print(f"Seeded {added} URL(s) from {SEEDS_FILE.name}")

    limit = max_pages or MAX_TOTAL_PAGES
    fetched = 0
    last_domain = ""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    with httpx.Client(
        headers=headers,
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT_SEC,
    ) as client:
        while fetched < limit:
            item = dequeue_url()
            if not item:
                if verbose:
                    print("Queue empty — crawl finished.")
                break

            url, domain, depth = item

            if url_already_indexed(url):
                continue

            if domain_page_count(domain) >= MAX_PAGES_PER_DOMAIN:
                if verbose:
                    print(f"Skip (domain cap): {url}")
                continue

            if not can_fetch(url, client):
                if verbose:
                    print(f"Blocked by robots.txt: {url}")
                continue

            # Politeness delay per domain
            if domain != last_domain and last_domain:
                time.sleep(DELAY_BETWEEN_REQUESTS_SEC)
            last_domain = domain

            try:
                resp = client.get(url)
            except httpx.HTTPError as exc:
                if verbose:
                    print(f"Fetch error: {url} — {exc}")
                continue

            content_type = resp.headers.get("content-type", "")
            if resp.status_code != 200 or "text/html" not in content_type:
                if verbose:
                    print(f"Skip non-HTML ({resp.status_code}): {url}")
                continue

            html = resp.text
            title, body, links = parse_html(html, str(resp.url))

            if not body.strip() and not title.strip():
                if verbose:
                    print(f"Skip empty page: {url}")
                continue

            upsert_page(str(resp.url), title, body)
            fetched += 1

            for link in links:
                enqueue_url(link, depth=depth + 1)

            if verbose:
                s = stats()
                print(
                    f"[{fetched}/{limit}] {title[:60] or url} "
                    f"(indexed={s['pages']}, queue={s['queued']})"
                )

            time.sleep(DELAY_BETWEEN_REQUESTS_SEC)

    if verbose:
        s = stats()
        print(f"\nDone. Indexed {s['pages']} pages across {s['domains']} domains.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl the web for your private index.")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help=f"Maximum pages to fetch this run (default {MAX_TOTAL_PAGES})",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Only load seeds into the queue, do not crawl.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print index stats and exit.",
    )
    args = parser.parse_args()

    init_db()

    if args.stats:
        s = stats()
        print(f"Pages: {s['pages']}, queued: {s['queued']}, domains: {s['domains']}")
        return

    if args.seed_only:
        added = seed_queue(load_seeds())
        print(f"Added {added} URL(s). Queue size: {queue_count()}")
        return

    crawl(max_pages=args.max_pages)


if __name__ == "__main__":
    main()
