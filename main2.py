from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastmcp import FastMCP
import fastmcp


app = FastAPI(title="MCP Server API")
mcp = FastMCP("mcp-server")

# Allow Streamable HTTP transport to work without session negotiation
fastmcp.settings.stateless_http = True


# Shared payload for every surface (REST + MCP tool)
STATIC_TEXT = "This is a static response from /read-file."


def _get_static_text() -> str:
    """Small helper so both REST and MCP paths stay in sync."""
    return STATIC_TEXT


@app.get("/read-file", response_class=PlainTextResponse, summary="Return static text")
async def read_file() -> str:
    """Legacy REST endpoint backed by the shared helper."""
    return _get_static_text()


def read_file_mcp() -> str:
    """MCP tool; reachable over Streamable HTTP transport."""
    return _get_static_text()


# Register the function as an MCP tool
# Agents will discover and call this via MCP protocol (tools/list and tools/call)
mcp.tool()(read_file_mcp)


if __name__ == "__main__":
    import uvicorn
    import asyncio
    import sys

    # Check if we should run Streamable HTTP server or FastAPI app
    if "--streamable-http" in sys.argv or "--http" in sys.argv:
        # Run Streamable HTTP server
        async def run_server():
            mcp.settings.host = "0.0.0.0"
            mcp.settings.port = 8766
            await mcp.run_streamable_http_async()
        
        asyncio.run(run_server())
    else:
        # Run FastAPI app
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)




