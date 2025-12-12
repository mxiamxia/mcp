# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CloudWatch Application Signals MCP Server - Remote Streamable HTTP Server."""

import asyncio
import json
import os
import sys
import uvicorn

# Import the FastMCP instance from the existing server
from .server import AWS_REGION, mcp
from .streamable_http_transport import StreamableHTTPTransport
from loguru import logger
from mcp.types import JSONRPCMessage
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


# Get configuration from environment variables
PORT = int(os.environ.get('MCP_PORT', 8080))  # Default to 8080 for HTTP mode
HOST = os.environ.get('MCP_HOST', '0.0.0.0')
MCP_API_KEY = os.environ.get('MCP_API_KEY', 'your-test-key')  # Optional API key for simple auth

# SSL/TLS configuration
# Default to HTTP mode (suitable for running behind ALB/CloudFront)
# Set DISABLE_SSL=false to enable direct HTTPS
DISABLE_SSL = os.environ.get('DISABLE_SSL', 'true').lower() == 'true'  # Default to disabled
SSL_KEYFILE = os.environ.get('SSL_KEYFILE', '/home/ec2-user/ssl/server.key')
SSL_CERTFILE = os.environ.get('SSL_CERTFILE', '/home/ec2-user/ssl/server.crt')

# Configure logging
log_level = os.environ.get('MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL', 'INFO').upper()

# Create Streamable HTTP transport
streamable_transport = StreamableHTTPTransport(endpoint='/mcp')


# Message handler that integrates with FastMCP
async def handle_mcp_message(message: JSONRPCMessage) -> dict:
    """Handle JSON-RPC messages from MCP clients.

    Args:
        message: The JSON-RPC message

    Returns:
        The response message
    """
    try:
        logger.debug(f'Processing MCP message: {message}')

        # Create a simple queue-based communication with the MCP server
        request_queue = asyncio.Queue()
        response_queue = asyncio.Queue()

        # Put the message in the request queue
        await request_queue.put(json.dumps(message).encode('utf-8') + b'\n')

        # Create a task to run the MCP server
        async def read_stream():
            return await request_queue.get()

        async def write_stream(data: bytes):
            await response_queue.put(data)

        # Simple stream interface
        class SimpleReadStream:
            async def readline(self):
                return await read_stream()

            async def read(self, n=-1):
                return await read_stream()

        class SimpleWriteStream:
            async def write(self, data: bytes):
                await write_stream(data)

            async def drain(self):
                pass

        read_stream_obj = SimpleReadStream()
        write_stream_obj = SimpleWriteStream()

        # Run the MCP server with this message
        # Note: This is a simplified approach; in production, maintain persistent connection
        task = asyncio.create_task(
            mcp._mcp_server.run(
                read_stream_obj,
                write_stream_obj,
                mcp._mcp_server.create_initialization_options(),
            )
        )

        # Wait for response with timeout
        try:
            response_data = await asyncio.wait_for(response_queue.get(), timeout=30.0)
            response = json.loads(response_data.decode('utf-8'))
            return response
        except asyncio.TimeoutError:
            logger.error('Timeout waiting for MCP server response')
            return {
                'jsonrpc': '2.0',
                'id': message.get('id'),
                'error': {'code': -32603, 'message': 'Internal error: timeout'},
            }
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f'Error handling MCP message: {e}', exc_info=True)
        return {
            'jsonrpc': '2.0',
            'id': message.get('id') if isinstance(message, dict) else None,
            'error': {'code': -32603, 'message': f'Internal error: {str(e)}'},
        }


# Set the message handler
streamable_transport.set_message_handler(handle_mcp_message)


async def simple_auth_middleware(request: Request, call_next):
    """Simple authentication middleware that accepts any API key.

    This is a pass-through authentication for development/testing.
    In production, implement proper authentication logic here.
    """
    # Skip auth for health check endpoint
    if request.url.path == '/health':
        return await call_next(request)

    # If MCP_API_KEY is set, check for it (basic validation)
    if MCP_API_KEY:
        auth_header = request.headers.get('Authorization', '')
        api_key = request.headers.get('X-API-Key', '')

        # Accept either Bearer token or X-API-Key header
        if not (auth_header.startswith('Bearer ') or api_key):
            logger.warning('Request missing API key or Authorization header')
            return JSONResponse(
                {
                    'error': 'Missing authentication. Provide Authorization: Bearer <token> or X-API-Key header'
                },
                status_code=401,
            )

        # For this simple implementation, any non-empty key is accepted
        provided_key = auth_header.replace('Bearer ', '') if auth_header else api_key
        if not provided_key:
            logger.warning('Empty API key provided')
            return JSONResponse({'error': 'Invalid authentication credentials'}, status_code=401)

        logger.debug(f'Request authenticated with key: {provided_key[:8]}...')
    else:
        logger.debug('No MCP_API_KEY set - authentication is disabled')

    return await call_next(request)


