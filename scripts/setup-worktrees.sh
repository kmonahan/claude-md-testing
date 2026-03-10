#!/usr/bin/env bash
# setup-worktrees.sh
# Creates N git worktrees from drupal-test, each with a unique ddev name,
# .env file, composer install, and theme build.
#
# Usage:
#   ./setup-worktrees.sh [COUNT] [BASE_BRANCH]
#
# Defaults:
#   COUNT=10
#   BASE_BRANCH=main
#
# Each worktree is created at ../drupal-test-worker-NN (sibling of drupal-test)
# and named ddev project "drupal-test-worker-NN".

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO="/Users/kjmonahan/AgentTests/drupal-test"
PARENT_DIR="/Users/kjmonahan/AgentTests"
COUNT="${1:-10}"
BASE_BRANCH="${2:-main}"
WORKER_PREFIX="drupal-test-worker"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
err() { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; }

setup_worktree() {
  local index="$1"
  local name
  name=$(printf "%s-%02d" "$WORKER_PREFIX" "$index")
  local worktree_path="$PARENT_DIR/$name"
  local branch_name="worker/$name"

  log "[$name] Setting up worktree at $worktree_path"

  # ── 1. Create git worktree ──────────────────────────────────────────────────
  if [[ -d "$worktree_path" ]]; then
    log "[$name] Directory already exists, skipping git worktree add"
  else
    git -C "$SOURCE_REPO" worktree add -b "$branch_name" "$worktree_path" "$BASE_BRANCH"
    log "[$name] Worktree created on branch $branch_name"
  fi

  # ── 2. Patch ddev config.yaml with unique project name ──────────────────────
  local ddev_config="$worktree_path/.ddev/config.yaml"
  if [[ ! -f "$ddev_config" ]]; then
    err "[$name] .ddev/config.yaml not found"
    return 1
  fi
  # Replace the name: line (only the first occurrence, the active setting)
  sed -i '' "s/^name: .*/name: $name/" "$ddev_config"
  log "[$name] ddev project name set to '$name'"

  # ── 3. Copy .env file ───────────────────────────────────────────────────────
  if [[ ! -f "$worktree_path/.env" ]]; then
    if [[ -f "$SOURCE_REPO/.env" ]]; then
      cp "$SOURCE_REPO/.env" "$worktree_path/.env"
      log "[$name] .env copied from source"
    elif [[ -f "$SOURCE_REPO/.env.example" ]]; then
      cp "$SOURCE_REPO/.env.example" "$worktree_path/.env"
      log "[$name] .env created from .env.example"
    else
      err "[$name] No .env or .env.example found in source repo"
      return 1
    fi
  else
    log "[$name] .env already exists, skipping"
  fi

  # ── 4-7. Run ddev commands from within the worktree directory ─────────────────
  cd "$worktree_path"

  log "[$name] Starting ddev..."
  ddev start -y 2>&1 | sed "s/^/[$name] /" || {
    err "[$name] ddev start failed"
    return 1
  }

  # ── 5. Composer install ─────────────────────────────────────────────────────
  log "[$name] Running composer install..."
  ddev composer install --no-interaction 2>&1 | sed "s/^/[$name] /" || {
    err "[$name] composer install failed"
    return 1
  }

  # ── 6. Theme build ──────────────────────────────────────────────────────────
  log "[$name] Installing theme dependencies..."
  ddev gesso install 2>&1 | sed "s/^/[$name] /" || {
    err "[$name] gesso install failed"
    return 1
  }

  log "[$name] Building theme..."
  ddev gesso build 2>&1 | sed "s/^/[$name] /" || {
    err "[$name] gesso build failed"
    return 1
  }

  # ── 7. Site install ──────────────────────────────────────────────────────────
  log "[$name] Installing the site..."
  ddev drush si --existing-config 2>&1 | sed "s/^/[$name] /" || {
    err "[$name] site install failed"
    return 1
  }

  log "[$name] Setup complete. Site available at https://$name.ddev.site"

}

# ── Main ──────────────────────────────────────────────────────────────────────
log "Setting up $COUNT worktrees from $SOURCE_REPO (branch: $BASE_BRANCH)"
log "Worktrees will be created in $PARENT_DIR"

FAILED=()
for i in $(seq 1 "$COUNT"); do
  # Run sequentially to avoid ddev race conditions during router setup.
  # Swap the next two lines to run in parallel (at your own risk):
  #   setup_worktree "$i" &
  if ! (setup_worktree "$i"); then
    FAILED+=("$i")
  fi
done

# wait  # Uncomment if running in parallel

if [[ ${#FAILED[@]} -gt 0 ]]; then
  err "The following workers failed to set up: ${FAILED[*]}"
  exit 1
fi

log "All $COUNT worktrees ready."
