#!/bin/bash
# Test script to verify SSE stream sends endpoint event

echo "Starting MCP server..."
python3 -m awslabs.cloudwatch_applicationsignals_mcp_server.remote_server_streamable > /tmp/mcp_test.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 3

echo "Testing SSE stream (GET /mcp)..."
echo "Expected: endpoint event, then session event"
echo ""

# Use timeout to prevent hanging
timeout 5 curl -N -H "X-API-Key: your-test-key" http://localhost:8080/mcp 2>/dev/null | head -6

echo ""
echo ""
echo "Server log (last 10 lines):"
tail -10 /tmp/mcp_test.log

# Cleanup
kill $SERVER_PID 2>/dev/null
sleep 1
