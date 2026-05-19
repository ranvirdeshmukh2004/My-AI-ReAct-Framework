"""
mcp — Model Context Protocol Integration
============================================
Provides optional MCP client support for the ReAct agent.
When enabled, the agent can discover and use tools from
external MCP servers (via SSE/HTTP or stdio transport).

This is fully additive — native tools are never affected.
"""

from agent.mcp.client import MCPManager

__all__ = ["MCPManager"]
