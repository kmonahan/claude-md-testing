#!/usr/bin/env bash
# teardown-worktrees.sh
# Stops ddev and removes worktrees created by setup-worktrees.sh.
#
# Usage:
#   ./teardown-worktrees.sh [COUNT] [WORKER_PREFIX]

set -euo pipefail

SOURCE_REPO="/Users/kjmonahan/AgentTests/drupal-test"
PARENT_DIR="/Users/kjmonahan/AgentTests"
COUNT="${1:-10}"
WORKER_PREFIX="${2:-drupal-test-worker}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

for i in $(seq 1 "$COUNT"); do
  name=$(printf "%s-%02d" "$WORKER_PREFIX" "$i")
  worktree_path="$PARENT_DIR/$name"
  branch_name="worker/$name"

  if [[ -d "$worktree_path" ]]; then
    log "[$name] Stopping ddev..."
    (cd "$worktree_path" && ddev stop --remove-data --omit-snapshot 2>/dev/null) || true

    log "[$name] Removing worktree..."
    git -C "$SOURCE_REPO" worktree remove --force "$worktree_path" 2>/dev/null || rm -rf "$worktree_path"

    log "[$name] Deleting branch $branch_name..."
    git -C "$SOURCE_REPO" branch -D "$branch_name" 2>/dev/null || true
  else
    log "[$name] Not found, skipping"
  fi
done

git -C "$SOURCE_REPO" worktree prune
log "Teardown complete."
