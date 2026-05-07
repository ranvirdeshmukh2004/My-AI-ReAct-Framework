"""
react_agent.py — Core AI Agent Loop
=========================================
The brain of the AI agent. Implements the ReAct
(Reason + Act) framework:

    Thought → Action → Observation → ... → Final Answer

The agent:
1. Receives a user query
2. Sends it to the LLM with tool descriptions
3. Parses the LLM's output (Thought/Action/Final Answer)
4. If Action → executes the tool, feeds result back as Observation
5. Repeats until Final Answer or max iterations reached
"""

import os
from agent.llm import chat_completion
from agent.parser import (
    parse_llm_output,
    format_tool_descriptions,
    AgentAction,
    AgentFinish,
)
from agent.memory import ConversationMemory
from tools.base import ToolRegistry

# Import all tools
from tools.search_tool import search_tool
from tools.calculator_tool import calculator_tool
from tools.file_tool import file_tool
from tools.python_tool import python_tool
from tools.weather_tool import weather_tool
from tools.wikipedia_tool import wikipedia_tool
from tools.url_reader_tool import url_reader_tool
from tools.datetime_tool import datetime_tool


# ============================================
# Load the ReAct prompt template
# ============================================

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "react_prompt.txt")


def load_prompt_template() -> str:
    """Load the ReAct system prompt from file."""
    with open(PROMPT_PATH, "r") as f:
        return f.read()


# ============================================
# ReAct Agent Class
# ============================================

class ReactAgent:
    """
    An autonomous AI agent using the ReAct framework.
    
    The agent reasons step-by-step, chooses tools dynamically,
    executes them, observes outputs, and continues until it
    can provide a final answer.
    
    Usage:
        agent = ReactAgent()
        result = agent.run("What is 2^10 + the population of Tokyo?")
        print(result["final_answer"])
        print(result["steps"])  # Full reasoning trace
    """

    def __init__(self, max_iterations: int = None):
        """
        Initialize the ReAct agent.
        
        Args:
            max_iterations: Maximum reasoning steps before forcing
                           a final answer (default from env or 10).
        """
        self.max_iterations = max_iterations or int(os.getenv("MAX_ITERATIONS", "10"))
        self.memory = ConversationMemory()
        self.prompt_template = load_prompt_template()

        # Initialize and register all tools
        self.tool_registry = ToolRegistry()
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all built-in tools."""
        self.tool_registry.register(search_tool)
        self.tool_registry.register(calculator_tool)
        self.tool_registry.register(file_tool)
        self.tool_registry.register(python_tool)
        self.tool_registry.register(weather_tool)
        self.tool_registry.register(wikipedia_tool)
        self.tool_registry.register(url_reader_tool)
        self.tool_registry.register(datetime_tool)

    def _build_system_prompt(self) -> str:
        """Build the system prompt with tool descriptions injected."""
        tool_descriptions = format_tool_descriptions(
            self.tool_registry.get_tool_descriptions()
        )
        return self.prompt_template.replace("{tools}", tool_descriptions)

    def _format_history(self, session_id: str) -> str:
        """Format conversation history for the prompt."""
        messages = self.memory.get_messages_for_llm(session_id, limit=10)
        if not messages:
            return "No previous conversation."

        lines = []
        for msg in messages:
            role = msg["role"].capitalize()
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def run(self, user_input: str, session_id: str = None) -> dict:
        """
        Run the ReAct agent on a user query.
        
        This is the main entry point. The agent will:
        1. Think about the query
        2. Decide if a tool is needed
        3. Execute tools and observe results
        4. Continue until a final answer is reached
        
        Args:
            user_input: The user's question or task.
            session_id: Optional session ID for conversation memory.
                       If None, creates a new session.
        
        Returns:
            dict with:
                - "final_answer": The agent's final response
                - "steps": List of reasoning steps (for display)
                - "session_id": The session ID used
        """
        # Session management
        if session_id is None:
            session_id = self.memory.new_session_id()

        # Save user message to memory
        self.memory.add_message(session_id, "user", user_input)

        # Build the full prompt
        system_prompt = self._build_system_prompt()
        history_text = self._format_history(session_id)

        # Prepare the system prompt (with history, but NOT the user input)
        full_system_prompt = system_prompt.replace("{history}", history_text).replace("{input}", user_input)

        # Track reasoning steps for display
        steps = []

        # The conversation context for the LLM
        # System prompt + user message as separate messages
        messages = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": f"Remember: Start with 'Thought:' and use tools when appropriate. For math, ALWAYS use the calculator tool.\n\nUser query: {user_input}"},
        ]

        # ============================================
        # ReAct Loop
        # ============================================

        for iteration in range(self.max_iterations):
            # --- Step 1: Get LLM response ---
            llm_response = chat_completion(messages)

            # --- Step 2: Parse the response ---
            parsed = parse_llm_output(llm_response)

            if isinstance(parsed, AgentFinish):
                # Agent is ready with a final answer
                step = {
                    "type": "final_answer",
                    "thought": parsed.thought,
                    "final_answer": parsed.final_answer,
                    "iteration": iteration + 1,
                }
                steps.append(step)

                # Save to memory
                self.memory.add_message(
                    session_id, "assistant", parsed.final_answer
                )

                return {
                    "final_answer": parsed.final_answer,
                    "steps": steps,
                    "session_id": session_id,
                }

            elif isinstance(parsed, AgentAction):
                # Agent wants to use a tool
                step = {
                    "type": "tool_use",
                    "thought": parsed.thought,
                    "action": parsed.action,
                    "action_input": parsed.action_input,
                    "iteration": iteration + 1,
                }

                # --- Step 3: Execute the tool ---
                observation = self.tool_registry.execute(
                    parsed.action, parsed.action_input
                )
                step["observation"] = observation
                steps.append(step)

                # --- Step 4: Feed observation back to the LLM ---
                # Add the assistant's response and the observation
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": f"Observation: {observation}",
                })

        # ============================================
        # Max iterations reached — force a final answer
        # ============================================

        fallback_answer = (
            "I've reached my maximum reasoning steps. "
            "Based on what I've gathered so far, here's my best answer:\n\n"
        )

        # Try to get a summary from the LLM
        messages.append({
            "role": "user",
            "content": (
                "You've reached the maximum number of steps. "
                "Please provide your Final Answer now based on "
                "everything you've learned so far."
            ),
        })

        try:
            final_response = chat_completion(messages)
            final_parsed = parse_llm_output(final_response)
            if isinstance(final_parsed, AgentFinish):
                fallback_answer = final_parsed.final_answer
            else:
                fallback_answer += final_response
        except Exception:
            fallback_answer += "Unable to generate a summary."

        steps.append({
            "type": "max_iterations",
            "thought": "Reached maximum iterations",
            "final_answer": fallback_answer,
            "iteration": self.max_iterations,
        })

        self.memory.add_message(session_id, "assistant", fallback_answer)

        return {
            "final_answer": fallback_answer,
            "steps": steps,
            "session_id": session_id,
        }

    def get_available_tools(self) -> list[dict]:
        """Get information about all available tools."""
        return self.tool_registry.get_tool_descriptions()
