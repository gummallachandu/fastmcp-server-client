import json
from typing import Any, Dict, List, Optional
from datetime import datetime

import streamlit as st
from openai import OpenAI
from mcp_clients import MCPSSEClient

# Page configuration
st.set_page_config(page_title="Content Generator", page_icon="✨", layout="centered")

# Initialize session state
if 'generated_content' not in st.session_state:
    st.session_state.generated_content = ""
READ_TOOL_CANDIDATES = [
    "read_file_mcp",
    "read_file",
    "readfile",
    "read_from_file",
]
DEFAULT_FILE_PATH = "sample.txt"


if 'mcp_client' not in st.session_state:
    st.session_state.mcp_client = None
if 'mcp_client_key' not in st.session_state:
    st.session_state.mcp_client_key = None
if 'mcp_connected' not in st.session_state:
    st.session_state.mcp_connected = False
if 'mcp_server_url' not in st.session_state:
    st.session_state.mcp_server_url = ""
if 'available_tools' not in st.session_state:
    st.session_state.available_tools = []
if 'agent_history' not in st.session_state:
    st.session_state.agent_history = []

def get_mcp_client(endpoint: str) -> Optional[MCPSSEClient]:
    """Get or create MCP client for the selected transport."""
    if not endpoint:
        return None

    key = ("SSE", endpoint)
    current_key = st.session_state.get("mcp_client_key")
    current_client = st.session_state.get("mcp_client")

    if current_key != key and current_client:
        try:
            current_client.close()
        except Exception:
            pass
        st.session_state.mcp_client = None
        st.session_state.mcp_connected = False

    if st.session_state.mcp_client is None:
        try:
            client = MCPSSEClient(endpoint)
            client.connect()
            st.session_state.mcp_client = client
            st.session_state.mcp_client_key = key
            st.session_state.mcp_server_url = endpoint
        except Exception as error:
            st.error(f"Error creating MCP client: {error}")
            st.session_state.mcp_client = None
            st.session_state.mcp_client_key = None
            return None

    return st.session_state.mcp_client

def discover_tools(mcp_client) -> list:
    """Discover available tools from MCP server"""
    if not mcp_client:
        return []
    
    try:
        tools = mcp_client.discover_tools()
        if tools:
            st.session_state.available_tools = tools
            st.session_state.mcp_connected = True
            return tools
        else:
            # Show debug info
            st.warning("No tools discovered. Check the console output for details.")
            st.session_state.mcp_connected = True  # Still marked as connected
            return []
    except Exception as e:
        st.error(f"Error discovering tools: {str(e)}")
        st.session_state.mcp_connected = False
        return []

