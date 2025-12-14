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


# Get configuration from environment variables
PORT = int(os.environ.get('MCP_PORT', 8080))
HOST = os.environ.get('MCP_HOST', '0.0.0.0')

# Configure logging
log_level = os.environ.get('MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL', 'INFO').upper()


def main():
    """Run the remote MCP server using FastMCP's built-in streamable HTTP app."""
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level=log_level)

    logger.info(
        'Starting CloudWatch Application Signals MCP Remote Server (Simple Streamable HTTP)'
    )
    logger.info(f'Server: {HOST}:{PORT}')
    logger.info(f'Region: {AWS_REGION}')
    logger.info('Transport: Streamable HTTP (FastMCP built-in)')

    logger.info('Endpoints:')
    logger.info(f'  MCP SSE Endpoint: http://{HOST}:{PORT}/sse')
    logger.info(f'  MCP Messages: http://{HOST}:{PORT}/message')

    try:
        # Use FastMCP's built-in streamable_http_app
        uvicorn.run(
            mcp.streamable_http_app,
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
