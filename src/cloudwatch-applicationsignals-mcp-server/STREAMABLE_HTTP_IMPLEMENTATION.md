# MCP Streamable HTTP Transport Implementation

## Overview

This document describes the implementation of the **MCP Streamable HTTP transport** for the CloudWatch Application Signals MCP Server, as specified in the [MCP specification 2025-11-25](https://spec.modelcontextprotocol.io/specification/2025-11-25/basic/transports).

## What Changed

### Previous Implementation Issues

The previous `remote_server_streamable.py` attempted to use FastMCP's built-in `sse_app()`, but this approach had several problems:

1. **Incorrect transport pattern**: FastMCP's `sse_app()` uses separate `/sse` and `/messages` endpoints, which is the deprecated HTTP+SSE transport (2024-11-05)
2. **Missing unified endpoint**: MCP Streamable HTTP requires a single endpoint that handles both GET (SSE) and POST (JSON-RPC)
3. **Session management mismatch**: The old transport sent session/endpoint events, but the new spec doesn't

### New Implementation

The new implementation (`remote_server_streamable.py`) provides a **complete, spec-compliant** MCP Streamable HTTP transport with:

#### Key Features

1. **Unified `/mcp` endpoint**: Single endpoint handling both:
   - `GET` requests for establishing SSE streams (server-to-client)
   - `POST` requests for JSON-RPC messages (client-to-server)

2. **Proper session management**:
   - Session IDs are generated server-side on GET requests
   - Session ID returned in `Mcp-Session-Id` response header (NOT in SSE events)
   - No session/endpoint events sent in the stream
   - Session cleanup on disconnect

3. **Protocol version support**:
   - Accepts `MCP-Protocol-Version` header
   - Defaults to `2025-03-26` for backwards compatibility

4. **Message handling**:
   - GET: Establishes SSE stream for server-initiated requests/notifications
   - POST: Handles client JSON-RPC requests, responses, and notifications
   - Returns 202 Accepted for notifications and responses
   - Returns JSON response for requests

5. **Stream resumability**:
   - Event IDs attached to SSE events
   - Message buffer (last 100 messages) for redelivery
   - Support for `Last-Event-ID` header (ready for future implementation)

6. **Security & monitoring**:
   - Simple API key authentication (configurable)
   - Health check endpoint (`/health`)
   - Server info endpoint (`/info`)
   - SSL/TLS support (optional)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  MCP Client                              │
└────────────┬───────────────────────────┬─────────────────┘
             │                           │
             │ GET /mcp                  │ POST /mcp
             │ (Establish SSE stream)    │ (Send JSON-RPC)
             │                           │
             ▼                           ▼
┌─────────────────────────────────────────────────────────┐
│            Streamable HTTP Server                        │
│                                                          │
│  ┌────────────────┐         ┌──────────────────┐       │
│  │  GET Handler   │         │  POST Handler     │       │
│  │  (SSE Stream)  │         │  (JSON-RPC)       │       │
│  └────────┬───────┘         └─────────┬────────┘       │
│           │                           │                 │
│           ▼                           ▼                 │
│  ┌──────────────────────────────────────────────┐      │
│  │         Session Management                    │      │
│  │  - session_id -> {queue, buffer, metadata}    │      │
│  └──────────────────┬───────────────────────────┘      │
│                     │                                   │
│                     ▼                                   │
│  ┌──────────────────────────────────────────────┐      │
│  │       FastMCP Request Processing              │      │
│  │  - initialize, tools/list, tools/call, etc.   │      │
│  └──────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

## Protocol Flow

### 1. Client Establishes SSE Stream

```http
GET /mcp HTTP/1.1
Host: server.example.com
Accept: text/event-stream
MCP-Protocol-Version: 2025-11-25

HTTP/1.1 200 OK
Content-Type: text/event-stream
Mcp-Session-Id: 550e8400-e29b-41d4-a716-446655440000
Cache-Control: no-cache
Connection: keep-alive

: keepalive
```

**Note**: No session/endpoint events are sent (per 2025-11-25 spec)

### 2. Client Sends Initialize Request

```http
POST /mcp HTTP/1.1
Host: server.example.com
Content-Type: application/json
Accept: application/json, text/event-stream
MCP-Protocol-Version: 2025-11-25
Mcp-Session-Id: 550e8400-e29b-41d4-a716-446655440000

{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test-client", "version": "1.0.0"}
  },
  "id": 1
}

HTTP/1.1 200 OK
Content-Type: application/json
Mcp-Session-Id: 550e8400-e29b-41d4-a716-446655440000

{
  "jsonrpc": "2.0",
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {...},
    "serverInfo": {"name": "cloudwatch-applicationsignals", "version": "0.1.19"}
  },
  "id": 1
}
```

### 3. Client Calls Tools

```http
POST /mcp HTTP/1.1
Host: server.example.com
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25
Mcp-Session-Id: 550e8400-e29b-41d4-a716-446655440000

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "audit_services",
    "arguments": {
      "service_targets": "[{\"Type\":\"service\",\"Service\":\"my-service\"}]"
    }
  },
  "id": 2
}

HTTP/1.1 200 OK
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "result": {
    "content": [...]
  },
  "id": 2
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PORT` | `8080` | Server port |
| `MCP_HOST` | `0.0.0.0` | Server host |
| `MCP_API_KEY` | `your-test-key` | Optional API key for authentication |
| `DISABLE_SSL` | `true` | Disable SSL/TLS (suitable for ALB/CloudFront) |
| `SSL_KEYFILE` | `/home/ec2-user/ssl/server.key` | SSL private key path |
| `SSL_CERTFILE` | `/home/ec2-user/ssl/server.crt` | SSL certificate path |
| `MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL` | `INFO` | Log level |
| `AWS_REGION` | `us-east-1` | AWS region |

### Running the Server

```bash
# Run with default settings (HTTP mode)
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable

# Run with custom port
MCP_PORT=3000 python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable

# Run with SSL/TLS
DISABLE_SSL=false \
SSL_KEYFILE=/path/to/key.pem \
SSL_CERTFILE=/path/to/cert.pem \
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable

# Run with debug logging
MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL=DEBUG \
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

## Testing

A test script is provided at `test_streamable_server.py`:

```bash
# In one terminal, start the server
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable

# In another terminal, run the test
python test_streamable_server.py
```

### Manual Testing with curl

```bash
# Health check
curl http://localhost:8080/health

# Server info
curl http://localhost:8080/info

# Initialize
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "MCP-Protocol-Version: 2024-11-05" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    },
    "id": 1
  }'

