"""
Agent Mode — a Claude-style autonomous agent for JARVIS, powered by Gemini.

Given a high-level goal, it plans and works through it the way a coding/computer
agent does: reading files, editing/creating files, listing directories and
running shell commands, observing the result, and iterating until the task is
done. It uses the same Gemini API key as the rest of JARVIS (config/api_keys.json),
so it stays on the free/generous Gemini quota.

This module is fully self-contained and additive — it does not import from or
modify any other JARVIS action. Wired into main.py as the "agent_mode" tool.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Commands the agent is NOT allowed to run — catastrophic / irreversible ops.
# A blocklist can't be exhaustive, but it stops the obvious disasters so a
# single misunderstood instruction can't wipe the machine.
_DANGEROUS_PATTERNS = [
    r"\brm\s+-[a-z]*r",                       # rm -r / rm -rf
    r"\bdel\b.*\/[sq]",                       # del /s or /q (recursive/quiet)
    r"\brmdir\b.*\/s",                        # rmdir /s
    r"\brd\b.*\/s",                           # rd /s
    r"remove-item.*-recurse",                 # PowerShell recursive delete
    r"remove-item.*-force",                   # PowerShell forced delete
    r"\bformat\b\s+[a-z]:",                   # format C:
    r"format-volume",
    r"clear-disk",
    r"\bdiskpart\b",
    r"\bmkfs",
    r"\bcipher\b.*\/w",                       # secure-wipe free space
    r"\bshutdown\b",
    r"restart-computer",
    r"stop-computer",
    r"reg\s+delete",
    r"remove-itemproperty",
    r":\s*\(\)\s*\{",                         # bash fork bomb
    r">\s*/dev/sd",
]
_DANGEROUS_RE = re.compile("|".join(_DANGEROUS_PATTERNS), re.IGNORECASE)

# Model: flash is fast and quota-friendly; the agent loop makes it capable.
AGENT_MODEL = "gemini-2.5-flash"
MAX_STEPS = 18                 # hard cap on tool-call rounds per task
CMD_TIMEOUT = 90               # seconds per shell command
MAX_READ_CHARS = 20000         # truncate huge file reads
MAX_OUTPUT_CHARS = 8000        # truncate huge command output


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


API_CONFIG_PATH = _base_dir() / "config" / "api_keys.json"
# Default working root for the agent when no absolute path is given.
DEFAULT_ROOT = Path.home()


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _resolve(path_str: str, root: Path) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = root / p
    return p


# ── Tool implementations ─────────────────────────────────────────────────────

def _tool_list_dir(args: dict, root: Path) -> str:
    target = _resolve(args.get("path", "."), root)
    try:
        if not target.exists():
            return f"ERROR: path does not exist: {target}"
        if target.is_file():
            return f"{target} is a file, not a directory."
        entries = []
        for item in sorted(target.iterdir()):
            kind = "dir " if item.is_dir() else "file"
            entries.append(f"[{kind}] {item.name}")
        listing = "\n".join(entries) if entries else "(empty)"
        return f"Contents of {target}:\n{listing}"
    except Exception as e:
        return f"ERROR listing {target}: {e}"


def _tool_read_file(args: dict, root: Path) -> str:
    target = _resolve(args.get("path", ""), root)
    try:
        if not target.exists():
            return f"ERROR: file does not exist: {target}"
        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > MAX_READ_CHARS:
            text = text[:MAX_READ_CHARS] + f"\n...[truncated, {len(text)} chars total]"
        return f"--- {target} ---\n{text}"
    except Exception as e:
        return f"ERROR reading {target}: {e}"


def _tool_write_file(args: dict, root: Path) -> str:
    target = _resolve(args.get("path", ""), root)
    content = args.get("content", "")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} chars to {target}"
    except Exception as e:
        return f"ERROR writing {target}: {e}"


def _tool_edit_file(args: dict, root: Path) -> str:
    target = _resolve(args.get("path", ""), root)
    old = args.get("old_string", "")
    new = args.get("new_string", "")
    try:
        if not target.exists():
            return f"ERROR: file does not exist: {target}"
        text = target.read_text(encoding="utf-8", errors="replace")
        count = text.count(old)
        if count == 0:
            return "ERROR: old_string not found in file. Read the file again and match exactly."
        if count > 1:
            return f"ERROR: old_string appears {count} times — make it unique with more context."
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        return f"OK: edited {target}"
    except Exception as e:
        return f"ERROR editing {target}: {e}"


def _tool_run_command(args: dict, root: Path) -> str:
    command = args.get("command", "").strip()
    cwd = _resolve(args.get("cwd", "."), root)
    if not command:
        return "ERROR: empty command."
    if _DANGEROUS_RE.search(command):
        return ("BLOCKED: this command is considered destructive (recursive/forced delete, "
                "disk format, system shutdown, or registry wipe) and was not run for safety. "
                "Find a safer, more targeted approach, or tell the user it needs to be done manually.")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CMD_TIMEOUT,
            cwd=str(cwd) if cwd.exists() else str(root),
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        parts = [f"exit_code: {result.returncode}"]
        if out:
            parts.append(f"STDOUT:\n{out}")
        if err:
            parts.append(f"STDERR:\n{err}")
        combined = "\n\n".join(parts)
        if len(combined) > MAX_OUTPUT_CHARS:
            combined = combined[:MAX_OUTPUT_CHARS] + "\n...[output truncated]"
        return combined
    except subprocess.TimeoutExpired:
        return f"Command timed out after {CMD_TIMEOUT}s (likely a long-running/GUI process — treat as started)."
    except Exception as e:
        return f"ERROR running command: {e}"


_TOOL_IMPLS = {
    "list_dir": _tool_list_dir,
    "read_file": _tool_read_file,
    "write_file": _tool_write_file,
    "edit_file": _tool_edit_file,
    "run_command": _tool_run_command,
}


# ── Gemini tool schema (function declarations) ───────────────────────────────

def _build_tools(types):
    fns = [
        types.FunctionDeclaration(
            name="list_dir",
            description="List files and folders in a directory.",
            parameters=types.Schema(
                type="OBJECT",
                properties={"path": types.Schema(type="STRING", description="Directory path (absolute, or relative to the working root).")},
                required=["path"],
            ),
        ),
        types.FunctionDeclaration(
            name="read_file",
            description="Read the full text contents of a file.",
            parameters=types.Schema(
                type="OBJECT",
                properties={"path": types.Schema(type="STRING", description="File path.")},
                required=["path"],
            ),
        ),
        types.FunctionDeclaration(
            name="write_file",
            description="Create or overwrite a file with the given content.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(type="STRING", description="File path."),
                    "content": types.Schema(type="STRING", description="Full file content to write."),
                },
                required=["path", "content"],
            ),
        ),
        types.FunctionDeclaration(
            name="edit_file",
            description="Replace one exact unique occurrence of old_string with new_string in a file. Read the file first.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(type="STRING", description="File path."),
                    "old_string": types.Schema(type="STRING", description="Exact text to replace (must be unique in the file)."),
                    "new_string": types.Schema(type="STRING", description="Replacement text."),
                },
                required=["path", "old_string", "new_string"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_command",
            description="Run a shell command and get its stdout/stderr/exit code. Use for building, testing, git, running scripts, etc.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "command": types.Schema(type="STRING", description="The shell command to run."),
                    "cwd": types.Schema(type="STRING", description="Working directory (optional)."),
                },
                required=["command"],
            ),
        ),
    ]
    return [types.Tool(function_declarations=fns)]


_SYSTEM_INSTRUCTION = """You are JARVIS operating in Agent Mode — an autonomous coding and computer agent working directly on the user's Windows machine, in the style of Claude Code.

