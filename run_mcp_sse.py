import asyncio

from main import mcp


async def main() -> None:
    """
    Launch the MCP server over SSE (Server-Sent Events) transport.

    Exposes the tools at `http://<host>:8766/sse` following the MCP stream spec.
    
    NOTE: This is optional if you're running the FastAPI app (main.py) which mounts
    the MCP server at /mcp. In that case, use http://localhost:8000/mcp/sse instead.
    """
    # Configure host/port specifically for the SSE transport to avoid clashes
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = 8766

    await mcp.run_sse_async()


if __name__ == "__main__":
    asyncio.run(main())

