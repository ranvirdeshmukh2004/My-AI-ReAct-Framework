"""
search_tool.py — Web & News Search
=====================================
DuckDuckGo-backed search with no API key.

Beyond a plain query it understands inline operators the agent can emit:

    climate policy                 → general web search
    site:arxiv.org transformers    → domain-restricted
    recent: openai funding         → past-week results only
    news: semiconductor tariffs    → news index with publication dates

Results are de-duplicated by domain so five links to the same site do not
crowd out the rest, and every result is emitted with a ``[Source N]``
marker plus a ``[SOURCES]`` block for citation.
"""

from __future__ import annotations

import re

from tools.base import Tool
from tools.common import ToolError, clean_input, format_sources

# The `duckduckgo_search` package was renamed to `ddgs`. The old package
# still imports but its backend silently returns zero results, so prefer
# `ddgs` and keep the legacy import only as a fallback.
try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - legacy environments
    from duckduckgo_search import DDGS

MAX_RESULTS = 6
SNIPPET_CHARS = 300

# "recent:", "today:", "week:" → DuckDuckGo timelimit codes.
_TIME_PREFIXES = {
    "today": "d", "day": "d", "recent": "w", "week": "w",
    "month": "m", "year": "y",
}


def _parse_query(raw: str) -> tuple[str, str | None, bool]:
    """
    Split inline operators off the query.

    Returns ``(query, timelimit, news_mode)``. Doing this here means the
    agent can express intent in the single string argument the ReAct format
    gives it, without a second round trip.
    """
    query = raw.strip()
    news = False
    timelimit = None

    match = re.match(r"^(news|recent|today|week|month|year)\s*:\s*(.+)$",
                     query, re.IGNORECASE)
    if match:
        keyword = match.group(1).lower()
        query = match.group(2).strip()
        if keyword == "news":
            news = True
        else:
            timelimit = _TIME_PREFIXES.get(keyword)

    # Bare "latest"/"today" wording also implies recency.
    if timelimit is None and re.search(r"\b(latest|breaking|today's)\b", query, re.I):
        timelimit = "w"

    return query, timelimit, news


def _snippet(text: str) -> str:
    """
    Trim a result snippet to one readable line.

    A short excerpt gets a plain ellipsis rather than the verbose
    "[truncated — N more characters]" note, which would dominate it.
    """
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= SNIPPET_CHARS:
        return flat
    cut = flat[:SNIPPET_CHARS]
    boundary = cut.rfind(". ")
    if boundary > SNIPPET_CHARS * 0.5:
        return cut[:boundary + 1]
    return cut.rsplit(" ", 1)[0] + "…"


def _domain(url: str) -> str:
    """Extract a bare domain for de-duplication and display."""
    match = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return match.group(1).lower() if match else ""


def _dedupe(results: list[dict], limit: int) -> list[dict]:
    """
    Keep at most two results per domain.

    Without this a single site with good SEO can occupy every slot, which
    both wastes context and gives the model a one-sided view.
    """
    seen: dict[str, int] = {}
    kept = []
    for item in results:
        domain = _domain(item.get("href") or item.get("url") or "")
        if seen.get(domain, 0) >= 2:
            continue
        seen[domain] = seen.get(domain, 0) + 1
        kept.append(item)
        if len(kept) >= limit:
            break
    return kept


def _run_search(query: str, timelimit: str | None, news: bool) -> list[dict]:
    """Execute the search, retrying once on a transient backend error."""
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with DDGS() as ddgs:
                if news:
                    return list(ddgs.news(
                        query, max_results=MAX_RESULTS * 2, timelimit=timelimit,
                    ))
                return list(ddgs.text(
                    query, max_results=MAX_RESULTS * 2,
                    timelimit=timelimit, safesearch="moderate",
                ))
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                continue
    raise ToolError(
        f"Search backend error: {last_error}",
        "Try rephrasing the query, or use wikipedia for encyclopedic facts.",
    )


def web_search(query: str) -> str:
    """
    Search the web (or news) and return ranked, citable results.

    Args:
        query: Search terms, optionally prefixed with ``news:``/``recent:``
               or containing a ``site:`` filter.

    Returns:
        Formatted results with a ``[SOURCES]`` block, or an error message.
    """
    raw = clean_input(query)
    if not raw:
        return str(ToolError("No search query provided."))

    search_terms, timelimit, news = _parse_query(raw)
    if not search_terms:
        return str(ToolError("The search query was empty after parsing."))

    try:
        results = _run_search(search_terms, timelimit, news)
    except ToolError as exc:
        return str(exc)

    if not results:
        # A time filter is the usual reason a sensible query returns nothing.
        if timelimit or news:
            try:
                results = _run_search(search_terms, None, False)
            except ToolError:
                results = []
        if not results:
            return (
                f"No results found for '{search_terms}'.\n"
                "💡 Try broader keywords, or drop any site: filter."
            )

    results = _dedupe(results, MAX_RESULTS)

    lines = []
    sources = []
    for index, item in enumerate(results, 1):
        title = (item.get("title") or "Untitled").strip()
        url = (item.get("href") or item.get("url") or "").strip()
        body = (item.get("body") or item.get("excerpt") or "").strip()
        body = _snippet(body)

        entry = f"{index}. **{title}** [Source {index}]"
        if news:
            date = (item.get("date") or "").split("T")[0]
            outlet = item.get("source") or _domain(url)
            meta = " · ".join(part for part in (outlet, date) if part)
            if meta:
                entry += f"\n   _{meta}_"
        else:
            entry += f"\n   _{_domain(url)}_"

        entry += f"\n   {body}\n   {url}"
        lines.append(entry)
        sources.append((title, url))

    label = "📰 News results" if news else "🌐 Web results"
    if timelimit:
        label += " (recent)"

    header = f"{label} for '{search_terms}' — {len(results)} found\n"
    return header + "\n\n".join(lines) + format_sources(sources)


search_tool = Tool(
    name="web_search",
    description=(
        "Search the web for current information. Supports inline operators: "
        "'site:example.com query' to restrict to a domain, 'news: query' for "
        "news articles with dates and outlets, and 'recent: query' to limit "
        "to the past week. Returns titles, sources, snippets and URLs. "
        "Use it for anything recent, changing, or not in training data."
    ),
    function=web_search,
)
