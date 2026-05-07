"""
datetime_tool.py — Date & Time Tool
=======================================
Provides current date/time, timezone conversions,
and date calculations.

No external API needed — uses Python's built-in datetime.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from tools.base import Tool


# Common timezone aliases
TIMEZONE_ALIASES = {
    "est": "America/New_York",
    "cst": "America/Chicago",
    "mst": "America/Denver",
    "pst": "America/Los_Angeles",
    "gmt": "Europe/London",
    "utc": "UTC",
    "ist": "Asia/Kolkata",
    "jst": "Asia/Tokyo",
    "cet": "Europe/Paris",
    "aest": "Australia/Sydney",
    "bst": "Europe/London",
    "kst": "Asia/Seoul",
    "cst_china": "Asia/Shanghai",
    "sgt": "Asia/Singapore",
}


def datetime_query(query: str) -> str:
    """
    Handle date and time queries.
    
    Args:
        query: A date/time query string.
               Examples:
               - "now" or "current time"
               - "time in Tokyo"
               - "time in EST"
               - "days until 2026-12-31"
               - "date 30 days from now"
    
    Returns:
        Formatted date/time information.
    """
    query = query.strip().lower()

    # Current time
    if query in ("now", "current time", "current date", "today", "date", "time"):
        return _current_time_multi()

    # Time in a specific timezone
    if "time in" in query or "time at" in query:
        tz_name = query.split("time in")[-1].split("time at")[-1].strip()
        return _time_in_timezone(tz_name)

    # Days until a date
    if "days until" in query or "days to" in query:
        date_str = query.split("until")[-1].split("to")[-1].strip()
        return _days_until(date_str)

    # Date calculation
    if "days from now" in query or "days from today" in query:
        parts = query.replace("days from now", "").replace("days from today", "").strip()
        try:
            days = int(parts)
            return _date_offset(days)
        except ValueError:
            pass

    # Default: show current time in multiple zones
    return _current_time_multi()


def _current_time_multi() -> str:
    """Show current time in multiple popular timezones."""
    now = datetime.now(timezone.utc)
    zones = [
        ("🇺🇸 New York", "America/New_York"),
        ("🇬🇧 London", "Europe/London"),
        ("🇮🇳 Mumbai", "Asia/Kolkata"),
        ("🇯🇵 Tokyo", "Asia/Tokyo"),
        ("🇦🇺 Sydney", "Australia/Sydney"),
    ]

    lines = [f"🕐 Current Time (UTC: {now.strftime('%Y-%m-%d %H:%M:%S')})\n"]
    for label, tz in zones:
        local = now.astimezone(ZoneInfo(tz))
        lines.append(f"  {label}: {local.strftime('%Y-%m-%d %I:%M %p %Z')}")

    return "\n".join(lines)


def _time_in_timezone(tz_input: str) -> str:
    """Get current time in a specific timezone."""
    tz_input = tz_input.strip().lower()

    # Check aliases first
    tz_name = TIMEZONE_ALIASES.get(tz_input, tz_input)

    # Try common city names
    city_map = {
        "new york": "America/New_York",
        "los angeles": "America/Los_Angeles",
        "chicago": "America/Chicago",
        "london": "Europe/London",
        "paris": "Europe/Paris",
        "berlin": "Europe/Berlin",
        "tokyo": "Asia/Tokyo",
        "mumbai": "Asia/Kolkata",
        "delhi": "Asia/Kolkata",
        "sydney": "Australia/Sydney",
        "singapore": "Asia/Singapore",
        "dubai": "Asia/Dubai",
        "shanghai": "Asia/Shanghai",
        "seoul": "Asia/Seoul",
        "moscow": "Europe/Moscow",
        "toronto": "America/Toronto",
        "sao paulo": "America/Sao_Paulo",
    }

    if tz_input in city_map:
        tz_name = city_map[tz_input]

    try:
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        return (
            f"🕐 Current time in {tz_input.title()}:\n"
            f"   {now.strftime('%A, %B %d, %Y')}\n"
            f"   {now.strftime('%I:%M:%S %p %Z')} (UTC{now.strftime('%z')})"
        )
    except Exception:
        return f"Unknown timezone: '{tz_input}'. Try city names like 'Tokyo', 'London', or timezone codes like 'EST', 'IST'."


def _days_until(date_str: str) -> str:
    """Calculate days until a given date."""
    date_str = date_str.strip()
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y"]

    target = None
    for fmt in formats:
        try:
            target = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue

    if target is None:
        return f"Could not parse date '{date_str}'. Use format YYYY-MM-DD."

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    delta = target - today

    if delta.days > 0:
        return f"📅 {delta.days} days until {target.strftime('%B %d, %Y')}"
    elif delta.days == 0:
        return f"📅 That's today! ({target.strftime('%B %d, %Y')})"
    else:
        return f"📅 That date was {abs(delta.days)} days ago ({target.strftime('%B %d, %Y')})"


def _date_offset(days: int) -> str:
    """Calculate the date N days from now."""
    future = datetime.now() + timedelta(days=days)
    return (
        f"📅 {days} days from now:\n"
        f"   {future.strftime('%A, %B %d, %Y')}"
    )


# ============================================
# Register as a Tool
# ============================================

datetime_tool = Tool(
    name="datetime",
    description=(
        "Get current date/time, timezone conversions, and date calculations. "
        "Input examples: 'now', 'time in Tokyo', 'time in EST', "
        "'days until 2026-12-31', '30 days from now'."
    ),
    function=datetime_query,
)
