"""
bridge.py — MCP Tool → ReAct Tool Bridge
============================================
Converts MCP tools (discovered from servers) into ReAct-compatible
Tool objects that can be registered in the ToolRegistry.

Each MCP tool gets a [MCP] prefix in its description so the LLM
and user can distinguish them from native tools.
"""

from tools.base import Tool


def create_mcp_tools(mcp_manager) -> list:
    """
    Convert all MCP tools into ReAct-compatible Tool objects.

    Args:
        mcp_manager: An MCPManager instance with connected servers.

    Returns:
        List of Tool objects ready for ToolRegistry.register().
    """
    tools = []

    for mcp_tool in mcp_manager.get_all_tools():
        tool_name = mcp_tool["name"]
        description = mcp_tool.get("description", "")

        # Build a useful description that includes parameter hints
        param_hint = _build_param_hint(mcp_tool.get("input_schema", {}))
        full_description = f"[MCP] {description}"
        if param_hint:
            full_description += f" {param_hint}"

        # Create a closure that captures the tool name
        def make_fn(tn):
            def fn(input_text: str) -> str:
                return mcp_manager.call_tool_sync(tn, input_text)
            return fn

        tools.append(Tool(
            name=tool_name,
            description=full_description,
            function=make_fn(tool_name),
        ))

    return tools


def _build_param_hint(schema: dict) -> str:
    """
    Build a short parameter hint string from the tool's input schema.

    Examples:
        {"properties": {"query": {"type": "string"}}} → "(Input: a query string)"
        {"properties": {"a": ..., "b": ...}} → "(Input: JSON with keys: a, b)"
    """
    if not schema:
        return ""

    properties = schema.get("properties", {})
    if not properties:
        return ""

    if len(properties) == 1:
        param_name = list(properties.keys())[0]
        param_type = properties[param_name].get("type", "string")
        param_desc = properties[param_name].get("description", "")
        if param_desc:
            return f"(Input: {param_desc})"
        return f"(Input: a {param_type})"

    # Multiple parameters — hint that JSON input is expected
    keys = ", ".join(properties.keys())
    return f"(Input: JSON with keys: {keys})"
