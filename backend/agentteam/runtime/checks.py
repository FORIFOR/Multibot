"""Registered programmatic checks. Every result is bound to a concrete artifact revision by the caller."""
from __future__ import annotations

import json
import asyncio
import base64
import sys
import os
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


def json_schema_check(data: bytes, schema: dict[str, Any] | None, input_format: str = "json") -> dict[str, Any]:
    from jsonschema import Draft202012Validator
    if not schema:
        return {"status": "blocked", "problems": ["args.schema is required"]}
    def external_reference(value):
        if isinstance(value, dict):
            if any(key in value for key in ('$id', '$dynamicRef', '$recursiveRef')):
                return True
            ref = value.get('$ref')
            if ref is not None and (not isinstance(ref, str) or not (ref == '#' or ref.startswith('#/'))):
                return True
            return any(external_reference(v) for v in value.values())
        return isinstance(value, list) and any(external_reference(v) for v in value)
    if external_reference(schema):
        return {'status': 'blocked', 'problems': ['schema identifiers and non-local/dynamic references are not allowed']}
    try:
        if input_format not in ("json", "text"):
            return {"status": "blocked", "problems": ["unsupported input_format"]}
        text = data.decode("utf-8")
        doc = text if input_format == "text" else json.loads(text)
    except Exception as e:
        return {"status": "fail", "problems": [f"invalid {'UTF-8 text' if input_format == 'text' else 'JSON'}: {e}"]}
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
    except Exception as exc:
        # A model-supplied schema is untrusted input. Keep malformed schema
        # errors bounded and explicit instead of leaking a worker traceback.
        return {"status": "blocked", "problems": [f"invalid schema: {type(exc).__name__}"]}
    errs = []
    for e in validator.iter_errors(doc):
        message = e.message
        if isinstance(e.instance, str) and e.validator in ('minLength', 'maxLength'):
            message = f"text length {len(e.instance)} is too {'long' if e.validator == 'maxLength' else 'short'} ({e.validator}={e.validator_value})"
            if e.validator == 'maxLength':
                message += f"; remove at least {len(e.instance) - e.validator_value} characters. Condense repeated or nonessential details without changing source conditions."
        errs.append(f"{'/'.join(str(x) for x in e.path) or '$'}: {message}")
        if len(errs) >= 20:
            break
    result = {"status": "pass" if not errs else "fail", "problems": errs[:20]}
    if input_format == "text":
        result.update(unicode_code_points=len(text), utf8_bytes=len(data))
    return result


def python_syntax(data: bytes, filename: str = "artifact.py") -> dict[str, Any]:
    try:
        compile(data.decode("utf-8"), filename, "exec")
        return {"status": "pass"}
    except SyntaxError as e:
        return {"status": "fail", "problems": [f"{filename}:{e.lineno}: {e.msg}"]}


def html_links(data: bytes, *, allowed_hosts: list[str] | None = None) -> dict[str, Any]:
    """Internal anchors resolve to an id; external links only to allowed hosts (if given); no localhost links."""
    text = data.decode("utf-8", errors="replace")
    ids = set(re.findall(r'\sid=["\']([^"\']+)["\']', text))
    hrefs = re.findall(r'href=["\']([^"\']*)["\']', text)
    problems = []
    for h in hrefs:
        if h.startswith("#") and len(h) > 1 and h[1:] not in ids:
            problems.append(f"anchor {h} has no target id")
        elif re.match(r"https?://(localhost|127\.0\.0\.1)", h):
            problems.append(f"localhost link: {h}")
        elif allowed_hosts and re.match(r"https?://", h):
            host = re.sub(r"^https?://([^/]+).*$", r"\1", h)
            if not any(host == a or host.endswith("." + a) for a in allowed_hosts):
                problems.append(f"external host not allowed: {host}")
    return {"status": "pass" if not problems else "fail", "links": len(hrefs), "anchors": len(ids), "problems": problems[:20]}


