#!/usr/bin/env bash
# session_tokens_all.sh
# Extracts session IDs from all agent log files and runs session_tokens.py for each.

set -euo pipefail

LOGS_DIR="${1:-/Users/kjmonahan/AgentTests/agent-logs}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -d "$LOGS_DIR" ]]; then
  echo "ERROR: Logs directory not found: $LOGS_DIR"
  exit 1
fi

shopt -s nullglob
logs=("$LOGS_DIR"/*.log)

if [[ ${#logs[@]} -eq 0 ]]; then
  echo "No .log files found in $LOGS_DIR"
  exit 1
fi

for logfile in "${logs[@]}"; do
  session_id=$(sed -n '1s/^\[session_id: \(.*\)\]$/\1/p' "$logfile")
  if [[ -z "$session_id" ]]; then
    echo "WARNING: No session ID found in $(basename "$logfile"), skipping."
    continue
  fi
  echo "=== $(basename "$logfile") ==="
  python3 "$SCRIPT_DIR/session_tokens.py" "$session_id"
  echo
done
