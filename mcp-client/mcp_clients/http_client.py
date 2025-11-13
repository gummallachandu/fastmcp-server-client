"""HTTP transport helper for FastMCP's REST shim."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .utils import normalize_http_base, normalize_tool_result

import requests


class MCPHttpClient:
    """Operate through FastMCP's HTTP shim endpoints (non-spec transport)."""

    def __init__(self, base_url: str) -> None:
        http_base = normalize_http_base(base_url)
        if not http_base:
            raise ValueError("Base URL must be provided")

        self.base_url = http_base
        self.session = requests.Session()
        self.tools_cache: Dict[str, Any] = {}
        self.connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.session.close()
        self.connected = False

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    def discover_tools(self) -> List[Dict[str, Any]]:
        self.connect()

        tools_map: Dict[str, Dict[str, Any]] = {}
        try:
            tools_via_rpc = self._discover_from_mcp_endpoint()
            for tool in tools_via_rpc:
                name = tool.get("name")
                if not name:
                    continue
                merged = dict(tool)
                merged.setdefault("inputSchema", {"type": "object", "properties": {}, "required": []})
                tools_map[name] = merged
        except Exception as error:
            print(f"⚠️  MCP tools/list via HTTP failed: {error}")

        tools = list(tools_map.values())
        self.tools_cache = {tool["name"]: tool for tool in tools if tool.get("name")}
        return tools

    def _discover_from_mcp_endpoint(self) -> List[Dict[str, Any]]:
        endpoints_to_try = [
            ("POST", "mcp/tools/list", {}),
            ("POST", "tools/list", {"method": "tools/list"}),
            ("GET", "mcp/tools/list", None),
            ("GET", "tools/list", None),
        ]

        for method, endpoint, payload in endpoints_to_try:
            try:
                result = self._send_http_request(endpoint, payload, method)
                tools: List[Any] = []
                if isinstance(result, dict):
                    tools = (
                        result.get("tools")
                        or result.get("result", {}).get("tools")
                        or result.get("data")
                        or result.get("items")
                        or []
                    )
                elif isinstance(result, list):
                    tools = result

                cleaned: List[Dict[str, Any]] = [
                    dict(tool)
                    for tool in tools
                    if isinstance(tool, dict) and tool.get("name")
                ]
                if cleaned:
                    for entry in cleaned:
                        entry.setdefault("inputSchema", {"type": "object", "properties": {}, "required": []})
                    return cleaned
            except Exception:
                continue

        return []

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------
    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.connect()
        arguments = arguments or {}

        endpoints: List[Tuple[str, Dict[str, Any], str]] = []
        endpoints.extend(
            [
                ("call_tool", {"tool_name": tool_name, "arguments": arguments}, "POST"),
                ("tools/call", {"name": tool_name, "arguments": arguments}, "POST"),
                ("mcp/tools/call", {"name": tool_name, "arguments": arguments}, "POST"),
                (f"tools/{tool_name}", arguments, "POST"),
                (f"invoke/{tool_name}", arguments, "POST"),
                (f"mcp/{tool_name}", arguments, "POST"),
            ]
        )

        last_error: Optional[str] = None
        for endpoint, payload, method in endpoints:
            try:
                result = self._send_http_request(endpoint, payload, method)
                return normalize_tool_result(result)
            except Exception as error:
                last_error = str(error)
                continue

        raise Exception(f"Could not call tool '{tool_name}' via HTTP. Last error: {last_error}")

    def read_file(self, file_path: str) -> str:
        for candidate in ("read_file", "readfile", "read_file_mcp"):
            if candidate in self.tools_cache:
                result = self.call_tool(candidate, {"path": file_path})
                return result.get("content", "")
        return f"No read_file tool available on {self.base_url}"

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------
    def _send_http_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        method: str = "POST",
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        method_upper = method.upper()
        if method_upper == "GET":
            response = self.session.get(url, params=payload, timeout=10)
        else:
            response = self.session.post(url, json=payload, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            return response.json()
        return {"content": response.text}
