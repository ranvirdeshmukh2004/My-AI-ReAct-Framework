"""
parser.py — ReAct Output Parser
=================================
Parses the LLM's text output into structured components:
- Thought: The agent's reasoning
- Action: Which tool to use
- Action Input: What to pass to the tool
- Final Answer: The terminal response

Uses regex to extract each block from the LLM's free-form text.
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
    # Clean up the text
    if not text:
        return AgentFinish(thought="", final_answer="I wasn't able to generate a response. Please try again.")
    text = text.strip()

    # --- Check for Final Answer first ---
    final_answer_match = re.search(
        r"Final\s*Answer\s*:\s*(.*)",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if final_answer_match:
        final_answer = final_answer_match.group(1).strip()
        thought = extract_thought(text)
        return AgentFinish(thought=thought, final_answer=final_answer)

    # --- Check for Action (tool use) ---
    action_match = re.search(
        r"Action\s*:\s*(.+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    action_input_match = re.search(
        r"Action\s*Input\s*:\s*(.*?)(?:\n\s*(?:Thought|Action|Observation|Final)|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    if action_match:
        action = action_match.group(1).strip()
        action_input = ""
        if action_input_match:
            action_input = action_input_match.group(1).strip()
        thought = extract_thought(text)

        return AgentAction(
            thought=thought,
            action=action,
            action_input=action_input,
        )

    # --- Fallback: Treat entire output as a final answer ---
    # This handles cases where the LLM doesn't follow the format exactly
    return AgentFinish(
        thought="",
        final_answer=text,
    )


def extract_thought(text: str) -> str:
    """
    Extract the Thought block from the LLM output.
    
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
