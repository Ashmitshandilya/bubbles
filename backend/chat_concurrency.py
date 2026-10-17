"""Two small thread pools for the chat path (the database and the embedding service answer in about 80 ms each, so independent
reads are started together instead of one after another).

Why two: a stage task may start leaf reads and wait for them; if both kinds shared one pool, enough simultaneous chats could fill it
with waiting stage tasks and starve the reads they wait for. Stage tasks only ever submit to the leaf pool, and leaf tasks never
submit anything, so no cycle exists.

Every task runs in a copy of the caller's context, so the request id and note used by ops_telemetry, the time-zone offset and the AI
reply budget keep working inside it.
"""
from __future__ import annotations

import contextvars
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

_STAGE = ThreadPoolExecutor(max_workers=12, thread_name_prefix="chat-stage")
_LEAF = ThreadPoolExecutor(max_workers=32, thread_name_prefix="chat-io")


def submit(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
    """Runs ``fn`` on the stage pool (it may call submit_io). Returns a Future."""
    return _STAGE.submit(contextvars.copy_context().run, fn, *args, **kwargs)


def submit_io(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
    """Runs ``fn`` on the leaf pool (``fn`` must not submit work itself). Returns a Future."""
    return _LEAF.submit(contextvars.copy_context().run, fn, *args, **kwargs)


def settled(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, BaseException | None]:
    """``(value, None)`` or ``(None, error)``: lets several reads run side by side and each one fail on its own."""
    try:
        return fn(*args, **kwargs), None
    except Exception as error:  # noqa: BLE001
        return None, error
