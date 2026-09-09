"""
convert_tool.py — Unit Conversion
====================================
Offline dimensional conversion across length, mass, volume, area, speed,
temperature, energy, power, pressure, data size and time.

Everything is expressed relative to one SI base unit per dimension, so a
conversion is a division rather than an N×N table. Temperature is handled
separately because its scales have offsets, not just factors.

No network call, no API key — deterministic and instant.
"""

from __future__ import annotations

import re

from tools.base import Tool
from tools.common import ToolError, clean_input

# dimension -> {unit alias: factor relative to the dimension's base unit}
_UNITS: dict[str, dict[str, float]] = {
    "length": {
        "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
        "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
        "kilometre": 1000.0, "kilometres": 1000.0,
        "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
        "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
        "um": 1e-6, "micron": 1e-6, "nm": 1e-9, "nanometer": 1e-9,
        "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
        "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
        "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
        "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
        "nmi": 1852.0, "nauticalmile": 1852.0,
        "ly": 9.4607304725808e15, "lightyear": 9.4607304725808e15,
        "au": 1.495978707e11,
    },
    "mass": {
        "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
        "g": 0.001, "gram": 0.001, "grams": 0.001,
        "mg": 1e-6, "milligram": 1e-6, "milligrams": 1e-6,
        "t": 1000.0, "tonne": 1000.0, "tonnes": 1000.0, "metricton": 1000.0,
        "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237,
        "pounds": 0.45359237,
        "oz": 0.028349523125, "ounce": 0.028349523125, "ounces": 0.028349523125,
        "st": 6.35029318, "stone": 6.35029318,
        "ton": 907.18474, "shortton": 907.18474,
    },
    "volume": {
        "l": 1.0, "liter": 1.0, "liters": 1.0, "litre": 1.0, "litres": 1.0,
        "ml": 0.001, "milliliter": 0.001, "milliliters": 0.001,
        "m3": 1000.0, "cubicmeter": 1000.0, "cubicmeters": 1000.0,
        "gal": 3.785411784, "gallon": 3.785411784, "gallons": 3.785411784,
        "qt": 0.946352946, "quart": 0.946352946, "quarts": 0.946352946,
        "pt": 0.473176473, "pint": 0.473176473, "pints": 0.473176473,
        "cup": 0.2365882365, "cups": 0.2365882365,
        "floz": 0.0295735295625, "fluidounce": 0.0295735295625,
        "tbsp": 0.01478676478125, "tablespoon": 0.01478676478125,
        "tsp": 0.00492892159375, "teaspoon": 0.00492892159375,
    },
    "area": {
        "m2": 1.0, "sqm": 1.0, "squaremeter": 1.0, "squaremeters": 1.0,
        "km2": 1e6, "sqkm": 1e6, "squarekilometer": 1e6,
        "cm2": 1e-4, "sqcm": 1e-4,
        "ha": 10000.0, "hectare": 10000.0, "hectares": 10000.0,
        "acre": 4046.8564224, "acres": 4046.8564224,
        "sqft": 0.09290304, "ft2": 0.09290304, "squarefoot": 0.09290304,
        "sqmi": 2589988.110336, "mi2": 2589988.110336,
        "sqin": 0.00064516, "in2": 0.00064516,
    },
    "speed": {
        "m/s": 1.0, "mps": 1.0, "meterspersecond": 1.0,
        "km/h": 0.277777778, "kmh": 0.277777778, "kph": 0.277777778,
        "mph": 0.44704, "mi/h": 0.44704,
        "kn": 0.514444444, "knot": 0.514444444, "knots": 0.514444444,
        "ft/s": 0.3048, "fps": 0.3048,
        "c": 299792458.0, "lightspeed": 299792458.0,
    },
    "energy": {
        "j": 1.0, "joule": 1.0, "joules": 1.0,
        "kj": 1000.0, "kilojoule": 1000.0,
        "cal": 4.184, "calorie": 4.184, "calories": 4.184,
        "kcal": 4184.0, "kilocalorie": 4184.0,
        "wh": 3600.0, "watthour": 3600.0,
        "kwh": 3.6e6, "kilowatthour": 3.6e6,
        "btu": 1055.05585262, "ev": 1.602176634e-19, "electronvolt": 1.602176634e-19,
    },
    "power": {
        "w": 1.0, "watt": 1.0, "watts": 1.0,
        "kw": 1000.0, "kilowatt": 1000.0, "mw": 1e6, "megawatt": 1e6,
        "gw": 1e9, "gigawatt": 1e9,
        "hp": 745.6998715823, "horsepower": 745.6998715823,
    },
    "pressure": {
        "pa": 1.0, "pascal": 1.0, "pascals": 1.0,
        "kpa": 1000.0, "kilopascal": 1000.0,
        "bar": 100000.0, "bars": 100000.0, "mbar": 100.0, "millibar": 100.0,
        "atm": 101325.0, "atmosphere": 101325.0,
        "psi": 6894.757293168, "torr": 133.322368421, "mmhg": 133.322368421,
    },
    "data": {
        # Decimal (SI) and binary (IEC) prefixes kept distinct on purpose:
        # conflating MB and MiB is a classic source of wrong answers.
        "b": 1.0, "byte": 1.0, "bytes": 1.0,
        "bit": 0.125, "bits": 0.125,
        "kb": 1e3, "kilobyte": 1e3, "mb": 1e6, "megabyte": 1e6,
        "gb": 1e9, "gigabyte": 1e9, "tb": 1e12, "terabyte": 1e12,
        "pb": 1e15, "petabyte": 1e15,
        "kib": 1024.0, "kibibyte": 1024.0,
        "mib": 1048576.0, "mebibyte": 1048576.0,
        "gib": 1073741824.0, "gibibyte": 1073741824.0,
        "tib": 1099511627776.0, "tebibyte": 1099511627776.0,
        "kbit": 125.0, "mbit": 125000.0, "gbit": 125000000.0,
    },
    "time": {
        "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
        "ms": 0.001, "millisecond": 0.001, "milliseconds": 0.001,
        "us": 1e-6, "microsecond": 1e-6, "ns": 1e-9, "nanosecond": 1e-9,
        "min": 60.0, "minute": 60.0, "minutes": 60.0,
        "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
        "d": 86400.0, "day": 86400.0, "days": 86400.0,
        "wk": 604800.0, "week": 604800.0, "weeks": 604800.0,
        "mo": 2629746.0, "month": 2629746.0, "months": 2629746.0,
        "yr": 31556952.0, "year": 31556952.0, "years": 31556952.0,
    },
}

