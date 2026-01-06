#!/bin/bash
# NLM MongoDB Docker Setup - Simplified
# Just starts MongoDB and creates the credentials file

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREDENTIALS_DIR="$HOME/.nlm"
CREDENTIALS_FILE="$CREDENTIALS_DIR/mongodb_credentials.env"

echo "=== NLM MongoDB Setup ==="

# Create credentials directory
mkdir -p "$CREDENTIALS_DIR"

# Create Tier 2 credentials file (simple - no auth for local dev)
cat > "$CREDENTIALS_FILE" << 'EOF'
# NLM MongoDB Credentials (Local Docker - No Auth)
MONGODB_CONNECTION_STRING="mongodb://localhost:27018/nlm_db"
EOF

echo "Created: $CREDENTIALS_FILE"

# Start MongoDB
cd "$SCRIPT_DIR"
docker compose up -d

echo ""
echo "MongoDB running on localhost:27018"
echo "Test: mongosh mongodb://localhost:27018/nlm_db"
