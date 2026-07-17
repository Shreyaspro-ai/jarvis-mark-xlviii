"""
Spellbook — Harry Potter voice spells for JARVIS.

Maps incantations to real actions, reusing existing JARVIS capabilities:

  accio <app>          -> open the app
  avada kedavra <app>  -> kill the app's process (terminate its task)
  lumos                -> brightness up
  nox                  -> brightness down
  silencio             -> mute
  sonorus              -> volume up
  quietus              -> volume down

JARVIS routes spoken spells to the `cast_spell` tool with {spell, target}.
"""

import platform
import subprocess
from datetime import datetime
from pathlib import Path

from actions.open_app import open_app, _normalize
from actions.computer_settings import computer_settings
from actions.power_control import power_control

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_SYSTEM = platform.system()


# ── low-level helpers used by the new spells ──────────────────────────────
try:
    from core.focus import preserve_focus
except Exception:                       # focus helper optional / non-Windows
    from contextlib import contextmanager

    @contextmanager
    def preserve_focus():
        yield None


def _hotkey(*keys) -> bool:
    """Send a key combo. Tries pyautogui, then Windows SendKeys fallback.

    Wrapped in preserve_focus() so the keystrokes don't land in — and the focus
    isn't stolen from — whatever the user is currently typing in.
    """
    try:
        import pyautogui
        with preserve_focus():
            pyautogui.hotkey(*keys)
        return True
    except Exception:
        pass
    if _SYSTEM == "Windows":
        # Map to WScript SendKeys tokens.
        token_map = {"win": "^{ESC}", "alt": "%", "ctrl": "^", "shift": "+",
                     "f4": "{F4}", "d": "d", "c": "c", "m": "m"}
        try:
            combo = "".join(token_map.get(k.lower(), k) for k in keys)
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(New-Object -ComObject WScript.Shell).SendKeys('{combo}')"],
                timeout=6, capture_output=True,
            )
            return True
        except Exception:
            return False
    return False


def _tell_time() -> str:
    now = datetime.now()
    return f"Tempus — it is {now.strftime('%I:%M %p').lstrip('0')} on {now.strftime('%A, %B %d')}, sir."


def _clear_clipboard() -> str:
    try:
        if _SYSTEM == "Windows":
            subprocess.run('cmd /c "echo off | clip"', shell=True, timeout=6)
        elif _SYSTEM == "Darwin":
            subprocess.run("pbcopy < /dev/null", shell=True, timeout=6)
        else:
            subprocess.run("xsel -bc", shell=True, timeout=6)
        return "Obliviate — the clipboard has been wiped clean, sir."
    except Exception as e:
        return f"The memory charm fizzled: {e}"


def _copy_selection() -> str:
    return ("Geminio — copied the selection, sir." if _hotkey("ctrl", "c")
            else "The duplication charm failed, sir.")


def _close_active_window() -> str:
    return ("Expelliarmus — the active window has been dismissed, sir."
            if _hotkey("alt", "f4") else "The disarming charm missed, sir.")


def _show_desktop() -> str:
    if _SYSTEM == "Windows":
        ok = _hotkey("win", "d")
    else:
        ok = _hotkey("ctrl", "alt", "d")
    return ("Wingardium Leviosa — windows lifted away, revealing the desktop, sir."
            if ok else "The levitation charm couldn't lift the windows, sir.")


def _screenshot() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path.home() / "Desktop" / f"revelio_{ts}.png"
    try:
        try:
            from PIL import ImageGrab
            ImageGrab.grab().save(str(path))
            return f"Revelio — screen revealed and captured to {path}, sir."
        except Exception:
            import pyautogui
            pyautogui.screenshot(str(path))
            return f"Revelio — screen revealed and captured to {path}, sir."
    except Exception as e:
        return f"Revelio failed to capture the screen: {e}"


def _restart_explorer() -> str:
    if _SYSTEM != "Windows":
        return "Reparo only mends the Windows desktop, sir."
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"],
                       capture_output=True, timeout=8)
        subprocess.Popen("explorer.exe")
        return "Reparo — the desktop and taskbar have been mended, sir."
    except Exception as e:
        return f"Reparo couldn't mend the desktop: {e}"

# Never let a kill-spell touch these — killing them can crash or brick the session.
_PROTECTED_PROCESSES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe",
    "fontdrvhost.exe", "dwm.exe", "explorer.exe", "python.exe", "pythonw.exe",
    "kernel", "systemd", "init", "launchd", "windowserver",
}


