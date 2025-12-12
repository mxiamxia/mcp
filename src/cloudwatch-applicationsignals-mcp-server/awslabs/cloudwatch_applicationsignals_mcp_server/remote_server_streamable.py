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


# Get FastMCP's built-in SSE app
# FastMCP automatically handles all MCP protocol messages
sse_app = mcp.sse_app()


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
            'transport': 'sse',
            'region': AWS_REGION,
            'endpoints': {
                'health': '/health',
                'info': '/info',
                'sse': '/sse',
                'messages': '/messages',
            },
            'authentication': 'enabled' if MCP_API_KEY else 'disabled',
        }
    )


# Create Starlette application with FastMCP's SSE app mounted
app = Starlette(
    debug=log_level == 'DEBUG',
    routes=[
        Route('/health', endpoint=health_check, methods=['GET']),
        Route('/info', endpoint=server_info, methods=['GET']),
        Mount('/', app=sse_app),  # Mount FastMCP's SSE app at root (handles /sse and /messages)
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

    logger.info('Starting CloudWatch Application Signals MCP Remote Server (SSE)')
    logger.info(f'Server: {HOST}:{PORT}')
    logger.info(f'Region: {AWS_REGION}')
    logger.info(f'Protocol: {protocol.upper()}')
    logger.info('Transport: SSE (FastMCP built-in)')
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
    logger.info(f'  SSE Stream: {protocol}://{HOST}:{PORT}/sse')
    logger.info(f'  Messages: {protocol}://{HOST}:{PORT}/messages/{{sessionId}}')

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