def file_size_max(data: bytes, max_bytes: int) -> dict[str, Any]:
    return {"status": "pass" if len(data) <= max_bytes else "fail", "bytes": len(data), "max_bytes": max_bytes,
            "problems": [] if len(data) <= max_bytes else [f"{len(data)} bytes > {max_bytes}"]}


def regex_count(data: bytes, pattern: str, min_count: int = 1, max_count: int | None = None) -> dict[str, Any]:
    text = data.decode("utf-8", errors="replace")
    n = len(re.findall(pattern, text, flags=re.M))
    ok = n >= min_count and (max_count is None or n <= max_count)
    return {"status": "pass" if ok else "fail", "count": n, "problems": [] if ok else [f"{n} matches of /{pattern}/ (want {min_count}..{max_count if max_count is not None else '∞'})"]}


CHECK_KINDS = {
    "html_basic": "HTML: title, viewport, headings, empty links, alt text, script count",
    "html_links": "HTML: internal anchors resolve; no localhost links; optional args.allowed_hosts for external links",
    "json_schema": "JSON validates against args.schema (JSON Schema)",
    "python_syntax": "Python source compiles",
    "file_size_max": "Artifact is at most args.max_bytes",
    "regex_count": "Occurrences of args.pattern between args.min_count (default 1) and args.max_count",
    "json_valid": "JSON parses",
    "markdown_basic": "Markdown: headings present; optional required sections (args.sections)",
    "text_contains": "All args.needles occur exactly in raw UTF-8 text, including Markdown markers, whitespace and punctuation; not rendered text or semantic coverage",
    "text_not_contains": "None of args.needles occur exactly in raw UTF-8 text, including Markdown markers, whitespace and punctuation; not semantic absence",
    "command": "Run args.command in the task workspace sandbox; pass iff exit code 0",
}


async def isolated_check(kind, data, args):
    data = data or b''
    if len(data) > 2_000_000 or len(json.dumps(args).encode()) > 100_000:
        return {'status': 'blocked', 'problems': ['validation input exceeds supported size']}
    process = await asyncio.create_subprocess_exec(sys.executable, '-I', str(Path(__file__).with_name('check_worker.py')),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        env={'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1'})
    try:
        raw, _ = await asyncio.wait_for(process.communicate(json.dumps({'kind': kind, 'data': base64.b64encode(data).decode(), 'args': args}).encode()), timeout=5)
        if process.returncode != 0 or len(raw) > 65536:
            return {'status': 'blocked', 'problems': ['validation worker exceeded its resource limit or failed']}
        return json.loads(raw)
    except asyncio.TimeoutError:
        return {'status': 'blocked', 'problems': ['validation worker timed out']}
    finally:
        if process.returncode is None:
            process.kill(); await process.wait()


async def run_check(kind: str, data: bytes | None, args: dict[str, Any], workspace: Path | None, *, require_container=False) -> dict[str, Any]:
    if kind in ('json_schema', 'regex_count'):
        return await isolated_check(kind, data, args)
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
    if kind == "html_links":
        return html_links(data or b"", allowed_hosts=args.get("allowed_hosts"))
    if kind == "python_syntax":
        return python_syntax(data or b"", str(args.get("filename") or "artifact.py"))
    if kind == "file_size_max":
        return file_size_max(data or b"", int(args.get("max_bytes") or 1_000_000))
    if kind == "command":
        if workspace is None:
            return {"status": "blocked", "problems": ["no workspace for command check"]}
        r = await run_command(str(args.get("command") or "true"), workspace, timeout=float(args.get("timeout") or 120), require_container=require_container)
        status = "blocked" if r.denied else ("fail" if r.timed_out or r.exit_code != 0 else "pass")
        return {"status": status, "backend": r.backend, "exit_code": r.exit_code, "stdout": r.stdout, "stderr": r.stderr,
                "timed_out": r.timed_out, "reason": r.reason}
    return {"status": "blocked", "problems": [f"unknown check kind {kind}; known: {', '.join(CHECK_KINDS)}"]}