# List tools
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2024-11-05" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}'
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (returns service status) |
| `/info` | GET | Server information and capabilities |
| `/mcp` | GET | Establish SSE stream for server-to-client messages |
| `/mcp` | POST | Send JSON-RPC messages from client to server |

## MCP Methods Supported

All standard MCP methods are supported through FastMCP:

- `initialize` - Initialize the MCP session
- `tools/list` - List available tools
- `tools/call` - Call a tool
- `resources/list` - List resources (if any)
- `resources/read` - Read a resource
- `prompts/list` - List prompts (if any)
- `prompts/get` - Get a prompt

## Differences from Previous Implementation

| Feature | Old (HTTP+SSE) | New (Streamable HTTP) |
|---------|----------------|------------------------|
| **Endpoints** | `/sse` and `/messages/{sessionId}` | Single `/mcp` endpoint |
| **Session events** | Sent `endpoint` and `session` events | No session events sent |
| **Session ID** | In SSE event data | In `Mcp-Session-Id` header only |
| **Protocol** | 2024-11-05 (deprecated) | 2025-11-25 (current) |
| **GET usage** | Establish stream with session event | Establish stream (no events) |
| **POST usage** | Send to `/messages/{sessionId}` | Send to `/mcp` with header |

## Security Considerations

1. **Authentication**: The current implementation uses simple API key authentication. For production, implement proper OAuth2 or JWT authentication.

2. **SSL/TLS**: By default, SSL is disabled for deployment behind load balancers. Enable SSL for direct client access.

3. **Rate limiting**: Consider adding rate limiting middleware for production deployments.

4. **CORS**: Add CORS middleware if accessed from web browsers.

## Future Enhancements

1. **Stream resumability**: Implement full resumability with `Last-Event-ID` support
2. **Multiple concurrent streams**: Support multiple SSE streams per session
3. **Message redelivery**: Implement message redelivery for disconnected clients
4. **Advanced authentication**: OAuth2, JWT, or custom auth strategies
5. **Metrics and monitoring**: Add Prometheus metrics, CloudWatch metrics
6. **Graceful shutdown**: Implement graceful session cleanup on shutdown

## References

- [MCP Specification 2025-11-25](https://spec.modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP Streamable HTTP Transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [Server-Sent Events (SSE)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [JSON-RPC 2.0](https://www.jsonrpc.org/specification)

## Troubleshooting

### Server won't start

1. Check if port is already in use: `lsof -i :8080`
2. Check AWS credentials are configured
3. Check logs for initialization errors

### Client can't connect

1. Verify server is running: `curl http://localhost:8080/health`
2. Check firewall rules
3. Verify SSL configuration if using HTTPS

### Tools not working

1. Check AWS credentials and permissions
2. Verify AWS region is correct
3. Check Application Signals is enabled in your AWS account
4. Review server logs for errors

## License

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
Licensed under the Apache License, Version 2.0.
