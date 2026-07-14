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

from actions.open_app import open_app, _normalize
from actions.computer_settings import computer_settings

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_SYSTEM = platform.system()

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


# spell -> (kind, settings_action). kind: "open" | "kill" | "setting"
_SPELLBOOK = {
    "accio":        ("open", None),
    "avada kedavra": ("kill", None),
    "lumos":        ("setting", "brightness_up"),
    "nox":          ("setting", "brightness_down"),
    "silencio":     ("setting", "mute"),
    "sonorus":      ("setting", "volume_up"),
    "quietus":      ("setting", "volume_down"),
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

    kind, setting_action = entry

    if kind == "open":
        if not target:
            return "Accio what? Name the app to summon."
        result = open_app(parameters={"app_name": target}, player=player)
        return result if result else f"Accio {target}."

    if kind == "kill":
        return _kill_app(target)

    if kind == "setting":
        return computer_settings(parameters={"action": setting_action}, player=player)

    return f"Unknown spell effect for '{spell}'."
