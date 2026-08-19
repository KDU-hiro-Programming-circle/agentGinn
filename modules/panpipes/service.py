"""Panpipes service layer: image->barcode->ISBN identification stays
read-only until a caller explicitly registers/borrows/returns, so the
#library channel flow can show a book's info before writing anything.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.config import config as config_store
from shared.logger import get_logger

from . import barcode
from . import isbn as isbn_lookup
from . import models

logger = get_logger(__name__)


class PanpipesError(Exception):
    """User-facing error (already borrowed, not registered, not found, ...)."""


async def identify_from_image(image_bytes: bytes) -> tuple[str, isbn_lookup.BookInfo | None]:
    """Image -> barcode -> ISBN -> metadata lookup. No DB writes.

    Raises PanpipesError if no ISBN barcode could be decoded at all.
    Returns (isbn, None) if the ISBN was read but no book info was found
    anywhere -- the caller should offer /panpipes register instead.
    """
    isbns = barcode.extract_isbns(image_bytes)
    if not isbns:
        raise PanpipesError(
            "画像からISBNバーコードを読み取れませんでした。`/panpipes register` で手動登録してください。"
        )
    isbn = isbns[0]
    info = await isbn_lookup.lookup(isbn)
    return isbn, info


async def register_from_lookup(isbn: str, info: isbn_lookup.BookInfo, registered_by: str) -> models.Book:
    existing = await models.get_book_by_isbn(isbn)
    if existing is not None:
        return existing
    return await models.create_book(
        isbn=info.isbn,
        title=info.title,
        author=info.author,
        publisher=info.publisher,
        thumbnail_url=info.thumbnail_url,
        registered_by=registered_by,
    )


async def register_manual(
    *, isbn: str | None, title: str, author: str | None, registered_by: str
) -> models.Book:
    if isbn:
        existing = await models.get_book_by_isbn(isbn)
        if existing is not None:
            return existing
    return await models.create_book(
        isbn=isbn,
        title=title,
        author=author,
        publisher=None,
        thumbnail_url=None,
        registered_by=registered_by,
    )


async def borrow_book(book: models.Book, borrower_id: str) -> models.Borrow:
    existing = await models.get_open_borrow(book.id)
    if existing is not None:
        raise PanpipesError(f"『{book.title}』は既に貸出中です。")

    panpipes_cfg = config_store.load("panpipes")
    borrow_days = panpipes_cfg.get("borrow_days", 14)
    due_at = (datetime.now(timezone.utc) + timedelta(days=borrow_days)).isoformat()
    return await models.create_borrow(book.id, borrower_id, due_at)


async def borrow_by_isbn(isbn: str, borrower_id: str) -> models.Borrow:
    book = await models.get_book_by_isbn(isbn)
    if book is None:
        raise PanpipesError("この本はまだ登録されていません。先に「新規登録」を行ってください。")
    return await borrow_book(book, borrower_id)


async def return_book(book: models.Book, actor_id: str) -> models.Borrow:
    borrow = await models.get_open_borrow(book.id)
    if borrow is None:
        raise PanpipesError(f"『{book.title}』は貸出中ではありません。")
    await models.return_borrow(borrow, actor_id)
    return borrow


async def return_by_isbn(isbn: str, actor_id: str) -> models.Borrow:
    book = await models.get_book_by_isbn(isbn)
    if book is None:
        raise PanpipesError("この本はまだ登録されていません。")
    return await return_book(book, actor_id)


async def check_overdue() -> list[tuple[models.Borrow, models.Book]]:
    """Called daily by the scheduler. Returns newly-overdue borrows
    (not yet mentioned) paired with their book, and marks them notified."""
    now_iso = datetime.now(timezone.utc).isoformat()
    pending = await models.unnotified_overdue_borrows(now_iso)
    results: list[tuple[models.Borrow, models.Book]] = []
    for borrow in pending:
        book = await models.get_book(borrow.book_id)
        if book is None:
            continue
        results.append((borrow, book))
        await models.mark_overdue_notified(borrow.id)
    return results
