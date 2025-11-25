from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastmcp import FastMCP
import fastmcp


app = FastAPI(title="MCP Server API")
mcp = FastMCP("mcp-server")

# Allow HTTP/SSE transports to work without session negotiation
fastmcp.settings.stateless_http = True

# Mount MCP server on the FastAPI app to share the same port
app.mount("/mcp", mcp.http_app())


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
    """MCP tool; reachable over SSE transport."""
    return _get_static_text()


# Register the function as an MCP tool
# Agents will discover and call this via MCP protocol (tools/list and tools/call)
mcp.tool()(read_file_mcp)


if __name__ == "__main__":
    import uvicorn

    # Use 0.0.0.0 to allow remote connections via SSE
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)




