# -*- coding: utf-8 -*-
"""Keep JARVIS out of the user's way.

Two problems this solves:

1. Anything that injects keystrokes (pyautogui / SendKeys) sends them to whatever
   window currently has focus. If the user is typing, JARVIS types into THEIR
   document. `preserve_focus()` remembers the foreground window and puts it back.

2. A user who is actively typing should not have their app yanked out from under
   them. `user_is_busy()` reports whether input happened in the last few seconds
   so callers can defer, and `foreground_is_fullscreen()` catches games/video.

Everything degrades to a no-op off Windows, so the Linux clone still runs.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager

_IS_WIN = sys.platform == "win32"

# how recently the user must have typed/moved for us to call them "busy"
BUSY_WINDOW_SECONDS = 4.0


def _user32():
    if not _IS_WIN:
        return None
    try:
        import ctypes
        return ctypes.windll.user32
    except Exception:
        return None


def get_foreground_window():
    """Handle of the window the user is currently in, or None."""
    u = _user32()
    if not u:
        return None
    try:
        hwnd = u.GetForegroundWindow()
        return hwnd or None
    except Exception:
        return None


def restore_foreground_window(hwnd) -> bool:
    """Put focus back where it was. Returns True if it worked."""
    u = _user32()
    if not u or not hwnd:
        return False
    try:
        if not u.IsWindow(hwnd):
            return False
        # Windows refuses SetForegroundWindow from a background process unless
        # the calling thread is attached to the target's input queue.
        import ctypes
        pid = ctypes.c_ulong()
        target_tid = u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        attached = False
        if target_tid and target_tid != cur_tid:
            attached = bool(u.AttachThreadInput(cur_tid, target_tid, True))
        try:
            u.SetForegroundWindow(hwnd)
        finally:
            if attached:
                u.AttachThreadInput(cur_tid, target_tid, False)
        return True
    except Exception:
        return False


@contextmanager
def preserve_focus():
    """Wrap any action that steals focus or injects keys.

        with preserve_focus():
            pyautogui.hotkey("win", "d")

    Whatever the user was in gets focus back afterwards.
    """
    hwnd = get_foreground_window()
    try:
        yield hwnd
    finally:
        if hwnd:
            # let the injected input land before we steal focus back
            time.sleep(0.15)
            restore_foreground_window(hwnd)


def idle_seconds() -> float:
    """Seconds since the user last touched the keyboard or mouse.

    Returns a large number if we can't tell (i.e. assume they're idle and it's
    safe to act) — never block a task just because detection failed.
    """
    u = _user32()
    if not u:
        return 999.0
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not u.GetLastInputInfo(ctypes.byref(info)):
            return 999.0
        tick = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (tick - info.dwTime) / 1000.0)
    except Exception:
        return 999.0


def user_is_busy(window: float = BUSY_WINDOW_SECONDS) -> bool:
    """True if the user typed or moved the mouse in the last few seconds."""
    return idle_seconds() < window


def foreground_is_fullscreen() -> bool:
    """True if a fullscreen app (game, video, presentation) is in front."""
    u = _user32()
    if not u:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return False
        shell = u.GetShellWindow()
        desktop = u.GetDesktopWindow()
        if hwnd in (shell, desktop):
            return False
        rect = wintypes.RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        sw = u.GetSystemMetrics(0)
        sh = u.GetSystemMetrics(1)
        return (rect.right - rect.left) >= sw and (rect.bottom - rect.top) >= sh
    except Exception:
        return False


def safe_to_interrupt() -> bool:
    """Is it polite to grab the screen/keyboard right now?"""
    return not user_is_busy() and not foreground_is_fullscreen()
