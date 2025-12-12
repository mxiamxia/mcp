# Remote MCP Server Deployment Guide

This guide explains how to deploy the CloudWatch Application Signals MCP Server as a remote HTTP/SSE server on AWS EC2.

## Overview

The remote MCP server allows clients to connect over HTTP using Server-Sent Events (SSE) transport instead of stdio. This enables:

- Deployment on remote servers (EC2, containers, etc.)
- Multiple clients connecting to the same server instance
- Access via public IP or domain name
- Simple pass-through authentication for development/testing

## Prerequisites

1. AWS EC2 instance (Amazon Linux 2023, Amazon Linux 2, or Ubuntu recommended)
2. Python 3.10 or higher
3. AWS credentials (Access Key ID and Secret Access Key)
4. Security group allowing inbound traffic on port 8000 (or your chosen port)

## Installation on EC2

### 1. Connect to your EC2 instance

```bash
ssh -i your-key.pem ec2-user@your-ec2-public-ip
```

### 2. Install Python 3.10+ and dependencies

**IMPORTANT:** This MCP server requires Python 3.10 or higher.

**Amazon Linux 2023:**
```bash
sudo yum update -y
sudo yum install python3.11 python3.11-pip git -y

# Verify Python version
python3.11 --version  # Should show 3.11.x
```

**Amazon Linux 2:**
```bash
# Option 1: Try Amazon Linux Extras (if available)
sudo amazon-linux-extras enable python3.11
sudo yum install python3.11 python3.11-pip git -y

# Option 2: Build Python 3.11 from source (if extras not available)
sudo yum update -y
sudo yum groupinstall "Development Tools" -y
sudo yum install openssl-devel bzip2-devel libffi-devel wget -y

cd /tmp
wget https://www.python.org/ftp/python/3.11.8/Python-3.11.8.tgz
tar xzf Python-3.11.8.tgz
cd Python-3.11.8
./configure --enable-optimizations
sudo make altinstall

# Verify installation
python3.11 --version

# Install git
sudo yum install git -y
```

**Ubuntu:**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev python3-pip git -y

# Verify Python version
python3.10 --version  # Should show 3.10.x or higher
```

### 3. Clone the repository and install

```bash
cd /home/ec2-user
git clone https://github.com/awslabs/mcp.git
cd mcp/src/cloudwatch-applicationsignals-mcp-server
git checkout rmt-server

# Create virtual environment with Python 3.10+
# For Amazon Linux 2023/AL2:
python3.11 -m venv venv

# For Ubuntu:
# python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install the package
pip install -e .
```

## Configuration

### Required Environment Variables

Set the following environment variables before starting the server:

```bash
# AWS Credentials
export AWS_ACCESS_KEY_ID="your-access-key-id"  # pragma: allowlist secret
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"  # pragma: allowlist secret
export AWS_REGION="us-east-1"  # or your preferred region

# Optional: Session token for temporary credentials
# export AWS_SESSION_TOKEN="your-session-token"

# Server Configuration
export MCP_PORT=8000                    # Port to listen on (default: 8000)
export MCP_HOST="0.0.0.0"              # Host to bind to (default: 0.0.0.0)
export MCP_API_KEY="your-secret-key"   # pragma: allowlist secret - Optional: Enable simple authentication

# Logging
export MCP_CLOUDWATCH_APPLICATIONSIGNALS_LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
```

### Using AWS Profile (Alternative)

Instead of explicit credentials, you can use an AWS profile:

```bash
export AWS_PROFILE="your-profile-name"
export AWS_REGION="us-east-1"
```

### Using EC2 IAM Role (Recommended for Production)

For EC2 instances with an IAM role attached, no credentials are needed:

```bash
# Only specify the region
export AWS_REGION="us-east-1"
export MCP_PORT=8000
```

The server will automatically use the EC2 instance's IAM role credentials.

## Starting the Server

### Method 1: Direct Python Command

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run the server
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server
```

Or using the installed script:

```bash
# Make sure virtual environment is activated
source venv/bin/activate

awslabs.cloudwatch-applicationsignals-mcp-server-remote
```

### Method 2: Using nohup (Background Process)

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Start server in background
nohup python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server > server.log 2>&1 &
```

View logs:
```bash
tail -f server.log
```

Stop the server:
```bash
# Find the process ID
ps aux | grep remote_server

