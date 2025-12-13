# MCP Client Configuration Guide

## Overview

This guide explains how to configure MCP clients (like Claude Desktop or custom implementations) to connect to the CloudWatch Application Signals MCP Server using the Streamable HTTP transport.

## Configuration

### Claude Desktop (mcp.json)

Add this configuration to your `mcp.json` file:

```json
{
  "mcpServers": {
    "cloudwatch-applicationsignals-remote": {
      "url": "http://localhost:8080/mcp",
      "transport": "sse",
      "headers": {
        "X-API-Key": "your-custom-secret-key"
      }
    }
  }
}
```

**Important Notes:**

1. **Transport Type**: Use `"transport": "sse"` (NOT `"streamable-http"`)
   - The MCP SSE transport implements the streamable HTTP protocol
   - Claude Desktop and most MCP clients use `"sse"` as the transport identifier

2. **Endpoint URL**: Use `/mcp` as the endpoint
   - The server automatically handles the SSE stream on GET `/mcp`
   - The client will receive an `endpoint` event telling it to POST to `/messages/{sessionId}`
   - This is all handled automatically by the MCP protocol

3. **Authentication**: The `X-API-Key` header is optional
   - Set `MCP_API_KEY` environment variable on the server side
   - Default value is `"your-test-key"` for development
   - Can also use `"Authorization": "Bearer <token>"` header

### Example Configurations

#### Local Development (No Auth)

```json
{
  "mcpServers": {
    "cloudwatch-applicationsignals": {
      "url": "http://localhost:8080/mcp",
      "transport": "sse"
    }
  }
}
```

To run the server without authentication:

```bash
# Disable authentication by not setting MCP_API_KEY
unset MCP_API_KEY
# Or set it to empty string
MCP_API_KEY="" python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

#### Production (with HTTPS and Auth)

```json
{
  "mcpServers": {
    "cloudwatch-applicationsignals-prod": {
      "url": "https://mcp-server.example.com/mcp",
      "transport": "sse",
      "headers": {
        "X-API-Key": "prod-secret-key-here",
        "X-Custom-Header": "any-value"
      }
    }
  }
}
```

Server configuration:

```bash
# Enable SSL/TLS
DISABLE_SSL=false \
SSL_KEYFILE=/path/to/server.key \
SSL_CERTFILE=/path/to/server.crt \
MCP_API_KEY="prod-secret-key-here" \  # pragma: allowlist secret
MCP_PORT=443 \
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable  # pragma: allowlist secret
```

#### Behind Load Balancer (ALB/CloudFront)

```json
{
  "mcpServers": {
    "cloudwatch-applicationsignals-alb": {
      "url": "https://alb-endpoint.amazonaws.com/mcp",
      "transport": "sse",
      "headers": {
        "X-API-Key": "your-secret-key"
      }
    }
  }
}
```

Server configuration (runs HTTP behind ALB which handles SSL):

```bash
# HTTP mode suitable for ALB/CloudFront with SSL termination
DISABLE_SSL=true \
MCP_API_KEY="your-secret-key" \  # pragma: allowlist secret
MCP_PORT=8080 \
MCP_HOST=0.0.0.0 \
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable  # pragma: allowlist secret
```

## Protocol Flow

When a client connects, here's what happens:

1. **Client establishes SSE connection**:
   ```http
   GET /mcp HTTP/1.1
   Host: localhost:8080
   Accept: text/event-stream
   X-API-Key: your-custom-secret-key
   ```

2. **Server responds with SSE stream**:
   ```http
   HTTP/1.1 200 OK
   Content-Type: text/event-stream
   Cache-Control: no-cache
   Connection: keep-alive

   event: endpoint
   data: {"uri": "http://localhost:8080/messages/{sessionId}"}

   event: message
   data: {"jsonrpc":"2.0","method":"initialized","params":{}}
   ```

3. **Client sends messages to the endpoint**:
   ```http
   POST /messages/{sessionId} HTTP/1.1
   Host: localhost:8080
   Content-Type: application/json
   X-API-Key: your-custom-secret-key

   {"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}
   ```

4. **Server responds on the SSE stream**:
   ```
   event: message
   data: {"jsonrpc":"2.0","result":{"tools":[...]},"id":1}
   ```

## Testing the Connection

### 1. Start the Server

```bash
# Basic startup
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable

# With debug logging
MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL=DEBUG \
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

### 2. Test Health Endpoint

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "cloudwatch-applicationsignals-mcp-server",
  "version": "0.1.19",
  "region": "us-east-1",
  "transport": "streamable-http"
}
```

### 3. Test SSE Connection

```bash
# This should establish an SSE stream and show the endpoint event
curl -N -H "X-API-Key: your-test-key" http://localhost:8080/mcp
```

Expected output (streaming):
```
event: endpoint
data: http://localhost:8080/messages/<some-session-id>

