"""
url_reader_tool.py — Web Page Reader
=======================================
Fetches a URL and returns clean, readable Markdown.

Improvements over naive regex scraping:
- **Real HTML parsing** via BeautifulSoup/lxml, so malformed markup, nested
  tags and inline scripts do not corrupt the extracted text.
- **Boilerplate removal** — nav, header, footer, aside, forms and cookie
  banners are dropped, then the densest content block is selected, which is
  what keeps an article's body rather than its sidebar.
- **Structure preserved** — headings, lists, links, tables and code blocks
  survive as Markdown, so the model can cite and quote precisely.
- **SSRF-guarded** — internal and metadata addresses are refused.
- **Content-type aware** — JSON, plain text and PDFs are handled rather
  than being rendered as garbage.
"""

from __future__ import annotations

import json
import re

from tools.base import Tool
from tools.common import (
    ToolError,
    clean_input,
    format_sources,
    guard_url,
    http_get,
    truncate,
)

MAX_CONTENT_CHARS = 8000
MAX_BYTES = 5 * 1024 * 1024  # refuse to parse enormous pages

# Elements that never carry article content.
_STRIP_TAGS = [
    "script", "style", "noscript", "iframe", "svg", "canvas", "form",
    "nav", "header", "footer", "aside", "menu", "dialog", "template",
    "button", "input", "select", "textarea",
]

# Class/id fragments that mark chrome rather than content.
_BOILERPLATE_HINT = re.compile(
    r"(nav|menu|sidebar|footer|header|banner|cookie|consent|popup|modal|"
    r"advert|\bads?\b|social|share|comment|related|recommend|newsletter|"
    r"subscribe|paywall|breadcrumb|pagination|skip-link)",
    re.IGNORECASE,
)


