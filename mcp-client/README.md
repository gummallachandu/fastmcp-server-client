# MCP SSE Agent Playground

A Streamlit application that lets an LLM agent decide which MCP tool to call (over FastMCP's SSE transport) and then compose a concise response that blends the tool output with its own reasoning.

## Features

- **Natural-language Agent**: Provide a free-form instruction; the agent picks the MCP tool (via SSE) and executes it.
- **FastMCP Client**: Uses `fastmcp.Client` under the hood for a spec-compliant SSE transport.
- **Tool Discovery**: Lists MCP tools and their schemas automatically.
- **Concise Responses**: Generates ~50 word summaries that incorporate tool results.
- **Run History**: Keeps recent agent runs with tool plans, outputs, and download links.

## Architecture

The app includes:
- **`mcp_clients/sse_client.py`**: Thin wrapper around `fastmcp.Client` that runs in a background event loop.
- **`mcp_clients/websocket_client.py`** *(optional)*: JSON-RPC 2.0 over WebSocket.
- **`mcp_clients/http_client.py`** *(optional legacy shim)*: HTTP endpoints exposed by FastMCP.
- **`mcp_clients/utils.py`**: Helper utilities shared by the client implementations.
- **`app.py`**: Streamlit interface, LLM agent orchestration, and response rendering.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure your MCP server (FastMCP) is running. To expose the SSE transport used by the agent:
   ```bash
   python run_mcp_sse.py
   ```
   This starts the MCP SSE endpoint at `http://0.0.0.0:8766/sse`.

3. Run the app:
```bash
streamlit run app.py
```

## Usage

1. **Configure MCP Server Connection** (sidebar):
   - Enter the SSE URL (default: `http://localhost:8766/sse`)
   - Click **“Connect to MCP Server”** to list the available tools

2. **Enter OpenAI API Key** (in sidebar)

3. **Main Interface**:
   - Enter a natural-language request (e.g. “Summarise sample.txt and relate it to AI ethics.”)
   - Click **“Run Agent”** – the agent decides which tool to call and composes a reply.

4. **View Results**:
   - Latest agent response (downloadable)
   - Discovered tool catalog
   - Run history with plans, tool output, and raw MCP responses

## MCP Client Usage

### FastMCP SSE Client (used by the app)

```python
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8766/sse") as client:
        tools = await client.list_tools()
        print([tool.name for tool in tools])

        result = await client.call_tool("read_file_mcp", {"path": "sample.txt"})
        print(result.data)

asyncio.run(main())
```

### Optional transports

The repository still includes helper clients for other surfaces exposed by FastMCP:

- `mcp_clients/websocket_client.py` – JSON-RPC 2.0 over WebSocket.
- `mcp_clients/http_client.py` – HTTP shim endpoints.

These aren’t used in the Streamlit app but can help when testing other transports.

## Requirements

- Python 3.9+
- OpenAI API key
- FastMCP server exposing an SSE MCP endpoint (e.g. `python run_mcp_sse.py`)
- Streamlit
- `fastmcp`, `openai`, `requests` (installed via `requirements.txt`)

## File Structure

```
mcp-client/
├── app.py              # Streamlit application
├── mcp_clients/        # MCP client implementations (websocket/http/sse/utils)
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

