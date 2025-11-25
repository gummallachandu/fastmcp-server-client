#!/usr/bin/env python3
"""
Simple FastMCP Client SSE Test with SSL verification support.
"""

import asyncio
import sys
import os
import httpx


async def main():
    """Test FastMCP client with SSE transport."""
    
    # Check SSL verification first (before parsing URL)
    verify_ssl = os.getenv("SSL_VERIFY", "true").lower() != "false"
    if "--no-ssl-verify" in sys.argv:
        verify_ssl = False
        sys.argv.remove("--no-ssl-verify")
    
    # Get server URL (after removing flags)
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8766/sse"
    
    print(f"Connecting to: {server_url}")
    print(f"SSL Verification: {'Enabled' if verify_ssl else 'Disabled'}\n")
    
    try:
        from fastmcp import Client
        from fastmcp.client.transports import SSETransport
        
        # Create transport with SSL configuration
        if not verify_ssl:
            # Factory function that accepts arguments and returns client with SSL disabled
            def create_client(**kwargs):
                kwargs['verify'] = False
                return httpx.AsyncClient(**kwargs)
            
            transport = SSETransport(
                url=server_url,
                httpx_client_factory=create_client
            )
        else:
            transport = SSETransport(url=server_url)
        
        # Connect and test
        client = Client(transport)
        async with client:
            # Discover tools
            tools = await client.list_tools()
            print(f"Found {len(tools)} tool(s):")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            
            if tools:
                # Call first tool
                result = await client.call_tool(tools[0].name, {})
                print(f"\nTool result: {result.data if hasattr(result, 'data') else result}")
        
        print("\n✅ Test successful!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
