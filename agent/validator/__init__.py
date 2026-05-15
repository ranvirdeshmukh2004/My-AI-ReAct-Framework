"""
validator — AI Agent Independent Verification System
======================================================
Provides post-response validation by independently verifying
the agent's answer through multiple strategies:

- Multi-Model Consensus: A different model answers independently & compares
- Math Re-Verification: Re-evaluates calculator expressions
- Tool Re-Execution: Re-runs deterministic tool calls
- Source URL Validation: Checks if cited URLs are accessible

Combined Validation Score: weighted 0-10
"""

from agent.validator.base import ValidationReport
from agent.validator.consensus import run_consensus
from agent.validator.math_validator import run_math_validation
from agent.validator.tool_rerun import run_tool_rerun
from agent.validator.source_validator import run_source_validation


def run_full_validation(
    query: str,
    answer: str,
    steps: list,
    sources: list,
    agent_model: str = "",
    validator_model: str = None,
) -> ValidationReport:
    """
    Run all validators and return a combined ValidationReport.

    Args:
        query: Original user question.
        answer: Agent's final answer text.
        steps: List of agent step dicts from the ReAct loop.
        sources: List of source dicts from tool calls.
        agent_model: The model the agent used (for consensus rotation).
        validator_model: Explicit override for consensus validator model.

    Returns:
        ValidationReport with overall weighted score (0-10).
    """
    # 1. Math Re-Verification — pure Python, always runs
    math = None
    try:
        math = run_math_validation(steps)
    except Exception:
        pass

    # 2. Tool Re-Execution — pure Python + tool calls, always runs
    tool_rerun = None
    try:
        tool_rerun = run_tool_rerun(steps)
    except Exception:
        pass

    # 3. Source URL Validation — HTTP only, always runs
    source_url = None
    try:
        source_url = run_source_validation(sources)
    except Exception:
        pass

    # 4. Multi-Model Consensus — 2 LLM calls (most expensive, run last)
    consensus = None
    try:
        consensus = run_consensus(
            query=query,
            agent_answer=answer,
            agent_model=agent_model,
            validator_model=validator_model,
        )
    except Exception:
        pass

    return ValidationReport(
        consensus=consensus,
        math=math,
        tool_rerun=tool_rerun,
        source_url=source_url,
    )