def call_mcp_tool(mcp_client, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> dict:
    """Call an MCP tool with given arguments"""
    if not mcp_client:
        return {"error": "MCP client not connected", "content": ""}
    
    try:
        result = mcp_client.call_tool(tool_name, arguments or {})
        return {
            "success": True,
            "content": result.get("content", ""),
            "raw": result.get("raw"),
            "tool": tool_name,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "content": "", "tool": tool_name}


def find_read_tool(tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Locate the file-reading tool from the discovered MCP tools."""
    for candidate in READ_TOOL_CANDIDATES:
        for tool in tools:
            if tool.get("name") == candidate:
                return tool

    for tool in tools:
        name = (tool.get("name") or "").lower()
        if "read" in name and "file" in name:
            return tool

    return tools[0] if tools else None


def prepare_tool_arguments(tool: Optional[Dict[str, Any]], planned_args: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure required arguments are populated for the selected tool."""
    args = dict(planned_args or {})
    if not tool:
        return args

    schema = tool.get("inputSchema") or {}
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = schema.get("required", []) if isinstance(schema, dict) else []

    path_prop = properties.get("path", {})
    if "path" in properties and "path" not in args:
        default_path = path_prop.get("default") or DEFAULT_FILE_PATH
        if default_path:
            args["path"] = default_path

    for param in required:
        if param not in args or args[param] in (None, ""):
            default_value = properties.get(param, {}).get("default")
            if default_value is not None:
                args[param] = default_value

    missing = [param for param in required if param not in args or args[param] in (None, "")]
    if missing:
        raise ValueError(f"Missing required arguments: {', '.join(missing)}")

    return args

def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from a block of text."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def plan_tool_with_llm(
    user_request: str,
    tools: List[Dict[str, Any]],
    api_key: str,
    required_tool_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Ask the LLM which tool to call and with which arguments."""
    client = OpenAI(api_key=api_key)

    tool_blocks = []
    for tool in tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")
        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        if properties:
            param_lines = []
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "string")
                param_desc = param_info.get("description", "")
                param_lines.append(f"      - {param_name} ({param_type}): {param_desc}")
            params_text = "\n".join(param_lines)
        else:
            params_text = "      - None"
        tool_blocks.append(f"- Name: {name}\n  Description: {desc}\n  Parameters:\n{params_text}")

    tool_catalog = "\n".join(tool_blocks) if tool_blocks else "No tools are currently available."

    instruction_line = (
        f"You must call the file-reading tool named '{required_tool_name}' and supply its required arguments. "
        f"If no path is provided by the user, default to '{DEFAULT_FILE_PATH}'."
        if required_tool_name
        else "Decide whether to call a tool to help the user."
    )

    prompt = f"""
You are an MCP agent. {instruction_line}

Available tools:
{tool_catalog}

User request: {user_request}

Respond with a single JSON object containing:
- "tool_name": string or null
- "arguments": object (use {{}} if no arguments or no tool)
- "reasoning": short explanation

Return JSON only, no additional commentary.
"""
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        raw_output = response.output_text.strip()
        plan_data = _extract_json_object(raw_output) or {}
    except Exception as error:
        plan_data = {"tool_name": None, "arguments": {}, "reasoning": f"Planning failed: {error}"}

    tool_name = plan_data.get("tool_name")
    if isinstance(tool_name, str):
        tool_name = tool_name.strip() or None
    else:
        tool_name = None

    available_names = {tool.get("name") for tool in tools if tool.get("name")}
    if tool_name and tool_name not in available_names:
        plan_data.setdefault("reasoning", "")
        plan_data["reasoning"] += f" (tool '{tool_name}' not available)"
        tool_name = None

    if required_tool_name:
        if required_tool_name not in available_names:
            plan_data.setdefault("reasoning", "")
            plan_data["reasoning"] += f" (required tool '{required_tool_name}' not available)"
            tool_name = None
        else:
            if tool_name != required_tool_name:
                plan_data.setdefault("reasoning", "")
                if tool_name:
                    plan_data["reasoning"] += f" (overriding '{tool_name}' with required '{required_tool_name}')"
                else:
                    plan_data["reasoning"] += f" (using required tool '{required_tool_name}')"
                tool_name = required_tool_name

    arguments = plan_data.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}

    reasoning = plan_data.get("reasoning", "")

    plan_data["tool_name"] = tool_name
    plan_data["arguments"] = arguments
    plan_data["reasoning"] = reasoning
    return plan_data


def compose_final_response(
    user_request: str,
    tool_name: Optional[str],
    tool_output: str,
    reasoning: str,
    api_key: str,
) -> str:
    """Compose the final answer for the user, using tool output if available."""
    client = OpenAI(api_key=api_key)

    context_parts = [f"User request: {user_request}"]
    if tool_name and tool_output:
        context_parts.append(f"Tool '{tool_name}' output:\n{tool_output}")
    elif tool_name:
        context_parts.append(f"Tool '{tool_name}' returned no content.")
    if reasoning:
        context_parts.append(f"Tool selection reasoning: {reasoning}")

    context = "\n\n".join(context_parts)
    prompt = (
        "Compose a helpful response for the user based on the context below. "
        "Write exactly 50 words (no more, no less) summarising the topic, and highlight key details from the tool output when available.\n\n"
        f"{context}\n\n"
        "Respond with plain text only."
    )

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        summary_text = response.output_text.strip()
    except Exception as error:
        fallback = user_request
        if tool_output:
            fallback += f"\n\nTool '{tool_name}' output:\n{tool_output}"
        fallback += f"\n\n(Note: failed to contact language model: {error})"
        return fallback

    if tool_output:
        summary_text = (
            f"{summary_text}\n\n"
            f"--- File Content ({tool_name or 'tool'}) ---\n"
            f"{tool_output}"
        )

    return summary_text

# Main UI
st.title("✨ MCP Agent Playground")
st.markdown(
    "Describe your goal and let the agent decide which MCP tool to invoke over the SSE transport. "
    "It will then compose a concise answer that incorporates any data returned by the tool."
)

# Sidebar configuration
with st.sidebar:
    st.header("Configuration")

    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        help="Enter an OpenAI API key with access to the Responses API.",
    )

    st.divider()
    st.header("MCP Server")

    default_value = st.session_state.get("mcp_server_url") or "http://localhost:8766/sse"
    mcp_server_url = st.text_input(
        "MCP SSE URL",
        value=default_value,
        help="SSE endpoint exposed by FastMCP, e.g. http://localhost:8766/sse",
    )

    if st.button("🔌 Connect to MCP Server"):
        with st.spinner("Connecting to MCP server..."):
            client = get_mcp_client(mcp_server_url)
            if client:
                tools = discover_tools(client)
                if tools:
                    st.success(f"Connected! Found {len(tools)} tools.")
                else:
                    st.warning("Connected but no tools found.")
            else:
                st.error("Failed to connect to MCP server.")

    if st.session_state.mcp_connected and st.session_state.available_tools:
        st.caption("Discovered tools:")
        for tool in st.session_state.available_tools:
            st.write(f"- {tool.get('name', 'Unknown')}")

# Agent request
user_request = st.text_area(
    "What should the agent do?",
    placeholder="Summarize the content of sample.txt and relate it to AI ethics.",
    help="The agent will decide which MCP tool to call over the SSE transport.",
)

run_agent_clicked = st.button(
    "🤖 Run Agent",
    type="primary",
    disabled=not api_key or not st.session_state.mcp_connected,
)

if run_agent_clicked:
    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar first.")
    elif not st.session_state.mcp_connected:
        st.error("Connect to the MCP server before running the agent.")
    elif not user_request.strip():
        st.error("Please enter a request for the agent.")
    else:
        client = get_mcp_client(mcp_server_url)
        if not client:
            st.error("Failed to connect to the MCP server. Try connecting again.")
        else:
            with st.spinner("Running agent..."):
                tools = st.session_state.available_tools or discover_tools(client)
                read_tool = find_read_tool(tools)
                required_tool_name = read_tool.get("name") if read_tool else None
                plan = plan_tool_with_llm(
                    user_request,
                    tools,
                    api_key,
                    required_tool_name=required_tool_name,
                )

                tool_result = None
                tool_error = None
                tool_output_text = ""
                arguments_used: Dict[str, Any] = {}

                tool_name = plan.get("tool_name")
                if tool_name:
                    available_names = {tool.get("name") for tool in tools if tool.get("name")}
                    if tool_name not in available_names:
                        tool_error = f"Tool '{tool_name}' is not available."
                        plan["tool_name"] = None
                    else:
                        target_tool = next((tool for tool in tools if tool.get("name") == tool_name), None)
                        try:
                            arguments_used = prepare_tool_arguments(target_tool, plan.get("arguments", {}))
                        except ValueError as error:
                            tool_error = str(error)
                            plan["tool_name"] = None
                        else:
                            call_result = call_mcp_tool(client, tool_name, arguments_used)
                            if call_result.get("success"):
                                tool_result = call_result
                                tool_output_text = call_result.get("content", "")
                            else:
                                tool_error = call_result.get("error") or "Unknown error while invoking the tool."

                final_response = compose_final_response(
                    user_request=user_request,
                    tool_name=plan.get("tool_name"),
                    tool_output=tool_output_text,
                    reasoning=plan.get("reasoning", ""),
                    api_key=api_key,
                )

                st.session_state.generated_content = final_response
                entry = {
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "request": user_request,
                    "plan": plan,
                    "arguments_used": arguments_used,
                    "tool_result": tool_result,
                    "tool_error": tool_error,
                    "final_response": final_response,
                }
                st.session_state.agent_history.insert(0, entry)
                st.session_state.agent_history = st.session_state.agent_history[:10]
                st.success("Agent run completed!")

if st.session_state.generated_content:
    st.divider()
    st.subheader("📝 Latest Agent Response")
    st.write(st.session_state.generated_content)
    st.download_button(
        label="📥 Download Latest Response",
        data=st.session_state.generated_content,
        file_name="agent_response.txt",
        mime="text/plain",
        key="download_latest_response",
    )

if st.session_state.mcp_connected and st.session_state.available_tools:
    st.divider()
    st.subheader("🛠️ Available MCP Tools")
    st.markdown(f"**Total Tools Available:** {len(st.session_state.available_tools)}")

    for idx, tool in enumerate(st.session_state.available_tools):
        tool_name = tool.get("name", f"Tool {idx + 1}")
        tool_desc = tool.get("description", "No description provided.")
        schema = tool.get("inputSchema") or {}
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required_params = schema.get("required", []) if isinstance(schema, dict) else []

        with st.expander(f"📋 {tool_name}", expanded=False):
            st.write("**Description:**")
            st.info(tool_desc)

            if properties:
                st.write("**Parameters:**")
                lines = []
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    required_flag = " (required)" if param_name in required_params else ""
                    lines.append(f"- `{param_name}` ({param_type}){required_flag}: {param_desc}")
                st.markdown("\n".join(lines))
            else:
                st.write("**Parameters:** None")

            if st.checkbox(f"Show raw schema for {tool_name}", key=f"schema_{idx}"):
                st.json(tool)

if st.session_state.agent_history:
    st.divider()
    st.subheader("🧠 Agent Run History")
    for idx, run in enumerate(st.session_state.agent_history):
        title = f"Run {idx + 1}: {run['request']}"
        if run.get("timestamp"):
            title += f" ({run['timestamp']})"
        with st.expander(title, expanded=(idx == 0)):
            st.markdown("**Agent Response**")
            st.write(run["final_response"])

            if run.get("tool_error"):
                st.error(run["tool_error"])

            tool_result = run.get("tool_result")
            if tool_result:
                st.markdown("**Tool Output**")
                st.text_area(
                    "Output content",
                    value=tool_result.get("content", ""),
                    height=180,
                    key=f"history_output_{idx}",
                    disabled=True,
                )
                raw_payload = tool_result.get("raw")
                if raw_payload is not None:
                    st.markdown("**Raw Result**")
                    payload_content = getattr(raw_payload, "data", raw_payload)
                    try:
                        st.json(payload_content)
                    except Exception:
                        st.write(str(payload_content))

            if run.get("arguments_used"):
                st.markdown("**Tool Arguments Used**")
                st.json(run["arguments_used"])

            st.markdown("**Tool Plan**")
            st.json(run["plan"])

            st.download_button(
                "Download response",
                data=run["final_response"],
                file_name=f"agent_response_{idx + 1}.txt",
                mime="text/plain",
                key=f"download_history_{idx}",
            )

