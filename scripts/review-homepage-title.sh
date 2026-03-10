#!/usr/bin/env bash
# review-homepage-title.sh
# Reviews worktrees for successful implementation of the homepage-title task.
#
# Usage:
#   ./review-homepage-title.sh [COUNT] [WORKER_PREFIX]
#
# Checks each worktree against the homepage-title.txt prompt criteria.

set -euo pipefail

COUNT="${1:-10}"
WORKER_PREFIX="${2:-drupal-test-worker}"
PARENT_DIR="/Users/kjmonahan/AgentTests"
BASE_REPO="$PARENT_DIR/drupal-test"

PASS="PASS"
FAIL="FAIL"
WARN="WARN"

# Counters
total_workers=0
fully_passing=0

check() {
  local label="$1"
  local result="$2"
  local detail="${3:-}"
  local color_pass="\033[0;32m"
  local color_fail="\033[0;31m"
  local color_warn="\033[0;33m"
  local color_reset="\033[0m"

  if [[ "$result" == "$PASS" ]]; then
    printf "  ${color_pass}[PASS]${color_reset} %s" "$label"
  elif [[ "$result" == "$WARN" ]]; then
    printf "  ${color_warn}[WARN]${color_reset} %s" "$label"
  else
    printf "  ${color_fail}[FAIL]${color_reset} %s" "$label"
  fi

  [[ -n "$detail" ]] && printf " (%s)" "$detail"
  printf "\n"
}

