"""
Power / screensaver control for JARVIS.

Adds capabilities the assistant was missing:
  disable_screensaver  - turn the screensaver off (and keep the display awake)
  enable_screensaver   - turn it back on
  keep_awake           - prevent screensaver AND sleep until told otherwise
  allow_sleep          - release the keep-awake hold
  lock_screen          - lock the workstation now

Windows-first (uses SetThreadExecutionState + SystemParametersInfo + registry).
Other OSes get a best-effort or a clear "not supported" message.
"""

import platform
import subprocess

_SYSTEM = platform.system()

# Windows SetThreadExecutionState flags
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002

# SystemParametersInfo
_SPI_SETSCREENSAVEACTIVE = 0x0011
_SPIF_SENDWININICHANGE = 0x02


def _set_execution_state(flags: int) -> bool:
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
        return True
    except Exception as e:
        print(f"[power] SetThreadExecutionState failed: {e}")
        return False


def _set_screensaver_active(active: bool) -> bool:
    """Toggle the screensaver via registry + live SystemParametersInfo."""
    ok = True
    # Registry (persists across the setting UI)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "ScreenSaveActive", 0, winreg.REG_SZ,
                          "1" if active else "0")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[power] registry set failed: {e}")
        ok = False
    # Apply immediately for the current session
    try:
        import ctypes
        ctypes.windll.user32.SystemParametersInfoW(
            _SPI_SETSCREENSAVEACTIVE, 1 if active else 0, None,
            _SPIF_SENDWININICHANGE,
        )
    except Exception as e:
        print(f"[power] SystemParametersInfo failed: {e}")
        ok = False
    return ok


def _disable_screensaver() -> str:
    if _SYSTEM != "Windows":
        # Best effort on Linux desktops
        if _SYSTEM == "Linux":
            for cmd in (["xset", "s", "off"], ["xset", "-dpms"]):
                try:
                    subprocess.run(cmd, timeout=5)
                except Exception:
                    pass
            return "Screensaver disabled (Linux, best effort)."
        return f"Screensaver control isn't supported on {_SYSTEM}."
    sc = _set_screensaver_active(False)
    _set_execution_state(_ES_CONTINUOUS | _ES_DISPLAY_REQUIRED | _ES_SYSTEM_REQUIRED)
    return ("Screensaver turned off and the display will stay awake, sir."
            if sc else "I tried to turn off the screensaver but couldn't confirm it.")


def _enable_screensaver() -> str:
    if _SYSTEM != "Windows":
        if _SYSTEM == "Linux":
            try:
                subprocess.run(["xset", "s", "on"], timeout=5)
                subprocess.run(["xset", "+dpms"], timeout=5)
            except Exception:
                pass
            return "Screensaver re-enabled (Linux, best effort)."
        return f"Screensaver control isn't supported on {_SYSTEM}."
    sc = _set_screensaver_active(True)
    _set_execution_state(_ES_CONTINUOUS)  # release any keep-awake hold
    return ("Screensaver turned back on, sir."
            if sc else "I tried to re-enable the screensaver but couldn't confirm it.")


def _keep_awake() -> str:
    if _SYSTEM != "Windows":
        return _disable_screensaver()
    _set_execution_state(_ES_CONTINUOUS | _ES_DISPLAY_REQUIRED | _ES_SYSTEM_REQUIRED)
    return "I'll keep the display awake and prevent sleep, sir."


def _allow_sleep() -> str:
    if _SYSTEM != "Windows":
        return _enable_screensaver()
    _set_execution_state(_ES_CONTINUOUS)
    return "Sleep and screensaver are allowed again, sir."


def _lock_screen() -> str:
    try:
        if _SYSTEM == "Windows":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5)
        elif _SYSTEM == "Darwin":
            subprocess.run(["pmset", "displaysleepnow"], timeout=5)
        elif _SYSTEM == "Linux":
            subprocess.run(["xdg-screensaver", "lock"], timeout=5)
        return "Locked, sir."
    except Exception as e:
        return f"Could not lock the screen: {e}"


_ACTIONS = {
    "disable_screensaver": _disable_screensaver,
    "screensaver_off":     _disable_screensaver,
    "enable_screensaver":  _enable_screensaver,
    "screensaver_on":      _enable_screensaver,
    "keep_awake":          _keep_awake,
    "caffeine":            _keep_awake,
    "prevent_sleep":       _keep_awake,
    "allow_sleep":         _allow_sleep,
    "lock_screen":         _lock_screen,
    "lock":                _lock_screen,
}


def power_control(parameters: dict = None, response=None, player=None,
                  session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = (p.get("action", "") or "").lower().strip().replace(" ", "_")

    if player:
        player.write_log(f"[power] {action}")

    fn = _ACTIONS.get(action)
    if not fn:
        return (f"Unknown power action: '{action}'. Try disable_screensaver, "
                "enable_screensaver, keep_awake, allow_sleep, or lock_screen.")
    return fn()
