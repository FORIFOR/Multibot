"""web_fetch with SSRF guard and web_search (best-effort DuckDuckGo HTML; no API key)."""
from __future__ import annotations

import html
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_BYTES = 2_000_000
UA = "AgentTeam/0.1 (+https://github.com/; research fetch)"


class FetchDenied(Exception):
    pass


def _is_private_host(host: str) -> bool:
    if host in ("localhost", "metadata.google.internal") or host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise FetchDenied(f"cannot resolve host {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return True
        if str(ip).startswith("169.254.") or str(ip) == "100.100.100.200":
            return True
    return False


def check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise FetchDenied(f"scheme {u.scheme!r} not allowed")
    if not u.hostname:
        raise FetchDenied("missing host")
    if u.username or u.password:
        raise FetchDenied("credentials in URL not allowed")
    if _is_private_host(u.hostname):
        raise FetchDenied(f"host {u.hostname} resolves to a private/loopback/metadata address")


def extract_text(content_type: str, body: bytes, url: str) -> tuple[str, str]:
    if "html" in content_type:
        soup = BeautifulSoup(body, "html.parser")
        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()
        title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
        text = soup.get_text("\n")
        text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
        return title, text
    return "", body.decode("utf-8", errors="replace")


async def web_fetch(url: str, *, max_chars: int = 12000, timeout: float = 30.0) -> dict[str, Any]:
    check_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers={"user-agent": UA}) as client:
        current = url
        for _ in range(5):
            r = await client.get(current)
            if r.is_redirect and r.headers.get("location"):
                current = str(r.next_request.url) if r.next_request else r.headers["location"]
                check_url(current)  # re-check every hop
                continue
            break
        else:
            raise FetchDenied("too many redirects")
        body = r.content[:MAX_BYTES]
        ctype = r.headers.get("content-type", "")
        title, text = extract_text(ctype, body, current)
        truncated = len(text) > max_chars
        return {"url": current, "status": r.status_code, "content_type": ctype, "title": title,
                "text": text[:max_chars], "truncated": truncated, "bytes": len(r.content)}


async def web_search(query: str, *, max_results: int = 8, timeout: float = 20.0) -> dict[str, Any]:
    """Best-effort search via DuckDuckGo's HTML endpoint. Results are discovery hints, not verified facts."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"user-agent": UA}) as client:
        r = await client.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for a in soup.select("a.result__a")[:max_results]:
        href = a.get("href") or ""
        snippet_el = a.find_parent("div", class_="result__body")
        snippet = snippet_el.select_one(".result__snippet").get_text(" ", strip=True) if snippet_el and snippet_el.select_one(".result__snippet") else ""
        results.append({"title": html.unescape(a.get_text(" ", strip=True)), "url": href, "snippet": snippet})
    return {"query": query, "engine": "duckduckgo-html", "results": results,
            "note": "search results are discovery hints; fetch and verify primary sources before citing"}