def _target_process_names(target: str) -> list[str]:
    """Best-effort mapping from a spoken app name to likely process names."""
    norm = _normalize(target).strip()
    candidates = {target.strip(), norm}
    names = set()
    for c in candidates:
        if not c:
            continue
        base = c.split()[0] if " " in c else c   # "Google Chrome" -> "Google" is bad;
        # prefer the normalized single token, then whole string without spaces
        names.add(c)
        names.add(c.replace(" ", ""))
        if not c.lower().endswith(".exe") and _SYSTEM == "Windows":
            names.add(c + ".exe")
            names.add(c.replace(" ", "") + ".exe")
    return [n for n in names if n]


def _kill_app(target: str) -> str:
    if not target:
        return "Which app should I strike down?"

    wanted = {n.lower() for n in _target_process_names(target)}
    # Drop any protected names that snuck into the target set.
    wanted = {w for w in wanted if w not in _PROTECTED_PROCESSES}
    if not wanted:
        return f"I will not target a protected system process ({target})."

    killed = 0

    if _PSUTIL:
        for proc in psutil.process_iter(["name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if not pname or pname in _PROTECTED_PROCESSES:
                    continue
                pbase = pname[:-4] if pname.endswith(".exe") else pname
                if pname in wanted or pbase in {w[:-4] if w.endswith(".exe") else w for w in wanted}:
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                continue
        if killed:
            return f"Avada Kedavra — struck down {target} ({killed} process{'es' if killed != 1 else ''})."

    # Fallback: taskkill on Windows.
    if _SYSTEM == "Windows":
        for name in _target_process_names(target):
            img = name if name.lower().endswith(".exe") else name + ".exe"
            if img.lower() in _PROTECTED_PROCESSES:
                continue
            try:
                r = subprocess.run(
                    ["taskkill", "/IM", img, "/F"],
                    capture_output=True, text=True, timeout=10,
                )
                if r.returncode == 0:
                    return f"Avada Kedavra — struck down {target}."
            except Exception:
                continue

    return f"Couldn't find a running {target} to strike down."


# spell -> (kind, arg). kind: "open" | "kill" | "setting" | "power" | "func"
_SPELLBOOK = {
    # ── original seven ──
    "accio":            ("open", None),
    "avada kedavra":    ("kill", None),
    "lumos":            ("setting", "brightness_up"),
    "nox":              ("setting", "brightness_down"),
    "silencio":         ("setting", "mute"),
    "sonorus":          ("setting", "volume_up"),
    "quietus":          ("setting", "volume_down"),

    # ── 15 more ──
    "incendio":         ("setting", "brightness_up"),   # fire → more light
    "glacius":          ("setting", "brightness_down"),  # ice → dim
    "crescendo":        ("setting", "volume_up"),        # swell the sound
    "colloportus":      ("power",   "lock_screen"),      # sealing charm → lock
    "colloporto":       ("power",   "lock_screen"),
    "protego":          ("power",   "enable_screensaver"),  # shield the screen
    "alohomora":        ("power",   "keep_awake"),       # unlock the display from sleep
    "finite incantatem": ("power",  "allow_sleep"),      # end active effects
    "finite":           ("power",   "allow_sleep"),
    "stupefy":          ("power",   "lock_screen"),      # stun → lock
    "tempus":           ("func",    _tell_time),         # conjure the time
    "obliviate":        ("func",    _clear_clipboard),   # memory charm → wipe clipboard
    "geminio":          ("func",    _copy_selection),    # duplication → copy
    "revelio":          ("func",    _screenshot),        # reveal → screenshot
    "reparo":           ("func",    _restart_explorer),  # mend the desktop
    "expelliarmus":     ("func",    _close_active_window),  # disarm → close window
    "wingardium leviosa": ("func",  _show_desktop),      # levitate windows away
    "expecto patronum": ("open",    "Task Manager"),     # summon a guardian
}


def cast_spell(parameters: dict = None, response=None, player=None,
               session_memory=None, speak=None) -> str:
    p = parameters or {}
    spell = (p.get("spell", "") or "").lower().strip()
    target = (p.get("target", "") or p.get("app", "") or "").strip()

    if player:
        player.write_log(f"[spell] {spell} {target}".strip())

    entry = _SPELLBOOK.get(spell)
    if not entry:
        return f"That's not a spell I know: '{spell}'."

    kind, arg = entry

    if kind == "open":
        app = arg or target                       # fixed target (e.g. Task Manager) or spoken one
        if not app:
            return "Accio what? Name the app to summon."
        result = open_app(parameters={"app_name": app}, player=player)
        return result if result else f"Accio {app}."

    if kind == "kill":
        return _kill_app(target)

    if kind == "setting":
        return computer_settings(parameters={"action": arg}, player=player)

    if kind == "power":
        return power_control(parameters={"action": arg}, player=player, speak=speak)

    if kind == "func":
        try:
            return arg()
        except Exception as e:
            return f"The spell '{spell}' misfired: {e}"

    return f"Unknown spell effect for '{spell}'."
