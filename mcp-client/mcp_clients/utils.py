"""Shared helper utilities for MCP client transports."""

from __future__ import annotations

import json
from typing import Any, Dict
from urllib.parse import urlparse, urlunparse

def normalize_http_base(url: str, default_scheme: str = "http") -> str:
    """Convert ws://, wss://, or bare host strings into an HTTP(S) base URL."""
    parsed = urlparse(url)
    scheme = parsed.scheme
    netloc = parsed.netloc
    path = parsed.path

    if scheme in {"ws", "wss"}:
        scheme = "http" if scheme == "ws" else "https"
    elif scheme in {"http", "https"}:
        pass
    else:
        scheme = default_scheme

    if not netloc and path:
        netloc = path
        path = ""

    return urlunparse((scheme, netloc, "", "", "", "")).rstrip("/")


def normalize_tool_result(result: Any) -> Dict[str, Any]:
    """Convert an MCP `tools/call` response into a friendly structure."""
    if result is None:
        return {"content": "", "raw": result}

    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            fragments = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
            if fragments:
                joined = "\n".join(fragment.strip() for fragment in fragments if fragment)
                return {"content": joined, "raw": result}

        if isinstance(content, str):
            return {"content": content, "raw": result}

        if "message" in result:
            return {"content": str(result["message"]), "raw": result}

        return {"content": json.dumps(result, indent=2), "raw": result}

    if isinstance(result, list):
        try:
            return {"content": "\n".join(map(str, result)), "raw": result}
        except Exception:
            return {"content": str(result), "raw": result}

    return {"content": str(result), "raw": result}
