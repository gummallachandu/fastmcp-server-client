"""Specification-aligned MCP client that speaks JSON-RPC over WebSocket."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from .utils import normalize_tool_result


class MCPWebSocketClient:
    """MCP client that communicates over WebSocket using JSON-RPC 2.0."""

    def __init__(
        self,
        server_url: str,
        client_name: str = "Streamlit MCP Client",
        client_version: str = "0.1.0",
    ) -> None:
        if not server_url:
            raise ValueError("Server URL must be provided")
        if not (server_url.startswith("ws://") or server_url.startswith("wss://")):
            raise ValueError("Server URL must start with ws:// or wss://")

        self.server_url = server_url
        self.client_name = client_name
        self.client_version = client_version

        self._ws = None  # type: ignore[var-annotated]
        self._request_id = 0
        self.connected = False
        self.server_info: Dict[str, Any] = {}
        self.capabilities: Dict[str, Any] = {}
        self.tools_cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> None:
        if self.connected:
            return

        self._ws = connect(
            self.server_url,
            open_timeout=10,
            close_timeout=10,
            ping_interval=None,
        )  # type: ignore[call-arg]

        init_params = {
            "protocolVersion": "1.0",
            "capabilities": {},
            "clientInfo": {"name": self.client_name, "version": self.client_version},
        }
        result = self._send_rpc_request("initialize", init_params)
        self.server_info = result.get("serverInfo", {})
        self.capabilities = result.get("capabilities", {})
        self.connected = True

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except (ConnectionClosed, ConnectionClosedOK, ConnectionClosedError):
                pass
            finally:
                self._ws = None
        self.connected = False

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    def discover_tools(self) -> List[Dict[str, Any]]:
        self.connect()

        tools_map: Dict[str, Dict[str, Any]] = {}
        tools_via_rpc = self._discover_via_rpc()
        for tool in tools_via_rpc:
            name = tool.get("name")
            if not name:
                continue
            merged = dict(tool)
            merged.setdefault("inputSchema", {"type": "object", "properties": {}, "required": []})
            tools_map[name] = merged

        self.tools_cache = tools_map
        return list(tools_map.values())

    def _discover_via_rpc(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            params: Dict[str, Any] = {}
            if cursor:
                params["cursor"] = cursor

            result = self._send_rpc_request("tools/list", params)
            tools.extend(result.get("tools", []))
            cursor = result.get("nextCursor")

            if not cursor:
                break

        return tools

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------
    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.connect()
        payload = {"name": tool_name, "arguments": arguments or {}}
        result = self._send_rpc_request("tools/call", payload)
        return normalize_tool_result(result)

    def read_file(self, file_path: str) -> str:
        for candidate in ("read_file", "readfile", "read_file_mcp"):
            if candidate in self.tools_cache:
                response = self.call_tool(candidate, {"path": file_path})
                return response.get("content", "")
        return f"Error: no read_file tool registered on {self.server_url}"

    # ------------------------------------------------------------------
    # JSON-RPC helpers
    # ------------------------------------------------------------------
    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_rpc_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.connected or self._ws is None:
            raise RuntimeError("MCP WebSocket client is not connected")

        request_id = self._next_request_id()
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        self._ws.send(json.dumps(message))

        while True:
            raw = self._ws.recv()
            data = json.loads(raw)

            if "id" not in data:
                self._handle_notification(data)
                continue

            if data["id"] != request_id:
                self._handle_out_of_order_message(data)
                continue

            if "error" in data:
                raise Exception(data["error"])

            return data.get("result", {})

    def _handle_notification(self, message: Dict[str, Any]) -> None:
        print(f"🔔 MCP notification: {json.dumps(message, indent=2)}")

    def _handle_out_of_order_message(self, message: Dict[str, Any]) -> None:
        print(f"⚠️  Out-of-order MCP message: {json.dumps(message, indent=2)}")

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
