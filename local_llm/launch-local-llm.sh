#!/bin/bash
#
# NLM Local LLM Launcher for Claude Code
# Launches Claude Code CLI pointing to local llama.cpp server
#

SERVER_URL="http://127.0.0.1:8080"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if server is running
if ! curl -s --connect-timeout 2 "${SERVER_URL}/health" > /dev/null 2>&1; then
    echo "Error: llama.cpp server is not running at ${SERVER_URL}"
    echo ""
    echo "Start the server first in another terminal:"
    echo "  ${SCRIPT_DIR}/start-server.sh"
    echo ""
    exit 1
fi

echo "Server running at ${SERVER_URL}"
echo "Launching Claude Code with local LLM..."
echo ""

export ANTHROPIC_BASE_URL="${SERVER_URL}"
export ANTHROPIC_AUTH_TOKEN="dummy"
export ANTHROPIC_MODEL="local-model"

exec claude "$@"
