"""
wikipedia_tool.py — Wikipedia Lookup Tool
============================================
Fetches summaries from Wikipedia for any topic.
Uses the free Wikipedia API — no key required!

Supports:
- Topic summaries
- Key facts extraction
- Any language Wikipedia (defaults to English)
"""

import httpx
from tools.base import Tool


WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"


def wikipedia_lookup(topic: str) -> str:
    """
    Look up a topic on Wikipedia and return a summary.
    
    Args:
        topic: The topic to search for.
               Examples: "Python programming", "Albert Einstein"
    
    Returns:
        Wikipedia summary text.
    """
    topic = topic.strip().strip("'\"")

    # Format for Wikipedia URL (replace spaces with underscores)
    formatted_topic = topic.replace(" ", "_")

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(
                f"{WIKIPEDIA_API}{formatted_topic}",
                headers={"User-Agent": "AI-Agent/1.0"},
            )

        if response.status_code == 404:
            # Try a search instead
            return _search_wikipedia(topic)

        if response.status_code != 200:
            return f"Could not find Wikipedia article for '{topic}'."

        data = response.json()

        title = data.get("title", topic)
        extract = data.get("extract", "No summary available.")
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        description = data.get("description", "")

        result = f"📖 **{title}**"
        if description:
            result += f"\n_{description}_"
        result += f"\n\n{extract}"
        if page_url:
            result += f"\n\n🔗 Source: {page_url}"

        return result

    except Exception as e:
        return f"Wikipedia error: {str(e)}. Please try a different topic."


def _search_wikipedia(query: str) -> str:
    """Fallback: search Wikipedia for the topic."""
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json",
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                search_url,
                params=params,
                headers={"User-Agent": "AI-Agent/1.0"},
            )

        data = response.json()
        results = data.get("query", {}).get("search", [])

        if not results:
            return f"No Wikipedia articles found for '{query}'."

        formatted = [f"📖 Wikipedia search results for '{query}':\n"]
        for i, r in enumerate(results, 1):
            title = r["title"]
            # Remove HTML tags from snippet
            snippet = r.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
            formatted.append(f"{i}. **{title}**\n   {snippet}\n")

        return "\n".join(formatted)

    except Exception:
        return f"Could not search Wikipedia for '{query}'."


# ============================================
# Register as a Tool
# ============================================

wikipedia_tool = Tool(
    name="wikipedia",
    description=(
        "Look up information on Wikipedia. Returns a summary of the topic. "
        "Use this for factual information about people, places, concepts, "
        "history, science, and more. Input should be a topic name."
    ),
    function=wikipedia_lookup,
)
