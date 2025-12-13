#!/bin/bash
# Test script for CloudWatch Application Signals MCP Server (Streamable HTTP)

set -e

BASE_URL="${MCP_URL:-http://localhost:8080}"
API_KEY="${MCP_API_KEY:-your-test-key}"

echo "=================================================="
echo "MCP Server Connection Test"
echo "=================================================="
echo "Base URL: $BASE_URL"
echo "API Key: ${API_KEY:0:8}..."
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "-------------------"
curl -s "$BASE_URL/health" | python3 -m json.tool || echo "FAILED"
echo ""

# Test 2: Server Info
echo "Test 2: Server Info"
echo "-------------------"
curl -s "$BASE_URL/info" | python3 -m json.tool || echo "FAILED"
echo ""

# Test 3: SSE Connection (will timeout after 3 seconds)
echo "Test 3: SSE Connection (3 second sample)"
echo "-----------------------------------------"
echo "This should show 'endpoint' event and possibly 'message' events..."
timeout 3 curl -N -H "X-API-Key: $API_KEY" "$BASE_URL/mcp" 2>/dev/null || true
echo ""
echo ""

echo "=================================================="
echo "Tests Complete!"
echo "=================================================="
echo ""
echo "If all tests passed, your server is working correctly."
echo ""
echo "To configure an MCP client (like Claude Desktop), add this to your mcp.json:"
echo ""
echo '{'
echo '  "mcpServers": {'
echo '    "cloudwatch-applicationsignals-remote": {'
echo "      \"url\": \"$BASE_URL/mcp\","
echo '      "transport": "sse",'
echo '      "headers": {'
echo "        \"X-API-Key\": \"$API_KEY\""
echo '      }'
echo '    }'
echo '  }'
echo '}'
echo ""
