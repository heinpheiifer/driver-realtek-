#!/usr/bin/env python3
"""FastAPI search server — fully local, no third-party search APIs."""

from __future__ import annotations

from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import API_HOST, API_PORT, ROOT
from db import init_db, search, stats

WEB_DIR = ROOT / "web"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Private Search",
    description="Self-hosted web search. No Google. No Microsoft.",
    version="1.0.0",
    lifespan=lifespan,
)


class SearchHit(BaseModel):
    url: str
    title: str
    snippet: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
    total: int


class StatsResponse(BaseModel):
    pages: int
    queued: int
    domains: int

@app.get("/", response_class=HTMLResponse)
def home() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/search", response_model=SearchResponse)
def api_search(q: str = Query("", min_length=0), limit: int = Query(20, ge=1, le=100)) -> SearchResponse:
    hits = search(q, limit=limit)
    return SearchResponse(
        query=q,
        results=[
            SearchHit(url=h.url, title=h.title, snippet=h.snippet, score=h.score)
            for h in hits
        ],
        total=len(hits),
    )


@app.get("/api/stats", response_model=StatsResponse)
def api_stats() -> StatsResponse:
    s = stats()
    return StatsResponse(**s)


# Static assets
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=False)


if __name__ == "__main__":
    main()
