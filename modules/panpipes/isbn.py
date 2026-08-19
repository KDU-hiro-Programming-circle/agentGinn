"""ISBN -> book metadata lookup.

openBD (Japan-focused, free, keyless) is tried first, falling back to
Google Books (also keyless for basic lookups). If neither has the
book, the caller should fall back to manual entry via
/panpipes register.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from shared.logger import get_logger
from shared.utils import retry_async

logger = get_logger(__name__)

OPENBD_URL = "https://api.openbd.jp/v1/get"
GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"


@dataclass
class BookInfo:
    isbn: str
    title: str
    author: str | None
    publisher: str | None
    thumbnail_url: str | None


@retry_async(attempts=2, delay_seconds=1.0, exceptions=(httpx.HTTPError,))
async def _lookup_openbd(isbn: str) -> BookInfo | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(OPENBD_URL, params={"isbn": isbn})
    resp.raise_for_status()
    body = resp.json()
    if not body or body[0] is None:
        return None
    summary = body[0].get("summary") or {}
    title = summary.get("title")
    if not title:
        return None
    return BookInfo(
        isbn=isbn,
        title=title,
        author=summary.get("author"),
        publisher=summary.get("publisher"),
        thumbnail_url=summary.get("cover") or None,
    )


@retry_async(attempts=2, delay_seconds=1.0, exceptions=(httpx.HTTPError,))
async def _lookup_google_books(isbn: str) -> BookInfo | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(GOOGLE_BOOKS_URL, params={"q": f"isbn:{isbn}"})
    resp.raise_for_status()
    body = resp.json()
    items = body.get("items") or []
    if not items:
        return None
    info = items[0]["volumeInfo"]
    title = info.get("title")
    if not title:
        return None
    return BookInfo(
        isbn=isbn,
        title=title,
        author=", ".join(info.get("authors", [])) or None,
        publisher=info.get("publisher"),
        thumbnail_url=(info.get("imageLinks") or {}).get("thumbnail"),
    )


async def lookup(isbn: str) -> BookInfo | None:
    try:
        result = await _lookup_openbd(isbn)
        if result is not None:
            return result
    except httpx.HTTPError:
        logger.exception("openBD lookup failed for isbn=%s", isbn)

    try:
        return await _lookup_google_books(isbn)
    except httpx.HTTPError:
        logger.exception("Google Books lookup failed for isbn=%s", isbn)
        return None
