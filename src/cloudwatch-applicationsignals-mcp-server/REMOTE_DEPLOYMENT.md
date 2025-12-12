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
4. Security group allowing inbound traffic on port 443 (HTTPS)

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

## HTTPS/SSL Setup (Required for Remote MCP)

**IMPORTANT:** Remote MCP servers must use HTTPS. HTTP is only allowed for localhost connections.

### Option 1: Direct HTTPS with Self-Signed Certificate (Simplest - No Nginx Required)

This method uses your EC2's DNS name (e.g., `ec2-18-208-249-167.compute-1.amazonaws.com`) with a self-signed certificate.

#### Step 1: Generate SSL Certificate

```bash
# Using the provided script
cd /home/ec2-user/mcp/src/cloudwatch-applicationsignals-mcp-server
EC2_DNS="ec2-18-208-249-167.compute-1.amazonaws.com" ./generate-ssl-cert.sh

# Or manually:
mkdir -p ~/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ~/ssl/server.key \
  -out ~/ssl/server.crt \
  -subj "/C=US/ST=State/L=City/O=MyOrg/CN=ec2-18-208-249-167.compute-1.amazonaws.com" \
  -addext "subjectAltName=DNS:ec2-18-208-249-167.compute-1.amazonaws.com,DNS:localhost"

chmod 600 ~/ssl/server.key
chmod 644 ~/ssl/server.crt
```

#### Step 2: Start MCP Server with HTTPS

```bash
# Set environment variables
export AWS_REGION="us-east-1"
export MCP_PORT=443  # HTTPS default port (requires sudo) or use 8443
export MCP_HOST="0.0.0.0"
export SSL_KEYFILE="$HOME/ssl/server.key"
export SSL_CERTFILE="$HOME/ssl/server.crt"

# Start server (use sudo if port 443)
sudo -E python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server

# Or use port 8443 (no sudo required):
# export MCP_PORT=8443
# python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server
```

#### Step 3: Test HTTPS Connection

```bash
# From your local machine (will show certificate warning - this is expected)
curl -k https://ec2-18-208-249-167.compute-1.amazonaws.com/health

# Or with port 8443:
# curl -k https://ec2-18-208-249-167.compute-1.amazonaws.com:8443/health
```

**Note:** The `-k` flag tells curl to accept self-signed certificates. MCP clients may need similar configuration.

### Option 2: Using Nginx as Reverse Proxy with Let's Encrypt (Production)

#### Step 1: Install Nginx

**Amazon Linux 2023:**
```bash
sudo yum install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

**Ubuntu:**
```bash
sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

#### Step 2: Install Certbot for Let's Encrypt SSL

**Amazon Linux 2023:**
```bash
sudo yum install python3-certbot-nginx -y
```

**Ubuntu:**
```bash
sudo apt install certbot python3-certbot-nginx -y
```

#### Step 3: Obtain SSL Certificate

Replace `your-domain.com` with your actual domain name:

```bash
sudo certbot --nginx -d your-domain.com
```

Follow the prompts to:
- Enter your email address
- Agree to terms of service
- Choose whether to redirect HTTP to HTTPS (recommended: yes)

#### Step 4: Configure Nginx

Create Nginx configuration file:

```bash
sudo nano /etc/nginx/conf.d/mcp-server.conf
```

