# CloudWatch Application Signals MCP - Streamable HTTP Transport

This document describes the Streamable HTTP transport implementation for the CloudWatch Application Signals MCP Server.

## Overview

The Streamable HTTP transport is a modern MCP transport protocol that provides:
- Single unified endpoint for all MCP operations
- Session management with automatic session ID assignment
- Stream resumability for reliable connections
- Server-Sent Events (SSE) for streaming responses
- Support for both streaming and request/response patterns

## Quick Start

### 1. Install the Server

```bash
cd /path/to/cloudwatch-applicationsignals-mcp-server
pip install -e .
```

### 2. Start the Streamable HTTP Server

**Default: HTTP mode on port 8080 (suitable for ALB/CloudFront)**

```bash
# Using the installed script
awslabs.cloudwatch-applicationsignals-mcp-server-streamable

# Or using Python module
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

The server runs in HTTP mode on port 8080 by default (no SSL/TLS).

**To enable HTTPS (for direct access without ALB):**

```bash
export DISABLE_SSL=false
export MCP_PORT=443
sudo -E python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

Note: Port 443 requires sudo. You'll also need SSL certificates configured via `SSL_KEYFILE` and `SSL_CERTFILE` environment variables.

### 3. Configure Your MCP Client

**For clients that support Streamable HTTP:**

```json
{
  "mcpServers": {
    "cloudwatch-appsignals": {
      "url": "https://your-server.com/mcp",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer your-test-key"
      }
    }
  }
}
```

## Endpoints

### `/mcp` - Main MCP Endpoint

Supports three HTTP methods:

#### GET - Establish SSE Stream
Establishes a Server-Sent Events stream for receiving server-initiated messages.

**Request Headers:**
- `Authorization: Bearer <token>` - Authentication token
- `Mcp-Session-Id: <session-id>` - (Optional) Session ID for resumption
- `Last-Event-ID: <event-id>` - (Optional) Last received event ID for resumability

**Response:**
- Content-Type: `text/event-stream`
- Returns SSE stream with session initialization and messages

**Example:**
```bash
curl -N -H "Authorization: Bearer your-test-key" \
  https://your-server.com/mcp
```

#### POST - Send JSON-RPC Message
Sends a JSON-RPC message to the server.

**Request Headers:**
- `Authorization: Bearer <token>` - Authentication token
- `Mcp-Session-Id: <session-id>` - Session ID (required)
- `Content-Type: application/json`

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": { ... }
}
```

**Example:**
```bash
curl -X POST https://your-server.com/mcp \
  -H "Authorization: Bearer your-test-key" \
  -H "Mcp-Session-Id: abc-123" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

#### DELETE - Terminate Session
Terminates an active session and closes the SSE stream.

**Request Headers:**
- `Authorization: Bearer <token>` - Authentication token
- `Mcp-Session-Id: <session-id>` - Session ID to terminate

**Example:**
```bash
curl -X DELETE https://your-server.com/mcp \
  -H "Authorization: Bearer your-test-key" \
  -H "Mcp-Session-Id: abc-123"
```

### `/health` - Health Check

Returns server health status.

```bash
curl https://your-server.com/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "cloudwatch-applicationsignals-mcp-server",
  "version": "0.1.19",
  "region": "us-east-1",
  "transport": "streamable-http"
}
```

### `/info` - Server Information

Returns server configuration and capabilities.

```bash
curl https://your-server.com/info
```

## Environment Variables

### Required
- `AWS_REGION` - AWS region (default: us-east-1)

