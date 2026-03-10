# CLAUDE.md Testing

Tests how Claude Code complete tasks with various AGENTS.md/CLAUDE.md configurations.

## Setup
Run `setup-worktrees.sh` to create multiple copies of a base Drupal repo, using git worktrees
and separate ddev names.

## Testing
Run `run-agents.sh` to pass the same prompt to all test instances.
```bash
bash run-agents.sh "$(cat ../prompts/homepage-title.txt)" 10
```

Run the appropriate python testing script (or create your own).

Run `session_tokens_all.sh` to compute the tokens used for each session (based on what's
in the `.jsonl` files, which does not always match Claude's usage meter).

## Teardown
Run `teardown-worktrees.sh` to clean up and remove the test instances.