from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from mcp.server.fastmcp import FastMCP


app = FastAPI(title="MCP Server API")
mcp = FastMCP("mcp-server")

# Allow HTTP/SSE transports to work without session negotiation
mcp.settings.stateless_http = True


# Shared payload for every surface (REST + MCP tool)
STATIC_TEXT = "This is a static response from /read-file."


def _get_static_text() -> str:
    """Small helper so both REST and MCP paths stay in sync."""
    return STATIC_TEXT


@app.get("/read-file", response_class=PlainTextResponse, summary="Return static text")
async def read_file() -> str:
    """Legacy REST endpoint backed by the shared helper."""
    return _get_static_text()


@mcp.tool()
def read_file_mcp() -> str:
    """MCP tool; reachable over stdio/WebSocket transports."""
    return _get_static_text()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)




