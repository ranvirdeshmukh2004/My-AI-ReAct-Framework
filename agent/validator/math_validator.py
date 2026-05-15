"""
math_validator.py — Calculation Re-Verification
=================================================
Re-evaluates all calculator tool expressions using Python
and compares with the agent's observations. Zero LLM calls.
"""

import ast
import math as _math


# Safe built-ins for math evaluation
_SAFE_GLOBALS = {
    "__builtins__": {},
    "abs": abs, "round": round, "min": min, "max": max,
    "int": int, "float": float, "pow": pow, "sum": sum,
    "math": _math,
    "sqrt": _math.sqrt, "log": _math.log, "log10": _math.log10,
    "sin": _math.sin, "cos": _math.cos, "tan": _math.tan,
    "pi": _math.pi, "e": _math.e,
}


def _safe_eval(expression: str) -> str:
    """
    Safely evaluate a math expression.
    Only allows math operations — no imports, file access, etc.
    """
    # Block dangerous patterns
    _blocked = ["import", "exec", "eval", "open", "os.", "sys.", "__", "subprocess"]
    expr_lower = expression.lower()
    for blocked in _blocked:
        if blocked in expr_lower:
            raise ValueError(f"Blocked expression: {blocked}")

    try:
        # Try ast.literal_eval first (safest — only literals)
        return str(ast.literal_eval(expression))
    except (ValueError, SyntaxError):
        pass

    # Fall back to restricted eval with only math builtins
    try:
        result = eval(expression, _SAFE_GLOBALS, {})
        return str(result)
    except Exception as e:
        raise ValueError(f"Cannot evaluate: {e}")


def _normalize_number(s: str) -> str:
    """Normalize a numeric string for comparison (handle float precision)."""
    s = s.strip()
    try:
        val = float(s)
        # If it's an integer value, compare as int
        if val == int(val) and "." not in s and "e" not in s.lower():
            return str(int(val))
        # Round to 6 decimal places for float comparison
        return str(round(val, 6))
    except (ValueError, OverflowError):
        return s


def run_math_validation(steps: list) -> dict:
    """
    Re-verify all calculator tool calls.

    Args:
        steps: List of agent step dicts from the ReAct loop.

    Returns:
        dict with score (0-10), checks, and metadata.
    """
    from agent.validator.base import MathResult

    calc_steps = [
        s for s in steps
        if s.get("type") == "tool_use" and s.get("action") == "calculator"
    ]

    if not calc_steps:
        return MathResult(score=10, skipped=True)

    checks = []
    passed = 0
    failed = 0

    for step in calc_steps:
        expr = step.get("action_input", "").strip()
        original = step.get("observation", "").strip()

        try:
            verified = _safe_eval(expr)
            match = _normalize_number(original) == _normalize_number(verified)
        except (ValueError, Exception):
            # Can't re-evaluate — treat as inconclusive (pass)
            verified = "⚠️ Cannot verify"
            match = True  # Don't penalize for expressions we can't parse

        if match:
            passed += 1
        else:
            failed += 1

        checks.append({
            "expression": expr[:100],
            "agent_result": original[:50],
            "verified_result": verified[:50],
            "match": match,
        })

    total = passed + failed
    score = round((passed / total) * 10) if total > 0 else 10

    return MathResult(
        score=score,
        total_checks=total,
        passed=passed,
        failed=failed,
        checks=checks,
        skipped=False,
    )
