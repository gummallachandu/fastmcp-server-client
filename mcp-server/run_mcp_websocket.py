import asyncio

from main import mcp


async def main() -> None:
    """
    Launch the MCP server over WebSocket transport.

    Exposes the same tools defined in `main.py` at `ws://<host>:8765/mcp`.
    """
    await mcp.run_websocket(host="0.0.0.0", port=8765)


if __name__ == "__main__":
    asyncio.run(main())

