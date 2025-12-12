#!/bin/bash

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

# Generate self-signed SSL certificate for MCP server
# This script creates a self-signed certificate for development/testing

SSL_DIR="${SSL_DIR:-$HOME/ssl}"
DAYS="${CERT_DAYS:-365}"
EC2_DNS="${EC2_DNS:-localhost}"

echo "======================================"
echo "SSL Certificate Generator"
echo "======================================"
echo ""
echo "This script will generate a self-signed SSL certificate"
echo "for your MCP server."
echo ""
echo "Configuration:"
echo "  SSL Directory: $SSL_DIR"
echo "  Valid for: $DAYS days"
echo "  Domain/DNS: $EC2_DNS"
echo ""

# Create SSL directory
mkdir -p "$SSL_DIR"

# Generate private key and certificate
openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
  -keyout "$SSL_DIR/server.key" \
  -out "$SSL_DIR/server.crt" \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=$EC2_DNS" \
  -addext "subjectAltName=DNS:$EC2_DNS,DNS:localhost,IP:127.0.0.1"

# Set appropriate permissions
chmod 600 "$SSL_DIR/server.key"
chmod 644 "$SSL_DIR/server.crt"

echo ""
echo "======================================"
echo "SSL Certificate Generated!"
echo "======================================"
echo ""
echo "Files created:"
echo "  Private Key: $SSL_DIR/server.key"
echo "  Certificate: $SSL_DIR/server.crt"
echo ""
echo "To use with the MCP server:"
echo "  export SSL_KEYFILE=$SSL_DIR/server.key"
echo "  export SSL_CERTFILE=$SSL_DIR/server.crt"
echo ""
echo "Or place them in the default location:"
echo "  /home/ec2-user/ssl/server.key"
echo "  /home/ec2-user/ssl/server.crt"
echo ""
echo "Note: This is a self-signed certificate for development."
echo "Clients may show security warnings."
echo ""
