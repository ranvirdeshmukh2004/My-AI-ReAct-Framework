"""
research_tool.py — Academic Papers & Code Search
===================================================
Two key-free research tools:

- ``arxiv_search`` — search arXiv for preprints, returning title, authors,
  publication date, categories, abstract and both the abstract and PDF
  links, so the agent can cite a primary source rather than a blog post.
- ``github_search`` — search GitHub for repositories, returning stars,
  language, licence, last-push date and description.

Both hit documented public endpoints with generous anonymous rate limits.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from tools.base import Tool
from tools.common import (
    ToolError,
    clean_input,
    format_sources,
    http_get,
    http_json,
)

ARXIV_API = "http://export.arxiv.org/api/query"
GITHUB_SEARCH = "https://api.github.com/search/repositories"

MAX_RESULTS = 5
ABSTRACT_CHARS = 700

_ATOM = {"a": "http://www.w3.org/2005/Atom"}


# ============================================
# arXiv
# ============================================

def _clean_ws(text: str) -> str:
    """arXiv wraps abstracts at source-column width; unwrap to one flow."""
    return re.sub(r"\s+", " ", (text or "")).strip()


def arxiv_search(query: str) -> str:
    """
    Search arXiv for papers matching a query.

    Args:
        query: Free-text terms, or a fielded query such as
               'au:Hinton', 'ti:attention', 'cat:cs.CL transformers'.

    Returns:
        Formatted paper records with a ``[SOURCES]`` block.
    """
    raw = clean_input(query)
    if not raw:
        return str(ToolError("No search query provided.",
                             "Try 'retrieval augmented generation' or 'au:Bengio'."))

    # Pass through a fielded query untouched; otherwise search all fields.
    search_query = raw if re.match(r"^(au|ti|abs|cat|all):", raw) else f"all:{raw}"

    try:
        response = http_get(
            ARXIV_API,
            params={
                "search_query": search_query,
                "start": 0,
                "max_results": MAX_RESULTS,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
            timeout=25.0,
        )
    except ToolError as exc:
        return str(exc)

    if response.status_code != 200:
        return str(ToolError(f"arXiv returned HTTP {response.status_code}."))

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        return str(ToolError(f"Could not parse the arXiv response: {exc}"))

    entries = root.findall("a:entry", _ATOM)
    if not entries:
        return (f"No arXiv papers found for '{raw}'.\n"
                "💡 Try broader terms, or a field prefix like 'ti:' or 'au:'.")

    blocks = []
    sources = []
    for index, entry in enumerate(entries, 1):
        title = _clean_ws(entry.findtext("a:title", "", _ATOM))
        summary = _clean_ws(entry.findtext("a:summary", "", _ATOM))
        published = (entry.findtext("a:published", "", _ATOM) or "")[:10]
        updated = (entry.findtext("a:updated", "", _ATOM) or "")[:10]

        authors = [
            _clean_ws(node.findtext("a:name", "", _ATOM))
            for node in entry.findall("a:author", _ATOM)
        ]
        author_text = ", ".join(authors[:4])
        if len(authors) > 4:
            author_text += f" +{len(authors) - 4} more"

        categories = [
            node.get("term", "") for node in entry.findall("a:category", _ATOM)
        ]

        abs_url = entry.findtext("a:id", "", _ATOM).strip()
        pdf_url = ""
        for link in entry.findall("a:link", _ATOM):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")

        if len(summary) > ABSTRACT_CHARS:
            summary = summary[:ABSTRACT_CHARS].rsplit(" ", 1)[0] + "…"

        block = [f"{index}. **{title}** [Source {index}]"]
        if author_text:
            block.append(f"   👤 {author_text}")
        meta = f"   📅 {published}"
        if updated and updated != published:
            meta += f" (revised {updated})"
        if categories:
            meta += f"  ·  🏷️ {', '.join(categories[:3])}"
        block.append(meta)
        block.append(f"   {summary}")
        block.append(f"   🔗 {abs_url}")
        if pdf_url:
            block.append(f"   📄 {pdf_url}")

        blocks.append("\n".join(block))
        sources.append((title, abs_url))

    header = f"📚 arXiv results for '{raw}' — {len(entries)} papers\n"
    return header + "\n\n".join(blocks) + format_sources(sources)


# ============================================
# GitHub
# ============================================

def github_search(query: str) -> str:
    """
    Search GitHub repositories.

    Args:
        query: Terms plus optional qualifiers, e.g.
               'react state management', 'language:rust cli stars:>1000'.

    Returns:
        Ranked repositories with stars, language, licence and last activity.
    """
    raw = clean_input(query)
    if not raw:
        return str(ToolError("No search query provided.",
                             "Try 'language:python web framework'."))

    try:
        payload = http_json(
            GITHUB_SEARCH,
            params={"q": raw, "sort": "stars", "order": "desc",
                    "per_page": MAX_RESULTS},
            headers={"Accept": "application/vnd.github+json"},
            timeout=20.0,
        )
    except ToolError as exc:
        if "403" in str(exc) or "429" in str(exc):
            return str(ToolError(
                "GitHub is rate-limiting anonymous search right now.",
                "Wait a minute and retry, or use web_search with 'site:github.com'.",
            ))
        if "422" in str(exc):
            return str(ToolError(
                f"GitHub rejected the query '{raw}'.",
                "Check qualifier syntax, e.g. 'language:python stars:>100'.",
            ))
        return str(exc)

    items = (payload or {}).get("items") or []
    if not items:
        return (f"No GitHub repositories found for '{raw}'.\n"
                "💡 Try fewer qualifiers or broader keywords.")

    blocks = []
    sources = []
    for index, repo in enumerate(items, 1):
        name = repo.get("full_name", "unknown")
        url = repo.get("html_url", "")
        description = (repo.get("description") or "No description").strip()
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        language = repo.get("language") or "—"
        pushed = (repo.get("pushed_at") or "")[:10]
        licence = ((repo.get("license") or {}).get("spdx_id") or "none")
        topics = repo.get("topics") or []

        block = [f"{index}. **{name}** [Source {index}]"]
        block.append(f"   ⭐ {stars:,}  ·  🍴 {forks:,}  ·  💻 {language}"
                     f"  ·  ⚖️ {licence}  ·  🕐 pushed {pushed}")
        block.append(f"   {description}")
        if topics:
            block.append(f"   🏷️ {', '.join(topics[:6])}")
        block.append(f"   🔗 {url}")

        blocks.append("\n".join(block))
        sources.append((name, url))

    total = (payload or {}).get("total_count", len(items))
    header = (f"💻 GitHub repositories for '{raw}' — "
              f"showing {len(items)} of {total:,}\n")
    return header + "\n\n".join(blocks) + format_sources(sources)


arxiv_tool = Tool(
    name="arxiv_search",
    description=(
        "Search arXiv for scientific papers and preprints. Returns title, "
        "authors, date, categories, abstract and links. Supports field "
        "prefixes: 'au:' author, 'ti:' title, 'abs:' abstract, 'cat:' "
        "category. Use for research questions, ML/physics/maths papers, or "
        "when a primary academic source is wanted rather than a blog post."
    ),
    function=arxiv_search,
)

github_tool = Tool(
    name="github_search",
    description=(
        "Search GitHub repositories by keyword and qualifiers such as "
        "'language:python', 'stars:>1000' or 'topic:llm'. Returns stars, "
        "forks, language, licence, last-push date and description. Use for "
        "finding libraries, tools or reference implementations."
    ),
    function=github_search,
)
