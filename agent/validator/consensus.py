"""
consensus.py — Multi-Model Consensus Validator
=================================================
Uses a DIFFERENT free model to independently answer the
same question, then compares the two answers for agreement.
2 LLM calls total (both free models).
"""

import os
import json
import re
from agent.llm import chat_completion


# Model rotation map: if agent uses X, validator uses Y
_MODEL_ROTATION = {
    "deepseek/deepseek-v4-flash:free": "google/gemma-4-31b-it:free",
    "google/gemma-4-31b-it:free": "deepseek/deepseek-v4-flash:free",
    "meta-llama/llama-3.3-70b-instruct:free": "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free": "google/gemma-4-31b-it:free",
    "openai/gpt-oss-120b:free": "deepseek/deepseek-v4-flash:free",
}
_DEFAULT_VALIDATOR_MODEL = "google/gemma-4-31b-it:free"


def _pick_validator_model(agent_model: str, explicit_model: str = None) -> str:
    """Pick a different model than the one the agent used."""
    if explicit_model:
        return explicit_model
    return _MODEL_ROTATION.get(agent_model, _DEFAULT_VALIDATOR_MODEL)


def _load_comparison_prompt() -> str:
    """Load the comparison system prompt."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "prompts", "validator_prompt.txt",
    )
    try:
        with open(prompt_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return (
            "Compare the two answers below. Return JSON with: "
            "agreement (full/partial/contradiction), score (0-10), "
            "agent_summary, validator_summary, differences."
        )


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip()

    # Remove markdown code fences
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    brace_match = re.search(r'\{[\s\S]*\}', text)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    return {}


def run_consensus(
    query: str,
    agent_answer: str,
    agent_model: str,
    validator_model: str = None,
) -> dict:
    """
    Multi-model consensus validation.

    Step 1: Ask a DIFFERENT model to answer the same question.
    Step 2: Compare both answers using a structured prompt.

    Args:
        query: The original user question.
        agent_answer: The agent's final answer.
        agent_model: The model the agent used (so we pick a different one).
        validator_model: Explicit override for the validator model.

    Returns:
        ConsensusResult dict.
    """
    from agent.validator.base import ConsensusResult

    v_model = _pick_validator_model(agent_model, validator_model)

    # --- Step 1: Independent answer from a different model ---
    try:
        independent_answer = chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a knowledgeable assistant. Answer the user's question "
                        "concisely and factually. Focus on key facts, numbers, and dates. "
                        "Keep your answer under 200 words."
                    ),
                },
                {"role": "user", "content": query},
            ],
            model=v_model,
            temperature=0.3,
            max_tokens=500,
        )
    except Exception:
        return ConsensusResult(
            score=5,
            agreement="not_run",
            agent_summary="",
            validator_summary="Validator model call failed",
            validator_model=v_model,
        )

    # --- Step 2: Compare answers using structured prompt ---
    comparison_prompt = _load_comparison_prompt()

    try:
        comparison_raw = chat_completion(
            messages=[
                {"role": "system", "content": comparison_prompt},
                {
                    "role": "user",
                    "content": (
                        f"## User Query\n{query}\n\n"
                        f"## Answer A (Primary Agent)\n{agent_answer[:1500]}\n\n"
                        f"## Answer B (Independent Validator)\n{independent_answer[:1500]}"
                    ),
                },
            ],
            model=v_model,
            temperature=0.1,
            max_tokens=600,
        )
    except Exception:
        return ConsensusResult(
            score=5,
            agreement="not_run",
            agent_summary="",
            validator_summary=independent_answer[:200],
            validator_model=v_model,
        )

    # --- Parse comparison result ---
    parsed = _parse_json(comparison_raw)

    if not parsed:
        # Couldn't parse — fallback to partial
        return ConsensusResult(
            score=5,
            agreement="partial",
            agent_summary="",
            validator_summary=independent_answer[:200],
            differences=["Could not parse comparison result"],
            validator_model=v_model,
        )

    return ConsensusResult(
        score=min(10, max(0, parsed.get("score", 5))),
        agreement=parsed.get("agreement", "partial"),
        agent_summary=parsed.get("agent_summary", "")[:300],
        validator_summary=parsed.get("validator_summary", "")[:300],
        differences=parsed.get("differences", [])[:5],
        validator_model=v_model,
    )
