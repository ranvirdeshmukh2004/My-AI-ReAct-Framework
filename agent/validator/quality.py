"""
quality.py — Response Quality Evaluator
=========================================
Uses a DIFFERENT model to evaluate the agent's response on 5
universal criteria: relevance, completeness, accuracy, clarity,
and helpfulness. No auto-passes — every response gets a fair score.

1 LLM call total (using a rotated free model).
"""

import os
import json
import re
from agent.llm import chat_completion


# Model rotation map: evaluator always uses a DIFFERENT model than the agent
# Uses Groq for reliability (separate rate limits from OpenRouter)
_MODEL_ROTATION = {
    "groq::meta-llama/llama-4-scout-17b-16e-instruct": "groq::llama-3.3-70b-versatile",
    "groq::llama-3.3-70b-versatile": "groq::meta-llama/llama-4-scout-17b-16e-instruct",
    "google/gemma-4-31b-it:free": "groq::meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-3.3-70b-instruct:free": "groq::meta-llama/llama-4-scout-17b-16e-instruct",
    "nvidia/nemotron-3-super-120b-a12b:free": "groq::meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-120b:free": "groq::meta-llama/llama-4-scout-17b-16e-instruct",
}
_DEFAULT_EVAL_MODEL = "groq::llama-3.3-70b-versatile"


def _pick_eval_model(agent_model: str) -> str:
    """Pick a different model than the one the agent used."""
    return _MODEL_ROTATION.get(agent_model, _DEFAULT_EVAL_MODEL)


def _load_eval_prompt() -> str:
    """Load the quality evaluation system prompt."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "prompts", "quality_eval_prompt.txt",
    )
    try:
        with open(prompt_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return (
            "Rate this AI response on relevance, completeness, accuracy, "
            "clarity, and helpfulness (1-10 each). Return JSON."
        )


def _parse_scores(text: str) -> dict:
    """Extract JSON scores from LLM response, handling markdown fences."""
    text = text.strip()

    # Strip <think>...</think> tags if present
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

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


def _clamp(val, lo=1, hi=10) -> int:
    """Clamp a value to [lo, hi] range."""
    try:
        return max(lo, min(hi, int(val)))
    except (TypeError, ValueError):
        return 5  # Default to middle if unparseable


def run_quality_evaluation(
    query: str,
    answer: str,
    steps: list,
    agent_model: str = "",
) -> dict:
    """
    Evaluate the agent's response quality using a different LLM.

    Args:
        query: The original user question.
        answer: The agent's final answer text.
        steps: List of agent step dicts (for context on what tools were used).
        agent_model: The model the agent used (so we pick a different one).

    Returns:
        QualityResult dataclass with scores for each criterion.
    """
    from agent.validator.base import QualityResult

    eval_model = _pick_eval_model(agent_model)
    eval_prompt = _load_eval_prompt()

    # Build context about tool usage (so evaluator knows what the agent did)
    tool_context = ""
    tool_steps = [s for s in steps if s.get("type") == "tool_use"]
    if tool_steps:
        tool_names = [s.get("action", "?") for s in tool_steps]
        tool_context = f"\n\n[The AI used these tools to gather information: {', '.join(tool_names)}]"

    try:
        raw_response = chat_completion(
            messages=[
                {"role": "system", "content": eval_prompt},
                {
                    "role": "user",
                    "content": (
                        f"## User's Question\n{query}\n\n"
                        f"## AI's Response\n{answer[:2000]}"
                        f"{tool_context}"
                    ),
                },
            ],
            model=eval_model,
            temperature=0.1,
            max_tokens=500,
        )
    except Exception:
        # LLM call failed — return a neutral score
        return QualityResult(
            relevance=5, completeness=5, accuracy=5, clarity=5, helpfulness=5,
            reasoning="Quality evaluation could not be performed (model unavailable).",
            evaluator_model=eval_model,
        )

    # Parse the scores
    parsed = _parse_scores(raw_response)

    if not parsed:
        return QualityResult(
            relevance=5, completeness=5, accuracy=5, clarity=5, helpfulness=5,
            reasoning="Could not parse evaluation response.",
            evaluator_model=eval_model,
        )

    return QualityResult(
        relevance=_clamp(parsed.get("relevance", 5)),
        completeness=_clamp(parsed.get("completeness", 5)),
        accuracy=_clamp(parsed.get("accuracy", 5)),
        clarity=_clamp(parsed.get("clarity", 5)),
        helpfulness=_clamp(parsed.get("helpfulness", 5)),
        reasoning=str(parsed.get("reasoning", ""))[:300],
        evaluator_model=eval_model,
    )