def _soup(html: str):
    """Parse HTML with lxml when available, falling back to the stdlib parser."""
    from bs4 import BeautifulSoup
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _extract_title(soup) -> str:
    """Prefer the OpenGraph title, then <h1>, then <title>."""
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def _extract_description(soup) -> str:
    """The page's own summary, useful context before the body text."""
    for attrs in ({"property": "og:description"}, {"name": "description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _pick_main(soup):
    """
    Choose the element most likely to hold the article body.

    Semantic containers win outright; otherwise score candidates by text
    length so a content div beats a link-heavy sidebar.
    """
    for selector in ("article", "main", '[role="main"]', "#content",
                     ".post-content", ".article-body", ".entry-content"):
        node = soup.select_one(selector)
        if node and len(node.get_text(strip=True)) > 200:
            return node

    best, best_score = None, 0
    for node in soup.find_all(["div", "section"]):
        text_len = len(node.get_text(strip=True))
        if text_len < 200:
            continue
        # Penalise link-dense blocks: navigation is mostly anchors.
        link_len = sum(len(a.get_text(strip=True)) for a in node.find_all("a"))
        score = text_len - 2 * link_len
        if score > best_score:
            best, best_score = node, score

    return best or soup.body or soup


def _attr_text(tag, name: str) -> str:
    """
    Read an attribute as a string, tolerating list-valued attrs.

    Returns "" for a tag that a previous decompose() already detached —
    find_all() hands back a snapshot, so children of a removed parent are
    still in the list but have had their attrs torn down.
    """
    attrs = getattr(tag, "attrs", None)
    if not attrs:
        return ""
    value = attrs.get(name)
    if value is None:
        return ""
    return " ".join(value) if isinstance(value, (list, tuple)) else str(value)


def _drop(tag) -> None:
    """Decompose a tag unless it is already detached."""
    if getattr(tag, "decomposed", False):
        return
    try:
        tag.decompose()
    except (AttributeError, ValueError):
        pass


def _clean(node) -> None:
    """Strip non-content elements and obvious chrome from the chosen subtree."""
    for tag in node.find_all(_STRIP_TAGS):
        _drop(tag)

    for tag in node.find_all(True):
        if getattr(tag, "decomposed", False):
            continue
        marker = f"{_attr_text(tag, 'class')} {_attr_text(tag, 'id')}"
        if marker.strip() and _BOILERPLATE_HINT.search(marker):
            _drop(tag)
        elif _attr_text(tag, "hidden"):
            _drop(tag)
        elif _attr_text(tag, "aria-hidden").lower() == "true":
            _drop(tag)


def _to_markdown(node, base_url: str) -> str:
    """Convert the cleaned subtree to Markdown, keeping structure and links."""
    try:
        from markdownify import markdownify
        text = markdownify(
            str(node),
            heading_style="ATX",
            strip=["img"],
            escape_asterisks=False,
            escape_underscores=False,
        )
    except Exception:
        text = node.get_text("\n", strip=True)

    # Collapse the excessive blank lines markdownify tends to leave behind.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _render_json(payload, url: str) -> str:
    """Pretty-print a JSON response instead of dumping one long line."""
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    return (
        f"🌐 JSON from: {url} [Source 1]\n"
        f"{'━' * 40}\n\n"
        f"{truncate(body, MAX_CONTENT_CHARS)}"
        + format_sources([(f"JSON response from {url}", url)])
    )


def read_url(url: str) -> str:
    """
    Fetch a URL and return its readable content as Markdown.

    Args:
        url: The page to read. A missing scheme defaults to https://.

    Returns:
        Extracted content with a ``[SOURCES]`` block, or an error message.
    """
    try:
        target = guard_url(clean_input(url))
    except ToolError as exc:
        return str(exc)

    try:
        response = http_get(target, guard=False, timeout=25.0)
    except ToolError as exc:
        return str(exc)

    if response.status_code != 200:
        return str(ToolError(
            f"Could not fetch the page (HTTP {response.status_code}).",
            "Check the URL, or the site may be blocking automated access.",
        ))

    content_type = response.headers.get("content-type", "").lower()
    final_url = str(response.url)

    # --- non-HTML payloads ---
    if "application/json" in content_type or "text/json" in content_type:
        try:
            return _render_json(response.json(), final_url)
        except Exception:
            pass  # fall through and treat it as text

    if "application/pdf" in content_type:
        return str(ToolError(
            "That URL is a PDF, not a web page.",
            "Download it and use read_file, or link to an HTML version.",
        ))

    if len(response.content) > MAX_BYTES:
        return str(ToolError(
            f"The page is too large to parse ({len(response.content) // 1024} KB).",
            "Try a more specific URL, such as a single article.",
        ))

    if content_type and not any(
        marker in content_type for marker in ("html", "text/", "xml")
    ):
        return str(ToolError(
            f"Unsupported content type '{content_type.split(';')[0]}'.",
            "This tool reads HTML pages, plain text and JSON.",
        ))

    html = response.text

    # --- plain text ---
    if "text/plain" in content_type:
        body = truncate(html.strip(), MAX_CONTENT_CHARS)
        return (
            f"🌐 Text from: {final_url} [Source 1]\n{'━' * 40}\n\n{body}"
            + format_sources([(final_url, final_url)])
        )

    # --- HTML ---
    try:
        soup = _soup(html)
    except ImportError:
        return str(ToolError(
            "beautifulsoup4 is not installed.",
            "Run: pip install beautifulsoup4 lxml markdownify",
        ))
    except Exception as exc:
        return str(ToolError(f"Could not parse the page HTML: {exc}"))

    title = _extract_title(soup) or final_url
    description = _extract_description(soup)

    main = _pick_main(soup)
    _clean(main)
    body = _to_markdown(main, final_url)

    if len(body) < 120:
        # Extraction collapsed — fall back to the whole document text.
        _clean(soup)
        body = soup.get_text("\n", strip=True)
        body = re.sub(r"\n{3,}", "\n\n", body)

    if not body.strip():
        return str(ToolError(
            "The page returned no readable text.",
            "It may render entirely via JavaScript, which this tool cannot execute.",
        ))

    header = f"🌐 **{title}** [Source 1]\n{final_url}\n"
    if description:
        header += f"\n_{description}_\n"

    content = truncate(body, MAX_CONTENT_CHARS, note="fetch a more specific URL for the rest")

    return f"{header}{'━' * 40}\n\n{content}" + format_sources([(title, final_url)])


url_reader_tool = Tool(
    name="read_url",
    description=(
        "Fetch a web page and return its main content as clean Markdown with "
        "headings, lists, tables and links preserved. Strips navigation, ads "
        "and boilerplate. Also handles plain-text and JSON endpoints. "
        "Use it to read articles, documentation or API responses. "
        "Input is a URL such as 'https://example.com/article'."
    ),
    function=read_url,
)
