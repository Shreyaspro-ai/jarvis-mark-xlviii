# -*- coding: utf-8 -*-
"""Paperclip — orchestrate a team of AI agents from JARVIS.

github.com/paperclipai/paperclip (MIT). A self-hosted Node server + React UI
that runs a *team* of agents against business goals, with org charts, budgets,
governance and cost tracking. "If OpenClaw is an employee, Paperclip is the
company."

JARVIS shells out to the published `paperclipai` CLI — Paperclip is a platform,
not a library, so there is nothing to import. Where agent_mode is ONE agent
doing ONE task, this is a whole org you delegate a goal to and check on later.

Actions: status | doctor | onboard | company | goal | agent | run | cost
         activity | approval | dashboard | raw
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 180


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE = _base_dir()


def _cli() -> str | None:
    """The paperclipai executable, if installed."""
    for n in ("paperclipai", "paperclipai.cmd"):
        p = shutil.which(n)
        if p:
            return p
    return None


def _run(args: list[str], timeout: int = TIMEOUT) -> tuple[int, str]:
    exe = _cli()
    if not exe:
        return 127, "not installed"
    try:
        p = subprocess.run([exe, *args], capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace",
                           cwd=str(BASE))
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"


_NOT_INSTALLED = (
    "Paperclip CLI isn't installed. Install it with:\n"
    "  npm install -g paperclipai\n"
    "Then run action='onboard' once to set up the local server (it will ask for "
    "your agent providers and budgets)."
)

_NOT_ONBOARDED = (
    "Paperclip is installed but no local server is set up yet.\n"
    "Run action='onboard' once — it starts the self-hosted server and UI. "
    "No Paperclip account is needed."
)


def _clean(out: str, limit: int = 2200) -> str:
    out = out.strip()
    return out if len(out) <= limit else out[:limit] + f"\n… (+{len(out)-limit} chars)"


def paperclip(parameters: dict | None = None, response=None, player=None,
              session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = (p.get("action") or "status").strip().lower()
    args_str = (p.get("args") or "").strip()
    extra = args_str.split() if args_str else []

    exe = _cli()
    if not exe and action != "status":
        return _NOT_INSTALLED

    # ---- status: is it installed / reachable? -------------------------
    if action == "status":
        if not exe:
            return _NOT_INSTALLED
        rc, out = _run(["--version"], timeout=60)
        ver = out.splitlines()[0] if out else "?"
        rc2, out2 = _run(["doctor"], timeout=90)
        healthy = rc2 == 0
        return (f"Paperclip CLI {ver} — installed.\n"
                f"Server health (doctor): {'OK' if healthy else 'not ready'}\n"
                + ("" if healthy else f"\n{_clean(out2, 600)}\n\n{_NOT_ONBOARDED}"))

    # ---- one-time setup ----------------------------------------------
    if action == "onboard":
        rc, out = _run(["onboard", "--yes", *extra], timeout=900)
        return (f"Paperclip onboarding {'complete' if rc == 0 else f'failed (rc={rc})'}.\n"
                f"{_clean(out)}")

    if action == "doctor":
        rc, out = _run(["doctor", *extra], timeout=120)
        return f"Paperclip doctor (rc={rc}):\n{_clean(out)}"

    # ---- the working surface -----------------------------------------
    # Each maps to a paperclipai subcommand; default to a read-only listing so
    # a bare call never mutates anything.
    listable = {
        "company":   ["company"],
        "goal":      ["goal"],
        "agent":     ["agent"],
        "run":       ["run"],
        "cost":      ["cost"],
        "activity":  ["activity"],
        "approval":  ["approval"],
        "dashboard": ["dashboard"],
        "project":   ["project"],
        "issue":     ["issue"],
    }
    if action in listable:
        sub = listable[action] + (extra or ["list"])
        rc, out = _run(sub)
        if rc == 127:
            return _NOT_INSTALLED
        if rc != 0 and ("ECONNREFUSED" in out or "connect" in out.lower()):
            return _NOT_ONBOARDED
        head = f"paperclipai {' '.join(sub)}"
        return f"{head} (rc={rc}):\n{_clean(out)}"

    # ---- escape hatch -------------------------------------------------
    if action == "raw":
        if not extra:
            return "action='raw' needs args, e.g. args='agent list'."
        rc, out = _run(extra)
        return f"paperclipai {' '.join(extra)} (rc={rc}):\n{_clean(out)}"

    return ("Unknown action. Use: status, doctor, onboard, company, goal, agent, run, "
            "cost, activity, approval, dashboard, project, issue, raw.")
