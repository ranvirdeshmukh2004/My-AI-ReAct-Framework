"""
client.py — MCP Client Manager
==================================
Manages connections to multiple MCP servers, discovers their tools,
and provides sync wrappers for the async MCP protocol.

Supports two transports:
  - SSE/HTTP: Remote servers via URL (works everywhere, including Streamlit Cloud)
  - stdio: Local servers via subprocess (local dev only, requires Node.js)

Uses a dedicated background thread with its own event loop to bridge
async MCP operations into the sync ReAct agent loop.
"""

import os
import json
import asyncio
import threading
import logging

logger = logging.getLogger(__name__)


class MCPManager:
    """
    Manages connections to multiple MCP servers.

    Usage:
        mgr = MCPManager()
        mgr.add_server("brave", "https://mcp.example.com/sse", api_key="...")
        tools = mgr.get_all_tools()
        result = mgr.call_tool_sync("brave_web_search", "top MBA colleges")
        mgr.remove_server("brave")
        mgr.disconnect_all()
    """

    def __init__(self, config_path: str = None):
        """Initialize the MCP manager with a background event loop."""
        # Background event loop for async MCP operations
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Connection state
        self._sessions = {}       # server_name → ClientSession
        self._contexts = {}       # server_name → [context_managers] (kept alive)
        self._tools = {}          # tool_name → (server_name, tool_info_dict)
        self._server_info = {}    # server_name → {url, connected, tool_count, ...}

        # Load default config if exists
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "mcp_servers.json",
            )
        self._config_path = config_path
        self._load_default_servers()

    def _run_loop(self):
        """Run the background event loop forever (daemon thread)."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro, timeout: float = 30.0):
        """Submit an async coroutine to the background loop and wait for result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # ========================================
    # Default Server Config
    # ========================================

    def _load_default_servers(self):
        """Load default server configs from mcp_servers.json (auto-connect enabled ones)."""
        if not os.path.exists(self._config_path):
            return

        try:
            with open(self._config_path, "r") as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"MCP: Could not load config: {e}")
            return

        for name, cfg in config.get("servers", {}).items():
            if not cfg.get("enabled", False):
                continue

            url = cfg.get("url", "")
            transport = cfg.get("transport", "sse")

            # Resolve environment variable references like ${BRAVE_API_KEY}
            api_key_env = cfg.get("api_key_env", "")
            api_key = ""
            if api_key_env:
                api_key = os.getenv(api_key_env, "")

            if url:
                self.add_server(name, url, api_key=api_key, transport=transport)

    # ========================================
    # Server Management
    # ========================================

    def add_server(self, name: str, url: str, api_key: str = None,
                   transport: str = "sse", description: str = None) -> bool:
        """
        Connect to an MCP server and discover its tools.

        Args:
            name: Human-readable server name (e.g. "Brave Search")
            url: Server URL for SSE, or command for stdio
            api_key: Optional API key/token
            transport: "sse", "rest", or "stdio"
            description: What the server's tools do (used for REST transport)

        Returns:
            True if connection succeeded, False otherwise.
        """
        # Don't connect twice
        if name in self._sessions:
            logger.info(f"MCP: '{name}' already connected, skipping")
            return True

        try:
            return self._run_async(
                self._async_add_server(name, url, api_key, transport, description),
                timeout=30.0,
            )
        except Exception as e:
            # Extract useful error message (ExceptionGroups nest errors)
            err_msg = str(e)
            if not err_msg or err_msg == "":
                err_msg = repr(e)
            # Dig into ExceptionGroups for the real error
            inner = e
            for _ in range(5):
                if hasattr(inner, 'exceptions') and inner.exceptions:
                    inner = inner.exceptions[0]
                elif inner.__cause__:
                    inner = inner.__cause__
                else:
                    break
            if inner is not e:
                err_msg = f"{type(inner).__name__}: {inner}"

            logger.error(f"MCP: Failed to connect to '{name}': {err_msg}")
            self._server_info[name] = {
                "url": url,
                "connected": False,
                "tool_count": 0,
                "transport": transport,
                "error": err_msg,
            }
            return False

    async def _async_add_server(self, name, url, api_key, transport, description=None):
        """Async implementation of server connection."""
        try:
            from mcp import ClientSession
        except ImportError:
            logger.error("MCP: 'mcp' package not installed. Run: pip install mcp")
            return False

        session = None
        contexts = []

        # Build headers for authentication
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if transport == "sse":
            # Try SSE first, fall back to streamable HTTP
            connected = False

            # Attempt SSE
            try:
                from mcp.client.sse import sse_client
                sse_cm = sse_client(url, headers=headers)
                streams = await sse_cm.__aenter__()
                contexts.append(sse_cm)
                # SSE returns (read, write)
                if isinstance(streams, tuple) and len(streams) == 2:
                    read, write = streams
                elif isinstance(streams, tuple) and len(streams) >= 3:
                    read, write = streams[0], streams[1]
                else:
                    read, write = streams
                connected = True
            except Exception as sse_err:
                logger.info(f"MCP: SSE failed for '{name}', trying streamable HTTP: {sse_err}")
                # Clean up failed SSE contexts
                for ctx in reversed(contexts):
                    try:
                        await ctx.__aexit__(None, None, None)
                    except Exception:
                        pass
                contexts = []

            # Fallback to streamable HTTP
            if not connected:
                try:
                    from mcp.client.streamable_http import streamablehttp_client
                    http_cm = streamablehttp_client(url, headers=headers)
                    streams = await http_cm.__aenter__()
                    contexts.append(http_cm)
                    # streamable HTTP returns (read, write, session_id)
                    if isinstance(streams, tuple) and len(streams) >= 3:
                        read, write = streams[0], streams[1]
                    elif isinstance(streams, tuple) and len(streams) == 2:
                        read, write = streams
                    else:
                        read, write = streams
                    connected = True
                except Exception as http_err:
                    logger.error(f"MCP: Both SSE and streamable HTTP failed for '{name}': {http_err}")
                    return False

            session_cm = ClientSession(read, write)
            session = await session_cm.__aenter__()
            contexts.append(session_cm)

        elif transport == "stdio":
            try:
                from mcp import StdioServerParameters
                from mcp.client.stdio import stdio_client
            except ImportError:
                logger.error("MCP: stdio client not available")
                return False

            # For stdio, url is the command and we might need args
            # Parse "command arg1 arg2" format
            parts = url.split()
            command = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            env_vars = dict(os.environ)
            if api_key:
                env_vars["API_KEY"] = api_key

            params = StdioServerParameters(
                command=command,
                args=args,
                env=env_vars,
            )

            stdio_cm = stdio_client(params)
            streams = await stdio_cm.__aenter__()
            contexts.append(stdio_cm)

            if isinstance(streams, tuple):
                read, write = streams[0], streams[1]
            else:
                read, write = streams

            session_cm = ClientSession(read, write)
            session = await session_cm.__aenter__()
            contexts.append(session_cm)

        elif transport == "rest":
            # REST API transport — for servers that expose tools via HTTP POST
            # (e.g., /mcp/tools/call) instead of standard MCP protocol
            import httpx

            base_url = url.rstrip("/")
            # Use the provided URL directly as the MCP JSON-RPC endpoint
            call_url = base_url

            req_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if api_key:
                req_headers["Authorization"] = f"Bearer {api_key}"

            # Probe the endpoint using JSON-RPC tools/list
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    probe = await client.post(
                        call_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/list",
                            "params": {},
                        },
                        headers=req_headers,
                    )
                    logger.info(f"MCP REST: Server '{name}' reachable (status {probe.status_code})")

                    # Try to extract tools from the response
                    discovered_tools = []
                    if probe.status_code == 200:
                        try:
                            probe_data = probe.json()
                            result = probe_data.get("result", {})
                            if isinstance(result, dict) and "tools" in result:
                                discovered_tools = result["tools"]
                                logger.info(f"MCP REST: Discovered {len(discovered_tools)} tools from JSON-RPC")
                        except Exception:
                            pass
            except Exception as probe_err:
                logger.error(f"MCP REST: Cannot reach '{name}' at {call_url}: {probe_err}")
                return False

            # Store REST server info (no MCP session needed)
            self._sessions[name] = "rest"  # Marker for REST transport
            self._contexts[name] = []
            self._server_info[name] = {
                "url": url,
                "call_url": call_url,
                "connected": True,
                "tool_count": 0,
                "transport": "rest",
                "error": None,
                "headers": req_headers,
            }

            # Register discovered tools from JSON-RPC tools/list
            if discovered_tools:
                for td in discovered_tools:
                    t_name = td.get("name", "")
                    if t_name:
                        t_desc = td.get("description", f"MCP tool from {name}")
                        self._tools[t_name] = (name, {
                            "name": t_name,
                            "original_name": t_name,
                            "description": f"[MCP] {t_desc}",
                            "input_schema": td.get("inputSchema", td.get("input_schema", {})),
                        })
                self._server_info[name]["tool_count"] = len(discovered_tools)

            # If no tools discovered, register a generic caller
            if not any(sn == name for _, (sn, _) in self._tools.items()):
                generic_name = f"{name.lower().replace(' ', '_')}_call"
                self._tools[generic_name] = (name, {
                    "name": generic_name,
                    "original_name": generic_name,
                    "description": f"[MCP] {description or f'Call tools on {name} server'}. Input: JSON with 'tool' (tool name) and 'arguments' (dict of args) keys.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string", "description": "Name of the tool to call"},
                            "arguments": {"type": "object", "description": "Tool arguments"},
                        },
                        "required": ["tool", "arguments"],
                    },
                })
                self._server_info[name]["tool_count"] = 1

            logger.info(f"MCP REST: Connected to '{name}' — {self._server_info[name]['tool_count']} tools")
            return True

        else:
            logger.error(f"MCP: Unknown transport '{transport}'")
            return False

        # Initialize session and discover tools (for SSE/stdio transports only)
        await session.initialize()
        tools_response = await session.list_tools()
        tools = tools_response.tools if hasattr(tools_response, 'tools') else []

        # Store connection state
        self._sessions[name] = session
        self._contexts[name] = contexts
        self._server_info[name] = {
            "url": url,
            "connected": True,
            "tool_count": len(tools),
            "transport": transport,
            "error": None,
        }

        # Register discovered tools
        for tool in tools:
            tool_name = tool.name
            # Avoid name collisions with other servers
            if tool_name in self._tools:
                tool_name = f"{name}_{tool_name}"

            self._tools[tool_name] = (name, {
                "name": tool_name,
                "original_name": tool.name,  # Original name for calling
                "description": tool.description or f"MCP tool from {name}",
                "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
            })

        logger.info(f"MCP: Connected to '{name}' — {len(tools)} tools discovered")
        return True

    def remove_server(self, name: str):
        """Disconnect from an MCP server and remove its tools."""
        if name not in self._server_info:
            return

        try:
            self._run_async(self._async_remove_server(name), timeout=10.0)
        except Exception as e:
            logger.warning(f"MCP: Error disconnecting '{name}': {e}")

        # Clean up state regardless of async result
        self._sessions.pop(name, None)
        self._contexts.pop(name, None)
        self._server_info.pop(name, None)

        # Remove tools belonging to this server
        to_remove = [tn for tn, (sn, _) in self._tools.items() if sn == name]
        for tn in to_remove:
            del self._tools[tn]

    async def _async_remove_server(self, name):
        """Async cleanup of server connection."""
        contexts = self._contexts.get(name, [])
        # Close in reverse order (session first, then transport)
        for ctx in reversed(contexts):
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                pass

    def disconnect_all(self):
        """Disconnect from all MCP servers."""
        for name in list(self._server_info.keys()):
            self.remove_server(name)

    # ========================================
    # Tool Calling
    # ========================================

    def call_tool_sync(self, tool_name: str, input_text: str) -> str:
        """
        Call an MCP tool synchronously (for the ReAct loop).

        Args:
            tool_name: Name of the MCP tool.
            input_text: Raw string input from the agent's Action Input.

        Returns:
            Tool output as a string.
        """
        if tool_name not in self._tools:
            return f"❌ Error: MCP tool '{tool_name}' not found"

        try:
            arguments = self._prepare_arguments(tool_name, input_text)
            return self._run_async(
                self._async_call_tool(tool_name, arguments),
                timeout=30.0,
            )
        except Exception as e:
            return f"❌ Error calling MCP tool '{tool_name}': {e}"

    def _prepare_arguments(self, tool_name: str, input_text: str) -> dict:
        """
        Convert the ReAct agent's string input into MCP tool arguments.

        Strategy:
        1. Try JSON parse (LLM might give structured input)
        2. If tool has one parameter, use input as its value
        3. Try common parameter names (query, input, text)
        4. Fall back to first parameter in schema
        """
        _, tool_info = self._tools[tool_name]
        schema = tool_info.get("input_schema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # 1. Try JSON parse
        try:
            parsed = json.loads(input_text.strip())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. Single parameter — use it directly
        if len(properties) == 1:
            param_name = list(properties.keys())[0]
            return {param_name: input_text.strip()}

        # 3. Common parameter names
        for common_name in ["query", "input", "text", "content", "url", "path"]:
            if common_name in properties:
                return {common_name: input_text.strip()}

        # 4. First required parameter
        if required:
            return {required[0]: input_text.strip()}

        # 5. First property
        if properties:
            return {list(properties.keys())[0]: input_text.strip()}

        # 6. Last resort
        return {"input": input_text.strip()}

    async def _async_call_tool(self, tool_name: str, arguments: dict) -> str:
        """Async implementation of tool calling."""
        server_name, tool_info = self._tools[tool_name]
        session = self._sessions.get(server_name)
        if not session:
            return f"❌ Server '{server_name}' is not connected"

        # Use original tool name for the MCP call
        original_name = tool_info.get("original_name", tool_name)

        # REST transport — use HTTP POST instead of MCP session
        if session == "rest":
            return await self._rest_call_tool(server_name, original_name, arguments)

        # Standard MCP protocol call
        result = await session.call_tool(original_name, arguments=arguments)

        # Extract text content from result
        texts = []
        if hasattr(result, 'content'):
            for content_item in result.content:
                if hasattr(content_item, 'text'):
                    texts.append(content_item.text)
                elif hasattr(content_item, 'data'):
                    texts.append(str(content_item.data))
                else:
                    texts.append(str(content_item))

        return "\n".join(texts) if texts else str(result)

    async def _rest_call_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Call a tool via REST/JSON-RPC (POST to the MCP endpoint)."""
        import httpx

        info = self._server_info.get(server_name, {})
        call_url = info.get("call_url", "")
        base_headers = info.get("headers", {})

        if not call_url:
            return f"❌ No call URL for server '{server_name}'"

        # If this is a generic caller, extract tool name from arguments
        if tool_name.endswith("_call") and "tool" in arguments:
            actual_tool = arguments.get("tool", tool_name)
            actual_args = arguments.get("arguments", {})
        else:
            actual_tool = tool_name
            actual_args = arguments

        # Use MCP JSON-RPC protocol format
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": actual_tool,
                "arguments": actual_args,
            },
        }

        headers = {
            **base_headers,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info(f"MCP REST: Calling {call_url} with tool='{actual_tool}', args={actual_args}")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(call_url, json=payload, headers=headers)

                logger.info(f"MCP REST: Response status={resp.status_code}, length={len(resp.text)}")

                if not resp.text or resp.text.strip() == "":
                    return f"❌ Server returned empty response (HTTP {resp.status_code})"

                try:
                    data = resp.json()
                except Exception:
                    logger.warning(f"MCP REST: Non-JSON response: {resp.text[:500]}")
                    return resp.text[:2000]

                # Handle JSON-RPC response format
                if isinstance(data, dict):
                    # JSON-RPC error
                    if "error" in data:
                        err = data["error"]
                        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                        return f"❌ Server error: {msg}"

                    # JSON-RPC success — result contains content array
                    if "result" in data:
                        result = data["result"]
                        if isinstance(result, dict) and "content" in result:
                            content = result["content"]
                            if isinstance(content, list):
                                texts = []
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        texts.append(item["text"])
                                    else:
                                        texts.append(str(item))
                                return "\n".join(texts)
                            return str(content)
                        return str(result) if not isinstance(result, dict) else json.dumps(result, indent=2)

                    # Non-JSON-RPC: direct content
                    if "content" in data:
                        content = data["content"]
                        if isinstance(content, list):
                            texts = []
                            for item in content:
                                if isinstance(item, dict) and "text" in item:
                                    texts.append(item["text"])
                                else:
                                    texts.append(str(item))
                            return "\n".join(texts)
                        return str(content)

                    if "message" in data:
                        return str(data["message"])

                return json.dumps(data, indent=2)
        except Exception as e:
            logger.error(f"MCP REST: Call failed: {e}")
            return f"❌ REST call failed: {e}"

    # ========================================
    # Tool Discovery
    # ========================================

    def get_all_tools(self) -> list[dict]:
        """Get all discovered MCP tools as a list of dicts."""
        return [info for _, info in self._tools.values()]

    def get_tools_by_server(self) -> dict:
        """Get tools grouped by server name. Returns {tool_name: (server_name, tool_info)}."""
        return dict(self._tools)

    def get_tool_names(self) -> list[str]:
        """Get names of all MCP tools."""
        return list(self._tools.keys())

    def get_status(self) -> dict:
        """Get connection status for all servers (for the UI panel)."""
        return dict(self._server_info)

    def is_connected(self, name: str) -> bool:
        """Check if a specific server is connected."""
        info = self._server_info.get(name, {})
        return info.get("connected", False)

    def __len__(self) -> int:
        """Number of MCP tools available."""
        return len(self._tools)

    def __repr__(self) -> str:
        servers = len(self._server_info)
        tools = len(self._tools)
        return f"MCPManager({servers} servers, {tools} tools)"
