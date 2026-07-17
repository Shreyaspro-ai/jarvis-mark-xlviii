# -*- coding: utf-8 -*-
"""WhatsApp for JARVIS — scrape the contact list, match properly, then send.

Why this exists: actions/send_message.py drives WhatsApp blind. It hits Ctrl+F,
types a name and presses Enter on whatever happens to be highlighted — it never
checks WHO it selected. Ask for "srinivas 2" and it will happily send to
"Srinivas 25". It also injects real keystrokes, so it fights the user for the
keyboard.

This module instead scrapes WhatsApp Web's DOM with Playwright:
  * every chat row is read out of the page, by name
  * exact match wins (case/space-insensitive)
  * no exact match -> the most similar name, scored, and reported
  * the chat header is VERIFIED to be the intended contact before typing
  * Playwright types into the page, not the OS, so it never steals your keyboard

Why not mitmproxy: WhatsApp pins certificates and wraps everything in the Noise
protocol with end-to-end encryption. You'd capture ciphertext you can't replay.
The DOM is the honest interface.

Actions: status | contacts | find | send
"""
from __future__ import annotations

import difflib
import re
import sys
import unicodedata
from pathlib import Path

WA_URL = "https://web.whatsapp.com/"
NAV_TIMEOUT = 60_000
SETTLE = 2_500


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE = _base_dir()
PROFILE = BASE / "memory" / "whatsapp-profile"      # keeps the QR login


