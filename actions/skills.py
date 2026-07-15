"""
Self-improving skill library for JARVIS.

JARVIS learns from experience: after finishing a non-trivial task it records a
reusable, step-by-step "skill". Next time a similar request comes in, it searches
its skills first and follows what already worked — and refines the skill if it
found a better way. This is the closed learning loop that makes the assistant get
better over time instead of solving the same problem from scratch each session.

Capability inspired by Hermes Agent (Nous Research, MIT) and OpenClaw (MIT) —
their agent-curated, self-improving skill systems — reimplemented natively for
JARVIS and compatible in spirit with the agentskills.io idea.

Local only: skills live in memory/skills.json and are never uploaded.
"""

import json
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
SKILLS_PATH = BASE_DIR / "memory" / "skills.json"


def _load() -> list[dict]:
    if not SKILLS_PATH.exists():
        return []
    try:
        data = json.loads(SKILLS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_all(skills: list[dict]) -> None:
    SKILLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SKILLS_PATH.write_text(
        json.dumps(skills, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _tokens(q: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", q or "") if len(w) > 2]


def _score(skill: dict, query: str) -> int:
    ql = query.lower()
    name = (skill.get("name") or "").lower()
    desc = (skill.get("description") or "").lower()
    tags = " ".join(skill.get("tags", [])).lower()
    content = (skill.get("content") or "").lower()
    s = 0
    if ql and ql in name:
        s += 6
    for t in _tokens(query):
        if t in name:
            s += 3
        if t in desc:
            s += 2
        if t in tags:
            s += 2
        if t in content:
            s += 1
    return s


def _find_by_name(skills: list[dict], name: str) -> dict | None:
    nl = (name or "").strip().lower()
    return next((s for s in skills if (s.get("name") or "").lower() == nl), None)


def _save(p: dict) -> str:
    name = (p.get("name") or "").strip()
    if not name:
        return "A skill needs a name, sir."
    content = (p.get("content") or p.get("steps") or "").strip()
    if not content:
        return "A skill needs its steps/content, sir."
    desc = (p.get("description") or "").strip()
    tags = p.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    skills = _load()
    existing = _find_by_name(skills, name)
    now = datetime.now().isoformat(timespec="seconds")
    if existing:  # improve in place (self-improvement)
        existing["content"] = content
        if desc:
            existing["description"] = desc
        if tags:
            existing["tags"] = tags
        existing["updated"] = now
        existing["revisions"] = existing.get("revisions", 1) + 1
        _save_all(skills)
        return f"Refined the skill '{name}' (revision {existing['revisions']}), sir."
    skills.append({
        "name": name, "description": desc, "content": content, "tags": tags,
        "created": now, "updated": now, "uses": 0, "revisions": 1,
    })
    _save_all(skills)
    return f"Learned a new skill: '{name}', sir. I'll reuse it next time."


def _find(p: dict) -> str:
    query = (p.get("query") or p.get("name") or "").strip()
    skills = _load()
    if not skills:
        return "I haven't learned any skills yet, sir."
    if not query:
        return _list(p)
    ranked = sorted(((_score(s, query), s) for s in skills),
                    key=lambda x: x[0], reverse=True)
    hits = [s for sc, s in ranked if sc > 0][:5]
    if not hits:
        return f"No learned skill matches '{query}', sir."
    lines = [f"Matching skills for '{query}':"]
    for s in hits:
        lines.append(f"- {s['name']}: {s.get('description', '')[:90]} "
                     f"(used {s.get('uses', 0)}x)")
    lines.append("Use skills(action='get', name=...) to load one and follow it.")
    return "\n".join(lines)


def _get(p: dict) -> str:
    name = (p.get("name") or p.get("query") or "").strip()
    skills = _load()
    s = _find_by_name(skills, name)
    if not s:  # fall back to best fuzzy match
        ranked = sorted(((_score(x, name), x) for x in skills),
                        key=lambda t: t[0], reverse=True)
        s = ranked[0][1] if ranked and ranked[0][0] > 0 else None
    if not s:
        return f"I don't have a skill called '{name}', sir."
    s["uses"] = s.get("uses", 0) + 1
    s["last_used"] = datetime.now().isoformat(timespec="seconds")
    _save_all(skills)
    return (f"Skill: {s['name']}\n{s.get('description', '')}\n"
            f"{'-' * 40}\n{s['content']}\n{'-' * 40}\n"
            "Follow these steps. If you find a better way, save the skill again to improve it.")


def _list(p: dict) -> str:
    skills = _load()
    if not skills:
        return "I haven't learned any skills yet, sir."
    skills = sorted(skills, key=lambda s: s.get("uses", 0), reverse=True)
    lines = [f"I know {len(skills)} skill(s):"]
    for s in skills:
        lines.append(f"- {s['name']} — {s.get('description', '')[:70]} "
                     f"({s.get('uses', 0)}x, rev {s.get('revisions', 1)})")
    return "\n".join(lines)


def _delete(p: dict) -> str:
    name = (p.get("name") or "").strip()
    skills = _load()
    s = _find_by_name(skills, name)
    if not s:
        return f"No skill named '{name}' to forget, sir."
    skills.remove(s)
    _save_all(skills)
    return f"Forgotten the skill '{name}', sir."


_ACTIONS = {
    "save": _save, "learn": _save,
    "find": _find, "search": _find,
    "get": _get, "use": _get,
    "list": _list, "all": _list,
    "delete": _delete, "forget": _delete,
}


def skills(parameters: dict = None, response=None, player=None,
           session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = (p.get("action", "find") or "find").lower().strip()
    if player:
        player.write_log(f"[skills] {action} {p.get('name', p.get('query', ''))}".strip())
    fn = _ACTIONS.get(action)
    if not fn:
        return (f"Unknown skills action '{action}'. Use save, find, get, list, or delete.")
    try:
        return fn(p)
    except Exception as e:
        return f"Skills operation failed, sir: {e}"
