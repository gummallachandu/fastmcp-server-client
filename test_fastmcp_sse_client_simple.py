#!/usr/bin/env python3
"""
Simple FastMCP Client SSE Test

This is a clean, simple test of FastMCP client using SSE transport only.
"""

import asyncio
import sys


async def main():
    """Test FastMCP client with SSE transport."""
    
    # Get server URL
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    else:
        # Default: FastAPI app with MCP mounted at /mcp
        server_url = "http://localhost:8000/mcp/sse"
    
    print("=" * 70)
    print("FastMCP Client - SSE Transport Test")
    print("=" * 70)
    print()
    print(f"Connecting to: {server_url}")
    print()
    
    try:
        from fastmcp import Client
        from fastmcp.client.transports import SSETransport
        
        # Create SSE transport
        transport = SSETransport(url=server_url)
        
        # Create client
        client = Client(transport)
        
        print("Step 1: Connecting...")
        print("-" * 70)
        
        # Connect and use client
        async with client:
            print("✅ Connected!")
            print()
            
            print("Step 2: Discovering tools...")
            print("-" * 70)
            
            tools = await client.list_tools()
            
            print(f"✅ Found {len(tools)} tool(s):\n")
            for tool in tools:
                print(f"  • {tool.name}")
                print(f"    {tool.description}")
                print()
            
            if tools:
                print("Step 3: Calling tool...")
                print("-" * 70)
                
                tool_name = tools[0].name
                result = await client.call_tool(tool_name, {})
                
                print(f"✅ Called '{tool_name}'")
                print()
                print("Result:")
                if hasattr(result, 'data'):
                    print(f"  {result.data}")
                elif hasattr(result, 'content'):
                    for content in result.content:
                        if hasattr(content, 'text'):
                            print(f"  {content.text}")
                        else:
                            print(f"  {content}")
                else:
                    print(f"  {result}")
                print()
        
        print("=" * 70)
        print("✅ Test successful!")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Make sure:")
        print("  1. FastAPI app is running: python3 main.py")
        print("  2. Server URL is correct (default: http://localhost:8000/mcp/sse)")
        print("  3. Server is accessible from this machine")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

test_fastmcp_sse_client_simple
