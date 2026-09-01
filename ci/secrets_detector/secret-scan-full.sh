#!/usr/bin/env bash
set -euo pipefail

command -v trufflehog >/dev/null 2>&1 || {
  echo "ERROR: trufflehog not installed — cannot scan history for secrets." >&2
  echo "Install: https://github.com/trufflesecurity/trufflehog#installation" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

trufflehog git "file://$(pwd)" \
  --no-verification --fail --no-update \
  --exclude-paths="$SCRIPT_DIR/secret-scan-exclude.txt"