How you work:
- You are given a goal. Break it down and complete it end to end by USING TOOLS, not by describing what you would do.
- Investigate before acting: list_dir and read_file to understand the situation before you write or run anything.
- Make changes with write_file / edit_file. Verify your work by running it with run_command and reading the output.
- If something fails, read the error, fix it, and try again. Iterate until it actually works.
- Prefer minimal, targeted changes. Do not tamper with unrelated files.
- The machine runs Windows with PowerShell available via run_command (shell=True). Paths use backslashes.

When the goal is fully accomplished (or you are truly blocked), STOP calling tools and reply with a short plain-text summary of what you did and the outcome. Keep the final summary concise and spoken-friendly, addressing the user as 'sir'."""


def _run_agent(goal: str, root: Path, log=None) -> str:
    from google import genai
    from google.genai import types

    def _log(msg: str):
        if log:
            log(f"[Agent] {msg}")
        else:
            print(f"[Agent] {msg}")

    client = genai.Client(api_key=_get_api_key())
    tools = _build_tools(types)
    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION,
        tools=tools,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=f"Working root: {root}\n\nGoal: {goal}")],
        )
    ]

    final_text = ""
    for step in range(1, MAX_STEPS + 1):
        try:
            response = client.models.generate_content(
                model=AGENT_MODEL, contents=contents, config=config
            )
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "quota" in msg or "resource_exhausted" in msg:
                return "I hit the Gemini rate limit mid-task, sir. Please try again in a moment."
            return f"Agent error, sir: {e}"

        candidate = response.candidates[0] if response.candidates else None
        if candidate is None or candidate.content is None:
            final_text = (getattr(response, "text", "") or "").strip()
            break

        parts = candidate.content.parts or []
        function_calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

        # Record the model turn.
        contents.append(candidate.content)

        if not function_calls:
            text_bits = [p.text for p in parts if getattr(p, "text", None)]
            final_text = "\n".join(t for t in text_bits if t).strip()
            break

        # Execute every requested tool call and return the results.
        response_parts = []
        for fc in function_calls:
            name = fc.name
            args = dict(fc.args) if fc.args else {}
            impl = _TOOL_IMPLS.get(name)
            if impl is None:
                result = f"ERROR: unknown tool '{name}'"
            else:
                preview = args.get("command") or args.get("path") or ""
                _log(f"step {step}: {name} {preview}")
                result = impl(args, root)
            response_parts.append(
                types.Part.from_function_response(name=name, response={"result": result})
            )

        contents.append(types.Content(role="user", parts=response_parts))
    else:
        final_text = "I reached the step limit for this task, sir. I've done as much as I could — you may want to check the result."

    return final_text or "Task complete, sir."


def agent_mode(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    """JARVIS action entry point. parameters: {goal: str, working_dir?: str}."""
    p = parameters or {}
    goal = (p.get("goal") or p.get("task") or p.get("description") or "").strip()
    working_dir = (p.get("working_dir") or "").strip()

    if not goal:
        return "What would you like me to do in agent mode, sir?"

    root = Path(working_dir) if working_dir else DEFAULT_ROOT
    if not root.exists():
        root = DEFAULT_ROOT

    def _log(msg: str):
        print(msg)
        if player and hasattr(player, "write_log"):
            try:
                player.write_log(msg)
            except Exception:
                pass

    _log(f"[Agent] Starting: {goal}")
    result = _run_agent(goal, root, log=_log)
    if speak:
        try:
            speak(result)
        except Exception:
            pass
    return result
