"""
Cross-session memory recall for JARVIS.

Gives JARVIS a searchable long-term memory of its own past conversations, so it
can answer "what did we decide last time", "that thing I mentioned yesterday",
etc. Every spoken exchange is journalled to a local SQLite FTS5 database; the
`recall` tool full-text-searches it.

Capability inspired by Hermes Agent (Nous Research, MIT) — its FTS5 session
search / cross-session recall — reimplemented natively for JARVIS.

Local only: the DB lives in memory/history.db and is never uploaded.
"""

import re
import sqlite3
import threading
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "memory" / "history.db"

_lock = threading.Lock()
_fts = None  # True if FTS5 is available, else fall back to LIKE


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH), timeout=5)


def _init() -> None:
    global _fts
    con = _connect()
    try:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS conv USING fts5(ts, role, text)")
        _fts = True
    except sqlite3.OperationalError:
        con.execute("CREATE TABLE IF NOT EXISTS conv (ts TEXT, role TEXT, text TEXT)")
        _fts = False
    con.commit()
    con.close()


try:
    _init()
except Exception as e:  # never let memory init crash JARVIS
    print(f"[recall] init failed: {e}")


def _tokens(q: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", q or "") if len(w) > 2]


def journal(role: str, text: str) -> None:
    """Append one utterance to the searchable history. Best-effort, never raises."""
    if not text or not text.strip():
        return
    try:
        with _lock:
            con = _connect()
            con.execute(
                "INSERT INTO conv (ts, role, text) VALUES (?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), role, text.strip()),
            )
            con.commit()
            con.close()
    except Exception as e:
        print(f"[recall] journal failed: {e}")


def _search(query: str, limit: int = 8) -> list[tuple]:
    con = _connect()
    try:
        if _fts:
            q = " OR ".join(_tokens(query))
            if not q:
                return []
            rows = con.execute(
                "SELECT ts, role, text FROM conv WHERE conv MATCH ? ORDER BY rank LIMIT ?",
                (q, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT ts, role, text FROM conv WHERE text LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return rows
    finally:
        con.close()


def _recent(limit: int = 8) -> list[tuple]:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT ts, role, text FROM conv ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return list(reversed(rows))
    finally:
        con.close()


def recall(parameters: dict = None, response=None, player=None,
           session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = (p.get("action", "search") or "search").lower().strip()
    try:
        limit = int(p.get("limit", 8))
    except (TypeError, ValueError):
        limit = 8
    limit = max(1, min(limit, 20))

    if player:
        player.write_log(f"[recall] {action} {p.get('query', '')}".strip())

    try:
        if action == "recent":
            rows = _recent(limit)
        else:
            query = (p.get("query", "") or "").strip()
            if not query:
                return "What should I search our past conversations for, sir?"
            rows = _search(query, limit)
    except Exception as e:
        return f"Memory search failed, sir: {e}"

    if not rows:
        return "I couldn't find anything about that in our past conversations, sir."

    who = {"user": "You", "jarvis": "Me"}
    lines = [f"[{ts}] {who.get(role, role)}: {text[:220]}" for ts, role, text in rows]
    return "From our past conversations:\n" + "\n".join(lines)
