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

"""MCP Streamable HTTP Transport Implementation.

This module implements the MCP Streamable HTTP transport protocol as specified in:
https://spec.modelcontextprotocol.io/specification/architecture/#http-with-sse

Key features:
- Single unified endpoint supporting both GET and POST
- Session management with Mcp-Session-Id headers
- Stream resumability with Last-Event-ID support
- Flexible response format (SSE or direct JSON)
"""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from loguru import logger
from mcp.types import JSONRPCMessage
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from typing import Any


class StreamableHTTPTransport:
    """Implements MCP Streamable HTTP transport protocol.

    This transport provides:
    - Unified endpoint for GET (streaming) and POST (request/response)
    - Session management
    - Stream resumability
    - Server-Sent Events for streaming responses
    """

    def __init__(self, endpoint: str = '/mcp'):
        """Initialize StreamableHTTPTransport.

        Args:
            endpoint: The base endpoint path (default: /mcp)
        """
        self.endpoint = endpoint
        self.sessions: dict[str, dict[str, Any]] = {}
        self.message_handler: Callable[[JSONRPCMessage], Awaitable[Any]] | None = None

    def set_message_handler(self, handler: Callable[[JSONRPCMessage], Awaitable[Any]]) -> None:
        """Set the handler for incoming JSON-RPC messages.

        Args:
            handler: Async function to handle JSON-RPC messages
        """
        self.message_handler = handler

    async def handle_get(self, request: Request) -> Response:
        """Handle GET request - establish SSE stream.

        Args:
            request: Starlette Request object

        Returns:
            StreamingResponse with Server-Sent Events
        """
        # Get or create session
        session_id = request.headers.get('Mcp-Session-Id')
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f'Created new session: {session_id}')
        else:
            logger.info(f'Resuming session: {session_id}')

        # Get Last-Event-ID for stream resumption
        last_event_id = request.headers.get('Last-Event-ID')
        if last_event_id:
            logger.debug(f'Client requesting events after: {last_event_id}')

        # Create or get session data
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'id': session_id,
                'queue': asyncio.Queue(),
                'event_counter': 0,
                'message_buffer': [],  # Buffer for resumability
            }

        session = self.sessions[session_id]

        async def event_generator():
            """Generate Server-Sent Events."""
            try:
                # Send endpoint event for backward compatibility with older MCP clients
                # This tells clients where to send POST requests
                yield 'event: endpoint\n'
                yield f'data: {json.dumps({"endpoint": self.endpoint})}\n\n'

                # Send session ID event
                yield 'event: session\n'
                yield f'data: {json.dumps({"sessionId": session_id})}\n\n'

                # Stream messages from the queue
                while True:
                    try:
                        message = await asyncio.wait_for(session['queue'].get(), timeout=30.0)

                        if message is None:  # Sentinel to close stream
                            break

                        # Increment event counter for resumability
                        session['event_counter'] += 1
                        event_id = str(session['event_counter'])

                        # Add to buffer for resumability
                        session['message_buffer'].append({'id': event_id, 'data': message})

                        # Keep last 100 messages for resumability
                        if len(session['message_buffer']) > 100:
                            session['message_buffer'].pop(0)

                        # Send as SSE
                        yield f'id: {event_id}\n'
                        yield 'event: message\n'
                        yield f'data: {json.dumps(message)}\n\n'

                    except asyncio.TimeoutError:
                        # Send keepalive comment
                        yield ': keepalive\n\n'

            except Exception as e:
                logger.error(f'Error in SSE stream: {e}', exc_info=True)
            finally:
                logger.info(f'SSE stream closed for session: {session_id}')

        return StreamingResponse(
            event_generator(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',  # Disable nginx buffering
                'Mcp-Session-Id': session_id,
            },
        )

    async def handle_post(self, request: Request) -> Response:
        """Handle POST request - process JSON-RPC message.

        Args:
            request: Starlette Request object

        Returns:
            JSON response or StreamingResponse
        """
        # Get session ID from header, or use stateless mode
        session_id = request.headers.get('Mcp-Session-Id')
        is_stateless = False

        if not session_id:
            # Stateless mode: generate temporary session ID for this request only
            session_id = str(uuid.uuid4())
            is_stateless = True
            logger.warning(
                f'POST request without Mcp-Session-Id header - using stateless mode (session {session_id})'
            )
            logger.warning(
                'Client should establish session via GET request first for bidirectional communication'
            )

        # Ensure session exists (create if needed)
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'id': session_id,
                'queue': asyncio.Queue(),
                'event_counter': 0,
                'message_buffer': [],
                'is_stateless': is_stateless,  # Mark for cleanup
            }
            logger.info(f'Created {"stateless " if is_stateless else ""}session: {session_id}')

        session = self.sessions[session_id]

        try:
            # Parse JSON-RPC message
            body = await request.body()
            message = json.loads(body.decode('utf-8'))

            logger.debug(f'Received message: {message}')

            # Handle the message if handler is set
            if self.message_handler:
                response = await self.message_handler(message)

                # Queue response for SSE stream (if not stateless)
                if not is_stateless:
                    await session['queue'].put(response)

                # Cleanup stateless sessions immediately after response
                if is_stateless and session_id in self.sessions:
                    del self.sessions[session_id]
                    logger.debug(f'Cleaned up stateless session: {session_id}')

                # Return response directly
                return Response(
                    content=json.dumps(response),
                    media_type='application/json',
                    headers={'Mcp-Session-Id': session_id},
                )
            else:
                logger.warning('No message handler set')
                # Cleanup stateless session on error too
                if is_stateless and session_id in self.sessions:
                    del self.sessions[session_id]

                return Response(
                    content=json.dumps({'error': 'No message handler configured'}),
                    status_code=500,
                    media_type='application/json',
                )

        except json.JSONDecodeError as e:
            logger.error(f'Invalid JSON: {e}')
            return Response(
                content=json.dumps({'error': 'Invalid JSON'}),
                status_code=400,
                media_type='application/json',
            )
        except Exception as e:
            logger.error(f'Error handling POST: {e}', exc_info=True)
            return Response(
                content=json.dumps({'error': str(e)}),
                status_code=500,
                media_type='application/json',
            )

    async def handle_delete(self, request: Request) -> Response:
        """Handle DELETE request - terminate session.

        Args:
            request: Starlette Request object

        Returns:
            JSON response
        """
        session_id = request.headers.get('Mcp-Session-Id')

        if not session_id or session_id not in self.sessions:
            return Response(
                content=json.dumps({'error': 'Session not found'}),
                status_code=404,
                media_type='application/json',
            )

        # Send sentinel to close SSE stream
        await self.sessions[session_id]['queue'].put(None)

        # Remove session
        del self.sessions[session_id]
        logger.info(f'Session terminated: {session_id}')

        return Response(
            content=json.dumps({'status': 'session terminated'}),
            media_type='application/json',
        )

    async def send_message(self, session_id: str, message: dict[str, Any]) -> None:
        """Send a message to a specific session.

        Args:
            session_id: The session ID
            message: The message to send
        """
        if session_id in self.sessions:
            await self.sessions[session_id]['queue'].put(message)
        else:
            logger.warning(f'Attempted to send message to non-existent session: {session_id}')