review_worktree() {
  local index="$1"
  local name
  name=$(printf "%s-%02d" "$WORKER_PREFIX" "$index")
  local wt="$PARENT_DIR/$name"

  if [[ ! -d "$wt" ]]; then
    return 0
  fi

  total_workers=$((total_workers + 1))
  local pass_count=0
  local fail_count=0
  local check_count=4

  echo ""
  echo "=========================================="
  echo "  $name"
  echo "=========================================="

  # ----------------------------------------------------------------
  # Collect custom PHP files (.module and .inc only — NOT .theme).
  # Hooks must live in .module or .inc files per the task requirements.
  # ----------------------------------------------------------------
  local php_files
  php_files=$(find \
    "$wt/web/modules/custom" \
    "$wt/web/themes/gesso" \
    \( -name "*.module" -o -name "*.inc" \) \
    2>/dev/null | grep -v node_modules | grep -v vendor | grep -v "\.test\." || true)

  # Also collect .theme files separately to check they DON'T contain the hooks
  local theme_files
  theme_files=$(find \
    "$wt/web/themes/gesso" \
    -name "*.theme" \
    2>/dev/null | grep -v node_modules || true)

  # ----------------------------------------------------------------
  # CHECK 1: hook_field_widget_complete_paragraphs_form_alter created
  # ----------------------------------------------------------------
  # This is the proper Drupal hook for altering paragraph widget forms.
  # Accept any function matching: <module>_field_widget_complete_paragraphs_form_alter
  local paragraphs_alter_file=""
  local paragraphs_alter_fn=""

  if [[ -n "$php_files" ]]; then
    while IFS= read -r f; do
      local match
      match=$(grep -n 'function .*_field_widget_complete_paragraphs_form_alter' "$f" 2>/dev/null | head -1 || true)
      if [[ -n "$match" ]]; then
        paragraphs_alter_file="$f"
        paragraphs_alter_fn=$(echo "$match" | grep -oE 'function [a-zA-Z_]+' | head -1 | sed 's/function //')
        break
      fi
    done <<< "$php_files"
  fi

  if [[ -n "$paragraphs_alter_file" ]]; then
    local rel_file
    rel_file=$(echo "$paragraphs_alter_file" | sed "s|$wt/||")
    check "hook_field_widget_complete_paragraphs_form_alter created" "$PASS" \
      "$paragraphs_alter_fn in $rel_file"
    pass_count=$((pass_count + 1))
  else
    check "hook_field_widget_complete_paragraphs_form_alter created" "$FAIL" \
      "no function matching *_field_widget_complete_paragraphs_form_alter found"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 2: hook_preprocess_node created/altered using field_is_homepage
  # ----------------------------------------------------------------
  # Look for a preprocess_node function that references field_is_homepage
  local preprocess_file=""
  local preprocess_fn=""

  if [[ -n "$php_files" ]]; then
    while IFS= read -r f; do
      # File must contain both a preprocess_node function AND field_is_homepage
      if grep -q 'function .*preprocess_node' "$f" 2>/dev/null && \
         grep -q 'field_is_homepage' "$f" 2>/dev/null; then
        preprocess_file="$f"
        preprocess_fn=$(grep -n 'function .*preprocess_node' "$f" 2>/dev/null | head -1 | \
          grep -oE 'function [a-zA-Z_]+' | head -1 | sed 's/function //')
        break
      fi
    done <<< "$php_files"
  fi

  if [[ -n "$preprocess_file" ]]; then
    local rel_file
    rel_file=$(echo "$preprocess_file" | sed "s|$wt/||")
    check "hook_preprocess_node uses field_is_homepage" "$PASS" \
      "$preprocess_fn in $rel_file"
    pass_count=$((pass_count + 1))
  else
    check "hook_preprocess_node uses field_is_homepage" "$FAIL" \
      "no preprocess_node function referencing field_is_homepage found"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 3: Hooks are NOT placed in a .theme file
  # ----------------------------------------------------------------
  local hooks_in_theme=""

  if [[ -n "$theme_files" ]]; then
    while IFS= read -r f; do
      local match
      match=$(grep -n '^function [a-zA-Z][a-zA-Z0-9_]*(' "$f" 2>/dev/null | \
        grep -vE '^[0-9]+:function _' | head -1 || true)
      if [[ -n "$match" ]]; then
        local fn_name
        fn_name=$(echo "$match" | grep -oE 'function [a-zA-Z][a-zA-Z0-9_]+' | head -1 | sed 's/function //')
        local rel_f
        rel_f=$(echo "$f" | sed "s|$wt/||")
        hooks_in_theme="$fn_name in $rel_f"
        break
      fi
    done <<< "$theme_files"
  fi

  if [[ -z "$hooks_in_theme" ]]; then
    check "Hooks not placed in .theme file" "$PASS"
    pass_count=$((pass_count + 1))
  else
    check "Hooks not placed in .theme file" "$FAIL" \
      "hook function found in .theme file: $hooks_in_theme"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 4: New/modified hooks have 'Implements hook_' docblock comment
  # ----------------------------------------------------------------
  # Only check functions that are new or modified relative to the base repo.
  # Strategy: diff each file against its base repo counterpart. Functions
  # appearing on added lines (+function ...) are new or moved/modified.
  # For files with no base counterpart, all functions are considered new.
  local hooks_without_comment=0
  local hooks_total=0
  local missing_comment_examples=""

  if [[ -n "$php_files" ]]; then
    while IFS= read -r f; do
      # Determine the corresponding base file path
      local rel_path
      rel_path=$(echo "$f" | sed "s|$wt/||")
      local base_file="$BASE_REPO/$rel_path"

      # Collect new/modified public function names in this file
      local new_fns=""
      if [[ ! -f "$base_file" ]]; then
        # Entirely new file — all public functions are new
        new_fns=$(grep -oE '^function [a-zA-Z][a-zA-Z0-9_]+' "$f" 2>/dev/null | sed 's/^function //' || true)
      else
        # Diff: extract function names that appear only on added lines
        new_fns=$(diff "$base_file" "$f" 2>/dev/null | \
          grep '^+' | grep -v '^+++' | \
          grep -oE '^[+]function [a-zA-Z][a-zA-Z0-9_]+' | \
          sed 's/^+function //' || true)
      fi

      [[ -z "$new_fns" ]] && continue

      # For each new/modified function, find its line number in the worktree
      # file and check for "Implements hook_" in the preceding 5 lines
      while IFS= read -r fn_name; do
        [[ -z "$fn_name" ]] && continue
        local lineno
        lineno=$(grep -n "^function ${fn_name}(" "$f" 2>/dev/null | head -1 | cut -d: -f1 || true)
        [[ -z "$lineno" ]] && continue

        hooks_total=$((hooks_total + 1))

        local start_line=$(( lineno > 5 ? lineno - 5 : 1 ))
        local context
        context=$(sed -n "${start_line},$((lineno - 1))p" "$f" 2>/dev/null || true)

        if ! echo "$context" | grep -qE 'Implements hook_'; then
          hooks_without_comment=$((hooks_without_comment + 1))
          if [[ -z "$missing_comment_examples" ]]; then
            local rel_f
            rel_f=$(echo "$f" | sed "s|$wt/||")
            missing_comment_examples="$fn_name in $rel_f (line $lineno)"
          fi
        fi
      done <<< "$new_fns"
    done <<< "$php_files"
  fi

  if [[ "$hooks_total" -eq 0 ]]; then
    check "New/modified hooks have 'Implements hook_' docblock" "$WARN" \
      "no new or modified public hook functions found to check"
    fail_count=$((fail_count + 1))
  elif [[ "$hooks_without_comment" -eq 0 ]]; then
    check "New/modified hooks have 'Implements hook_' docblock" "$PASS" \
      "$hooks_total hook(s) checked"
    pass_count=$((pass_count + 1))
  else
    check "New/modified hooks have 'Implements hook_' docblock" "$FAIL" \
      "$hooks_without_comment/$hooks_total hook(s) missing comment; e.g. $missing_comment_examples"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # Summary for this worker
  # ----------------------------------------------------------------
  echo ""
  echo "  Result: $pass_count/$check_count checks passed"

  if [[ "$fail_count" -eq 0 ]]; then
    fully_passing=$((fully_passing + 1))
    echo -e "  \033[0;32mFULLY PASSING\033[0m"
  else
    echo -e "  \033[0;31m$fail_count check(s) failed\033[0m"
  fi
}

# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
echo "Homepage Title Review"
echo "Prompt: homepage-title.txt"
echo "Workers: $WORKER_PREFIX-01 through $(printf "%s-%02d" "$WORKER_PREFIX" "$COUNT")"

for i in $(seq 1 "$COUNT"); do
  name=$(printf "%s-%02d" "$WORKER_PREFIX" "$i")
  if [[ -d "$PARENT_DIR/$name" ]]; then
    review_worktree "$i"
  fi
done

echo ""
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo "Total worktrees reviewed: $total_workers"
echo "Fully passing:            $fully_passing"
echo "Partial/failing:          $((total_workers - fully_passing))"
if [[ "$total_workers" -gt 0 ]]; then
  pct=$(( (fully_passing * 100) / total_workers ))
  echo "Success rate:             ${pct}%"
fi
echo ""