# Kill the process
kill <PID>
```

### Method 3: Using the Startup Script

```bash
./start_remote_server.sh
```

## EC2 Security Group Configuration

Configure your EC2 security group to allow inbound traffic:

1. Go to EC2 Console → Security Groups
2. Select your instance's security group
3. Add inbound rule:
   - Type: Custom TCP
   - Port: 8000 (or your MCP_PORT)
   - Source: 0.0.0.0/0 (for public access) or specific IP ranges

**Security Note:** For production, restrict source IPs to known client addresses.

## Testing the Server

### 1. Health Check

From your local machine or another server:

```bash
curl http://your-ec2-public-ip:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "cloudwatch-applicationsignals-mcp-server",
  "version": "0.1.19",
  "region": "us-east-1",
  "transport": "sse"
}
```

### 2. Server Info

```bash
curl http://your-ec2-public-ip:8000/info
```

### 3. Test with Authentication (if MCP_API_KEY is set)

```bash
curl -H "Authorization: Bearer your-secret-key" http://your-ec2-public-ip:8000/info  # pragma: allowlist secret
```

Or using X-API-Key header:

```bash
curl -H "X-API-Key: your-secret-key" http://your-ec2-public-ip:8000/info  # pragma: allowlist secret
```

## Client Configuration

Update your MCP client configuration to connect to the remote server:

### Claude Desktop / VS Code / Cursor

```json
{
  "mcpServers": {
    "cloudwatch-applicationsignals-remote": {
      "url": "http://your-ec2-public-ip:8000/sse",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer your-secret-key"
      }
    }
  }
}
```

**Note:** Replace `your-ec2-public-ip` with your actual EC2 public IP address or domain name.

## Authentication

The server supports simple pass-through authentication:

### Disabled Authentication (Default)

If `MCP_API_KEY` is not set, the server accepts all requests without authentication:

```bash
# No MCP_API_KEY set - authentication disabled
python3 -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server
```

### Simple Authentication

Set `MCP_API_KEY` to require authentication:

```bash
export MCP_API_KEY="your-secret-key"  # pragma: allowlist secret
python3 -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server
```

Clients must provide the key via:
- `Authorization: Bearer <key>` header, OR
- `X-API-Key: <key>` header

**Important:** This is a simple pass-through auth for development. For production:
1. Use HTTPS/TLS (not implemented in this basic version)
2. Implement proper token validation
3. Consider using AWS API Gateway with authentication
4. Use VPC and security groups to restrict access

## Monitoring and Logs

### View Server Logs

If running with nohup:
```bash
tail -f server.log
```

If running in foreground, logs appear in stderr.

### Check Server Process

```bash
ps aux | grep remote_server
```

### Monitor Resource Usage

```bash
top -p <PID>
```

## Troubleshooting

### Server won't start

1. Check if port is already in use:
   ```bash
   sudo lsof -i :8000
   ```

2. Verify AWS credentials:
   ```bash
   aws sts get-caller-identity
   ```

3. Check Python version:
   ```bash
   python3.11 --version  # Should be 3.10 or higher (3.11 recommended)
   # Or python3.10 --version on Ubuntu
   ```

   If you get "Python 3.9.x" or lower, you need to install Python 3.10+ (see installation section above)

### Connection refused

1. Verify security group allows inbound traffic on port 8000
2. Check if server is running:
   ```bash
   curl http://localhost:8000/health
   ```
3. Verify EC2 public IP is correct

### Authentication errors

1. Ensure client sends correct header format
2. Verify `MCP_API_KEY` matches between server and client
3. Check server logs for authentication messages

### AWS credential errors

1. Verify credentials are set correctly:
   ```bash
   echo $AWS_ACCESS_KEY_ID
   echo $AWS_REGION
   ```

2. Test AWS access:
   ```bash
   aws application-signals list-services --region us-east-1
   ```

3. Check IAM permissions include required actions

## Required IAM Permissions

The AWS credentials must have these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "application-signals:*",
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "logs:GetQueryResults",
        "logs:StartQuery",
        "logs:StopQuery",
        "logs:FilterLogEvents",
        "xray:GetTraceSummaries",
        "xray:BatchGetTraces",
        "synthetics:GetCanary",
        "synthetics:GetCanaryRuns",
        "s3:GetObject",
        "s3:ListBucket",
        "iam:GetRole",
        "iam:GetPolicy",
        "iam:GetPolicyVersion"
      ],
      "Resource": "*"
    }
  ]
}
```

## Production Considerations

For production deployments:

1. **Use HTTPS**: Put server behind NGINX or AWS ALB with TLS
2. **Proper Authentication**: Implement OAuth2, JWT, or AWS Cognito
3. **Monitoring**: Set up CloudWatch metrics and alarms
4. **High Availability**: Deploy multiple instances with load balancer
5. **Auto-scaling**: Use Auto Scaling Groups
6. **Logging**: Send logs to CloudWatch Logs
7. **Secrets Management**: Use AWS Secrets Manager for credentials
8. **VPC**: Deploy in private subnet with bastion host or VPN

## Next Steps

- Test all MCP tools to ensure they work correctly
- Set up monitoring and alerting
- Configure backups and disaster recovery
- Implement production-grade authentication
- Set up CI/CD pipeline for updates
