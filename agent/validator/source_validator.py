"""
source_validator.py — Source URL Accessibility Validator
=========================================================
Checks if cited URLs are actually accessible (HTTP HEAD).
Zero LLM calls — only HTTP requests.
"""

import httpx


def run_source_validation(sources: list) -> dict:
    """
    Verify that cited source URLs are accessible.

    Args:
        sources: List of source dicts, each with a "url" key.

    Returns:
        SourceURLResult dict with score (0-10) and per-URL results.
    """
    from agent.validator.base import SourceURLResult

    if not sources:
        return SourceURLResult(score=10, skipped=True)

    # Deduplicate URLs
    seen = set()
    unique_sources = []
    for s in sources:
        url = s.get("url", "").strip()
        if url and url not in seen:
            seen.add(url)
            unique_sources.append(s)

    if not unique_sources:
        return SourceURLResult(score=10, skipped=True)

    checks = []
    accessible_count = 0
    failed_count = 0

    for source in unique_sources:
        url = source.get("url", "").strip()
        if not url:
            continue

        try:
            # Use HEAD request (fast, doesn't download body)
            # Fall back to GET with stream if HEAD isn't supported
            with httpx.Client(timeout=8, follow_redirects=True) as client:
                try:
                    resp = client.head(url)
                except httpx.HTTPError:
                    resp = client.get(url, headers={"Range": "bytes=0-0"})

            is_accessible = resp.status_code < 400

            if is_accessible:
                accessible_count += 1
            else:
                failed_count += 1

            checks.append({
                "url": url[:120],
                "accessible": is_accessible,
                "status_code": resp.status_code,
                "error": "",
            })

        except httpx.TimeoutException:
            failed_count += 1
            checks.append({
                "url": url[:120],
                "accessible": False,
                "status_code": 0,
                "error": "Timeout",
            })
        except Exception as e:
            failed_count += 1
            checks.append({
                "url": url[:120],
                "accessible": False,
                "status_code": 0,
                "error": str(e)[:60],
            })

    total = accessible_count + failed_count
    score = round((accessible_count / total) * 10) if total > 0 else 10

    return SourceURLResult(
        score=score,
        total_checks=total,
        accessible=accessible_count,
        failed=failed_count,
        checks=checks,
        skipped=False,
    )
