#!/usr/bin/env bash
# run-agents.sh
# Runs a Claude Code agent in each worktree with the same prompt, in parallel.
#
# Usage:
#   ./run-agents.sh "Your prompt here" [COUNT] [WORKER_PREFIX]
#
# Requires: claude CLI (Claude Code) installed and authenticated
#
# Agents run concurrently, one per worktree. Output for each is written to
# logs/agent-NN.log so you can monitor them independently.

set -euo pipefail

PROMPT="${1:-}"
COUNT="${2:-10}"
WORKER_PREFIX="${3:-drupal-test-worker}"
PARENT_DIR="/Users/kjmonahan/AgentTests"
LOGS_DIR="$PARENT_DIR/agent-logs"

if [[ -z "$PROMPT" ]]; then
  echo "Usage: $0 \"<prompt>\" [COUNT] [WORKER_PREFIX]"
  echo "Example: $0 \"Add a blue border to the hero component\" 10"
  exit 1
fi

if ! command -v claude &>/dev/null; then
  echo "ERROR: 'claude' CLI not found. Install Claude Code and ensure it's in PATH."
  exit 1
fi

mkdir -p "$LOGS_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

run_agent() {
  local index="$1"
  local name
  name=$(printf "%s-%02d" "$WORKER_PREFIX" "$index")
  local worktree_path="$PARENT_DIR/$name"
  local logfile="$LOGS_DIR/$name.log"

  if [[ ! -d "$worktree_path" ]]; then
    echo "[$(date '+%H:%M:%S')] [$name] ERROR: worktree not found at $worktree_path" | tee "$logfile"
    return 1
  fi

  echo "[$(date '+%H:%M:%S')] [$name] Starting agent, logging to $logfile"

  # Run claude in the worktree directory with the prompt via stdin.
  # --print / -p runs non-interactively and exits after the response.
  # --output-format json gives us the session_id in the result envelope.
  (
    cd "$worktree_path"
    json_output=$(echo "$PROMPT" | claude --print \
      --output-format json \
      --allowedTools Edit,Read,Write,Bash,Glob,Grep)
    session_id=$(echo "$json_output" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id','unknown'))" 2>/dev/null || echo "unknown")
    echo "[session_id: $session_id]"
    echo "$json_output" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',''))" 2>/dev/null || echo "$json_output"
  ) >"$logfile" 2>&1

  local exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    echo "[$(date '+%H:%M:%S')] [$name] Agent completed successfully"
  else
    echo "[$(date '+%H:%M:%S')] [$name] Agent exited with code $exit_code (see $logfile)"
  fi
  return $exit_code
}

log "Launching $COUNT agents with prompt:"
log "  \"$PROMPT\""
log "Logs: $LOGS_DIR"
echo

PIDS=()
NAMES=()

for i in $(seq 1 "$COUNT"); do
  run_agent "$i" &
  PIDS+=($!)
  NAMES+=("$(printf "%s-%02d" "$WORKER_PREFIX" "$i")")
done

log "All $COUNT agents launched. Waiting for completion..."

FAILED=()
for i in "${!PIDS[@]}"; do
  pid="${PIDS[$i]}"
  name="${NAMES[$i]}"
  if wait "$pid"; then
    log "[$name] Done"
  else
    log "[$name] FAILED (exit code: $?)"
    FAILED+=("$name")
  fi
done

echo
if [[ ${#FAILED[@]} -gt 0 ]]; then
  log "Agents that failed: ${FAILED[*]}"
  log "Check logs in $LOGS_DIR"
  exit 1
fi

log "All $COUNT agents completed successfully."
log "Results are committed to each worktree's branch."
