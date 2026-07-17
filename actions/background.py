# -*- coding: utf-8 -*-
"""Background jobs for JARVIS.

The problem: agent_mode/dev_agent/code_helper can run for minutes. The Live
turn awaits the tool, so JARVIS goes deaf until it finishes — you can't talk to
him, and he can't tell you anything.

The fix: run those in a daemon thread and return IMMEDIATELY with a job id.
JARVIS says "started, I'll tell you when it's done" and carries on listening.
When the job finishes it logs to the HUD, and speaks only if you're idle —
never on top of you.

Tool actions: list | status | result | cancel | wait
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

try:
    from core.focus import user_is_busy
except Exception:                      # focus helper optional
    def user_is_busy(*_a, **_k) -> bool:
        return False

_LOCK = threading.Lock()
_JOBS: Dict[str, "Job"] = {}

# speak a completion only if the user has been idle this long
_QUIET_IDLE_SECONDS = 6.0
# how long a finished job's announcement keeps trying before giving up
_ANNOUNCE_TIMEOUT = 300.0


@dataclass
class Job:
    id: str
    name: str
    status: str = "running"          # running | done | failed | cancelled
    result: Any = None
    error: Optional[str] = None
    started: float = field(default_factory=time.time)
    finished: Optional[float] = None
    announced: bool = False
    _cancel: threading.Event = field(default_factory=threading.Event)

    @property
    def elapsed(self) -> float:
        return (self.finished or time.time()) - self.started

    def brief(self) -> str:
        bits = f"[{self.id}] {self.name} — {self.status}, {self.elapsed:.0f}s"
        if self.error:
            bits += f" ({self.error[:80]})"
        return bits


def _short_id() -> str:
    return uuid.uuid4().hex[:4]


def start_job(name: str, fn: Callable[[], Any], player=None, speak=None) -> Job:
    """Run fn() on a daemon thread. Returns immediately with the Job."""
    job = Job(id=_short_id(), name=name)
    with _LOCK:
        _JOBS[job.id] = job

    def _runner():
        try:
            job.result = fn()
            job.status = "cancelled" if job._cancel.is_set() else "done"
        except Exception as e:
            job.status = "failed"
            job.error = f"{type(e).__name__}: {e}"
            job.result = traceback.format_exc(limit=3)
        finally:
            job.finished = time.time()
            _announce(job, player, speak)

    threading.Thread(target=_runner, name=f"jarvis-job-{job.id}", daemon=True).start()
    if player is not None:
        try:
            player.write_log(f"BG: started [{job.id}] {name}")
        except Exception:
            pass
    return job


def _announce(job: Job, player, speak) -> None:
    """Report a finished job without talking over the user."""
    # HUD log is silent — always safe, do it straight away.
    if player is not None:
        try:
            player.write_log(f"BG: {job.brief()}")
        except Exception:
            pass

    if speak is None:
        job.announced = True
        return

    # Wait for a gap in the user's typing before saying anything out loud.
    deadline = time.time() + _ANNOUNCE_TIMEOUT
    while time.time() < deadline:
        if not user_is_busy(_QUIET_IDLE_SECONDS):
            break
        time.sleep(2.0)

    verb = {
        "done": "finished",
        "failed": "failed",
        "cancelled": "was cancelled",
    }.get(job.status, job.status)
    try:
        speak(f"Background task {job.name} {verb}.")
    except Exception:
        pass
    job.announced = True


def get_job(job_id: str) -> Optional[Job]:
    with _LOCK:
        return _JOBS.get(job_id)


def all_jobs() -> Dict[str, Job]:
    with _LOCK:
        return dict(_JOBS)


def cancel_job(job_id: str) -> bool:
    """Cooperative cancel — sets a flag the job may check."""
    job = get_job(job_id)
    if not job or job.status != "running":
        return False
    job._cancel.set()
    return True


def is_cancelled(job_id: str) -> bool:
    job = get_job(job_id)
    return bool(job and job._cancel.is_set())


def background(parameters: dict | None = None, response=None, player=None,
               session_memory=None, speak=None) -> str:
    """Tool entry: inspect and manage background work."""
    p = parameters or {}
    action = (p.get("action") or "list").strip().lower()
    job_id = (p.get("job_id") or "").strip()

    if action == "list":
        jobs = all_jobs()
        if not jobs:
            return "No background tasks."
        running = [j for j in jobs.values() if j.status == "running"]
        recent = sorted(jobs.values(), key=lambda j: j.started, reverse=True)[:8]
        lines = [f"{len(running)} running, {len(jobs)} total."]
        lines += [f"  {j.brief()}" for j in recent]
        return "\n".join(lines)

    if action in ("status", "result"):
        if not job_id:
            running = [j for j in all_jobs().values() if j.status == "running"]
            if len(running) == 1:
                job = running[0]
            else:
                return "Which job? Give a job_id — use action='list' to see them."
        else:
            job = get_job(job_id)
        if not job:
            return f"No such job: {job_id}"
        if action == "status":
            return job.brief()
        if job.status == "running":
            return f"[{job.id}] {job.name} is still running ({job.elapsed:.0f}s)."
        return f"[{job.id}] {job.name} — {job.status}.\n{job.result}"

    if action == "cancel":
        if not job_id:
            return "Give a job_id to cancel."
        return (f"Cancel requested for {job_id}."
                if cancel_job(job_id) else
                f"Could not cancel {job_id} (unknown or already finished).")

    if action == "wait":
        job = get_job(job_id) if job_id else None
        if not job:
            return f"No such job: {job_id}"
        timeout = float(p.get("timeout") or 60)
        end = time.time() + timeout
        while job.status == "running" and time.time() < end:
            time.sleep(0.5)
        return job.brief()

    return f"Unknown action '{action}'. Use list, status, result, cancel or wait."
