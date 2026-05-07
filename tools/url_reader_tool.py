"""
url_reader_tool.py — Web Page Reader Tool
============================================
Fetches and extracts readable text from any URL.
Useful for summarizing articles, reading documentation,
or extracting information from web pages.

Uses httpx to fetch HTML and basic parsing to extract text.
"""

import re
import httpx
from tools.base import Tool


def read_url(url: str) -> str:
    """
    Fetch and extract readable text from a URL.
    
    Args:
        url: The web page URL to read.
    
    Returns:
        Extracted text content from the page.
    """
    url = url.strip().strip("'\"")

    # Add https:// if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        with httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        ) as client:
            response = client.get(url)

        if response.status_code != 200:
            return f"Error: Could not fetch URL (HTTP {response.status_code})"

        html = response.text

        # Basic HTML to text conversion
        text = _html_to_text(html)

        # Truncate if too long
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... [Truncated — page has {len(text)} characters]"

        return f"🌐 Content from: {url}\n{'━' * 40}\n\n{text}"

    except httpx.TimeoutException:
        return f"Error: Request timed out for URL: {url}"
    except Exception as e:
        return f"Error reading URL: {str(e)}"


def _html_to_text(html: str) -> str:
    """
    Basic HTML to plain text conversion.
    Strips tags and normalizes whitespace.
    """
    # Remove script and style elements
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Convert common elements to text markers
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<p[^>]*>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<h[1-6][^>]*>", "\n\n## ", html, flags=re.IGNORECASE)
    html = re.sub(r"</h[1-6]>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<li[^>]*>", "\n• ", html, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", "", html)

    # Decode HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")

    # Normalize whitespace
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    # Clean up leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)

    return text.strip()


# ============================================
# Register as a Tool
# ============================================

url_reader_tool = Tool(
    name="read_url",
    description=(
        "Fetch and read the text content of a web page URL. "
        "Use this to read articles, documentation, or any web page. "
        "Input should be a valid URL like 'https://example.com/article'."
    ),
    function=read_url,
)
