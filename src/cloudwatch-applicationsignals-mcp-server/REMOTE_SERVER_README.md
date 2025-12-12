# CloudWatch Application Signals MCP - Remote Server

This branch (`rmt-server`) contains the remote HTTP/SSE server implementation of the CloudWatch Application Signals MCP Server.

## Quick Start

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Set Environment Variables

```bash
# AWS Credentials
export AWS_ACCESS_KEY_ID="your-access-key-id"  # pragma: allowlist secret
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"  # pragma: allowlist secret
export AWS_REGION="us-east-1"

# Server Configuration (optional)
export MCP_PORT=8000
export MCP_HOST="0.0.0.0"
export MCP_API_KEY="your-secret-key"  # pragma: allowlist secret - Optional: enable authentication
```

### 3. Start the Server

**Option A: Using the startup script**
```bash
./start_remote_server.sh
```

**Option B: Direct Python command**
```bash
python3 -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server
```

**Option C: Using the installed script**
```bash
awslabs.cloudwatch-applicationsignals-mcp-server-remote
```

### 4. Test the Server

```bash
# Health check
curl http://localhost:8000/health

# Server info
curl http://localhost:8000/info
```

## Key Changes from Main Branch

1. **New Files:**
   - `remote_server.py` - HTTP/SSE server implementation
   - `REMOTE_DEPLOYMENT.md` - Comprehensive deployment guide
   - `start_remote_server.sh` - Quick start script
   - `REMOTE_SERVER_README.md` - This file

2. **Modified Files:**
   - `pyproject.toml` - Added `uvicorn` and `starlette` dependencies
   - `aws_clients.py` - Enhanced to support AWS credentials via environment variables

3. **New Features:**
   - HTTP/SSE transport (instead of stdio)
   - Simple pass-through authentication
   - Health check endpoint (`/health`)
   - Server info endpoint (`/info`)
   - Support for AWS credentials via environment variables
   - Support for EC2 IAM role credentials

## Environment Variables

### Required
- `AWS_REGION` - AWS region (default: us-east-1)

### AWS Credentials (choose one method)
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` - Explicit credentials
- `AWS_PROFILE` - Use AWS profile from ~/.aws/credentials
- EC2 IAM Role - No credentials needed if running on EC2 with IAM role

### Optional
- `MCP_PORT` - Server port (default: 8000)
- `MCP_HOST` - Host to bind to (default: 0.0.0.0)
- `MCP_API_KEY` - Enable simple authentication
- `MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL` - Logging level (default: INFO)

## Server Endpoints

- `GET /health` - Health check endpoint
- `GET /info` - Server information
- `GET /sse` - SSE endpoint for MCP protocol
- `POST /messages` - Message handler for SSE

## Client Configuration

Configure your MCP client to connect to the remote server:

```json
{
  "mcpServers": {
    "cloudwatch-applicationsignals-remote": {
      "url": "http://your-server-ip:8000/sse",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer your-secret-key"
      }
    }
  }
}
```

## Authentication

The server supports simple pass-through authentication:

- **Disabled (default)**: If `MCP_API_KEY` is not set, all requests are accepted
- **Enabled**: If `MCP_API_KEY` is set, clients must provide it via:
  - `Authorization: Bearer <key>` header, OR
  - `X-API-Key: <key>` header

**Note:** This is a simple authentication mechanism for development/testing. For production, implement proper authentication (OAuth2, JWT, etc.) and use HTTPS.

## Deployment

See [REMOTE_DEPLOYMENT.md](./REMOTE_DEPLOYMENT.md) for detailed deployment instructions including:
- EC2 setup and configuration
- Security group configuration
- Production considerations
- Troubleshooting guide

## Testing Locally

1. Start the server locally:
   ```bash
   ./start_remote_server.sh
   ```

2. Test with curl:
   ```bash
   curl http://localhost:8000/health
   ```

3. Configure your MCP client to use `http://localhost:8000/sse`

## Differences from Stdio Version

| Feature | Stdio (main branch) | Remote (rmt-server branch) |
|---------|-------------------|---------------------------|
| Transport | stdio | HTTP/SSE |
| Deployment | Local only | Local or Remote (EC2, etc.) |
| Multiple Clients | No | Yes |
| Authentication | N/A | Optional (simple) |
| Health Check | No | Yes (`/health`) |
| Public Access | No | Yes (via IP/domain) |

## Troubleshooting

### Server won't start
- Check if port 8000 is available: `lsof -i :8000`
- Verify Python version: `python3 --version` (requires 3.10+)
- Check AWS credentials: `aws sts get-caller-identity`

### Connection refused from remote client
- Verify server is running: `curl http://localhost:8000/health`
- Check firewall/security group allows inbound traffic on port 8000
- Verify you're using the correct public IP address

### Authentication errors
- Ensure `MCP_API_KEY` matches between server and client
- Check header format: `Authorization: Bearer <key>` or `X-API-Key: <key>`
- Review server logs for authentication messages

## Documentation

- [REMOTE_DEPLOYMENT.md](./REMOTE_DEPLOYMENT.md) - Complete deployment guide
- [README.md](./README.md) - Main README (stdio version)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review server logs (set `MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL=DEBUG`)
3. Open an issue on GitHub