# Temperature needs affine conversion, so it lives outside the factor table.
_TEMPERATURE = {"c", "celsius", "f", "fahrenheit", "k", "kelvin", "r", "rankine"}

_BASE_UNIT = {
    "length": "m", "mass": "kg", "volume": "L", "area": "m²", "speed": "m/s",
    "energy": "J", "power": "W", "pressure": "Pa", "data": "bytes", "time": "s",
}


def _normalize_unit(token: str) -> str:
    """Lowercase and strip punctuation/spaces so 'Square Feet' matches 'sqft'."""
    cleaned = token.strip().lower().rstrip(".")
    cleaned = cleaned.replace("²", "2").replace("³", "3")
    cleaned = re.sub(r"\s+", "", cleaned)
    if cleaned.startswith("square"):
        cleaned = "sq" + cleaned[len("square"):]
    if cleaned.startswith("cubic"):
        cleaned = cleaned[len("cubic"):] + "3"
    return cleaned


def _find_dimension(unit: str) -> str | None:
    """Return the dimension a unit belongs to, or None if unknown."""
    if unit in _TEMPERATURE:
        return "temperature"
    for dimension, table in _UNITS.items():
        if unit in table:
            return dimension
    return None


def _to_kelvin(value: float, unit: str) -> float:
    if unit in ("c", "celsius"):
        return value + 273.15
    if unit in ("f", "fahrenheit"):
        return (value - 32) * 5 / 9 + 273.15
    if unit in ("r", "rankine"):
        return value * 5 / 9
    return value  # already kelvin


