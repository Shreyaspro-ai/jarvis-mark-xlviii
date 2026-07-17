# -*- coding: utf-8 -*-
"""Self-update for JARVIS, independent of how he was launched.

The launcher scripts (start-jarvis.sh / Start-Jarvis.bat) pull before starting,
but people don't always use them — a Start Menu shortcut, a .desktop file, an
alias, or `python main.py` all bypass the updater and the clone silently rots.

So JARVIS checks for himself, at startup, in the background. Nothing is applied
while he's running (you can't hot-swap the code underneath a live process) —
he pulls, and the new code takes effect on the next restart. He mentions it
once, quietly, when the user isn't busy.

Works the same on Windows, macOS and Linux: it's just git.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BRANCH = "main"
REMOTE = "origin"
_TIMEOUT = 45


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE = _base_dir()


def _git(*args: str, timeout: int = _TIMEOUT) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", *args], cwd=str(BASE), capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except FileNotFoundError:
        return 127, "git not installed"
    except subprocess.TimeoutExpired:
        return 124, "git timed out"
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"


def is_git_clone() -> bool:
    return (BASE / ".git").exists()


def has_local_edits() -> bool:
    """True if tracked files were modified — we must not clobber them."""
    rc, _ = _git("diff", "--quiet")
    if rc == 1:
        return True
    rc, _ = _git("diff", "--cached", "--quiet")
    return rc == 1


def check_for_updates() -> dict:
    """Ask GitHub what's new. Read-only: fetch never changes the working tree.

    Returns {"ok", "behind", "commits", "reason"}.
    """
    if not is_git_clone():
        return {"ok": False, "behind": 0, "commits": [], "reason": "not a git clone"}

    rc, out = _git("fetch", REMOTE, BRANCH, "--quiet")
    if rc != 0:
        return {"ok": False, "behind": 0, "commits": [], "reason": f"offline or fetch failed ({out[:80]})"}

    rc, out = _git("rev-list", "--count", f"HEAD..{REMOTE}/{BRANCH}")
    if rc != 0:
        return {"ok": False, "behind": 0, "commits": [], "reason": out[:80]}
    try:
        behind = int(out.strip() or "0")
    except ValueError:
        behind = 0

    commits: list[str] = []
    if behind:
        rc, log = _git("log", "--oneline", "--no-decorate", f"HEAD..{REMOTE}/{BRANCH}")
        if rc == 0:
            commits = [ln.strip() for ln in log.splitlines() if ln.strip()][:10]

    return {"ok": True, "behind": behind, "commits": commits, "reason": ""}


def apply_update() -> dict:
    """Fast-forward to the latest. Refuses if the user has local edits.

    Returns {"ok", "updated", "message"}. The running process keeps the OLD
    code — a restart is required for it to take effect.
    """
    if not is_git_clone():
        return {"ok": False, "updated": False, "message": "Not a git clone — can't self-update."}

    if has_local_edits():
        return {"ok": False, "updated": False,
                "message": ("You have local changes to tracked files, so I won't overwrite them. "
                            "Stash or discard them first.")}

    info = check_for_updates()
    if not info["ok"]:
        return {"ok": False, "updated": False, "message": f"Couldn't check: {info['reason']}"}
    if info["behind"] == 0:
        return {"ok": True, "updated": False, "message": "Already up to date."}

    before, _ = _git("rev-parse", "--short", "HEAD")
    rc, out = _git("merge", "--ff-only", f"{REMOTE}/{BRANCH}", "--quiet")
    if rc != 0:
        return {"ok": False, "updated": False,
                "message": f"Branch has diverged from GitHub — needs fixing by hand. ({out[:100]})"}

    _, after = _git("rev-parse", "--short", "HEAD")
    n = info["behind"]
    return {"ok": True, "updated": True,
            "message": (f"Updated to {after.strip()} ({n} new commit{'s' if n != 1 else ''}). "
                        f"Restart me for it to take effect.")}


def startup_check(player=None, speak=None) -> None:
    """Fire-and-forget check at startup. Safe to call from a background thread.

    Pulls if it can, logs quietly to the HUD, and only speaks when the user is
    idle — never over them.
    """
    try:
        info = check_for_updates()
        if not info["ok"] or info["behind"] == 0:
            if player is not None and info["ok"]:
                try:
                    player.write_log("SYS: up to date.")
                except Exception:
                    pass
            return

        n = info["behind"]
        if player is not None:
            try:
                player.write_log(f"SYS: {n} update(s) available on GitHub:")
                for c in info["commits"][:5]:
                    player.write_log(f"     {c}")
            except Exception:
                pass

        res = apply_update()
        if player is not None:
            try:
                player.write_log(f"SYS: {res['message']}")
            except Exception:
                pass

        if res.get("updated") and speak is not None:
            # don't talk over the user
            try:
                from core.focus import user_is_busy
                import time
                deadline = time.time() + 300
                while user_is_busy(6.0) and time.time() < deadline:
                    time.sleep(2.0)
            except Exception:
                pass
            try:
                speak(f"I pulled {n} update{'s' if n != 1 else ''} from GitHub. "
                      f"They'll take effect next time you start me.")
            except Exception:
                pass
    except Exception:
        pass    # a broken update check must never stop JARVIS booting
