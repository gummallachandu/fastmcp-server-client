"""MCP SSE client built on top of fastmcp.Client."""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Awaitable, Dict, List, Optional

from fastmcp import Client as FastMCPClient
from mcp.types import Implementation

from .utils import normalize_tool_result


class MCPSSEClient:
    """
    Thin synchronous wrapper around fastmcp.Client using the SSE transport.

    The underlying fastmcp client speaks MCP JSON-RPC 2.0 and handles
    connection management. We run it on a background asyncio loop so the rest of
    the application can remain synchronous.
    """

    def __init__(
        self,
        server_url: str,
        client_name: str = "Streamlit MCP Client",
        client_version: str = "0.1.0",
    ) -> None:
        if not server_url:
            raise ValueError("Server URL must be provided")

        self.server_url = server_url
        self.client_name = client_name
        self.client_version = client_version

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()

        self._client_ctx: Optional[FastMCPClient] = None
        self._client: Optional[FastMCPClient] = None

        self.tools_cache: Dict[str, Any] = {}
        self.connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> None:
        if self.connected:
            return
        self._run(self._async_connect())
        self.connected = True

    def close(self) -> None:
        if not self.connected:
            return
        self._run(self._async_close())
        self.connected = False
        self.tools_cache.clear()

    async def _async_connect(self) -> None:
        client_info = Implementation(name=self.client_name, version=self.client_version)
        self._client_ctx = FastMCPClient(self.server_url, client_info=client_info)
        self._client = await self._client_ctx.__aenter__()

    async def _async_close(self) -> None:
        if self._client_ctx is not None:
            await self._client_ctx.__aexit__(None, None, None)
        self._client_ctx = None
        self._client = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    def discover_tools(self) -> List[Dict[str, Any]]:
        self.connect()
        assert self._client is not None

        tools = self._run(self._client.list_tools())
        serialized: List[Dict[str, Any]] = []
        for tool in tools:
            tool_dict = tool.model_dump()
            if tool_dict.get("name"):
                tool_dict.setdefault("inputSchema", {"type": "object", "properties": {}, "required": []})
                serialized.append(tool_dict)

        self.tools_cache = {tool["name"]: tool for tool in serialized if tool.get("name")}
        return serialized

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------
    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.connect()
        assert self._client is not None

        result = self._run(self._client.call_tool(tool_name, arguments or {}))
        normalized = normalize_tool_result(result.data)
        normalized["raw"] = result
        normalized["tool"] = tool_name
        return normalized

    def read_file(self, file_path: str) -> str:
        for candidate in ("read_file", "readfile", "read_file_mcp"):
            if candidate in self.tools_cache:
                response = self.call_tool(candidate, {"path": file_path})
                return response.get("content", "")
        return f"Error: no read_file tool registered on {self.server_url}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _run(self, coro: "Awaitable[Any] | asyncio.Future[Any]") -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
        finally:
            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread.is_alive():
                self._loop_thread.join(timeout=1)