def _from_kelvin(kelvin: float, unit: str) -> float:
    if unit in ("c", "celsius"):
        return kelvin - 273.15
    if unit in ("f", "fahrenheit"):
        return (kelvin - 273.15) * 9 / 5 + 32
    if unit in ("r", "rankine"):
        return kelvin * 9 / 5
    return kelvin


def _pretty(value: float) -> str:
    """Format a result with sensible precision rather than float noise."""
    if value == 0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 1e12 or magnitude < 1e-4:
        return f"{value:.6e}"
    if magnitude >= 100:
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{value:.6g}"


def _temp_label(unit: str) -> str:
    """Kelvin is an absolute scale and takes no degree sign; C/F/R do."""
    if unit in ("k", "kelvin"):
        return "K"
    return "°" + unit[0].upper()


def _parse(raw: str) -> tuple[float, str, str, str, str]:
    """Parse '100 km to miles' / '32F to C' / '5 feet in cm'."""
    text = raw.strip()
    text = re.sub(r"^(convert|how many|what is)\s+", "", text, flags=re.IGNORECASE)

    match = re.match(
        r"^\s*(-?[\d,]*\.?\d+)\s*([^\d]+?)\s+(?:to|in|into|as)\s+(.+)$",
        text, re.IGNORECASE,
    )
    if not match:
        # Allow a missing space: "32F to C"
        match = re.match(
            r"^\s*(-?[\d,]*\.?\d+)\s*(\S+?)\s*(?:to|in|into|as)\s+(.+)$",
            text, re.IGNORECASE,
        )
    if not match:
        raise ToolError(
            f"Could not parse '{raw}' as a conversion.",
            "Use the form '100 km to miles' or '32 F to C'.",
        )

    amount = float(match.group(1).replace(",", ""))
    src_raw, tgt_raw = match.group(2).strip(), match.group(3).strip()
    return (amount, _normalize_unit(src_raw), _normalize_unit(tgt_raw),
            src_raw, tgt_raw)


def convert_units(query: str) -> str:
    """
    Convert a quantity between units.

    Args:
        query: e.g. '100 km to miles', '32 F to C', '2 GB to MiB'.

    Returns:
        The converted value plus the conversion factor used.
    """
    raw = clean_input(query)
    if not raw:
        return str(ToolError("No conversion requested.",
                             "Try '100 km to miles'."))

    try:
        amount, source, target, source_label, target_label = _parse(raw)
    except ToolError as exc:
        return str(exc)

    source_dim = _find_dimension(source)
    target_dim = _find_dimension(target)

    if source_dim is None:
        return str(ToolError(f"Unknown unit '{source}'.", _supported_hint()))
    if target_dim is None:
        return str(ToolError(f"Unknown unit '{target}'.", _supported_hint()))

    if source_dim != target_dim:
        return str(ToolError(
            f"Cannot convert {source_dim} to {target_dim} — "
            f"'{source}' and '{target}' measure different things.",
            "Convert within one dimension, e.g. length to length.",
        ))

    # --- temperature (affine) ---
    if source_dim == "temperature":
        result = _from_kelvin(_to_kelvin(amount, source), target)
        return (f"🔄 **{_pretty(amount)}{_temp_label(source)} = "
                f"{_pretty(result)}{_temp_label(target)}**")

    # --- everything else (linear) ---
    factor = _UNITS[source_dim][source] / _UNITS[source_dim][target]
    result = amount * factor

    return (
        f"🔄 **{_pretty(amount)} {source_label} = {_pretty(result)} {target_label}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Dimension: {source_dim}\n"
        f"Factor: 1 {source_label} = {_pretty(factor)} {target_label}"
    )


def _supported_hint() -> str:
    return (
        "Supported dimensions: length, mass, volume, area, speed, "
        "temperature, energy, power, pressure, data and time."
    )


convert_tool = Tool(
    name="unit_convert",
    description=(
        "Convert between units of length, mass, volume, area, speed, "
        "temperature, energy, power, pressure, data size (MB vs MiB kept "
        "distinct) and time. Instant and offline. "
        "Input like '100 km to miles', '32 F to C' or '2 GB to MiB'."
    ),
    function=convert_units,
)
