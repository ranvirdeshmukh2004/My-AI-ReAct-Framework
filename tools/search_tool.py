"""
search_tool.py — Web Search Tool
===================================
Uses DuckDuckGo to search the web for free.
No API key required!

Returns the top results with title, snippet, and URL.
"""

from duckduckgo_search import DDGS
from tools.base import Tool


def web_search(query: str) -> str:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: The search query string.
    
    Returns:
        Formatted string with top search results.
    """
    try:
        # Initialize DuckDuckGo search
        with DDGS() as ddgs:
            # Get top 5 results
            results = list(ddgs.text(query, max_results=5))

        if not results:
            return "No search results found."

        # Format results nicely for the LLM
        formatted = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            body = result.get("body", "No description")
            href = result.get("href", "No URL")
            formatted.append(
                f"{i}. **{title}**\n"
                f"   {body}\n"
                f"   URL: {href}"
            )

        return "\n\n".join(formatted)

    except Exception as e:
        return f"Search error: {str(e)}. Please try a different query."


# ============================================
# Register as a Tool
# ============================================

search_tool = Tool(
    name="web_search",
    description=(
        "Search the web for current information using DuckDuckGo. "
        "Use this tool when you need to find recent news, facts, "
        "or any information that may not be in your training data. "
        "Input should be a search query string."
    ),
    function=web_search,
)
