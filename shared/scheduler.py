"""Single APScheduler instance shared by every module.

Jobs are namespaced ``{module}:{job_id}`` so a Module Manager disable
can cleanly remove exactly that module's jobs via unregister_module().
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger

from shared.logger import get_logger

logger = get_logger(__name__)

_scheduler = AsyncIOScheduler()
_jobs_by_module: dict[str, set[str]] = {}


def configure(timezone: str | None) -> None:
    """Set the scheduler's timezone. Must be called before start()."""
    global _scheduler
    if timezone:
        _scheduler = AsyncIOScheduler(timezone=timezone)


def start() -> None:
    if not _scheduler.running:
        _scheduler.start()
        logger.info("scheduler started (timezone=%s)", _scheduler.timezone)


def shutdown(wait: bool = True) -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=wait)
        logger.info("scheduler stopped")


def register_job(
    module: str,
    job_id: str,
    func: Callable[..., Awaitable[None]],
    trigger: str | BaseTrigger,
    **trigger_args: Any,
) -> None:
    full_id = f"{module}:{job_id}"
    _scheduler.add_job(func, trigger, id=full_id, replace_existing=True, **trigger_args)
    _jobs_by_module.setdefault(module, set()).add(full_id)
    logger.info("scheduler: registered job %s", full_id)


def unregister_module(module: str) -> None:
    for job_id in _jobs_by_module.pop(module, set()):
        if _scheduler.get_job(job_id) is not None:
            _scheduler.remove_job(job_id)
            logger.info("scheduler: unregistered job %s", job_id)