### AWS Credentials (choose one)
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` - Explicit credentials
- `AWS_PROFILE` - AWS profile from ~/.aws/credentials
- EC2 IAM Role - No configuration needed if running on EC2

### Optional
- `MCP_PORT` - Server port (default: 443)
- `MCP_HOST` - Host to bind to (default: 0.0.0.0)
- `MCP_API_KEY` - API key for authentication (default: your-test-key)
- `DISABLE_SSL` - Set to `true` to force HTTP mode (default: false)
- `SSL_KEYFILE` - Path to SSL private key (default: /home/ec2-user/ssl/server.key)
- `SSL_CERTFILE` - Path to SSL certificate (default: /home/ec2-user/ssl/server.crt)
- `MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL` - Logging level (default: INFO)

## Protocol Flow

### 1. Establish Connection

Client sends GET request to `/mcp`:
```
GET /mcp HTTP/1.1
Authorization: Bearer your-test-key
```

Server responds with SSE stream and assigns session ID:
```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Mcp-Session-Id: abc-123-def-456

event: session
data: {"sessionId":"abc-123-def-456"}

```

### 2. Send Messages

Client sends JSON-RPC messages via POST:
```
POST /mcp HTTP/1.1
Authorization: Bearer your-test-key
Mcp-Session-Id: abc-123-def-456
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```

Server responds directly AND streams to SSE:
```
HTTP/1.1 200 OK
Mcp-Session-Id: abc-123-def-456
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"result":{...}}
```

AND in the SSE stream:
```
id: 1
event: message
data: {"jsonrpc":"2.0","id":1,"result":{...}}

```

### 3. Stream Resumability

If the SSE connection drops, client can resume with Last-Event-ID:
```
GET /mcp HTTP/1.1
Authorization: Bearer your-test-key
Mcp-Session-Id: abc-123-def-456
Last-Event-ID: 5
```

Server sends any missed messages (events 6, 7, 8, etc.)

### 4. Terminate Session

Client sends DELETE request:
```
DELETE /mcp HTTP/1.1
Authorization: Bearer your-test-key
Mcp-Session-Id: abc-123-def-456
```

## Authentication

The server supports simple token-based authentication:

- **Authorization Header**: `Authorization: Bearer <token>`
- **X-API-Key Header**: `X-API-Key: <token>`

Default API key is `your-test-key`. Configure via `MCP_API_KEY` environment variable.

## SSL/TLS Configuration

### Direct HTTPS (Port 443)

```bash
export SSL_KEYFILE=/path/to/server.key
export SSL_CERTFILE=/path/to/server.crt
sudo -E python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

### HTTP Mode (Behind ALB/CloudFront)

```bash
export DISABLE_SSL=true
export MCP_PORT=8080
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

## Differences from SSE Transport

| Feature | SSE (Legacy) | Streamable HTTP |
|---------|--------------|-----------------|
| Endpoints | Separate `/sse` and `/messages/` | Unified `/mcp` |
| Session Management | Basic UUID | Full Mcp-Session-Id support |
| Resumability | Limited | Full with Last-Event-ID |
| Response Format | SSE only | SSE + direct JSON |
| Protocol Status | Deprecated | Current standard |

## Troubleshooting

### Connection Refused
- Check if server is running: `curl http://localhost:8080/health`
- Verify firewall/security group allows traffic on the port
- Check SSL certificate if using HTTPS

### Authentication Errors
- Ensure `Authorization: Bearer <token>` header is present
- Verify token matches `MCP_API_KEY` environment variable
- Check server logs for authentication messages

### Session Errors
- For POST requests, always include `Mcp-Session-Id` header
- Session IDs are assigned during GET request (SSE establishment)
- Use the session ID returned in the `Mcp-Session-Id` response header

### SSE Stream Issues
- Ensure client properly handles Server-Sent Events
- Check for proxy/load balancer buffering (disable with `X-Accel-Buffering: no`)
- Monitor keepalive messages (`: keepalive` comments every 30 seconds)

## Development

### Running Tests

```bash
pytest tests/
```

### Debug Logging

```bash
export MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL=DEBUG
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

## Additional Resources

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [MCP Streamable HTTP Transport Spec](https://spec.modelcontextprotocol.io/specification/architecture/#http-with-sse)
- [CloudWatch Application Signals Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Signals.html)
