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

"""CloudWatch Application Signals MCP Server - Simple Streamable HTTP Server."""

import os
import sys
import uvicorn

# Import the FastMCP instance from the existing server
from .server import AWS_REGION, mcp
from loguru import logger
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route


# Get configuration from environment variables
PORT = int(os.environ.get('MCP_PORT', 8080))
HOST = os.environ.get('MCP_HOST', '0.0.0.0')
MCP_API_KEY = os.environ.get('MCP_API_KEY', '')  # Empty = no auth

# Configure logging
log_level = os.environ.get('MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL', 'INFO').upper()


def create_app():
    """Create simple Starlette app with MCP SSE transport."""
    # Create SSE transport with /message as endpoint
    sse = SseServerTransport('/message')

    async def handle_sse(request: Request):
        """Handle SSE connections at /mcp endpoint."""
        logger.info(f'SSE connection from {request.client}')
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:  # type: ignore
            await mcp._mcp_server.run(
                streams[0], streams[1], mcp._mcp_server.create_initialization_options()
            )

    async def handle_post(request: Request):
        """Handle POST messages at /message endpoint."""
        logger.debug(f'POST message from {request.client}')
        await sse.handle_post_message(request.scope, request.receive, request._send)  # type: ignore

    # Simple app with just two routes
    app = Starlette(
        routes=[
            Route('/mcp', endpoint=handle_sse, methods=['GET']),
            Route('/message', endpoint=handle_post, methods=['POST']),
        ]
    )

    return app


def main():
    """Run the simple MCP server."""
    logger.remove()
    logger.add(sys.stderr, level=log_level)

    logger.info(
        'Starting CloudWatch Application Signals MCP Remote Server (Simple Streamable HTTP)'
    )
    logger.info(f'Server: {HOST}:{PORT}')
    logger.info(f'Region: {AWS_REGION}')
    logger.info(f'Authentication: {"enabled" if MCP_API_KEY else "disabled"}')

    logger.info('Endpoints:')
    logger.info(f'  SSE Endpoint: http://{HOST}:{PORT}/mcp')
    logger.info(f'  POST Messages: http://{HOST}:{PORT}/message')

    app = create_app()

    try:
        uvicorn.run(
            app, host=HOST, port=PORT, log_level=log_level.lower(), access_log=log_level == 'DEBUG'
        )
    except KeyboardInterrupt:
        logger.info('Server shutdown by user')
    except Exception as e:
        logger.error(f'Server error: {e}', exc_info=True)
        raise


if __name__ == '__main__':
    main()
