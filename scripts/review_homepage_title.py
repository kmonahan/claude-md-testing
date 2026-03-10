#!/usr/bin/env python3
"""
Reviews worktrees for successful implementation of the homepage-title task.

Usage:
  python3 review_homepage_title.py [COUNT] [WORKER_PREFIX]

Checks each worktree against the homepage-title.txt prompt criteria.
"""

import argparse
import difflib
import re
import sys
from pathlib import Path


PARENT_DIR = Path("/Users/kjmonahan/AgentTests")
BASE_REPO = PARENT_DIR / "drupal-test"

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[0;33m"
RESET = "\033[0m"


def check(label: str, result: str, detail: str = "") -> None:
    if result == "PASS":
        tag = f"{GREEN}[PASS]{RESET}"
    elif result == "WARN":
        tag = f"{YELLOW}[WARN]{RESET}"
    else:
        tag = f"{RED}[FAIL]{RESET}"
    line = f"  {tag} {label}"
    if detail:
        line += f" ({detail})"
    print(line)


def collect_php_files(wt: Path) -> list[Path]:
    """Collect .module and .inc files from custom modules and gesso theme."""
    results: list[Path] = []
    search_roots = [
        wt / "web" / "modules" / "custom",
        wt / "web" / "themes" / "gesso",
    ]
    for root in search_roots:
        if not root.is_dir():
            continue
        for ext in ("*.module", "*.inc"):
            for f in root.rglob(ext):
                parts = f.parts
                if "node_modules" in parts or "vendor" in parts:
                    continue
                if ".test." in f.name:
                    continue
                results.append(f)
    return results


def collect_theme_files(wt: Path) -> list[Path]:
    """Collect .theme files from the gesso theme directory."""
    results: list[Path] = []
    theme_root = wt / "web" / "themes" / "gesso"
    if theme_root.is_dir():
        for f in theme_root.rglob("*.theme"):
            if "node_modules" not in f.parts:
                results.append(f)
    return results


def review_worktree(index: int, worker_prefix: str) -> bool:
    """Review a single worktree. Returns True if fully passing."""
    name = f"{worker_prefix}-{index:02d}"
    wt = PARENT_DIR / name

    if not wt.is_dir():
        return False

    pass_count = 0
    fail_count = 0
    check_count = 4

    print()
    print("==========================================")
    print(f"  {name}")
    print("==========================================")

    php_files = collect_php_files(wt)
    theme_files = collect_theme_files(wt)

    # ------------------------------------------------------------------
    # CHECK 1: hook_field_widget_complete_paragraphs_form_alter created
    # ------------------------------------------------------------------
    paragraphs_alter_file: Path | None = None
    paragraphs_alter_fn = ""

    for f in php_files:
        content = f.read_text(errors="replace")
        for line in content.splitlines():
            m = re.search(r'function (\w+_field_widget_complete_paragraphs_form_alter)', line)
            if m:
                paragraphs_alter_file = f
                paragraphs_alter_fn = m.group(1)
                break
        if paragraphs_alter_file:
            break

    if paragraphs_alter_file:
        rel_file = paragraphs_alter_file.relative_to(wt)
        check("hook_field_widget_complete_paragraphs_form_alter created", "PASS",
              f"{paragraphs_alter_fn} in {rel_file}")
        pass_count += 1
    else:
        check("hook_field_widget_complete_paragraphs_form_alter created", "FAIL",
              "no function matching *_field_widget_complete_paragraphs_form_alter found")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 2: hook_preprocess_node created/altered using field_is_homepage
    # ------------------------------------------------------------------
    preprocess_file: Path | None = None
    preprocess_fn = ""

    for f in php_files:
        content = f.read_text(errors="replace")
        if re.search(r'function \w+preprocess_node', content) and "field_is_homepage" in content:
            preprocess_file = f
            for line in content.splitlines():
                m = re.search(r'function (\w*preprocess_node\w*)', line)
                if m:
                    preprocess_fn = m.group(1)
                    break
            break

    if preprocess_file:
        rel_file = preprocess_file.relative_to(wt)
        check("hook_preprocess_node uses field_is_homepage", "PASS",
              f"{preprocess_fn} in {rel_file}")
        pass_count += 1
    else:
        check("hook_preprocess_node uses field_is_homepage", "FAIL",
              "no preprocess_node function referencing field_is_homepage found")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 3: Hooks are NOT placed in a .theme file
    # ------------------------------------------------------------------
    hooks_in_theme = ""

    for f in theme_files:
        content = f.read_text(errors="replace")
        for line in content.splitlines():
            m = re.match(r'^function ([a-zA-Z][a-zA-Z0-9_]*)\(', line)
            if m and not m.group(1).startswith("_"):
                rel_f = f.relative_to(wt)
                hooks_in_theme = f"{m.group(1)} in {rel_f}"
                break
        if hooks_in_theme:
            break

    if not hooks_in_theme:
        check("Hooks not placed in .theme file", "PASS")
        pass_count += 1
    else:
        check("Hooks not placed in .theme file", "FAIL",
              f"hook function found in .theme file: {hooks_in_theme}")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 4: New/modified hooks have 'Implements hook_' docblock comment
    # ------------------------------------------------------------------
    hooks_without_comment = 0
    hooks_total = 0
    missing_comment_example = ""

    for f in php_files:
        rel_path = f.relative_to(wt)
        base_file = BASE_REPO / rel_path
        content = f.read_text(errors="replace")
        lines = content.splitlines()

        new_fns: list[str] = []
        if not base_file.is_file():
            # Entirely new file — all public functions are new
            for line in lines:
                m = re.match(r'^function ([a-zA-Z][a-zA-Z0-9_]+)', line)
                if m:
                    new_fns.append(m.group(1))
        else:
            # Diff: extract function names on added lines only
            base_lines = base_file.read_text(errors="replace").splitlines()
            diff = list(difflib.unified_diff(base_lines, lines, lineterm=""))
            for diff_line in diff:
                if diff_line.startswith("+") and not diff_line.startswith("+++"):
                    m = re.match(r'^\+function ([a-zA-Z][a-zA-Z0-9_]+)', diff_line)
                    if m:
                        new_fns.append(m.group(1))

        for fn_name in new_fns:
            if not fn_name:
                continue
            # Find line number of this function definition
            lineno = None
            for i, line in enumerate(lines, 1):
                if re.match(rf'^function {re.escape(fn_name)}\(', line):
                    lineno = i
                    break
            if lineno is None:
                continue

            hooks_total += 1
            start = max(0, lineno - 6)
            context_lines = lines[start:lineno - 1]
            context = "\n".join(context_lines)

            if not re.search(r'Implements hook_', context):
                hooks_without_comment += 1
                if not missing_comment_example:
                    rel_f = f.relative_to(wt)
                    missing_comment_example = f"{fn_name} in {rel_f} (line {lineno})"

    if hooks_total == 0:
        check("New/modified hooks have 'Implements hook_' docblock", "WARN",
              "no new or modified public hook functions found to check")
        fail_count += 1
    elif hooks_without_comment == 0:
        check("New/modified hooks have 'Implements hook_' docblock", "PASS",
              f"{hooks_total} hook(s) checked")
        pass_count += 1
    else:
        check("New/modified hooks have 'Implements hook_' docblock", "FAIL",
              f"{hooks_without_comment}/{hooks_total} hook(s) missing comment; "
              f"e.g. {missing_comment_example}")
        fail_count += 1

    # ------------------------------------------------------------------
    # Summary for this worker
    # ------------------------------------------------------------------
    print()
    print(f"  Result: {pass_count}/{check_count} checks passed")

    if fail_count == 0:
        print(f"  {GREEN}FULLY PASSING{RESET}")
        return True
    else:
        print(f"  {RED}{fail_count} check(s) failed{RESET}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review worktrees for homepage title task implementation."
    )
    parser.add_argument("count", nargs="?", type=int, default=10,
                        help="Number of workers to check (default: 10)")
    parser.add_argument("worker_prefix", nargs="?", default="drupal-test-worker",
                        help="Worker directory prefix (default: drupal-test-worker)")
    args = parser.parse_args()

    print("Homepage Title Review")
    print("Prompt: homepage-title.txt")
    print(f"Workers: {args.worker_prefix}-01 through {args.worker_prefix}-{args.count:02d}")

    total_workers = 0
    fully_passing = 0

    for i in range(1, args.count + 1):
        name = f"{args.worker_prefix}-{i:02d}"
        if (PARENT_DIR / name).is_dir():
            total_workers += 1
            if review_worktree(i, args.worker_prefix):
                fully_passing += 1

    print()
    print("==========================================")
    print("SUMMARY")
    print("==========================================")
    print(f"Total worktrees reviewed: {total_workers}")
    print(f"Fully passing:            {fully_passing}")
    print(f"Partial/failing:          {total_workers - fully_passing}")
    if total_workers > 0:
        pct = (fully_passing * 100) // total_workers
        print(f"Success rate:             {pct}%")
    print()


if __name__ == "__main__":
    main()
