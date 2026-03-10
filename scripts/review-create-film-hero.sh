#!/usr/bin/env bash
# review-create-film-hero.sh
# Reviews worktrees for successful creation of the film detail hero component.
#
# Usage:
#   ./review-create-film-hero.sh [COUNT] [WORKER_PREFIX]
#
# Checks each worktree against the create-film-hero.txt prompt criteria.

set -euo pipefail

COUNT="${1:-10}"
WORKER_PREFIX="${2:-drupal-test-worker}"
PARENT_DIR="/Users/kjmonahan/AgentTests"
BASE_REPO="$PARENT_DIR/drupal-test"

GESSO_THEME="web/themes/gesso"
BASE_LIBRARIES="$BASE_REPO/$GESSO_THEME/gesso.libraries.yml"
COMPONENTS_DIR="$GESSO_THEME/source/03-components"

PASS="PASS"
FAIL="FAIL"
WARN="WARN"

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
  local check_count=9

  echo ""
  echo "=========================================="
  echo "  $name"
  echo "=========================================="

  # ----------------------------------------------------------------
  # Find the new component directory (any dir added under 03-components
  # that isn't in the base repo)
  # ----------------------------------------------------------------
  local comp_dir=""
  local comp_name=""
  while IFS= read -r d; do
    local bname
    bname=$(basename "$d")
    if [[ ! -d "$BASE_REPO/$COMPONENTS_DIR/$bname" ]]; then
      comp_dir="$d"
      comp_name="$bname"
      break
    fi
  done < <(find "$wt/$COMPONENTS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

  if [[ -z "$comp_dir" ]]; then
    echo "  ERROR: No new component directory found under $COMPONENTS_DIR"
    echo "  Skipping all checks."
    fail_count=$check_count
    echo ""
    echo "  Result: 0/$check_count checks passed"
    echo -e "  \033[0;31m${fail_count} check(s) failed\033[0m"
    return 0
  fi

  echo "  Component found: $comp_name"
  echo ""

  # Locate key files
  local scss_file twig_file yml_file stories_file
  scss_file=$(find "$comp_dir" -maxdepth 1 -name "*.scss" ! -name "_*.scss" 2>/dev/null | head -1)
  twig_file=$(find "$comp_dir" -maxdepth 1 -name "*.twig" 2>/dev/null | head -1)
  yml_file=$(find "$comp_dir" -maxdepth 1 -name "*.yml" 2>/dev/null | head -1)
  stories_file=$(find "$comp_dir" -maxdepth 1 -name "*.stories.jsx" 2>/dev/null | head -1)

  # ----------------------------------------------------------------
  # CHECK 1: SCSS file exists and does not start with `_`
  # ----------------------------------------------------------------
  local any_scss
  any_scss=$(find "$comp_dir" -maxdepth 1 -name "*.scss" 2>/dev/null | head -1)
  local underscore_scss
  underscore_scss=$(find "$comp_dir" -maxdepth 1 -name "_*.scss" 2>/dev/null | head -1)

  if [[ -n "$scss_file" ]]; then
    check "SCSS file created, does not start with _" "$PASS" "$(basename "$scss_file")"
    pass_count=$((pass_count + 1))
  elif [[ -n "$underscore_scss" ]]; then
    check "SCSS file created, does not start with _" "$FAIL" "$(basename "$underscore_scss") starts with underscore"
    fail_count=$((fail_count + 1))
  else
    check "SCSS file created, does not start with _" "$FAIL" "no .scss file found in component directory"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 2: attach_library appears in the Twig template
  # ----------------------------------------------------------------
  if [[ -n "$twig_file" ]] && grep -q "attach_library" "$twig_file" 2>/dev/null; then
    check "attach_library in Twig template" "$PASS"
    pass_count=$((pass_count + 1))
  else
    check "attach_library in Twig template" "$FAIL" "attach_library not found in $(basename "${twig_file:-twig}")"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 3: New library entry added to gesso.libraries.yml
  # ----------------------------------------------------------------
  local libraries_file="$wt/$GESSO_THEME/gesso.libraries.yml"
  local new_library_found=false

  if [[ -f "$libraries_file" ]]; then
    # Check if any library key in the worker's file is absent from the base
    while IFS= read -r key; do
      key="${key%%:*}"
      key="${key#"${key%%[![:space:]]*}"}"  # ltrim
      if [[ -n "$key" ]] && ! grep -q "^${key}:" "$BASE_LIBRARIES" 2>/dev/null; then
        new_library_found=true
        break
      fi
    done < <(grep -E '^[a-zA-Z][a-zA-Z0-9_-]+:' "$libraries_file" 2>/dev/null || true)
  fi

  if [[ "$new_library_found" == true ]]; then
    check "New library entry in gesso.libraries.yml" "$PASS"
    pass_count=$((pass_count + 1))
  else
    check "New library entry in gesso.libraries.yml" "$FAIL" "no new top-level library key found"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 4: CSS class names start with c-
  # ----------------------------------------------------------------
  local bad_classes=""
  if [[ -n "$scss_file" ]]; then
    # Find class selectors that don't start with c- (ignore pseudo, BEM modifiers, state classes)
    # Look for lines like .something { where something doesn't start with c-
    bad_classes=$(grep -oE '\.[a-zA-Z][a-zA-Z0-9_-]*' "$scss_file" 2>/dev/null | \
      grep -v '^\.' | grep -v '^$' || true)
    bad_classes=$(grep -E '^\.[a-zA-Z]' "$scss_file" 2>/dev/null | \
      grep -oE '\.[a-zA-Z][a-zA-Z0-9_-]*' | \
      grep -v '^\.c-' | \
      grep -v '^\.has-' | \
      grep -v '^\.is-' | \
      grep -v '^\.js-' | \
      head -3 || true)
  fi

  if [[ -z "$bad_classes" ]]; then
    check "CSS class names start with c-" "$PASS"
    pass_count=$((pass_count + 1))
  else
    local example
    example=$(echo "$bad_classes" | head -1)
    check "CSS class names start with c-" "$FAIL" "found class not starting with c-: $example"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 5: CSS logical properties used instead of directional
  # ----------------------------------------------------------------
  # Directional properties: top, bottom, left, right as standalone CSS properties
  # (not inside e.g. border-top-left-radius, padding-top etc — those are also bad
  # but we check specifically for the property declarations)
  local directional_props=""
  if [[ -n "$scss_file" ]]; then
    # Match lines where top/bottom/left/right appear as a CSS property (colon follows)
    # Exclude: comments, selectors, values (e.g. "to bottom" in gradients, "center top")
    # Pattern: line that has ^[space]*(top|bottom|left|right)[space]*:
    directional_props=$(grep -nE '^\s*(top|bottom|left|right)\s*:' "$scss_file" 2>/dev/null | \
      grep -v '^\s*//' | head -3 || true)

    # Also check for directional margin/padding (margin-top, padding-left, etc.)
    local directional_longhand
    directional_longhand=$(grep -nE '^\s*(margin|padding)-(top|bottom|left|right)\s*:' "$scss_file" 2>/dev/null | \
      grep -v '^\s*//' | head -3 || true)

    if [[ -n "$directional_longhand" ]]; then
      directional_props="$directional_props"$'\n'"$directional_longhand"
      directional_props="${directional_props#$'\n'}"
    fi
  fi

  if [[ -z "$directional_props" ]]; then
    check "CSS logical properties used (no directional)" "$PASS"
    pass_count=$((pass_count + 1))
  else
    local example
    example=$(echo "$directional_props" | head -1 | sed 's/^[[:space:]]*//')
    check "CSS logical properties used (no directional)" "$FAIL" "directional property found: $example"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 6: gesso-spacing() and gesso-font-size() are used
  # gesso-font-size() may be omitted if display-text-style() is used,
  # since that mixin handles font sizing internally.
  # ----------------------------------------------------------------
  local has_spacing=false has_font_size=false has_display_text_style=false
  if [[ -n "$scss_file" ]]; then
    grep -q "gesso-spacing(" "$scss_file" 2>/dev/null && has_spacing=true
    grep -q "gesso-font-size(" "$scss_file" 2>/dev/null && has_font_size=true
    grep -q "display-text-style(" "$scss_file" 2>/dev/null && has_display_text_style=true
  fi

  local font_size_satisfied=false
  [[ "$has_font_size" == true || "$has_display_text_style" == true ]] && font_size_satisfied=true

  if [[ "$has_spacing" == true && "$font_size_satisfied" == true ]]; then
    if [[ "$has_font_size" == true ]]; then
      check "gesso-spacing() and gesso-font-size() used" "$PASS"
    else
      check "gesso-spacing() and gesso-font-size() used" "$PASS" "gesso-font-size() substituted by display-text-style()"
    fi
    pass_count=$((pass_count + 1))
  elif [[ "$has_spacing" == true && "$font_size_satisfied" == false ]]; then
    check "gesso-spacing() and gesso-font-size() used" "$FAIL" "gesso-spacing() found but gesso-font-size() and display-text-style() both missing"
    fail_count=$((fail_count + 1))
  elif [[ "$has_spacing" == false && "$font_size_satisfied" == true ]]; then
    check "gesso-spacing() and gesso-font-size() used" "$FAIL" "gesso-font-size()/display-text-style() found but gesso-spacing() missing"
    fail_count=$((fail_count + 1))
  else
    check "gesso-spacing() and gesso-font-size() used" "$FAIL" "none of gesso-spacing(), gesso-font-size(), or display-text-style() found"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 7: No bare px values (any px must be inside rem())
  # ----------------------------------------------------------------
  local bare_px=""
  if [[ -n "$scss_file" ]]; then
    # Find px values NOT preceded by rem( — i.e., not wrapped in rem()
    # Strategy: find all px occurrences, filter out those that are part of rem(...)
    # We do a line-by-line check: if the line has Npx but NOT rem(Npx), flag it
    bare_px=$(grep -n '[0-9]px' "$scss_file" 2>/dev/null | \
      grep -v '^\s*//' | \
      grep -vE 'rem\([^)]*[0-9]px' | \
      grep -vE '@[a-z]' | \
      head -3 || true)
  fi

  if [[ -z "$bare_px" ]]; then
    check "No bare px values (or px wrapped in rem())" "$PASS"
    pass_count=$((pass_count + 1))
  else
    local example
    example=$(echo "$bare_px" | head -1 | sed 's/^[[:space:]]*//')
    check "No bare px values (or px wrapped in rem())" "$FAIL" "bare px found: $example"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 8: YAML file created
  # ----------------------------------------------------------------
  if [[ -n "$yml_file" ]]; then
    check "YAML (.yml) file created" "$PASS" "$(basename "$yml_file")"
    pass_count=$((pass_count + 1))
  else
    check "YAML (.yml) file created" "$FAIL" "no .yml file found in component directory"
    fail_count=$((fail_count + 1))
  fi

  # ----------------------------------------------------------------
  # CHECK 9: .stories.jsx file created and imports twig and yaml
  # ----------------------------------------------------------------
  if [[ -z "$stories_file" ]]; then
    check ".stories.jsx created, imports twig + yaml" "$FAIL" "no .stories.jsx file found"
    fail_count=$((fail_count + 1))
  else
    local imports_twig=false imports_yml=false
    grep -qE "import.*\.twig" "$stories_file" 2>/dev/null && imports_twig=true
    grep -qE "import.*\.yml" "$stories_file" 2>/dev/null && imports_yml=true

    if [[ "$imports_twig" == true && "$imports_yml" == true ]]; then
      check ".stories.jsx created, imports twig + yaml" "$PASS" "$(basename "$stories_file")"
      pass_count=$((pass_count + 1))
    elif [[ "$imports_twig" == false && "$imports_yml" == true ]]; then
      check ".stories.jsx created, imports twig + yaml" "$FAIL" "missing import of .twig file"
      fail_count=$((fail_count + 1))
    elif [[ "$imports_twig" == true && "$imports_yml" == false ]]; then
      check ".stories.jsx created, imports twig + yaml" "$FAIL" "missing import of .yml file"
      fail_count=$((fail_count + 1))
    else
      check ".stories.jsx created, imports twig + yaml" "$FAIL" "missing imports for both .twig and .yml"
      fail_count=$((fail_count + 1))
    fi
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
echo "Film Hero Component Review"
echo "Prompt: create-film-hero.txt"
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
