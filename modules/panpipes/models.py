"""Data access for panpipes_* tables. All Panpipes SQL lives here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiosqlite

from shared.database import database
from shared.utils import utcnow_iso


@dataclass
class Book:
    id: int
    isbn: str | None
    title: str
    author: str | None
    publisher: str | None
    thumbnail_url: str | None
    registered_by: str
    created_at: str


@dataclass
class Borrow:
    id: int
    book_id: int
    borrower_id: str
    borrowed_at: str
    due_at: str
    returned_at: str | None
    overdue_notified: bool


def _book_from_row(row: aiosqlite.Row) -> Book:
    return Book(
        id=row["id"],
        isbn=row["isbn"],
        title=row["title"],
        author=row["author"],
        publisher=row["publisher"],
        thumbnail_url=row["thumbnail_url"],
        registered_by=row["registered_by"],
        created_at=row["created_at"],
    )


def _borrow_from_row(row: aiosqlite.Row) -> Borrow:
    return Borrow(
        id=row["id"],
        book_id=row["book_id"],
        borrower_id=row["borrower_id"],
        borrowed_at=row["borrowed_at"],
        due_at=row["due_at"],
        returned_at=row["returned_at"],
        overdue_notified=bool(row["overdue_notified"]),
    )


async def _add_history(conn: aiosqlite.Connection, book_id: int, event_type: str, actor_id: str) -> None:
    await conn.execute(
        "INSERT INTO panpipes_history (book_id, event_type, actor_id, created_at) VALUES (?, ?, ?, ?)",
        (book_id, event_type, actor_id, utcnow_iso()),
    )


# ---- Books ------------------------------------------------------------


async def get_book_by_isbn(isbn: str) -> Book | None:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM panpipes_books WHERE isbn = ?", (isbn,))
        row = await cur.fetchone()
        return _book_from_row(row) if row else None


async def get_book(book_id: int) -> Book | None:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM panpipes_books WHERE id = ?", (book_id,))
        row = await cur.fetchone()
        return _book_from_row(row) if row else None


async def search_books(query: str, limit: int = 10) -> list[Book]:
    like = f"%{query}%"
    async with database.connect() as conn:
        cur = await conn.execute(
            """
            SELECT * FROM panpipes_books
            WHERE title LIKE ? OR author LIKE ? OR isbn = ?
            ORDER BY title LIMIT ?
            """,
            (like, like, query, limit),
        )
        rows = await cur.fetchall()
        return [_book_from_row(row) for row in rows]


async def create_book(
    *,
    isbn: str | None,
    title: str,
    author: str | None,
    publisher: str | None,
    thumbnail_url: str | None,
    registered_by: str,
) -> Book:
    async with database.connect() as conn:
        cur = await conn.execute(
            """
            INSERT INTO panpipes_books (isbn, title, author, publisher, thumbnail_url, registered_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (isbn, title, author, publisher, thumbnail_url, registered_by, utcnow_iso()),
        )
        book_id = cur.lastrowid
        await _add_history(conn, book_id, "register", registered_by)
        cur = await conn.execute("SELECT * FROM panpipes_books WHERE id = ?", (book_id,))
        row = await cur.fetchone()
    assert row is not None
    return _book_from_row(row)


# ---- Borrowing ----------------------------------------------------------


async def get_open_borrow(book_id: int) -> Borrow | None:
    async with database.connect() as conn:
        cur = await conn.execute(
            "SELECT * FROM panpipes_borrow WHERE book_id = ? AND returned_at IS NULL", (book_id,)
        )
        row = await cur.fetchone()
        return _borrow_from_row(row) if row else None


async def create_borrow(book_id: int, borrower_id: str, due_at: str) -> Borrow:
    async with database.connect() as conn:
        cur = await conn.execute(
            """
            INSERT INTO panpipes_borrow (book_id, borrower_id, borrowed_at, due_at, returned_at, overdue_notified)
            VALUES (?, ?, ?, ?, NULL, 0)
            """,
            (book_id, borrower_id, utcnow_iso(), due_at),
        )
        borrow_id = cur.lastrowid
        await _add_history(conn, book_id, "borrow", borrower_id)
        cur = await conn.execute("SELECT * FROM panpipes_borrow WHERE id = ?", (borrow_id,))
        row = await cur.fetchone()
    assert row is not None
    return _borrow_from_row(row)


async def return_borrow(borrow: Borrow, actor_id: str) -> None:
    async with database.connect() as conn:
        await conn.execute("UPDATE panpipes_borrow SET returned_at = ? WHERE id = ?", (utcnow_iso(), borrow.id))
        await _add_history(conn, borrow.book_id, "return", actor_id)


async def book_history(book_id: int, limit: int = 20) -> list[dict[str, Any]]:
    async with database.connect() as conn:
        cur = await conn.execute(
            "SELECT * FROM panpipes_history WHERE book_id = ? ORDER BY id DESC LIMIT ?", (book_id, limit)
        )
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def list_overdue(today_iso: str) -> list[Borrow]:
    """All currently-overdue open borrows, regardless of notification state.
    today_iso is a YYYY-MM-DD date (not a timestamp) -- due dates are
    compared by calendar day only, so a book isn't overdue until the day
    after its due date."""
    async with database.connect() as conn:
        cur = await conn.execute(
            "SELECT * FROM panpipes_borrow WHERE returned_at IS NULL AND due_at < ?",
            (today_iso,),
        )
        rows = await cur.fetchall()
        return [_borrow_from_row(row) for row in rows]


async def unnotified_overdue_borrows(today_iso: str) -> list[Borrow]:
    """Overdue open borrows not yet mentioned by the scheduler's overdue
    check. today_iso is a YYYY-MM-DD date, compared by calendar day."""
    async with database.connect() as conn:
        cur = await conn.execute(
            "SELECT * FROM panpipes_borrow WHERE returned_at IS NULL AND due_at < ? AND overdue_notified = 0",
            (today_iso,),
        )
        rows = await cur.fetchall()
        return [_borrow_from_row(row) for row in rows]


async def mark_overdue_notified(borrow_id: int) -> None:
    async with database.connect() as conn:
        await conn.execute("UPDATE panpipes_borrow SET overdue_notified = 1 WHERE id = ?", (borrow_id,))