event: message
data: <initialization message>

: keepalive
```

### 4. Test with MCP Inspector

Use the MCP Inspector tool to test the full protocol:

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Test the server
mcp-inspector http://localhost:8080/mcp
```

## Troubleshooting

### Issue: Client can't connect

**Symptoms**: Connection timeout, refused, or 401 errors

**Solutions**:
1. Check server is running: `curl http://localhost:8080/health`
2. Verify API key matches between client and server
3. Check firewall rules allow connections on the port
4. Review server logs for authentication errors

### Issue: SSE stream doesn't send events

**Symptoms**: curl shows connection but no events

**Solutions**:
1. Check server logs for errors
2. Verify AWS credentials are configured correctly
3. Test with debug logging: `MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL=DEBUG`

### Issue: Tools not appearing in client

**Symptoms**: Client connects but no tools available

**Solutions**:
1. Check AWS Application Signals is enabled in your account
2. Verify AWS region is correct: `AWS_REGION=us-east-1`
3. Check IAM permissions for the server's AWS credentials
4. Review server startup logs for tool registration

### Issue: SSL/TLS certificate errors

**Symptoms**: SSL handshake failures, certificate verification errors

**Solutions**:
1. For development: Use HTTP mode (`DISABLE_SSL=true`)
2. For production: Ensure certificate and key files exist and are valid
3. Behind load balancer: Use HTTP mode and let ALB/CloudFront handle SSL
4. Check certificate paths: `SSL_CERTFILE` and `SSL_KEYFILE`

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PORT` | `8080` | Port to listen on |
| `MCP_HOST` | `0.0.0.0` | Host/IP to bind to |
| `MCP_API_KEY` | `your-test-key` | API key for authentication (empty to disable) |
| `DISABLE_SSL` | `true` | Disable SSL/TLS |
| `SSL_KEYFILE` | `/home/ec2-user/ssl/server.key` | Path to SSL private key |
| `SSL_CERTFILE` | `/home/ec2-user/ssl/server.crt` | Path to SSL certificate |
| `MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | - | AWS access key (optional, uses default credential chain) |
| `AWS_SECRET_ACCESS_KEY` | - | AWS secret key (optional) |
| `AWS_PROFILE` | - | AWS profile name (optional) |

## Security Best Practices

1. **Use HTTPS in production**: Always enable SSL/TLS or use a load balancer with SSL termination
2. **Use strong API keys**: Generate random, long API keys for production
3. **Restrict network access**: Use security groups/firewalls to limit who can connect
4. **Use IAM roles**: Prefer IAM roles over access keys for AWS credentials
5. **Monitor access logs**: Enable debug logging to track connections and requests
6. **Rotate credentials**: Regularly rotate API keys and AWS credentials
7. **Use environment variables**: Never hardcode credentials in configuration files

## Advanced Configuration

### Custom Port

```bash
MCP_PORT=3000 python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable
```

```json
{
  "mcpServers": {
    "cloudwatch-applicationsignals": {
      "url": "http://localhost:3000/mcp",
      "transport": "sse"
    }
  }
}
```

### Multiple Regions

Run multiple server instances for different regions:

```bash
# Region 1: us-east-1
AWS_REGION=us-east-1 MCP_PORT=8080 \
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable &

# Region 2: eu-west-1
AWS_REGION=eu-west-1 MCP_PORT=8081 \
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable &
```

Configure client with multiple servers:

```json
{
  "mcpServers": {
    "cloudwatch-applicationsignals-us": {
      "url": "http://localhost:8080/mcp",
      "transport": "sse"
    },
    "cloudwatch-applicationsignals-eu": {
      "url": "http://localhost:8081/mcp",
      "transport": "sse"
    }
  }
}
```

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN pip install -e .

EXPOSE 8080

ENV MCP_PORT=8080 \
    MCP_HOST=0.0.0.0 \
    DISABLE_SSL=true

CMD ["python", "-m", "awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable"]
```

Run with:
```bash
docker build -t cloudwatch-mcp-server .
docker run -p 8080:8080 \
  -e AWS_REGION=us-east-1 \
  -e MCP_API_KEY=your-secret-key \
  cloudwatch-mcp-server
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/awslabs/mcp/issues
- Documentation: https://awslabs.github.io/mcp/
- MCP Specification: https://spec.modelcontextprotocol.io/
