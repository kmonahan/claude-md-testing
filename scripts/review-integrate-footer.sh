#!/usr/bin/env bash
# review-integrate-footer.sh
# Reviews worktrees for successful integration of the global footer.
#
# Usage:
#   ./review-integrate-footer.sh [COUNT] [WORKER_PREFIX]
#
# Checks each worktree against the integrate-footer.txt prompt criteria.

set -euo pipefail

COUNT="${1:-10}"
WORKER_PREFIX="${2:-drupal-test-worker}"
PARENT_DIR="/Users/kjmonahan/AgentTests"
BASE_REPO="$PARENT_DIR/drupal-test"

GESSO_THEME="web/themes/gesso"
CONFIG_SYNC="config/sync"

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

  if [[ -n "$detail" ]]; then
    printf " (%s)" "$detail"
  fi
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
  local check_count=7

  echo ""
  echo "=========================================="
  echo "  $name"
  echo "=========================================="

  # ----------------------------------------------------------------
  # CHECK 1: Custom block type config added
  # ----------------------------------------------------------------
  # Look for block_content.type.*.yml in config/sync or gesso config dirs
  local block_type_file
  block_type_file=$(find "$wt/$CONFIG_SYNC" "$wt/$GESSO_THEME/config" \
    -name "block_content.type.*.yml" 2>/dev/null | head -1)

  if [[ -n "$block_type_file" ]]; then
    local type_id
    type_id=$(grep '^id: ' "$block_type_file" 2>/dev/null | head -1 | sed 's/^id: //' || true)
    check "Custom block type config added" "$PASS" "$(basename "$block_type_file") (id: $type_id)"
    pass_count=$((pass_count + 1))
  else
    check "Custom block type config added" "$FAIL" "no block_content.type.*.yml found in config/sync or theme config"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 2: menu-social.twig included or embedded in a twig file
  # ----------------------------------------------------------------
  local menu_social_refs
  menu_social_refs=$(find "$wt/$GESSO_THEME/templates" "$wt/$GESSO_THEME/source" \
    -name "*.twig" 2>/dev/null | \
    xargs grep -ln "menu-social" 2>/dev/null | \
    grep -v "menu-social\.twig$" | \
    grep -v node_modules | head -5 || true)

  if [[ -n "$menu_social_refs" ]]; then
    local ref_file
    ref_file=$(echo "$menu_social_refs" | head -1 | sed "s|$wt/||")
    check "menu-social.twig included/embedded" "$PASS" "referenced in $ref_file"
    pass_count=$((pass_count + 1))
  else
    check "menu-social.twig included/embedded" "$FAIL" "no include/embed of menu-social found in any twig file"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 3: Contact Us block in first footer slot
  # ----------------------------------------------------------------
  local footer_twig="$wt/$GESSO_THEME/templates/layout/region--footer.html.twig"
  local contact_in_first=false

  if [[ -f "$footer_twig" ]]; then
    # Extract the content between {% block first %} and {% endblock %}
    local first_block_content
    first_block_content=$(awk '/block first/{found=1} found{print} /endblock/{if(found){found=0}}' "$footer_twig" 2>/dev/null || true)

    # Check for contact block reference in first block
    if echo "$first_block_content" | grep -qiE "contact_us|contact-us|gesso_contact_us"; then
      contact_in_first=true
    fi
  fi

  # Also check for other twig files that might define footer slots
  if [[ "$contact_in_first" == false ]]; then
    local other_twigs
    other_twigs=$(find "$wt/$GESSO_THEME/templates" "$wt/$GESSO_THEME/source" \
      -name "*.twig" ! -name "footer.twig" ! -name "region--footer.html.twig" 2>/dev/null | head -20 || true)
    if [[ -n "$other_twigs" ]]; then
      while IFS= read -r f; do
        local first_block_content
        first_block_content=$(awk '/block first/{found=1} found{print} /endblock/{if(found){found=0}}' "$f" 2>/dev/null || true)
        if echo "$first_block_content" | grep -qiE "contact_us|contact-us|gesso_contact_us"; then
          contact_in_first=true
          break
        fi
      done <<< "$other_twigs"
    fi
  fi

  if [[ "$contact_in_first" == true ]]; then
    check "Contact Us block in first footer slot" "$PASS"
    pass_count=$((pass_count + 1))
  else
    check "Contact Us block in first footer slot" "$FAIL" "contact block not found in {% block first %}"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 4: Social links AND footer menu both in second footer slot
  # ----------------------------------------------------------------
  local social_in_second=false
  local menu_in_second=false

  if [[ -f "$footer_twig" ]]; then
    local second_block_content
    second_block_content=$(awk '/block second/{found=1} found{print} /endblock/{if(found){found=0}}' "$footer_twig" 2>/dev/null || true)

    if echo "$second_block_content" | grep -qiE "menu.social|menu-social|social"; then
      social_in_second=true
    fi
    if echo "$second_block_content" | grep -qiE "footer.*menu|gesso_footer|system_menu_block.*footer|footer.*block|menu.*footer"; then
      menu_in_second=true
    fi
  fi

  if [[ "$social_in_second" == true && "$menu_in_second" == true ]]; then
    check "Social links + footer menu in second slot" "$PASS"
    pass_count=$((pass_count + 1))
  elif [[ "$social_in_second" == true && "$menu_in_second" == false ]]; then
    check "Social links + footer menu in second slot" "$FAIL" "social found but footer menu missing from block second"
    fail_count=$((fail_count + 1))
  elif [[ "$social_in_second" == false && "$menu_in_second" == true ]]; then
    check "Social links + footer menu in second slot" "$FAIL" "footer menu found but social links missing from block second"
    fail_count=$((fail_count + 1))
  else
    check "Social links + footer menu in second slot" "$FAIL" "neither social links nor footer menu found in block second"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 5: Copyright in third footer slot
  # ----------------------------------------------------------------
  local copyright_in_third=false

  if [[ -f "$footer_twig" ]]; then
    local third_block_content
    third_block_content=$(awk '/block third/{found=1} found{print} /endblock/{if(found){found=0}}' "$footer_twig" 2>/dev/null || true)

    if echo "$third_block_content" | grep -qiE "copyright"; then
      copyright_in_third=true
    fi
  fi

  if [[ "$copyright_in_third" == true ]]; then
    check "Copyright in third footer slot" "$PASS"
    pass_count=$((pass_count + 1))
  else
    check "Copyright in third footer slot" "$FAIL" "copyright not found in {% block third %}"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 6: Copyright year is dynamic
  # ----------------------------------------------------------------
  # Look for dynamic year generation: date('Y'), date("Y"), 'date'|date('Y'),
  # current_year variable from preprocess, now|date, etc.
  local dynamic_year=false
  local year_detail=""

  # Check PHP preprocess hooks for dynamic year
  local php_files
  php_files=$(find "$wt/$GESSO_THEME" -name "*.php" -o -name "*.inc" -o -name "*.theme" 2>/dev/null | \
    grep -v node_modules | grep -v vendor | head -20 || true)

  if [[ -n "$php_files" ]]; then
    while IFS= read -r f; do
      if grep -qE "date\(['\"]Y['\"]|current_year|year.*date" "$f" 2>/dev/null; then
        dynamic_year=true
        year_detail="PHP dynamic year in $(basename "$f")"
        break
      fi
    done <<< "$php_files"
  fi

  # Check twig files for dynamic year (date filter, variable, etc.)
  if [[ "$dynamic_year" == false ]]; then
    local twig_year_refs
    twig_year_refs=$(grep -rn "current_year\|'now'|date\b.*Y\|now|date\b" \
      "$wt/$GESSO_THEME/templates" "$wt/$GESSO_THEME/source" 2>/dev/null | \
      grep -v node_modules | grep -i "year\|date" | head -5 || true)
    if [[ -n "$twig_year_refs" ]]; then
      dynamic_year=true
      year_detail="Twig dynamic year reference found"
    fi
  fi

  # Negative check: look for hardcoded 4-digit year like 2024, 2025, 2026
  local hardcoded_year
  hardcoded_year=$(grep -rn "202[0-9]\b" "$wt/$GESSO_THEME/templates" "$wt/$GESSO_THEME/source" \
    2>/dev/null | grep -v node_modules | grep -v "\.map" | \
    grep -iE "copyright|year" | head -3 || true)

  if [[ -n "$hardcoded_year" && "$dynamic_year" == false ]]; then
    check "Copyright year is dynamic" "$FAIL" "hardcoded year found"
    fail_count=$((fail_count + 1))
  elif [[ "$dynamic_year" == true ]]; then
    check "Copyright year is dynamic" "$PASS" "$year_detail"
    pass_count=$((pass_count + 1))
  else
    # No hardcoded year found, but also no explicit dynamic pattern detected
    # Could still be dynamic via variable passed from preprocess
    check "Copyright year is dynamic" "$WARN" "no explicit dynamic year pattern found; manual check recommended"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 7: footer.twig included or embedded somewhere
  # ----------------------------------------------------------------
  # The base region--footer.html.twig already embeds footer.twig, so we check
  # if it still does (wasn't removed) or if any other twig does.
  local footer_twig_refs
  footer_twig_refs=$(grep -rn "footer\.twig\|@layouts/footer\|embed.*footer\|include.*footer\.twig" \
    "$wt/$GESSO_THEME/templates" "$wt/$GESSO_THEME/source" 2>/dev/null | \
    grep -v "node_modules" | grep -v "\.map" | head -5 || true)

  if [[ -n "$footer_twig_refs" ]]; then
    local ref_file
    ref_file=$(echo "$footer_twig_refs" | head -1 | cut -d: -f1 | sed "s|$wt/||")
    check "footer.twig included/embedded" "$PASS" "in $ref_file"
    pass_count=$((pass_count + 1))
  else
    check "footer.twig included/embedded" "$FAIL" "no include/embed of footer.twig found"
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
echo "Footer Integration Review"
echo "Prompt: integrate-footer.txt"
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
