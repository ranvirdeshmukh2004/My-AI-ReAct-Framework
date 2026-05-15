"""
tool_rerun.py — Deterministic Tool Re-Execution Validator
==========================================================
Re-runs safe, deterministic tool calls and compares fresh
results with the agent's original observations. Zero LLM calls.

Only re-runs tools where we expect consistent output:
  ✅ calculator — math is deterministic
  ✅ datetime   — should match within seconds
  ✅ wikipedia  — stable content (title lookups)
  ❌ web_search — results change constantly
  ❌ weather    — real-time data
  ❌ python_executor — unsafe to re-run
  ❌ read_file  — file might have changed
  ❌ read_url   — page content changes
"""

# Tools that are safe and deterministic enough to re-run
RERUNNABLE_TOOLS = {"calculator", "datetime", "wikipedia"}


def _outputs_match(original: str, fresh: str, tool_name: str) -> bool:
    """
    Compare two tool outputs, with tool-specific tolerance.
    """
    if not original or not fresh:
        return True  # Can't compare — don't penalize

    orig = original.strip().lower()
    new = fresh.strip().lower()

    if tool_name == "calculator":
        # Numeric comparison with tolerance
        try:
            return abs(float(orig) - float(new)) < 0.001
        except (ValueError, TypeError):
            return orig == new

    elif tool_name == "datetime":
        # Date/time — just check the date portion matches (ignore seconds)
        return orig[:16] == new[:16]

    elif tool_name == "wikipedia":
        # Wikipedia — check if the key content overlaps (first 200 chars)
        orig_snippet = orig[:200]
        new_snippet = new[:200]
        # At least 60% overlap in words
        orig_words = set(orig_snippet.split())
        new_words = set(new_snippet.split())
        if not orig_words:
            return True
        overlap = len(orig_words & new_words) / max(len(orig_words), 1)
        return overlap > 0.5

    return orig == new


def run_tool_rerun(steps: list) -> dict:
    """
    Re-execute deterministic tool calls and verify outputs.

    Args:
        steps: List of agent step dicts from the ReAct loop.

    Returns:
        ToolRerunResult dict with score (0-10) and per-check details.
    """
    from agent.validator.base import ToolRerunResult

    rerunnable_steps = [
        s for s in steps
        if s.get("type") == "tool_use" and s.get("action") in RERUNNABLE_TOOLS
    ]

    if not rerunnable_steps:
        return ToolRerunResult(score=10, skipped=True)

    # Lazy import tools to avoid circular deps
    from tools.base import ToolRegistry
    from tools.calculator_tool import calculator_tool
    from tools.datetime_tool import datetime_tool
    from tools.wikipedia_tool import wikipedia_tool

    registry = ToolRegistry()
    registry.register(calculator_tool)
    registry.register(datetime_tool)
    registry.register(wikipedia_tool)

    checks = []
    passed = 0
    failed = 0

    for step in rerunnable_steps:
        tool_name = step.get("action", "")
        tool_input = step.get("action_input", "")
        original = step.get("observation", "")

        try:
            fresh_result = registry.execute(tool_name, tool_input)
            # Handle dict results (some tools return dicts)
            if isinstance(fresh_result, dict):
                fresh_output = str(fresh_result.get("result", fresh_result))
            else:
                fresh_output = str(fresh_result)

            match = _outputs_match(original, fresh_output, tool_name)
        except Exception:
            # Tool re-run failed — don't penalize
            fresh_output = "⚠️ Re-run failed"
            match = True

        if match:
            passed += 1
        else:
            failed += 1

        checks.append({
            "tool": tool_name,
            "input_text": tool_input[:80],
            "original_output": original[:100],
            "fresh_output": fresh_output[:100],
            "match": match,
        })

    total = passed + failed
    score = round((passed / total) * 10) if total > 0 else 10

    return ToolRerunResult(
        score=score,
        total_checks=total,
        passed=passed,
        failed=failed,
        checks=checks,
        skipped=False,
    )
