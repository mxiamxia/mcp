#!/usr/bin/env python3
"""Quick test script for the streamable HTTP server."""

import asyncio
import httpx
import json


async def test_server():
    """Test the streamable HTTP server endpoints."""
    base_url = 'http://localhost:8080'

    async with httpx.AsyncClient() as client:
        # Test health endpoint
        print('Testing /health endpoint...')
        response = await client.get(f'{base_url}/health')
        print(f'Status: {response.status_code}')
        print(f'Response: {response.json()}\n')

        # Test info endpoint
        print('Testing /info endpoint...')
        response = await client.get(f'{base_url}/info')
        print(f'Status: {response.status_code}')
        print(f'Response: {response.json()}\n')

        # Test MCP initialize
        print('Testing /mcp initialize...')
        init_request = {
            'jsonrpc': '2.0',
            'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {'roots': {'listChanged': True}},
                'clientInfo': {'name': 'test-client', 'version': '1.0.0'},
            },
            'id': 1,
        }

        response = await client.post(
            f'{base_url}/mcp',
            json=init_request,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2024-11-05',
            },
        )

        print(f'Status: {response.status_code}')
        print(f'Headers: {dict(response.headers)}')
        print(f'Response: {json.dumps(response.json(), indent=2)}\n')

        # Get session ID from response
        session_id = response.headers.get('Mcp-Session-Id')
        print(f'Session ID: {session_id}\n')

        # Test tools/list
        print('Testing /mcp tools/list...')
        tools_request = {'jsonrpc': '2.0', 'method': 'tools/list', 'params': {}, 'id': 2}

        response = await client.post(
            f'{base_url}/mcp',
            json=tools_request,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2024-11-05',
                'Mcp-Session-Id': session_id,
            },
        )

        print(f'Status: {response.status_code}')
        result = response.json()
        tools_count = len(result.get('result', {}).get('tools', []))
        print(f'Found {tools_count} tools')
        if tools_count > 0:
            print(f'First tool: {result["result"]["tools"][0]["name"]}\n')


if __name__ == '__main__':
    print('Starting streamable HTTP server test...\n')
    print('Make sure the server is running with:')
    print(
        '  python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable\n'
    )
    print('=' * 60)
    print()

    try:
        asyncio.run(test_server())
        print('\n' + '=' * 60)
        print('All tests passed!')
    except Exception as e:
        print(f'\nError: {e}')
        import traceback

        traceback.print_exc()
