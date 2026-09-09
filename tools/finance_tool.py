"""
finance_tool.py — Market Quotes & Currency Conversion
========================================================
Two key-free market tools:

- ``stock_quote``  — live equity/ETF/index/crypto quotes from Yahoo Finance,
  including day range, 52-week range, volume and market cap.
- ``currency_convert`` — FX conversion via the ECB reference rates published
  by frankfurter.app, with the quotation date so the model can cite it.

Both are read-only public endpoints; neither needs an API key.
"""

from __future__ import annotations

import re

from tools.base import Tool
from tools.common import ToolError, clean_input, http_json

YAHOO_QUOTE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FRANKFURTER = "https://api.frankfurter.app/latest"

# Common names the model may pass instead of a ticker.
_SYMBOL_ALIASES = {
    "s&p": "^GSPC", "s&p500": "^GSPC", "sp500": "^GSPC", "spx": "^GSPC",
    "dow": "^DJI", "dow jones": "^DJI", "nasdaq": "^IXIC",
    "ftse": "^FTSE", "nifty": "^NSEI", "sensex": "^BSESN",
    "nikkei": "^N225", "dax": "^GDAXI", "vix": "^VIX",
    "bitcoin": "BTC-USD", "btc": "BTC-USD",
    "ethereum": "ETH-USD", "eth": "ETH-USD",
    "gold": "GC=F", "silver": "SI=F", "oil": "CL=F", "crude": "CL=F",
}

_CURRENCY_WORDS = {
    "dollar": "USD", "dollars": "USD", "usd": "USD", "$": "USD",
    "euro": "EUR", "euros": "EUR", "eur": "EUR", "€": "EUR",
    "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "£": "GBP",
    "yen": "JPY", "jpy": "JPY", "¥": "JPY",
    "rupee": "INR", "rupees": "INR", "inr": "INR", "₹": "INR",
    "yuan": "CNY", "cny": "CNY", "rmb": "CNY",
    "franc": "CHF", "chf": "CHF", "cad": "CAD", "aud": "AUD",
}


# ============================================
# Stock quotes
# ============================================

def _normalize_symbol(raw: str) -> str:
    """Map a spoken name ('bitcoin', 'S&P') onto its Yahoo ticker."""
    cleaned = raw.strip().lower().lstrip("$")
    if cleaned in _SYMBOL_ALIASES:
        return _SYMBOL_ALIASES[cleaned]
    return raw.strip().upper().lstrip("$")


def _format_money(value: float | None, currency: str) -> str:
    if value is None:
        return "n/a"
    if abs(value) >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T {currency}"
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B {currency}"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M {currency}"
    return f"{value:,.2f} {currency}"


