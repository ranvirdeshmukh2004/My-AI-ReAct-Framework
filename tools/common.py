"""
common.py — Shared Tool Infrastructure
=========================================
Cross-cutting concerns every tool needs, in one place:

- ``http_get`` / ``http_json``: pooled HTTP with retry + exponential backoff
- ``guard_url``: SSRF protection (blocks private/loopback/metadata addresses)
- ``ToolError``: a consistent, LLM-readable failure format
- ``truncate`` / ``format_sources``: uniform output shaping

Every network-facing tool routes through here so that timeouts, retries,
user agents and error text stay consistent across the whole toolset.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import time
import urllib.parse
from typing import Any, Iterable

import httpx

# ============================================
# Configuration
# ============================================

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 20.0
DEFAULT_RETRIES = 2

# Transient conditions worth retrying. 4xx (other than 429) means the request
# itself is wrong, so retrying only wastes the agent's step budget.
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

# Cap tool output so a single observation cannot blow the model's context.
MAX_OUTPUT_CHARS = 8000


# ============================================
# Errors
# ============================================

class ToolError(Exception):
    """
    A failure that should be reported to the model as text, not raised.

    Tools return ``str(ToolError(...))`` so the agent sees a consistent,
    actionable message and can decide to retry with different input.
    """

    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        out = f"❌ {self.message}"
        if self.hint:
            out += f"\n💡 {self.hint}"
        return out


# ============================================
# SSRF Protection
# ============================================

_BLOCKED_HOSTS = {
    "localhost", "metadata.google.internal", "metadata",
    "instance-data", "169.254.169.254",
}


# NAT64 well-known prefix (RFC 6052). On an IPv6-only or NAT64 network a
# perfectly public host resolves through this prefix, and Python flags the
# whole range as `is_reserved` — so it must be decoded to the embedded IPv4
# rather than blocked outright.
_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")


def _unwrap_v6(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """Return the IPv4 address embedded in a NAT64 or IPv4-mapped IPv6 address."""
    if ip.ipv4_mapped:
        return ip.ipv4_mapped
    if ip in _NAT64_PREFIX:
        return ipaddress.ip_address(int(ip) & 0xFFFFFFFF)
    return None


def _is_blocked_ip(ip) -> bool:
    """
    Decide whether a single resolved address is off limits.

    IPv6 translation forms are unwrapped to the IPv4 they carry, so the
    decision is made about the real destination. `is_reserved` is only
    consulted for IPv4 (where it means the unroutable 240/4 block); for
    IPv6 it covers large legitimately-routed ranges and would cause false
    positives like the NAT64 one above.
    """
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = _unwrap_v6(ip)
        if embedded is not None:
            ip = embedded
        else:
            return (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_multicast or ip.is_unspecified)

    return (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def _is_private_address(host: str) -> bool:
    """
    Resolve a hostname and report whether it lands on a non-public address.

    Blocks if *any* resolved address is internal, which is what defeats a
    DNS-rebinding attempt that mixes one public and one private answer.
    Covers loopback, RFC1918, link-local (including the cloud metadata
    endpoint at 169.254.169.254) and unique-local IPv6.
    """
    # A bare IP literal never needs resolving.
    try:
        return _is_blocked_ip(ipaddress.ip_address(host))
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # Unresolvable: let the actual request produce the error message.
        return False

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            return True
    return False


def guard_url(url: str, *, allow_private: bool = False) -> str:
    """
    Validate and normalize a user/model-supplied URL before fetching it.

    Raises ToolError for anything that is not an ordinary public http(s)
    endpoint. Without this an agent can be talked into fetching
    ``http://169.254.169.254/`` and leaking cloud credentials into its own
    context window.
    """
    url = (url or "").strip().strip("'\"")
    if not url:
        raise ToolError("No URL provided.", "Pass a URL like 'https://example.com'.")

    # Reject a non-http scheme BEFORE defaulting to https, otherwise
    # "file:///etc/passwd" would be silently rewritten into a fetchable URL.
    if "://" in url:
        scheme = url.split("://", 1)[0].lower()
        if scheme not in ("http", "https"):
            raise ToolError(
                f"Unsupported URL scheme '{scheme}'.",
                "Only http:// and https:// URLs can be fetched.",
            )
    else:
        # A leading "word:" that is not a host:port is a scheme (file:, data:,
        # javascript:). The negative lookahead keeps "example.com:8080" valid.
        scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):(?!\d)", url)
        if scheme_match:
            raise ToolError(
                f"Unsupported URL scheme '{scheme_match.group(1).lower()}'.",
                "Only http:// and https:// URLs can be fetched.",
            )
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)

    host = (parsed.hostname or "").lower()
    if not host:
        raise ToolError(f"Could not parse a hostname from '{url}'.")

    if not allow_private:
        if host in _BLOCKED_HOSTS or _is_private_address(host):
            raise ToolError(
                f"Refusing to fetch internal address '{host}'.",
                "Only public internet URLs are allowed.",
            )

    return url


# ============================================
# HTTP with retry
# ============================================

def http_get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    follow_redirects: bool = True,
    guard: bool = True,
) -> httpx.Response:
    """
    GET with exponential backoff on transient failures.

    Retries on connect/read timeouts and on retryable status codes, honouring
    a Retry-After header when the server sends one. Raises ToolError once the
    retry budget is exhausted.
    """
    if guard:
        url = guard_url(url)

    merged_headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    if headers:
        merged_headers.update(headers)

    last_error = ""
    for attempt in range(retries + 1):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=follow_redirects,
            ) as client:
                response = client.get(url, params=params, headers=merged_headers)

            if response.status_code in RETRYABLE_STATUS and attempt < retries:
                wait = _retry_after(response, attempt)
                time.sleep(wait)
                last_error = f"HTTP {response.status_code}"
                continue

            return response

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            last_error = type(exc).__name__
            if attempt < retries:
                time.sleep(min(2 ** attempt, 4))
                continue
            raise ToolError(
                f"Could not reach {urllib.parse.urlparse(url).hostname} ({last_error}).",
                "The service may be down or unreachable — try again shortly.",
            ) from exc

    raise ToolError(
        f"Request to {urllib.parse.urlparse(url).hostname} failed after "
        f"{retries + 1} attempts ({last_error}).",
    )


def http_json(url: str, **kwargs) -> Any:
    """GET and parse JSON, raising ToolError on a non-200 or malformed body."""
    response = http_get(url, **kwargs)

    if response.status_code != 200:
        raise ToolError(
            f"Request failed with HTTP {response.status_code}.",
            _status_hint(response.status_code),
        )

    try:
        return response.json()
    except Exception as exc:
        raise ToolError("The service returned a malformed JSON response.") from exc


def _retry_after(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait before a retry, preferring the server's Retry-After."""
    raw = response.headers.get("Retry-After", "")
    if raw.isdigit():
        return min(float(raw), 5.0)
    return float(min(2 ** attempt, 4))


