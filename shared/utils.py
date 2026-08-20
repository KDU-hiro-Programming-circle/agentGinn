"""Small helpers shared across modules."""

from __future__ import annotations

import asyncio
import functools
import re
from datetime import datetime, timezone
from typing import Awaitable, Callable, Iterable, TypeVar

T = TypeVar("T")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def next_numbered_key(existing_names: Iterable[str], prefix: str) -> str:
    """Return "{prefix}{n}" where n is one greater than the highest existing suffix."""
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    numbers = [int(m.group(1)) for name in existing_names if (m := pattern.match(name))]
    return f"{prefix}{max(numbers, default=0) + 1}"


def format_datetime(iso_str: str, fmt: str = "%Y-%m-%d %H:%M") -> str:
    return datetime.fromisoformat(iso_str).strftime(fmt)


def retry_async(
    attempts: int = 3,
    delay_seconds: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Retry an async function with linear backoff on the given exceptions."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < attempts:
                        await asyncio.sleep(delay_seconds * attempt)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
