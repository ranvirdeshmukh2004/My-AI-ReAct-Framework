"""
quality_scorer.py — LLM-Based Quality & Fact-Check Auditor
=============================================================
Uses a single LLM call (Gemini Flash free) to:
1. Score response quality on 4 dimensions (0-10)
2. Extract and verify factual claims against tool observations
"""

import os
import json
from agent.auditor.base import QualityScore, FactCheckResult
from agent.llm import chat_completion, _get_secret

# Load auditor prompt template
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "auditor_prompt.txt")


def _load_auditor_prompt() -> str:
    """Load the auditor system prompt from file."""
    with open(_PROMPT_PATH, "r") as f:
        return f.read()


def _collect_observations(steps: list) -> str:
    """Extract all tool observations from the agent's steps."""
    observations = []
    for step in steps:
        if step.get("type") == "tool_use" and step.get("observation"):
            tool = step.get("action", "unknown")
            obs = step["observation"]
            # Truncate very long observations
            if len(obs) > 1500:
                obs = obs[:1500] + "... [truncated]"
            observations.append(f"[{tool}] {obs}")
    return "\n\n".join(observations) if observations else "No tool observations (general knowledge answer)."


def _parse_audit_json(raw: str) -> dict:
    """Parse the auditor's JSON response, handling common issues."""
    if not raw:
        return {}
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def run_quality_audit(
    query: str,
    answer: str,
    steps: list,
    sources: list,
    model: str = None,
) -> tuple:
    """
    Run quality scoring and fact checking via a single LLM call.

    Args:
        query: The user's original question.
        answer: The agent's final answer.
        steps: List of ReAct steps (for extracting observations).
        sources: List of source dicts.
        model: LLM model to use for auditing.

    Returns:
        Tuple of (QualityScore, FactCheckResult), either may be None on failure.
    """
    auditor_model = model or _get_secret("AUDITOR_MODEL", "google/gemini-2.0-flash-exp:free")

    system_prompt = _load_auditor_prompt()
    observations_text = _collect_observations(steps)

    # Truncate answer if very long
    answer_text = answer[:3000] if len(answer) > 3000 else answer

    user_message = (
        f"USER QUERY:\n{query}\n\n"
        f"AI AGENT'S ANSWER:\n{answer_text}\n\n"
        f"TOOL OBSERVATIONS:\n{observations_text}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # Call the auditor LLM (cheap/free model)
    raw_response = chat_completion(
        messages=messages,
        model=auditor_model,
        temperature=0.1,  # Low temperature for consistent scoring
        max_tokens=1024,
    )

    data = _parse_audit_json(raw_response)
    if not data:
        return None, None

    # Parse quality scores
    quality = None
    q = data.get("quality", {})
    if q:
        quality = QualityScore(
            accuracy=min(10, max(0, q.get("accuracy", 0))),
            completeness=min(10, max(0, q.get("completeness", 0))),
            relevance=min(10, max(0, q.get("relevance", 0))),
            citation_quality=min(10, max(0, q.get("citation_quality", 0))),
            summary=q.get("summary", ""),
        )

    # Parse fact check
    fact_check = None
    fc = data.get("fact_check", {})
    claims_data = fc.get("claims", [])
    if claims_data:
        verified = sum(1 for c in claims_data if c.get("status") == "verified")
        unverified = sum(1 for c in claims_data if c.get("status") == "unverified")
        hallucinated = sum(1 for c in claims_data if c.get("status") == "hallucinated")
        fact_check = FactCheckResult(
            total_claims=len(claims_data),
            verified=verified,
            unverified=unverified,
            hallucinated=hallucinated,
            claims=[
                {
                    "claim": c.get("claim", ""),
                    "status": c.get("status", "unverified"),
                    "evidence": c.get("evidence", ""),
                }
                for c in claims_data
            ],
        )

    return quality, fact_check
