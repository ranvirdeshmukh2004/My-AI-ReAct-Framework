"""
mcp — Model Context Protocol Integration
============================================
Provides optional MCP client support for the ReAct agent.
When enabled, the agent can discover and use tools from
external MCP servers (via SSE/HTTP or stdio transport).

This is fully additive — native tools are never affected.
"""

try:
    from agent.mcp.client import MCPManager
except ImportError:
    # mcp package not installed — provide a stub so the rest of the app
    # can still import agent.mcp without crashing
    MCPManager = None

__all__ = ["MCPManager"]
