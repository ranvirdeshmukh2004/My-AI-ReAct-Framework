"""
base.py — Tool System Foundation
===================================
Defines the Tool dataclass and ToolRegistry for managing
all available tools in the agent.

Each tool is a simple object with:
- name: unique identifier
- description: what the tool does (shown to the LLM)
- function: the Python callable that executes the tool
"""

from dataclasses import dataclass
from typing import Callable, Any


# ============================================
# Tool Definition
# ============================================

@dataclass
class Tool:
    """
    A tool that the agent can use.
    
    Attributes:
        name: Unique identifier (e.g., "web_search", "calculator").
        description: Human-readable description shown to the LLM
                     so it knows when to use this tool.
        function: The callable that actually executes the tool.
                  Should accept a single string argument and return a string.
    """
    name: str
    description: str
    function: Callable[[str], str]


# ============================================
# Tool Registry
# ============================================

class ToolRegistry:
    """
    Registry for managing available tools.
    
    Usage:
        registry = ToolRegistry()
        registry.register(Tool(
            name="calculator",
            description="Performs math calculations",
            function=my_calc_function,
        ))
        
        # Look up a tool by name
        tool = registry.get("calculator")
        result = tool.function("2 + 2")
        
        # Get all tool descriptions for the LLM prompt
        descriptions = registry.get_tool_descriptions()
    """

    def __init__(self):
        """Initialize an empty tool registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """
        Register a new tool.
        
        Args:
            tool: The Tool object to register.
        
        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered!")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """
        Look up a tool by name.
        
        Args:
            name: The tool's unique name.
        
        Returns:
            The Tool object, or None if not found.
        """
        return self._tools.get(name)

    def execute(self, name: str, input_text: str) -> str:
        """
        Execute a tool by name with the given input.
        
        Args:
            name: The tool's unique name.
            input_text: The input string to pass to the tool.
        
        Returns:
            The tool's output as a string.
        """
        tool = self.get(name)
        if tool is None:
            return f"❌ Error: Tool '{name}' not found. Available tools: {', '.join(self._tools.keys())}"
        
        try:
            result = tool.function(input_text)
            return str(result)
        except Exception as e:
            return f"❌ Error executing tool '{name}': {str(e)}"

    def get_tool_descriptions(self) -> list[dict]:
        """
        Get descriptions of all registered tools.
        
        Returns:
            List of dicts with 'name' and 'description' keys.
        """
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self._tools.values()
        ]

    def list_names(self) -> list[str]:
        """Get a list of all registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)
