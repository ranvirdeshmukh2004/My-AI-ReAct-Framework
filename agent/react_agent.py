"""
react_agent.py — Core AI Agent Loop
=========================================
The brain of the AI agent. Implements the ReAct
(Reason + Act) framework with:
- Redis caching for LLM and tool responses
- Supabase/SQLite memory for conversations
- Multi-provider RAG for document search (Pinecone, Weaviate, Qdrant)

    Thought → Action → Observation → ... → Final Answer
"""

import os
import time
from agent.llm import chat_completion, get_last_usage, reset_usage_accumulator, accumulate_usage
from agent.parser import (
    parse_llm_output,
    format_tool_descriptions,
    AgentAction,
    AgentFinish,
)
from agent.memory import get_memory, ConversationMemory
from agent.cache import RedisCache
from agent.rag import DocumentStore
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
from tools.rag_search_tool import rag_search_tool, set_document_store
import re as _re


# ============================================
# Source Extraction Helpers
# ============================================

def extract_sources(text: str) -> list[dict]:
    """Parse [SOURCES] block from tool output."""
    sources = []
    match = _re.search(r'\[SOURCES\]\n(.+)', text, _re.DOTALL)
    if not match:
        return sources
    for line in match.group(1).strip().split('\n'):
        m = _re.match(r'\[(\d+)\]\s*(.+?)\s*\|\s*(.+)', line.strip())
        if m:
            sources.append({"title": m.group(2).strip(), "url": m.group(3).strip()})
    return sources