def _status_hint(status: int) -> str:
    """A short, actionable hint for a failing status code."""
    return {
        400: "The request was malformed — check the input format.",
        401: "This endpoint needs credentials.",
        403: "Access is forbidden — the resource may be restricted.",
        404: "Not found — check the spelling or try a different query.",
        429: "Rate limited — wait a moment before retrying.",
    }.get(status, "The service may be temporarily unavailable.")


# ============================================
# Output shaping
# ============================================

def truncate(text: str, limit: int = MAX_OUTPUT_CHARS, note: str = "") -> str:
    """
    Cut text to a context-safe length, at a paragraph or line boundary when
    one is nearby, and say explicitly how much was omitted.
    """
    if len(text) <= limit:
        return text

    window = text[:limit]
    for sep in ("\n\n", "\n", ". "):
        cut = window.rfind(sep)
        if cut > limit * 0.6:
            window = window[:cut]
            break

    omitted = len(text) - len(window)
    suffix = f"\n\n… [truncated — {omitted:,} more characters"
    suffix += f"; {note}]" if note else "]"
    return window.rstrip() + suffix


def format_sources(sources: Iterable[tuple[str, str]], start: int = 1) -> str:
    """
    Build the ``[SOURCES]`` block the agent parses for citations.

    Each source is a ``(title, url)`` pair; numbering must line up with the
    ``[Source N]`` markers already embedded in the tool's text output.
    """
    lines = [f"[{i}] {title} | {url}" for i, (title, url) in enumerate(sources, start)]
    return "\n\n[SOURCES]\n" + "\n".join(lines) if lines else ""


def clean_input(raw: str, *, strip_fences: bool = False) -> str:
    """
    Normalize a model-supplied argument.

    Models routinely wrap arguments in quotes, backticks or markdown fences;
    passing those through verbatim is a common source of tool failures.
    """
    text = (raw or "").strip()

    if strip_fences and text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()

    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()

    return text
