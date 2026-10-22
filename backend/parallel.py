"""Run independent database reads side by side. Each read is a network round trip to Supabase, so reading N things one after another
costs N trips of waiting where one trip's worth is enough."""
from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable


def together(*jobs: Callable[[], Any]) -> list[Any]:
    """Results in the order of ``jobs``. The caller's context (request time zone) travels with each job; an error in any job is raised
    here, like in a plain sequential call."""
    if len(jobs) == 1:
        return [jobs[0]()]
    with ThreadPoolExecutor(max_workers=len(jobs), thread_name_prefix="read") as pool:
        futures = [pool.submit(contextvars.copy_context().run, job) for job in jobs]
        return [f.result() for f in futures]
