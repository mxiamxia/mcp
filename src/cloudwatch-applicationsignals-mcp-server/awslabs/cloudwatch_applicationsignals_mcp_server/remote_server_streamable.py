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

import os
import sys
import uvicorn

# Import the FastMCP instance from the existing server
from .server import AWS_REGION, mcp
from loguru import logger
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route


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


async def simple_auth_middleware(request: Request, call_next):
    """Simple authentication middleware that requires API key.

    This middleware enforces authentication for MCP endpoints and returns
    proper 401 responses with WWW-Authenticate headers when auth is required.
    """
    # Debug logging: print request details
    logger.info(f'Request URL: {request.url}')
    logger.info(f'Request Path: {request.url.path}')
    logger.info(f'Request Method: {request.method}')
    logger.info(f'Request Headers: {dict(request.headers)}')
    logger.info(f'Request Client: {request.client}')

    # Skip auth for health check and info endpoints only
    if request.url.path in ['/health', '/info']:
        return await call_next(request)

    # Check for authentication headers
    auth_header = request.headers.get('Authorization', '')
    api_key = request.headers.get('X-API-Key', '')

    # Accept either Bearer token or X-API-Key header
    if not (auth_header.startswith('Bearer ') or api_key):
        logger.warning('Request missing API key or Authorization header')
        # Return 401 with WWW-Authenticate header for MCP client discovery
        return JSONResponse(
            {
                'error': 'Missing authentication. Provide Authorization: Bearer <token> or X-API-Key header'
            },
            status_code=401,
            headers={'WWW-Authenticate': 'Bearer realm="MCP Server", charset="UTF-8"'},
        )

    # Validate the provided key
    provided_key = auth_header.replace('Bearer ', '') if auth_header else api_key
    if not provided_key:
        logger.warning('Empty API key provided')
        return JSONResponse(
            {'error': 'Invalid authentication credentials'},
            status_code=401,
            headers={'WWW-Authenticate': 'Bearer realm="MCP Server", charset="UTF-8"'},
        )

    # If MCP_API_KEY is set, validate against it; otherwise accept any non-empty key
    if MCP_API_KEY and provided_key != MCP_API_KEY:
        logger.warning(f'Invalid API key provided: {provided_key[:8]}...')
        return JSONResponse(
            {'error': 'Invalid authentication credentials'},
            status_code=401,
            headers={'WWW-Authenticate': 'Bearer realm="MCP Server", charset="UTF-8"'},
        )

    logger.info(f'Request authenticated with key: {provided_key[:8]}...')
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
            'endpoints': {
                'health': '/health',
                'info': '/info',
                'mcp': '/mcp',
            },
            'authentication': 'enabled' if MCP_API_KEY else 'disabled',
        }
    )


def create_app() -> Starlette:
    """Create the Starlette application with MCP SSE transport.

    This uses FastMCP's internal SSE transport which implements the
    MCP Streamable HTTP protocol correctly.
    """
    # Create SSE transport - use /mcp as the base path for messages
    sse = SseServerTransport('/messages/')

    async def handle_sse_get(request: Request) -> None:
        """Handle SSE GET requests for establishing bidirectional connection."""
        logger.info(f'New SSE connection from {request.client}')
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,  # type: ignore[reportPrivateUsage]
        ) as streams:
            # Run the MCP server with the established streams
            await mcp._mcp_server.run(
                streams[0],  # read stream
                streams[1],  # write stream
                mcp._mcp_server.create_initialization_options(),
            )

    async def handle_mcp_post(request: Request) -> None:
        """Handle POST requests to /mcp endpoint (stateless mode)."""
        logger.info(f'MCP POST request from {request.client}')
        # For stateless POST requests, use the message handler
        await sse.handle_post_message(
            request.scope,
            request.receive,
            request._send,  # type: ignore[reportPrivateUsage]
        )

    # Create Starlette app with routes
    app = Starlette(
        debug=log_level == 'DEBUG',
        routes=[
            Route('/health', endpoint=health_check, methods=['GET']),
            Route('/info', endpoint=server_info, methods=['GET']),
            # SSE endpoint for establishing the connection (GET)
            Route('/mcp', endpoint=handle_sse_get, methods=['GET']),
            # Stateless endpoint (POST)
            Route('/mcp', endpoint=handle_mcp_post, methods=['POST']),
            # Message endpoint for client-to-server messages (for stateful SSE sessions)
            Mount('/messages/', app=sse.handle_post_message),
        ],
    )

    # Add authentication middleware
    app.middleware('http')(simple_auth_middleware)

    return app


def main():
    """Run the remote MCP server."""
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level=log_level)

    # Check if SSL should be enabled
    # SSL is disabled if DISABLE_SSL=true or if SSL files don't exist
    ssl_enabled = not DISABLE_SSL and os.path.exists(SSL_KEYFILE) and os.path.exists(SSL_CERTFILE)
    protocol = 'https' if ssl_enabled else 'http'

    logger.info('Starting CloudWatch Application Signals MCP Remote Server (Streamable HTTP)')
    logger.info(f'Server: {HOST}:{PORT}')
    logger.info(f'Region: {AWS_REGION}')
    logger.info(f'Protocol: {protocol.upper()}')
    logger.info('Transport: Streamable HTTP (MCP SSE)')
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
    logger.info(f'  MCP SSE Endpoint: {protocol}://{HOST}:{PORT}/mcp')
    logger.info(f'  MCP Messages: {protocol}://{HOST}:{PORT}/messages/{{sessionId}}')

    # Create the app
    app = create_app()

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