async def health_check(request: Request):
    """Health check endpoint for load balancers and monitoring."""
    return JSONResponse(
        {
            'status': 'healthy',
            'service': 'cloudwatch-applicationsignals-mcp-server',
            'version': '0.1.19',
            'region': AWS_REGION,
            'transport': 'streamable-http',
        }
    )


async def server_info(request: Request):
    """Server information endpoint."""
    return JSONResponse(
        {
            'name': 'cloudwatch-applicationsignals-mcp-server',
            'description': 'AWS CloudWatch Application Signals MCP Server',
            'version': '0.1.19',
            'transport': 'streamable-http',
            'region': AWS_REGION,
            'endpoints': {'health': '/health', 'info': '/info', 'mcp': '/mcp'},
            'authentication': 'enabled' if MCP_API_KEY else 'disabled',
        }
    )


async def handle_mcp_endpoint(request: Request):
    """Handle MCP endpoint - supports GET, POST, DELETE."""
    if request.method == 'GET':
        return await streamable_transport.handle_get(request)
    elif request.method == 'POST':
        return await streamable_transport.handle_post(request)
    elif request.method == 'DELETE':
        return await streamable_transport.handle_delete(request)
    else:
        return JSONResponse(
            {'error': 'Method not allowed'},
            status_code=405,
        )


# Create Starlette application
app = Starlette(
    debug=log_level == 'DEBUG',
    routes=[
        Route('/health', endpoint=health_check, methods=['GET']),
        Route('/info', endpoint=server_info, methods=['GET']),
        Route('/mcp', endpoint=handle_mcp_endpoint, methods=['GET', 'POST', 'DELETE']),
    ],
)

# Add authentication middleware
app.middleware('http')(simple_auth_middleware)


def main():
    """Run the remote MCP server."""
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level=log_level)

    # Check if SSL should be enabled
    # SSL is disabled if DISABLE_SSL=true or if SSL files don't exist
    ssl_enabled = not DISABLE_SSL and os.path.exists(SSL_KEYFILE) and os.path.exists(SSL_CERTFILE)
    protocol = 'https' if ssl_enabled else 'http'

    logger.info('Starting CloudWatch Application Signals MCP Remote Server')
    logger.info(f'Server: {HOST}:{PORT}')
    logger.info(f'Region: {AWS_REGION}')
    logger.info(f'Protocol: {protocol.upper()}')
    logger.info('Transport: Streamable HTTP')
    logger.info(f'Authentication: {"enabled" if MCP_API_KEY else "disabled (pass-through)"}')

    if ssl_enabled:
        logger.info('SSL/TLS: enabled')
        logger.info(f'  Certificate: {SSL_CERTFILE}')
        logger.info(f'  Key: {SSL_KEYFILE}')
    else:
        if DISABLE_SSL:
            logger.info('SSL/TLS: disabled (DISABLE_SSL=true, running in HTTP mode)')
            logger.info('  Suitable for running behind ALB/CloudFront with SSL termination')
        else:
            logger.warning('SSL/TLS: disabled (HTTP mode)')
            logger.warning('  For remote access, MCP clients require HTTPS')
            logger.warning('  Set SSL_KEYFILE and SSL_CERTFILE, or use default paths:')
            logger.warning(f'    {SSL_KEYFILE}')
            logger.warning(f'    {SSL_CERTFILE}')

    logger.info('Endpoints:')
    logger.info(f'  Health Check: {protocol}://{HOST}:{PORT}/health')
    logger.info(f'  Server Info: {protocol}://{HOST}:{PORT}/info')
    logger.info(f'  MCP Endpoint: {protocol}://{HOST}:{PORT}/mcp')

    try:
        if ssl_enabled:
            uvicorn.run(
                app,
                host=HOST,
                port=PORT,
                log_level=log_level.lower(),
                access_log=log_level == 'DEBUG',
                ssl_keyfile=SSL_KEYFILE,
                ssl_certfile=SSL_CERTFILE,
            )
        else:
            uvicorn.run(
                app,
                host=HOST,
                port=PORT,
                log_level=log_level.lower(),
                access_log=log_level == 'DEBUG',
            )
    except KeyboardInterrupt:
        logger.info('Server shutdown by user')
    except Exception as e:
        logger.error(f'Server error: {e}', exc_info=True)
        raise


if __name__ == '__main__':
    main()
