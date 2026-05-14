"""
cost_auditor.py — Rule-Based Efficiency Auditor
==================================================
Analyzes tool usage patterns, token consumption,
and iteration count. No LLM call needed — pure Python.
"""

from agent.auditor.base import CostReport


def run_cost_audit(steps: list, token_usage: dict, timing: dict) -> CostReport:
    """
    Analyze the agent run for efficiency.

    Args:
        steps: List of step dicts from the ReAct loop.
        token_usage: {prompt_tokens, completion_tokens, total_tokens, llm_calls}
        timing: {total_ms, llm_ms, vector_search_ms}

    Returns:
        CostReport with efficiency rating and suggestions.
    """
    tool_steps = [s for s in steps if s.get("type") == "tool_use"]
    iterations = len(steps)
    tool_calls = len(tool_steps)
    total_tokens = token_usage.get("total_tokens", 0)
    llm_calls = token_usage.get("llm_calls", 0)
    total_ms = timing.get("total_ms", 0)
    llm_ms = timing.get("llm_ms", 0)
    vs_ms = timing.get("vector_search_ms", 0)

    suggestions = []
    penalty = 0  # Higher = worse

    # --- Check for duplicate tool calls ---
    tool_signatures = []
    duplicates = 0
    for s in tool_steps:
        sig = f"{s.get('action')}|{s.get('action_input', '')}"
        if sig in tool_signatures:
            duplicates += 1
        tool_signatures.append(sig)
    if duplicates > 0:
        suggestions.append(f"🔁 {duplicates} duplicate tool call(s) detected — same tool+input used twice")
        penalty += duplicates * 2

    # --- Check iteration count ---
    if iterations > 6:
        suggestions.append(f"⚠️ Used {iterations} steps — consider if fewer would suffice")
        penalty += 2
    elif iterations > 4:
        penalty += 1

    # --- Check token usage ---
    if total_tokens > 10000:
        suggestions.append(f"📊 High token usage ({total_tokens:,}) — response may be verbose")
        penalty += 2
    elif total_tokens > 8000:
        suggestions.append(f"📊 Moderate token usage ({total_tokens:,})")
        penalty += 1

    # --- Check response time ---
    if total_ms > 60000:
        suggestions.append(f"🐌 Very slow response ({total_ms/1000:.1f}s) — consider fewer tool calls")
        penalty += 2
    elif total_ms > 30000:
        suggestions.append(f"⏱️ Slow response ({total_ms/1000:.1f}s)")
        penalty += 1

    # --- Check for unnecessary tool calls ---
    tools_used = [s.get("action") for s in tool_steps]
    if "web_search" in tools_used and "wikipedia" in tools_used:
        # Using both for the same query might be redundant
        suggestions.append("💡 Both web_search and wikipedia used — one might have sufficed")
        penalty += 1

    # --- Estimate optimal tool calls ---
    # Simple heuristic: most queries need 1-2 tool calls
    if tool_calls == 0:
        optimal = 0  # No tools needed (general knowledge)
    elif tool_calls <= 2:
        optimal = tool_calls  # Already optimal
    else:
        optimal = max(1, tool_calls - 1)  # Could probably do with 1 fewer

    # --- Determine efficiency rating ---
    if penalty == 0:
        rating = "Optimal"
        if not suggestions:
            suggestions.append("✅ Efficient execution — no issues detected")
    elif penalty <= 2:
        rating = "Good"
    elif penalty <= 4:
        rating = "Fair"
    else:
        rating = "Wasteful"

    return CostReport(
        iterations=iterations,
        tool_calls=tool_calls,
        optimal_tool_calls=optimal,
        total_tokens=total_tokens,
        llm_calls=llm_calls,
        total_ms=total_ms,
        llm_ms=llm_ms,
        vector_search_ms=vs_ms,
        efficiency_rating=rating,
        suggestions=suggestions,
    )
