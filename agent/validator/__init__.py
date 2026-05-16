"""
validator — AI Agent Response Quality Validation
===================================================
Provides fair, unbiased post-response validation by evaluating
the agent's answer on 5 universal criteria using an independent model.

Primary:
  - Response Quality: Relevance, Completeness, Accuracy, Clarity, Helpfulness

Bonus (when applicable):
  - Math Re-Verification: Re-evaluates calculator expressions

No auto-passes. Every response gets a genuine evaluation.
"""

from agent.validator.base import ValidationReport
from agent.validator.quality import run_quality_evaluation
from agent.validator.math_validator import run_math_validation


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
        agent_model: The model the agent used (for rotation).
        validator_model: Explicit override for evaluator model.

    Returns:
        ValidationReport with overall quality-based score (0-10).
    """
    # 1. Response Quality Evaluation — 1 LLM call, ALWAYS runs
    quality = None
    try:
        quality = run_quality_evaluation(
            query=query,
            answer=answer,
            steps=steps,
            agent_model=agent_model,
        )
    except Exception:
        pass

    # 2. Math Re-Verification — 0 LLM calls, runs if calculator was used
    math = None
    try:
        math = run_math_validation(steps)
    except Exception:
        pass

    return ValidationReport(
        quality=quality,
        math=math,
    )
