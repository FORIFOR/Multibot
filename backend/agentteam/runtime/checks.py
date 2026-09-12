"""Registered programmatic checks. Every result is bound to a concrete artifact revision by the caller."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .sandbox import run_command


class _HTMLAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self.links: list[str] = []
        self.scripts = 0
        self.has_viewport = False
        self.headings = 0
        self.images_without_alt = 0
        self.inline_handlers = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "a":
            self.links.append(a.get("href") or "")
        elif tag == "script":
            self.scripts += 1
        elif tag == "meta" and (a.get("name") or "").lower() == "viewport":
            self.has_viewport = True
        elif tag in ("h1", "h2", "h3"):
            self.headings += 1
        elif tag == "img" and not a.get("alt"):
            self.images_without_alt += 1
        if any(k.lower().startswith("on") for k in a):
            self.inline_handlers += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def html_basic(data: bytes) -> dict[str, Any]:
    text = data.decode("utf-8", errors="replace")
    p = _HTMLAudit()
    p.feed(text)
    empty_links = [h for h in p.links if h in ("", "#")]
    problems = []
    if not p.title.strip():
        problems.append("missing <title>")
    if not p.has_viewport:
        problems.append("missing viewport meta (mobile)")
    if empty_links:
        problems.append(f"{len(empty_links)} link(s) with empty or '#' href")
    if p.headings == 0:
        problems.append("no headings")
    if p.images_without_alt:
        problems.append(f"{p.images_without_alt} image(s) without alt")
    return {"status": "pass" if not problems else "fail", "title": p.title.strip(), "links": len(p.links),
            "empty_links": len(empty_links), "scripts": p.scripts, "inline_handlers": p.inline_handlers,
            "viewport": p.has_viewport, "headings": p.headings, "problems": problems}


def json_valid(data: bytes) -> dict[str, Any]:
    try:
        json.loads(data.decode("utf-8"))
        return {"status": "pass"}
    except Exception as e:
        return {"status": "fail", "problems": [f"invalid JSON: {e}"]}


def markdown_basic(data: bytes, *, require_sections: list[str] | None = None) -> dict[str, Any]:
    text = data.decode("utf-8", errors="replace")
    headings = re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.M)
    problems = []
    if not headings:
        problems.append("no markdown headings")
    for s in require_sections or []:
        if not any(s.lower() in h.lower() for h in headings):
            problems.append(f"missing section: {s}")
    urls = re.findall(r"https?://[^\s)>\]]+", text)
    return {"status": "pass" if not problems else "fail", "headings": headings[:20], "urls": len(urls),
            "chars": len(text), "problems": problems}


def text_contains(data: bytes, needles: list[str]) -> dict[str, Any]:
    text = data.decode("utf-8", errors="replace")
    missing = [n for n in needles if n not in text]
    return {"status": "pass" if not missing else "fail", "missing": missing}


def text_not_contains(data: bytes, needles: list[str]) -> dict[str, Any]:
    text = data.decode("utf-8", errors="replace")
    found = [n for n in needles if n in text]
    return {"status": "pass" if not found else "fail", "found": found}


CHECK_KINDS = {
    "html_basic": "HTML: title, viewport, headings, empty links, alt text, script count",
    "json_valid": "JSON parses",
    "markdown_basic": "Markdown: headings present; optional required sections (args.sections)",
    "text_contains": "All args.needles present in the text",
    "text_not_contains": "None of args.needles present in the text",
    "command": "Run args.command in the task workspace sandbox; pass iff exit code 0",
}


async def run_check(kind: str, data: bytes | None, args: dict[str, Any], workspace: Path | None) -> dict[str, Any]:
    if kind == "html_basic":
        return html_basic(data or b"")
    if kind == "json_valid":
        return json_valid(data or b"")
    if kind == "markdown_basic":
        return markdown_basic(data or b"", require_sections=args.get("sections"))
    if kind == "text_contains":
        return text_contains(data or b"", list(args.get("needles") or []))
    if kind == "text_not_contains":
        return text_not_contains(data or b"", list(args.get("needles") or []))
    if kind == "command":
        if workspace is None:
            return {"status": "blocked", "problems": ["no workspace for command check"]}
        r = await run_command(str(args.get("command") or "true"), workspace, timeout=float(args.get("timeout") or 120))
        status = "blocked" if r.denied else ("fail" if r.timed_out or r.exit_code != 0 else "pass")
        return {"status": status, "backend": r.backend, "exit_code": r.exit_code, "stdout": r.stdout, "stderr": r.stderr,
                "timed_out": r.timed_out, "reason": r.reason}
    return {"status": "blocked", "problems": [f"unknown check kind {kind}; known: {', '.join(CHECK_KINDS)}"]}