def renumber_sources(text: str, offset: int) -> str:
    """Renumber [Source N] and [N] references in text by offset."""
    if offset == 0:
        return text
    def _replace(m):
        old_num = int(m.group(1))
        return m.group(0).replace(str(old_num), str(old_num + offset))
    text = _re.sub(r'\[Source (\d+)\]', _replace, text)
    # Also renumber in the [SOURCES] block
    lines = text.split('\n')
    new_lines = []
    in_sources = False
    for line in lines:
        if line.strip() == '[SOURCES]':
            in_sources = True
            new_lines.append(line)
            continue
        if in_sources:
            m = _re.match(r'\[(\d+)\](.+)', line)
            if m:
                new_lines.append(f'[{int(m.group(1)) + offset}]{m.group(2)}')
                continue
        new_lines.append(line)
    return '\n'.join(new_lines)


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
    An autonomous AI agent using the ReAct framework
    with caching, cloud memory, and RAG capabilities.
    """

    def __init__(self, max_iterations: int = None, vector_provider: str = "pinecone"):
        self.max_iterations = max_iterations or int(os.getenv("MAX_ITERATIONS", "10"))
        self.prompt_template = load_prompt_template()

        # Initialize infrastructure
        self.memory, self.memory_backend = get_memory()
        self.cache = RedisCache()
        self.doc_store = DocumentStore(provider=vector_provider)

        # Connect RAG tool to document store
        set_document_store(self.doc_store)

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
        self.tool_registry.register(rag_search_tool)

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

    def get_infrastructure_status(self) -> dict:
        """Get status of all infrastructure components."""
        return {
            "memory": {
                "backend": self.memory_backend,
                "connected": True,
            },
            "cache": {
                "backend": "Redis" if self.cache.is_redis else "In-Memory",
                "connected": self.cache.is_redis,
                "stats": self.cache.stats,
            },
            "rag": {
                "backend": self.doc_store.provider_name,
                "connected": self.doc_store.is_available,
                "documents": self.doc_store.indexed_documents,
            },
        }

    def run(self, user_input: str, session_id: str = None, skip_cache: bool = False) -> dict:
        """
        Run the ReAct agent on a user query.
        
        Returns dict with: final_answer, steps, session_id, cached, token_usage, timing
        """
        run_start = time.time()

        if session_id is None:
            session_id = self.memory.new_session_id()

        # Save user message to memory
        self.memory.add_message(session_id, "user", user_input)

        # --- Check LLM cache first ---
        cached_answer = None if skip_cache else self.cache.get("llm", user_input)
        if cached_answer:
            self.memory.add_message(session_id, "assistant", cached_answer)
            return {
                "final_answer": cached_answer,
                "steps": [{
                    "type": "final_answer",
                    "thought": "Retrieved from cache",
                    "final_answer": cached_answer,
                    "iteration": 0,
                    "cached": True,
                }],
                "session_id": session_id,
                "cached": True,
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "llm_calls": 0},
                "timing": {"total_ms": round((time.time() - run_start) * 1000, 1), "llm_ms": 0, "vector_search_ms": 0},
                "vector_provider": self.doc_store.provider_name,
                "sources": [],
            }

        # Build the full prompt
        system_prompt = self._build_system_prompt()
        history_text = self._format_history(session_id)
        full_system_prompt = system_prompt.replace("{history}", history_text).replace("{input}", user_input)

        steps = []
        token_usage = reset_usage_accumulator()
        llm_time_ms = 0
        vector_search_ms = 0
        all_sources = []  # Accumulated sources across all tool calls
        messages = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": f"Remember: Start with 'Thought:' and use tools when appropriate. For math, ALWAYS use the calculator tool.\n\nUser query: {user_input}"},
        ]

        # ============================================
        # ReAct Loop
        # ============================================
        for iteration in range(self.max_iterations):
            t_llm = time.time()
            llm_response = chat_completion(messages)
            llm_time_ms += (time.time() - t_llm) * 1000
            accumulate_usage(token_usage, get_last_usage())
            parsed = parse_llm_output(llm_response)

            if isinstance(parsed, AgentFinish):
                step = {
                    "type": "final_answer",
                    "thought": parsed.thought,
                    "final_answer": parsed.final_answer,
                    "iteration": iteration + 1,
                    "cached": False,
                }
                steps.append(step)

                # Cache the final answer
                self.cache.set("llm", user_input, parsed.final_answer)
                self.memory.add_message(session_id, "assistant", parsed.final_answer)

                return {
                    "final_answer": parsed.final_answer,
                    "steps": steps,
                    "session_id": session_id,
                    "cached": False,
                    "token_usage": token_usage,
                    "timing": {
                        "total_ms": round((time.time() - run_start) * 1000, 1),
                        "llm_ms": round(llm_time_ms, 1),
                        "vector_search_ms": round(vector_search_ms, 1),
                    },
                    "vector_provider": self.doc_store.provider_name,
                    "sources": all_sources,
                }

            elif isinstance(parsed, AgentAction):
                step = {
                    "type": "tool_use",
                    "thought": parsed.thought,
                    "action": parsed.action,
                    "action_input": parsed.action_input,
                    "iteration": iteration + 1,
                    "cached": False,
                }

                # --- Check tool cache ---
                tool_cached = self.cache.get(parsed.action, parsed.action_input)
                if tool_cached and not skip_cache:
                    observation = tool_cached
                    step["cached"] = True
                else:
                    observation = self.tool_registry.execute(
                        parsed.action, parsed.action_input
                    )
                    # Capture vector search time if doc_search was used
                    if parsed.action == "doc_search":
                        from tools.rag_search_tool import get_last_search_time_ms
                        vector_search_ms += get_last_search_time_ms()
                    # Cache tool result
                    self.cache.set(parsed.action, parsed.action_input, observation)

                step["observation"] = observation
                steps.append(step)

                # Extract and accumulate sources from tool output
                new_sources = extract_sources(observation)
                if new_sources:
                    offset = len(all_sources)
                    all_sources.extend(new_sources)
                    # Renumber sources in the observation for the LLM
                    observation = renumber_sources(observation, offset)

                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": f"Observation: {observation}",
                })

        # ============================================
        # Max iterations reached
        # ============================================
        fallback_answer = (
            "I've reached my maximum reasoning steps. "
            "Based on what I've gathered so far, here's my best answer:\n\n"
        )

        messages.append({
            "role": "user",
            "content": "You've reached the maximum number of steps. "
                       "Please provide your Final Answer now.",
        })

        try:
            t_llm = time.time()
            final_response = chat_completion(messages)
            llm_time_ms += (time.time() - t_llm) * 1000
            accumulate_usage(token_usage, get_last_usage())
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
            "cached": False,
        })

        self.memory.add_message(session_id, "assistant", fallback_answer)

        return {
            "final_answer": fallback_answer,
            "steps": steps,
            "session_id": session_id,
            "cached": False,
            "token_usage": token_usage,
            "timing": {
                "total_ms": round((time.time() - run_start) * 1000, 1),
                "llm_ms": round(llm_time_ms, 1),
                "vector_search_ms": round(vector_search_ms, 1),
            },
            "vector_provider": self.doc_store.provider_name,
            "sources": all_sources,
        }

    def get_available_tools(self) -> list[dict]:
        """Get information about all available tools."""
        return self.tool_registry.get_tool_descriptions()