def stock_quote(symbol: str) -> str:
    """
    Fetch a live market quote.

    Args:
        symbol: Ticker ('AAPL', 'MSFT'), index alias ('S&P', 'nasdaq'),
                crypto ('bitcoin') or commodity ('gold').

    Returns:
        A formatted quote block, or an actionable error.
    """
    raw = clean_input(symbol)
    if not raw:
        return str(ToolError("No symbol provided.",
                             "Pass a ticker like 'AAPL' or a name like 'bitcoin'."))

    ticker = _normalize_symbol(raw)

    try:
        payload = http_json(
            YAHOO_QUOTE.format(symbol=ticker),
            params={"range": "1d", "interval": "1d"},
            timeout=15.0,
        )
    except ToolError as exc:
        if "429" in str(exc):
            return str(ToolError(
                "Yahoo Finance is rate-limiting requests right now.",
                "Wait a few seconds and ask again, or use web_search for the price.",
            ))
        if "404" in str(exc):
            return str(ToolError(
                f"'{raw}' is not a recognised ticker.",
                "Try the exchange suffix, e.g. 'TSLA', 'RELIANCE.NS' or 'SHEL.L'.",
            ))
        return str(exc)

    chart = (payload or {}).get("chart") or {}
    if chart.get("error"):
        return str(ToolError(
            f"No market data for '{raw}'.",
            "Check the ticker symbol — try the exchange suffix, e.g. "
            "'TSLA', 'RELIANCE.NS' or 'SHEL.L'.",
        ))

    results = chart.get("result") or []
    if not results:
        return str(ToolError(f"No market data returned for '{raw}'."))

    meta = results[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    previous = meta.get("chartPreviousClose") or meta.get("previousClose")
    currency = meta.get("currency", "")
    name = meta.get("longName") or meta.get("shortName") or ticker
    exchange = meta.get("fullExchangeName") or meta.get("exchangeName", "")

    if price is None:
        return str(ToolError(f"No current price available for '{raw}'."))

    lines = [f"📈 **{name}** ({meta.get('symbol', ticker)})"]
    if exchange:
        lines.append(f"_{exchange}_")
    lines.append("━" * 34)
    lines.append(f"Price: {price:,.2f} {currency}")

    if previous:
        change = price - previous
        percent = (change / previous * 100) if previous else 0
        arrow = "▲" if change > 0 else ("▼" if change < 0 else "■")
        lines.append(f"Change: {arrow} {change:+,.2f} ({percent:+.2f}%) vs prev close {previous:,.2f}")

    low, high = meta.get("regularMarketDayLow"), meta.get("regularMarketDayHigh")
    if low and high:
        lines.append(f"Day range: {low:,.2f} – {high:,.2f}")

    lo52, hi52 = meta.get("fiftyTwoWeekLow"), meta.get("fiftyTwoWeekHigh")
    if lo52 and hi52:
        lines.append(f"52-week range: {lo52:,.2f} – {hi52:,.2f}")

    volume = meta.get("regularMarketVolume")
    if volume:
        lines.append(f"Volume: {volume:,}")

    return "\n".join(lines)


# ============================================
# Currency conversion
# ============================================

def _parse_conversion(raw: str) -> tuple[float, str, str]:
    """
    Understand the several phrasings a model uses for a conversion.

    Accepts '100 USD to EUR', 'USD to INR', '50 dollars in yen',
    'USD/JPY' and 'convert 20 GBP to USD'.
    """
    text = raw.strip().lower()
    text = re.sub(r"^(convert|exchange|how much is)\s+", "", text)

    amount = 1.0
    amount_match = re.match(r"^\s*([\d,]+(?:\.\d+)?)\s*", text)
    if amount_match:
        amount = float(amount_match.group(1).replace(",", ""))
        text = text[amount_match.end():]

    text = text.replace("/", " to ").replace("->", " to ")
    parts = re.split(r"\s+(?:to|in|into|as)\s+", text, maxsplit=1)
    if len(parts) != 2:
        raise ToolError(
            f"Could not parse '{raw}' as a conversion.",
            "Use the form '100 USD to EUR'.",
        )

    def to_code(token: str) -> str:
        token = token.strip().strip(".?!").strip()
        if token in _CURRENCY_WORDS:
            return _CURRENCY_WORDS[token]
        word = token.split()[0] if token.split() else token
        if word in _CURRENCY_WORDS:
            return _CURRENCY_WORDS[word]
        code = re.sub(r"[^a-z]", "", word).upper()
        if len(code) != 3:
            raise ToolError(
                f"'{token}' is not a recognised currency.",
                "Use a 3-letter ISO code such as USD, EUR, GBP, JPY or INR.",
            )
        return code

    return amount, to_code(parts[0]), to_code(parts[1])


def currency_convert(query: str) -> str:
    """
    Convert between currencies at the latest ECB reference rate.

    Args:
        query: e.g. '100 USD to EUR', 'GBP to INR', '50 dollars in yen'.

    Returns:
        The converted amount, the rate used and its quotation date.
    """
    raw = clean_input(query)
    if not raw:
        return str(ToolError("No conversion requested.",
                             "Try '100 USD to EUR'."))

    try:
        amount, source, target = _parse_conversion(raw)
    except ToolError as exc:
        return str(exc)

    if source == target:
        return f"💱 {amount:,.2f} {source} = {amount:,.2f} {target} (same currency)"

    try:
        payload = http_json(
            FRANKFURTER,
            params={"from": source, "to": target, "amount": amount},
            timeout=15.0,
        )
    except ToolError as exc:
        # frankfurter answers 404 for a currency it does not quote.
        if "404" in str(exc) or "422" in str(exc):
            return str(ToolError(
                f"'{source}' or '{target}' is not a supported currency code.",
                "Supported codes are the major traded currencies "
                "(USD, EUR, GBP, JPY, INR, CNY, CHF, CAD, AUD and similar).",
            ))
        return str(exc)

    rates = (payload or {}).get("rates") or {}
    if target not in rates:
        return str(ToolError(
            f"No exchange rate available for {source} → {target}.",
            "The service covers major traded currencies; check both codes.",
        ))

    converted = rates[target]
    unit_rate = converted / amount if amount else 0
    date = payload.get("date", "latest")

    return (
        f"💱 **{amount:,.2f} {source} = {converted:,.2f} {target}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Rate: 1 {source} = {unit_rate:.6g} {target}\n"
        f"Inverse: 1 {target} = {1 / unit_rate:.6g} {source}\n"
        f"Quoted: {date} (ECB reference rate)"
    )


stock_tool = Tool(
    name="stock_quote",
    description=(
        "Get a live market quote for a stock, ETF, index, commodity or "
        "cryptocurrency: price, daily change, day and 52-week ranges and "
        "volume. Accepts tickers ('AAPL', 'RELIANCE.NS') or names "
        "('bitcoin', 'nasdaq', 'gold'). Use for any question about what "
        "something is trading at."
    ),
    function=stock_quote,
)

currency_tool = Tool(
    name="currency_convert",
    description=(
        "Convert an amount between currencies at the current exchange rate, "
        "and report the rate and its date. Input like '100 USD to EUR', "
        "'GBP to INR' or '50 dollars in yen'."
    ),
    function=currency_convert,
)