Add the following configuration:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL certificate paths (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Server info endpoint
    location /info {
        proxy_pass http://127.0.0.1:8000/info;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE endpoint for MCP
    location /sse {
        proxy_pass http://127.0.0.1:8000/sse;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Connection '';
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE specific settings
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        chunked_transfer_encoding off;
    }

    # Messages endpoint
    location /messages/ {
        proxy_pass http://127.0.0.1:8000/messages/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Step 5: Test and Reload Nginx

```bash
# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

#### Step 6: Start MCP Server (localhost only)

Since Nginx is handling HTTPS, the MCP server should bind to localhost:

```bash
export MCP_HOST="127.0.0.1"  # Bind to localhost only
export MCP_PORT=8000
export AWS_REGION="us-east-1"

# Start server
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server

# Or run in background:
nohup python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server > server.log 2>&1 &
```

### Option 2: Using Self-Signed Certificate (Development Only)

**Note:** Self-signed certificates are not recommended for production and may not work with all MCP clients.

```bash
# Generate self-signed certificate
sudo mkdir -p /etc/ssl/mcp
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/mcp/server.key \
  -out /etc/ssl/mcp/server.crt

# Follow Nginx setup above with self-signed cert paths
```

## Complete EC2 Setup Example with HTTPS (No Nginx)

Here's a complete step-by-step example using EC2 DNS name **ec2-18-208-249-167.compute-1.amazonaws.com**:

### On Your EC2 Instance

```bash
# 1. SSH to your EC2 instance
ssh -i your-key.pem ec2-user@18.208.249.167

# 2. Install Python 3.11 (Amazon Linux 2023)
sudo yum update -y
sudo yum install python3.11 python3.11-pip git openssl -y
python3.11 --version  # Verify: should show 3.11.x

# 3. Clone the repository
cd /home/ec2-user
git clone https://github.com/awslabs/mcp.git
cd mcp/src/cloudwatch-applicationsignals-mcp-server
git checkout rmt-server

# 4. Set up virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .

# 5. Generate self-signed SSL certificate
EC2_DNS="ec2-18-208-249-167.compute-1.amazonaws.com" ./generate-ssl-cert.sh

# This creates:
#   ~/ssl/server.key
#   ~/ssl/server.crt

# 6. Configure environment variables
export AWS_REGION="us-east-1"
export MCP_PORT=8443  # Use 8443 to avoid needing sudo (or use 443 with sudo)
export MCP_HOST="0.0.0.0"
export SSL_KEYFILE="$HOME/ssl/server.key"
export SSL_CERTFILE="$HOME/ssl/server.crt"

# If using explicit AWS credentials:
# export AWS_ACCESS_KEY_ID="your-access-key-id"  # pragma: allowlist secret
# export AWS_SECRET_ACCESS_KEY="your-secret-access-key"  # pragma: allowlist secret

# Or if using IAM role attached to EC2, no credentials needed!

# 7. Start the server
python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server

# Or run in background:
# nohup python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server > server.log 2>&1 &

# If using port 443 (requires sudo):
# sudo -E python -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server
```

### Test from Your Local Machine

```bash
# Test health endpoint over HTTPS (use -k to accept self-signed cert)
curl -k https://ec2-18-208-249-167.compute-1.amazonaws.com:8443/health

# Expected output:
# {
#   "status": "healthy",
#   "service": "cloudwatch-applicationsignals-mcp-server",
#   "version": "0.1.19",
#   "region": "us-east-1",
#   "transport": "sse"
# }

# Test server info
curl -k https://ec2-18-208-249-167.compute-1.amazonaws.com:8443/info
```

### Configure Your MCP Client

Update your Claude Desktop or other MCP client configuration:

```json
{
  "mcpServers": {
    "cloudwatch-appsignals-remote": {
      "url": "https://ec2-18-208-249-167.compute-1.amazonaws.com:8443/sse",
      "transport": "sse"
    }
  }
}
```

**Important Notes:**
- Replace the DNS name with your actual EC2 DNS
- MCP clients may need configuration to accept self-signed certificates
- For production, use a proper domain with Let's Encrypt (see Option 2 above)

## EC2 Security Group Configuration

Configure your EC2 security group to allow HTTPS traffic:

1. Go to EC2 Console → Security Groups
2. Select your instance's security group
3. Add inbound rule:
   - **For port 8443 (recommended):**
     - Type: Custom TCP
     - Port: 8443
     - Source: 0.0.0.0/0 (for public access) or specific IP ranges

   - **For port 443 (standard HTTPS):**
     - Type: HTTPS
     - Port: 443
     - Source: 0.0.0.0/0 (for public access) or specific IP ranges

**Security Notes:**
- Port 8443 doesn't require sudo to run the server
- Port 443 requires running the server with sudo
- For production, restrict source IPs to known client addresses

## Testing the Server

### 1. Health Check

From your local machine or another server:

```bash
curl https://your-domain.com/health
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
curl https://your-domain.com/info
```

### 3. Test with Authentication (if MCP_API_KEY is set)

```bash
curl -H "Authorization: Bearer your-secret-key" https://your-domain.com/info  # pragma: allowlist secret
```

Or using X-API-Key header:

```bash
curl -H "X-API-Key: your-secret-key" https://your-domain.com/info  # pragma: allowlist secret
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
