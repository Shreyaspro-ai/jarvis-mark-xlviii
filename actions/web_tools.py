# -*- coding: utf-8 -*-
"""Web archiving, mirroring and analysis tools for JARVIS.

Wraps well-known open-source projects. JARVIS shells out to each; none of them
are imported into JARVIS's own venv, so their dependency trees stay isolated.

  archive      SingleFile CLI        github.com/gildas-lormeau/single-file-cli
  mirror       node-website-scraper  github.com/website-scraper/node-website-scraper
  crawl        Scrapy                github.com/scrapy/scrapy
  firecrawl    Firecrawl             github.com/firecrawl/firecrawl   (API key)
  intercept    mitmproxy / mitmdump  github.com/mitmproxy/mitmproxy
  to_openapi   mitmproxy2swagger     github.com/alextanhongpin/mitmproxy2swagger
  beautify     js-beautify           (unpack minified JS)
  format       Prettier              github.com/prettier/prettier
  obfuscate    javascript-obfuscator github.com/javascript-obfuscator/javascript-obfuscator

Intended for archiving pages you want offline, reading your own site's output,
and debugging traffic you are authorised to inspect.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 300


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE = _base_dir()
TOOLS = BASE / "tools"
OUT_ROOT = BASE / "memory" / "web"
_WIN = sys.platform == "win32"


def _web_venv_bin(name: str) -> str | None:
    """Executable inside the dedicated web-tools venv, if present."""
    sub = "Scripts" if _WIN else "bin"
    ext = ".exe" if _WIN else ""
    p = TOOLS / ".venv-web" / sub / f"{name}{ext}"
    if p.exists():
        return str(p)
    return shutil.which(name)


def _node_bin(name: str) -> str | None:
    return shutil.which(name) or shutil.which(f"{name}.cmd")


def _run(cmd: list[str], timeout: int = TIMEOUT, cwd: str | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=cwd, encoding="utf-8", errors="replace")
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except FileNotFoundError:
        return 127, f"not installed: {cmd[0]}"
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"


def _outdir(name: str) -> Path:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    return OUT_ROOT / name


def _slug(url: str) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in url.split("//")[-1])
    return keep.strip("-")[:60] or "page"


# ---------------------------------------------------------------- archive
def _archive(url: str, out: str | None) -> str:
    exe = _node_bin("single-file")
    if not exe:
        return "SingleFile CLI not installed (npm i -g single-file-cli)."
    dest = Path(out) if out else _outdir(f"{_slug(url)}.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    rc, log = _run([exe, url, str(dest), "--browser-headless=true"])
    if dest.exists() and dest.stat().st_size > 0:
        kb = dest.stat().st_size / 1024
        return f"Archived {url} -> {dest} ({kb:.0f} KB, single self-contained HTML)."
    return f"SingleFile failed (rc={rc}).\n{log[:400]}"


# ---------------------------------------------------------------- mirror
def _mirror(url: str, out: str | None, depth: int, max_res: int) -> str:
    node = shutil.which("node")
    script = TOOLS / "site-mirror.js"
    if not node or not script.exists():
        return "node-website-scraper wrapper missing (run: cd tools && npm install)."
    dest = Path(out) if out else _outdir(_slug(url))
    rc, log = _run([node, str(script), "--url", url, "--out", str(dest),
                    "--depth", str(depth), "--max", str(max_res)], cwd=str(TOOLS))
    for line in log.splitlines()[::-1]:
        line = line.strip()
        if line.startswith("{"):
            try:
                d = json.loads(line)
            except Exception:
                break
            if d.get("ok"):
                return (f"Mirrored {url} -> {dest} "
                        f"({d.get('pages')} page(s), {d.get('resources')} resources, depth {depth}).")
            return f"Mirror failed: {d.get('error')}"
    return f"Mirror failed (rc={rc}).\n{log[:400]}"


# ---------------------------------------------------------------- crawl
def _crawl(url: str, out: str | None, max_pages: int) -> str:
    exe = _web_venv_bin("scrapy")
    if not exe:
        return "Scrapy not installed (tools/.venv-web)."
    dest = Path(out) if out else _outdir(f"{_slug(url)}.jsonl")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    # one-off spider, no project scaffolding needed
    rc, log = _run([
        exe, "runspider", str(TOOLS / "quick_spider.py"),
        "-a", f"start={url}", "-a", f"maxpages={max_pages}",
        "-o", str(dest), "-s", "LOG_LEVEL=ERROR", "-s", "ROBOTSTXT_OBEY=True",
    ])
    if dest.exists() and dest.stat().st_size:
        n = sum(1 for _ in dest.open(encoding="utf-8", errors="replace"))
        return f"Crawled {url} -> {dest} ({n} pages, robots.txt respected)."
    return f"Crawl produced nothing (rc={rc}).\n{log[:400]}"


# ---------------------------------------------------------------- firecrawl
def _firecrawl(url: str, mode: str) -> str:
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        try:
            cfg = json.load(open(BASE / "config" / "api_keys.json", encoding="utf-8"))
            key = cfg.get("firecrawl_api_key")
        except Exception:
            key = None
    if not key:
        return ("Firecrawl needs an API key. Add \"firecrawl_api_key\" to config/api_keys.json "
                "or set FIRECRAWL_API_KEY. (Self-hosting needs Docker + Redis.)")
    try:
        import requests
        r = requests.post(
            f"https://api.firecrawl.dev/v1/{'crawl' if mode == 'crawl' else 'scrape'}",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"url": url}, timeout=90,
        )
        if r.status_code >= 400:
            return f"Firecrawl error {r.status_code}: {r.text[:200]}"
        data = r.json()
        md = (data.get("data") or {}).get("markdown") or json.dumps(data)[:1500]
        return f"Firecrawl ({mode}) {url}:\n{md[:2500]}"
    except Exception as e:
        return f"Firecrawl failed: {e}"


# ---------------------------------------------------------------- intercept
def _intercept(port: int, seconds: int, out: str | None) -> str:
    exe = _web_venv_bin("mitmdump")
    if not exe:
        return "mitmproxy not installed (tools/.venv-web)."
    dest = Path(out) if out else _outdir("capture.mitm")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-q", "--listen-port", str(port), "-w", str(dest)]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return f"Could not start mitmdump: {e}"
    try:
        p.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()
    size = dest.stat().st_size if dest.exists() else 0
    return (f"Captured {seconds}s of traffic on port {port} -> {dest} ({size/1024:.0f} KB).\n"
            f"Point the client at proxy 127.0.0.1:{port}. HTTPS needs mitmproxy's CA "
            f"installed (http://mitm.it while the proxy runs) — only do that on a machine "
            f"and traffic you're authorised to inspect.")


def _to_openapi(capture: str, out: str | None, base_url: str) -> str:
    exe = _web_venv_bin("mitmproxy2swagger")
    if not exe:
        return "mitmproxy2swagger not installed (tools/.venv-web)."
    src = Path(capture)
    if not src.exists():
        return f"No capture at {src}"
    dest = Path(out) if out else src.with_suffix(".openapi.yaml")
    rc, log = _run([exe, "-i", str(src), "-o", str(dest), "-p", base_url or "http://localhost", "-f", "flow"])
    if dest.exists():
        return (f"OpenAPI spec -> {dest}\nRe-run after un-commenting the 'ignore:' paths "
                f"in the file to flesh out the schema.")
    return f"mitmproxy2swagger failed (rc={rc}).\n{log[:400]}"


# ---------------------------------------------------------------- js
def _beautify(target: str, out: str | None) -> str:
    exe = _node_bin("js-beautify")
    if not exe:
        return "js-beautify not installed (npm i -g js-beautify)."
    src = Path(target)
    if not src.exists():
        return f"No such file: {src}"
    dest = Path(out) if out else src.with_suffix(".beautified" + src.suffix)
    rc, log = _run([exe, str(src), "-o", str(dest)])
    if dest.exists():
        return f"Unpacked {src.name} -> {dest} ({dest.stat().st_size/1024:.0f} KB readable)."
    return f"js-beautify failed (rc={rc}).\n{log[:300]}"


def _format(target: str) -> str:
    exe = _node_bin("prettier")
    if not exe:
        return "Prettier not installed (npm i -g prettier)."
    src = Path(target)
    if not src.exists():
        return f"No such file: {src}"
    rc, log = _run([exe, "--write", str(src)])
    return f"Prettier formatted {src.name}." if rc == 0 else f"Prettier failed:\n{log[:300]}"


def _obfuscate(target: str, out: str | None) -> str:
    node = shutil.which("node")
    if not node:
        return "node not found."
    src = Path(target)
    if not src.exists():
        return f"No such file: {src}"
    dest = Path(out) if out else src.with_suffix(".obf" + src.suffix)
    script = (
        "import ob from 'javascript-obfuscator';"
        "import {readFileSync,writeFileSync} from 'node:fs';"
        f"const c=readFileSync({json.dumps(str(src))},'utf8');"
        "const r=ob.obfuscate(c,{compact:true,controlFlowFlattening:false});"
        f"writeFileSync({json.dumps(str(dest))}, r.getObfuscatedCode());"
        "console.log('ok');"
    )
    rc, log = _run([node, "--input-type=module", "-e", script], cwd=str(TOOLS))
    if dest.exists():
        return f"Obfuscated {src.name} -> {dest}."
    return f"javascript-obfuscator failed (rc={rc}).\n{log[:300]}"


# ---------------------------------------------------------------- entry
_ACTIONS = ("archive", "mirror", "crawl", "firecrawl", "intercept",
            "to_openapi", "beautify", "format", "obfuscate", "status")


def web_tools(parameters: dict | None = None, response=None, player=None,
              session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = (p.get("action") or "archive").strip().lower()
    url = (p.get("url") or "").strip()
    target = (p.get("path") or "").strip()
    out = (p.get("out") or "").strip() or None

    if action == "status":
        rows = [
            ("SingleFile (archive)", _node_bin("single-file")),
            ("website-scraper (mirror)", str(TOOLS / "site-mirror.js") if (TOOLS / "site-mirror.js").exists() else None),
            ("Scrapy (crawl)", _web_venv_bin("scrapy")),
            ("mitmproxy (intercept)", _web_venv_bin("mitmdump")),
            ("mitmproxy2swagger", _web_venv_bin("mitmproxy2swagger")),
            ("js-beautify", _node_bin("js-beautify")),
            ("Prettier", _node_bin("prettier")),
            ("javascript-obfuscator", "bundled in tools/" if (TOOLS / "node_modules" / "javascript-obfuscator").exists() else None),
        ]
        return "Web tools:\n" + "\n".join(
            f"  {'OK  ' if v else 'MISS'} {k}" for k, v in rows)

    if action in ("archive", "mirror", "crawl", "firecrawl") and not url:
        return f"Need a url for action='{action}'."
    if action in ("beautify", "format", "obfuscate") and not target:
        return f"Need a path for action='{action}'."

    if action == "archive":
        return _archive(url, out)
    if action == "mirror":
        return _mirror(url, out, int(p.get("depth") or 1), int(p.get("max") or 200))
    if action == "crawl":
        return _crawl(url, out, int(p.get("max") or 50))
    if action == "firecrawl":
        return _firecrawl(url, (p.get("mode") or "scrape").lower())
    if action == "intercept":
        return _intercept(int(p.get("port") or 8080), int(p.get("seconds") or 30), out)
    if action == "to_openapi":
        return _to_openapi(target or str(_outdir("capture.mitm")), out, (p.get("base_url") or "").strip())
    if action == "beautify":
        return _beautify(target, out)
    if action == "format":
        return _format(target)
    if action == "obfuscate":
        return _obfuscate(target, out)

    return f"Unknown action '{action}'. Use one of: {', '.join(_ACTIONS)}."
