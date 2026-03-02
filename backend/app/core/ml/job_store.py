"""
In-memory job store for long-running ML tasks (signal-backtest, walk-forward).
Jobs run in background threads and results are cached so the user can
navigate away and retrieve them later.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class _Job:
    __slots__ = ("id", "job_type", "status", "result", "error", "created_at", "finished_at", "params")

    def __init__(self, job_id: str, job_type: str, params: Dict[str, Any] | None = None):
        self.id = job_id
        self.job_type = job_type
        self.status = JobStatus.PENDING
        self.result: Any = None
        self.error: str | None = None
        self.created_at = datetime.now().isoformat()
        self.finished_at: str | None = None
        self.params = params or {}

    def to_dict(self, include_result: bool = True) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "job_id": self.id,
            "job_type": self.job_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "params": self.params,
        }
        if include_result:
            d["result"] = self.result
            d["error"] = self.error
        return d


# ---- Singleton store -------------------------------------------------------

_lock = threading.Lock()
_jobs: Dict[str, _Job] = {}

# Only keep the latest N completed jobs to avoid unbounded memory growth.
_MAX_COMPLETED = 50


def _cleanup_old() -> None:
    """Drop oldest completed jobs beyond _MAX_COMPLETED."""
    completed = [j for j in _jobs.values() if j.status == JobStatus.COMPLETED]
    if len(completed) <= _MAX_COMPLETED:
        return
    completed.sort(key=lambda j: j.finished_at or "")
    for j in completed[: len(completed) - _MAX_COMPLETED]:
        _jobs.pop(j.id, None)


def submit_job(
    job_type: str,
    fn: Callable[..., Any],
    params: Dict[str, Any] | None = None,
    **fn_kwargs: Any,
) -> str:
    """
    Create a job entry and run *fn* in a daemon thread.
    Returns the job_id immediately.
    """
    job_id = uuid.uuid4().hex[:12]
    job = _Job(job_id, job_type, params)

    with _lock:
        _jobs[job_id] = job
        _cleanup_old()

    def _worker() -> None:
        job.status = JobStatus.RUNNING
        try:
            result = fn(**fn_kwargs)
            job.result = result
            job.status = JobStatus.COMPLETED
        except Exception as exc:
            logger.exception(f"Job {job_id} ({job_type}) failed")
            job.error = str(exc)
            job.status = JobStatus.FAILED
        finally:
            job.finished_at = datetime.now().isoformat()

    t = threading.Thread(target=_worker, daemon=True, name=f"ml-job-{job_id}")
    t.start()
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    job = _jobs.get(job_id)
    if job is None:
        return None
    return job.to_dict()


def get_latest_by_type(job_type: str) -> Optional[Dict[str, Any]]:
    """Return the most-recently finished (completed or failed) job of a given type."""
    candidates = [
        j for j in _jobs.values()
        if j.job_type == job_type and j.status in (JobStatus.COMPLETED, JobStatus.FAILED)
    ]
    if not candidates:
        # Check for running jobs
        running = [j for j in _jobs.values() if j.job_type == job_type and j.status == JobStatus.RUNNING]
        if running:
            return running[-1].to_dict(include_result=False)
        return None
    candidates.sort(key=lambda j: j.finished_at or "")
    return candidates[-1].to_dict()


def get_running_by_type(job_type: str) -> Optional[Dict[str, Any]]:
    """Return the currently running job of a given type, if any."""
    for j in _jobs.values():
        if j.job_type == job_type and j.status in (JobStatus.PENDING, JobStatus.RUNNING):
            return j.to_dict(include_result=False)
    return None
