"""web_fetch with SSRF guard and web_search (best-effort DuckDuckGo HTML; no API key)."""
from __future__ import annotations

import html
import asyncio
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import quote_plus, urlparse, urljoin

import httpcore
import httpx
from bs4 import BeautifulSoup

MAX_BYTES = 2_000_000
UA = "AgentTeam/0.1 (+https://github.com/; research fetch)"


class FetchDenied(Exception):
    pass


def _is_private_host(host: str) -> bool:
    host = host.lower().rstrip('.')
    if host in ("localhost", "metadata.google.internal") or host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise FetchDenied(f"cannot resolve host {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not _public_ip(ip):
            return True
    return False


def _public_ip(ip):
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def _validate_url(url: str):
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise FetchDenied(f"scheme {u.scheme!r} not allowed")
    if not u.hostname:
        raise FetchDenied("missing host")
    if u.username or u.password:
        raise FetchDenied("credentials in URL not allowed")
    if u.port not in (None, 80, 443):
        raise FetchDenied('research fetch permits only HTTP(S) ports 80 and 443')
    host = u.hostname.lower().rstrip('.')
    if host in ('localhost', 'metadata.google.internal') or host.endswith(('.local', '.internal')) or '%' in host:
        raise FetchDenied('local or metadata host is not allowed')
    return u


def check_url(url: str) -> None:
    u = _validate_url(url)
    if _is_private_host(u.hostname):
        raise FetchDenied(f"host {u.hostname} resolves to a private/loopback/metadata address")


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve immediately before connection and dial only a validated numeric IP.

    HTTPCore retains the original origin for Host, TLS SNI and certificate checks.
    DNS cannot substitute another address between validation and TCP connection.
    """
    def __init__(self):
        self.backend = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            infos = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            raise FetchDenied('cannot resolve research host') from None
        addresses = list(dict.fromkeys(info[4][0] for info in infos))
        if not addresses or any(not _public_ip(ipaddress.ip_address(ip)) for ip in addresses):
            raise FetchDenied('research host resolves to a non-public address')
        last_error = None
        for ip in addresses:
            try:
                return await self.backend.connect_tcp(ip, port, timeout=timeout, local_address=local_address, socket_options=socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        raise last_error

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class _ResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        async for chunk in self.stream:
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


class PublicTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.pool = httpcore.AsyncConnectionPool(network_backend=PublicNetworkBackend(), max_connections=2, retries=0)

    async def handle_async_request(self, request):
        response = await self.pool.handle_async_request(httpcore.Request(method=request.method,
            url=httpcore.URL(scheme=request.url.raw_scheme, host=request.url.raw_host, port=request.url.port, target=request.url.raw_path),
            headers=request.headers.raw, content=request.stream, extensions=request.extensions))
        return httpx.Response(response.status, headers=response.headers, stream=_ResponseStream(response.stream), extensions=response.extensions)

    async def aclose(self):
        await self.pool.aclose()


async def _fetch_response(url, *, timeout):
    current = url
    async with asyncio.timeout(timeout), httpx.AsyncClient(transport=PublicTransport(), timeout=timeout, trust_env=False,
            follow_redirects=False, headers={'user-agent': UA, 'accept-encoding': 'identity'}) as client:
        for _ in range(5):
            _validate_url(current)
            async with client.stream('GET', current) as response:
                if response.is_redirect and response.headers.get('location'):
                    current = urljoin(current, response.headers['location'])
                    continue
                # Avoid decoding an unbounded compression expansion. Research
                # servers must honor identity encoding for this bounded reader.
                if response.headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
                    raise FetchDenied('compressed response refused; identity encoding required')
                body = bytearray()
                truncated = False
                async for chunk in response.aiter_raw(chunk_size=65536):
                    remaining = MAX_BYTES - len(body)
                    body.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        truncated = True
                        break
                return current, response.status_code, response.headers.get('content-type', ''), bytes(body), truncated
        raise FetchDenied('too many redirects')


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
    max_chars = max(1, min(max_chars, 50000))
    current, status, ctype, body, capped = await _fetch_response(url, timeout=max(1, min(timeout, 60)))
    title, text = extract_text(ctype, body, current)
    return {'url': current, 'status': status, 'content_type': ctype, 'title': title,
            'text': text[:max_chars], 'truncated': capped or len(text) > max_chars, 'bytes': len(body), 'body_limit_reached': capped}


async def web_search(query: str, *, max_results: int = 8, timeout: float = 20.0) -> dict[str, Any]:
    """Best-effort search via DuckDuckGo's HTML endpoint. Results are discovery hints, not verified facts."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    _, status, _, body, truncated = await _fetch_response(url, timeout=max(1, min(timeout, 60)))
    if status != 200:
        raise FetchDenied('search endpoint returned an unsuccessful status')
    soup = BeautifulSoup(body, "html.parser")
    results = []
    for a in soup.select("a.result__a")[:max(1, min(max_results, 20))]:
        href = a.get("href") or ""
        snippet_el = a.find_parent("div", class_="result__body")
        snippet = snippet_el.select_one(".result__snippet").get_text(" ", strip=True) if snippet_el and snippet_el.select_one(".result__snippet") else ""
        results.append({"title": html.unescape(a.get_text(" ", strip=True)), "url": href, "snippet": snippet})
    return {"query": query, "engine": "duckduckgo-html", "results": results, 'truncated': truncated,
            "note": "search results are discovery hints; fetch and verify primary sources before citing"}