# ----------------------------------------------------------------- matching
def _norm(s: str) -> str:
    """Fold case, accents and runs of whitespace so 'Srinivas  2' == 'srinivas 2'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _score(query: str, name: str) -> float:
    q, n = _norm(query), _norm(name)
    if not q or not n:
        return 0.0
    if q == n:
        return 1.0
    base = difflib.SequenceMatcher(None, q, n).ratio()
    # a name that starts with / contains the query is a better hit than raw ratio
    if n.startswith(q):
        base = max(base, 0.94)
    elif q in n:
        base = max(base, 0.88)
    return base


def rank(query: str, names: list[str]) -> list[tuple[str, float]]:
    """Every candidate, best first. Exact matches (score 1.0) come first."""
    scored = [(n, _score(query, n)) for n in dict.fromkeys(names) if n.strip()]
    scored.sort(key=lambda t: (-t[1], len(t[0])))
    return scored


# ----------------------------------------------------------------- browser
def _open(p, headless: bool):
    PROFILE.mkdir(parents=True, exist_ok=True)
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE),
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
        viewport={"width": 1280, "height": 860},
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(20_000)
    page.goto(WA_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    page.wait_for_timeout(SETTLE)
    return ctx, page


def _logged_in(page) -> bool:
    for sel in ('div[aria-label="Chat list"]', '#pane-side', '[data-testid="chat-list"]'):
        try:
            if page.locator(sel).count():
                return True
        except Exception:
            pass
    return False


def _needs_qr(page) -> bool:
    for sel in ('canvas[aria-label*="scan"]', 'div[data-ref]', 'canvas'):
        try:
            if page.locator(sel).count():
                return True
        except Exception:
            pass
    return False


def _search_box(page):
    for sel in ('div[contenteditable="true"][data-tab="3"]',
                'div[aria-label="Search input textbox"]',
                'p.selectable-text[contenteditable="true"]',
                'div[contenteditable="true"]'):
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def _scrape_rows(page) -> list[str]:
    """Read the visible chat/contact rows out of the DOM."""
    names: list[str] = []
    try:
        names = page.eval_on_selector_all(
            '#pane-side [role="listitem"], div[aria-label="Chat list"] [role="listitem"]',
            """rows => rows.map(r => {
                   const t = r.querySelector('span[title]');
                   if (t && t.getAttribute('title')) return t.getAttribute('title');
                   const d = r.querySelector('span[dir="auto"]');
                   return d ? d.textContent : '';
               }).filter(Boolean)"""
        )
    except Exception:
        pass
    if not names:                       # fallback: any titled span in the left pane
        try:
            names = page.eval_on_selector_all(
                '#pane-side span[title]',
                "els => els.map(e => e.getAttribute('title')).filter(Boolean)")
        except Exception:
            names = []
    # de-dupe, keep order
    return list(dict.fromkeys(n.strip() for n in names if n and n.strip()))


def _search(page, query: str) -> list[str]:
    box = _search_box(page)
    if box is None:
        return _scrape_rows(page)
    try:
        box.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        box.type(query, delay=25)
        page.wait_for_timeout(1_800)
    except Exception:
        pass
    return _scrape_rows(page)


def _open_chat(page, name: str) -> bool:
    """Click the row whose title is exactly `name`, then confirm the header."""
    try:
        row = page.locator(f'#pane-side span[title="{name}"]').first
        if not row.count():
            row = page.get_by_title(name, exact=True).first
        row.click()
        page.wait_for_timeout(1_500)
    except Exception:
        return False
    return _header_name(page) is not None


def _header_name(page) -> str | None:
    for sel in ('header span[title]', '[data-testid="conversation-info-header"] span[title]'):
        try:
            loc = page.locator(sel).first
            if loc.count():
                return (loc.get_attribute("title") or "").strip() or None
        except Exception:
            continue
    return None


def _message_box(page):
    for sel in ('footer div[contenteditable="true"][data-tab="10"]',
                'div[aria-label="Type a message"]',
                'footer div[contenteditable="true"]'):
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible():
                return loc
        except Exception:
            continue
    return None


# ----------------------------------------------------------------- entry
def whatsapp(parameters: dict | None = None, response=None, player=None,
             session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = (p.get("action") or "send").strip().lower()
    contact = (p.get("contact") or p.get("receiver") or "").strip()
    message = (p.get("message") or "").strip()
    headless = str(p.get("headless", "false")).lower() in ("true", "1", "yes")
    threshold = float(p.get("threshold") or 0.55)

    if action in ("send", "find") and not contact:
        return "Which contact? Give me a name."
    if action == "send" and not message:
        return "What should I say?"

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return "Playwright isn't installed. Run: pip install playwright && playwright install chromium"

    try:
        with sync_playwright() as pw:
            ctx, page = _open(pw, headless)
            try:
                if not _logged_in(page):
                    if _needs_qr(page):
                        return ("WhatsApp Web needs a one-time login. A browser window is open — "
                                "scan the QR code with your phone (WhatsApp > Linked devices), "
                                "then ask me again. I'll stay logged in after that.")
                    return "WhatsApp Web didn't finish loading. Try again in a moment."

                if action == "status":
                    rows = _scrape_rows(page)
                    return (f"WhatsApp Web is logged in. {len(rows)} chats visible in the list.\n"
                            + "\n".join(f"  {n}" for n in rows[:10]))

                if action == "contacts":
                    rows = _scrape_rows(page)
                    if not rows:
                        return "Couldn't read the chat list."
                    return (f"{len(rows)} chats visible:\n" +
                            "\n".join(f"  {n}" for n in rows[:40]))

                # --- find / send both start with a real search + scrape ---
                names = _search(page, contact)
                if not names:
                    return f"No chats or contacts came back for '{contact}'."

                ranked = rank(contact, names)
                exact = [n for n, s in ranked if s >= 0.999]

                if action == "find":
                    lines = [f"  {s*100:5.1f}%  {n}" for n, s in ranked[:8]]
                    head = (f"Exact match for '{contact}': {', '.join(exact)}"
                            if exact else
                            f"No exact match for '{contact}'. Closest:")
                    return head + "\n" + "\n".join(lines)

                # --- send ---
                if exact:
                    target, score, why = exact[0], 1.0, "exact match"
                    if len(exact) > 1:
                        return (f"'{contact}' matches {len(exact)} chats exactly: "
                                f"{', '.join(exact)}. Which one?")
                else:
                    target, score = ranked[0]
                    if score < threshold:
                        close = ", ".join(f"{n} ({s*100:.0f}%)" for n, s in ranked[:3])
                        return (f"No contact called '{contact}'. Nothing close enough either — "
                                f"best guesses: {close}. Tell me which and I'll send it.")
                    why = f"closest match, {score*100:.0f}%"

                if not _open_chat(page, target):
                    return f"Found '{target}' but couldn't open the chat."

                header = _header_name(page)
                if header and _norm(header) != _norm(target):
                    return (f"Refusing to send: I clicked '{target}' but the chat that opened is "
                            f"'{header}'. Not risking the wrong person.")

                box = _message_box(page)
                if box is None:
                    return f"Opened '{target}' but couldn't find the message box."
                box.click()
                box.type(message, delay=15)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1_200)

                note = "" if score >= 0.999 else f" (you asked for '{contact}' — {why})"
                return f"Sent \"{message}\" to {target}{note}."
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
    except Exception as e:
        return f"WhatsApp automation failed: {type(e).__name__}: {e}"
