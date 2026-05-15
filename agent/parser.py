"""
parser.py — ReAct Output Parser
=================================
Parses the LLM's text output into structured components:
- Thought: The agent's reasoning
- Action: Which tool to use
- Action Input: What to pass to the tool
- Final Answer: The terminal response

Uses regex to extract each block from the LLM's free-form text.
Includes defensive handling for models (like DeepSeek) that:
  - Wrap reasoning in <think>...</think> tags
  - Simulate multi-step loops in a single response
  - Write Action and Action Input on the same line
"""

import re
from dataclasses import dataclass
from typing import Optional


# ============================================
# Data Classes
# ============================================

@dataclass
class AgentAction:
    """Represents a tool invocation step."""
    thought: str       # The agent's reasoning
    action: str        # Tool name to call
    action_input: str  # Input to pass to the tool


@dataclass
class AgentFinish:
    """Represents the agent's final answer."""
    thought: str       # The agent's final reasoning
    final_answer: str  # The complete answer to the user


# Type alias for parser output
ParseResult = AgentAction | AgentFinish


# ============================================
# Text Cleaning
# ============================================

def _clean_llm_text(text: str) -> str:
    """
    Clean raw LLM output before parsing.
    
    1. Strip <think>...</think> reasoning tags (DeepSeek, Gemma, etc.)
    2. Strip unclosed <think> tags (model got cut off mid-reasoning)
    3. Truncate at the first 'Observation:' — models should NEVER generate
       observations; those come from real tool execution.
    """
    if not text:
        return ""
    
    text = text.strip()
    
    # Strip completed <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Strip unclosed <think> blocks (model got cut off)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip()
    
    # Truncate at the first "Observation:" — the model should never
    # generate this; it means the model is simulating tool output.
    obs_match = re.search(r"\nObservation\s*:", text)
    if obs_match:
        text = text[:obs_match.start()].strip()
    
    return text


# ============================================
# Parser Functions
# ============================================

def parse_llm_output(text: str) -> ParseResult:
    """
    Parse the LLM's raw text output into a structured result.
    
    The LLM should output in one of two formats:
    
    Format 1 (Tool Use):
        Thought: <reasoning>
        Action: <tool_name>
        Action Input: <input>
    
    Format 2 (Final Answer):
        Thought: <reasoning>
        Final Answer: <answer>
    
    Args:
        text: Raw text from the LLM.
    
    Returns:
        AgentAction if the agent wants to use a tool,
        AgentFinish if the agent is ready to give a final answer.
    """
    # Clean the text (strip think tags, truncate at fake observations)
    text = _clean_llm_text(text)
    
    if not text:
        return AgentFinish(
            thought="",
            final_answer="I wasn't able to generate a response. Please try again.",
        )

    # --- Check for Final Answer ---
    # If multiple Final Answer blocks exist, take the LAST one (most refined)
    final_answer_matches = list(re.finditer(
        r"Final\s*Answer\s*:\s*(.*?)(?=\nThought\s*:|\nAction\s*:|\nFinal\s*Answer\s*:|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    ))
    
    # Also check for a trailing Final Answer that goes to end of string
    trailing_match = re.search(
        r"Final\s*Answer\s*:\s*(.*)\Z",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    # --- Check for Action (tool use) ---
    # Try the clean multi-line format first:
    #   Action: tool_name
    #   Action Input: value
    action_match = re.search(
        r"Action\s*:\s*(.+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )

    # Determine: does this response want to use a tool or give a final answer?
    # Priority: if there's an Action BEFORE a Final Answer, it's a tool call.
    # If Final Answer comes first (or is the only thing), it's a finish.
    
    has_action = action_match is not None
    has_final = bool(final_answer_matches) or trailing_match is not None
    
    if has_action and has_final:
        # Both exist — whichever comes FIRST in the text wins
        action_pos = action_match.start() if action_match else float('inf')
        final_pos = min(
            (m.start() for m in final_answer_matches),
            default=float('inf')
        )
        if trailing_match:
            final_pos = min(final_pos, trailing_match.start())
        
        if action_pos < final_pos:
            # Action comes first — treat as tool call
            return _parse_action(text, action_match)
        else:
            # Final Answer comes first — treat as finish
            return _parse_final_answer(text, final_answer_matches, trailing_match)
    
    elif has_action:
        return _parse_action(text, action_match)
    
    elif has_final:
        return _parse_final_answer(text, final_answer_matches, trailing_match)
    
    # --- Fallback: no Action or Final Answer found ---
    # The model didn't follow format. Treat the whole thing as a final answer.
    return AgentFinish(thought="", final_answer=text)


def _parse_action(text: str, action_match: re.Match) -> AgentAction:
    """Extract Action and Action Input from the text."""
    raw_action = action_match.group(1).strip()
    
    # Handle inline format: "Action: web_search Action Input: Lenskart"
    inline_match = re.match(
        r"(\S+)\s+Action\s*Input\s*:\s*(.*)",
        raw_action,
        re.IGNORECASE | re.DOTALL,
    )
    if inline_match:
        action = inline_match.group(1).strip()
        action_input = inline_match.group(2).strip()
    else:
        action = raw_action
        # Look for Action Input on a separate line
        input_match = re.search(
            r"Action\s*Input\s*:\s*(.*?)(?:\n\s*(?:Thought|Action|Observation|Final)|$)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        action_input = input_match.group(1).strip() if input_match else ""
    
    thought = extract_thought(text)
    
    return AgentAction(
        thought=thought,
        action=action,
        action_input=action_input,
    )


def _parse_final_answer(
    text: str,
    matches: list[re.Match],
    trailing_match: re.Match | None,
) -> AgentFinish:
    """Extract the Final Answer — use the last/best one if multiple exist."""
    # Use trailing match (captures everything to end of string) if available
    if trailing_match:
        final_answer = trailing_match.group(1).strip()
    elif matches:
        final_answer = matches[-1].group(1).strip()  # Last match = most refined
    else:
        final_answer = ""
    
    # Clean up: remove any trailing "Thought:" fragments
    final_answer = re.split(r"\n\s*Thought\s*:", final_answer)[0].strip()
    
    thought = extract_thought(text)
    return AgentFinish(thought=thought, final_answer=final_answer)


def extract_thought(text: str) -> str:
    """
    Extract the FIRST Thought block from the LLM output.
    
    Args:
        text: Raw LLM output text.
    
    Returns:
        The thought content, or empty string if not found.
    """
    thought_match = re.search(
        r"Thought\s*:\s*(.*?)(?:\n\s*(?:Action|Final\s*Answer)|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if thought_match:
        return thought_match.group(1).strip()
    return ""


def format_tool_descriptions(tools: list[dict]) -> str:
    """
    Format tool descriptions for injection into the system prompt.
    
    Args:
        tools: List of tool info dicts with 'name' and 'description' keys.
    
    Returns:
        Formatted string listing all available tools.
    """
    lines = []
    for tool in tools:
        name = tool["name"]
        desc = tool["description"]
        lines.append(f"  - {name}: {desc}")
    return "\n".join(lines)
