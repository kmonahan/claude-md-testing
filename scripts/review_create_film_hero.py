#!/usr/bin/env python3
"""
Reviews worktrees for successful creation of the film detail hero component.

Usage:
  python3 review_create_film_hero.py [COUNT] [WORKER_PREFIX]

Checks each worktree against the create-film-hero.txt prompt criteria.
"""

import argparse
import re
import sys
from pathlib import Path


PARENT_DIR = Path("/Users/kjmonahan/AgentTests")
BASE_REPO = PARENT_DIR / "drupal-test"
GESSO_THEME = "web/themes/gesso"
COMPONENTS_DIR = f"{GESSO_THEME}/source/03-components"
BASE_LIBRARIES = BASE_REPO / GESSO_THEME / "gesso.libraries.yml"

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


def review_worktree(index: int, worker_prefix: str) -> bool:
    """Review a single worktree. Returns True if fully passing."""
    name = f"{worker_prefix}-{index:02d}"
    wt = PARENT_DIR / name

    if not wt.is_dir():
        return False

    pass_count = 0
    fail_count = 0
    check_count = 9

    print()
    print("==========================================")
    print(f"  {name}")
    print("==========================================")

    # ------------------------------------------------------------------
    # Find the new component directory (any dir added under 03-components
    # that isn't in the base repo)
    # ------------------------------------------------------------------
    comp_dir: Path | None = None
    comp_name = ""
    components_path = wt / COMPONENTS_DIR
    base_components_path = BASE_REPO / COMPONENTS_DIR

    if components_path.is_dir():
        for d in sorted(components_path.iterdir()):
            if d.is_dir() and not (base_components_path / d.name).is_dir():
                comp_dir = d
                comp_name = d.name
                break

    if comp_dir is None:
        print(f"  ERROR: No new component directory found under {COMPONENTS_DIR}")
        print("  Skipping all checks.")
        print()
        print(f"  Result: 0/{check_count} checks passed")
        print(f"  {RED}{check_count} check(s) failed{RESET}")
        return False

    print(f"  Component found: {comp_name}")
    print()

    # Locate key files
    scss_files = [f for f in comp_dir.glob("*.scss") if not f.name.startswith("_")]
    underscore_scss = list(comp_dir.glob("_*.scss"))
    twig_files = list(comp_dir.glob("*.twig"))
    yml_files = list(comp_dir.glob("*.yml"))
    stories_files = list(comp_dir.glob("*.stories.jsx"))

    scss_file = scss_files[0] if scss_files else None
    twig_file = twig_files[0] if twig_files else None
    yml_file = yml_files[0] if yml_files else None
    stories_file = stories_files[0] if stories_files else None

    # ------------------------------------------------------------------
    # CHECK 1: SCSS file exists and does not start with `_`
    # ------------------------------------------------------------------
    if scss_file:
        check("SCSS file created, does not start with _", "PASS", scss_file.name)
        pass_count += 1
    elif underscore_scss:
        check("SCSS file created, does not start with _", "FAIL",
              f"{underscore_scss[0].name} starts with underscore")
        fail_count += 1
    else:
        check("SCSS file created, does not start with _", "FAIL",
              "no .scss file found in component directory")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 2: attach_library appears in the Twig template
    # ------------------------------------------------------------------
    if twig_file and "attach_library" in twig_file.read_text(errors="replace"):
        check("attach_library in Twig template", "PASS")
        pass_count += 1
    else:
        twig_name = twig_file.name if twig_file else "twig"
        check("attach_library in Twig template", "FAIL",
              f"attach_library not found in {twig_name}")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 3: New library entry added to gesso.libraries.yml
    # ------------------------------------------------------------------
    libraries_file = wt / GESSO_THEME / "gesso.libraries.yml"
    new_library_found = False

    if libraries_file.is_file() and BASE_LIBRARIES.is_file():
        base_keys: set[str] = set()
        for line in BASE_LIBRARIES.read_text(errors="replace").splitlines():
            m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):', line)
            if m:
                base_keys.add(m.group(1))

        for line in libraries_file.read_text(errors="replace").splitlines():
            m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):', line)
            if m and m.group(1) not in base_keys:
                new_library_found = True
                break
    elif libraries_file.is_file():
        # No base to compare, treat any key as new
        for line in libraries_file.read_text(errors="replace").splitlines():
            if re.match(r'^[a-zA-Z][a-zA-Z0-9_-]+:', line):
                new_library_found = True
                break

    if new_library_found:
        check("New library entry in gesso.libraries.yml", "PASS")
        pass_count += 1
    else:
        check("New library entry in gesso.libraries.yml", "FAIL",
              "no new top-level library key found")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 4: CSS class names start with c-
    # ------------------------------------------------------------------
    bad_classes: list[str] = []
    if scss_file:
        allowed_prefixes = (".c-", ".has-", ".is-", ".js-")
        for line in scss_file.read_text(errors="replace").splitlines():
            if re.match(r'^\.[a-zA-Z]', line):
                for cls in re.findall(r'\.[a-zA-Z][a-zA-Z0-9_-]*', line):
                    if not any(cls.startswith(p) for p in allowed_prefixes):
                        bad_classes.append(cls)
                        if len(bad_classes) >= 3:
                            break
            if len(bad_classes) >= 3:
                break

    if not bad_classes:
        check("CSS class names start with c-", "PASS")
        pass_count += 1
    else:
        check("CSS class names start with c-", "FAIL",
              f"found class not starting with c-: {bad_classes[0]}")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 5: CSS logical properties used instead of directional
    # ------------------------------------------------------------------
    directional_examples: list[str] = []
    if scss_file:
        for lineno, line in enumerate(scss_file.read_text(errors="replace").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            if re.match(r'^\s*(top|bottom|left|right)\s*:', line):
                directional_examples.append(f"{lineno}: {stripped}")
            elif re.match(r'^\s*(margin|padding)-(top|bottom|left|right)\s*:', line):
                directional_examples.append(f"{lineno}: {stripped}")
            if len(directional_examples) >= 3:
                break

    if not directional_examples:
        check("CSS logical properties used (no directional)", "PASS")
        pass_count += 1
    else:
        check("CSS logical properties used (no directional)", "FAIL",
              f"directional property found: {directional_examples[0]}")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 6: gesso-spacing() and gesso-font-size() are used
    # ------------------------------------------------------------------
    has_spacing = False
    has_font_size = False
    has_display_text_style = False

    if scss_file:
        content = scss_file.read_text(errors="replace")
        has_spacing = "gesso-spacing(" in content
        has_font_size = "gesso-font-size(" in content
        has_display_text_style = "display-text-style(" in content

    font_size_satisfied = has_font_size or has_display_text_style

    if has_spacing and font_size_satisfied:
        if has_font_size:
            check("gesso-spacing() and gesso-font-size() used", "PASS")
        else:
            check("gesso-spacing() and gesso-font-size() used", "PASS",
                  "gesso-font-size() substituted by display-text-style()")
        pass_count += 1
    elif has_spacing and not font_size_satisfied:
        check("gesso-spacing() and gesso-font-size() used", "FAIL",
              "gesso-spacing() found but gesso-font-size() and display-text-style() both missing")
        fail_count += 1
    elif not has_spacing and font_size_satisfied:
        check("gesso-spacing() and gesso-font-size() used", "FAIL",
              "gesso-font-size()/display-text-style() found but gesso-spacing() missing")
        fail_count += 1
    else:
        check("gesso-spacing() and gesso-font-size() used", "FAIL",
              "none of gesso-spacing(), gesso-font-size(), or display-text-style() found")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 7: No bare px values (any px must be inside rem())
    # ------------------------------------------------------------------
    bare_px_examples: list[str] = []
    if scss_file:
        for lineno, line in enumerate(scss_file.read_text(errors="replace").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            if re.search(r'[0-9]px', line):
                # Skip if px is inside rem(...)
                if re.search(r'rem\([^)]*[0-9]px', line):
                    continue
                # Skip @-rules
                if re.search(r'@[a-z]', line):
                    continue
                bare_px_examples.append(f"{lineno}: {stripped}")
                if len(bare_px_examples) >= 3:
                    break

    if not bare_px_examples:
        check("No bare px values (or px wrapped in rem())", "PASS")
        pass_count += 1
    else:
        check("No bare px values (or px wrapped in rem())", "FAIL",
              f"bare px found: {bare_px_examples[0]}")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 8: YAML file created
    # ------------------------------------------------------------------
    if yml_file:
        check("YAML (.yml) file created", "PASS", yml_file.name)
        pass_count += 1
    else:
        check("YAML (.yml) file created", "FAIL",
              "no .yml file found in component directory")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 9: .stories.jsx file created and imports twig and yaml
    # ------------------------------------------------------------------
    if not stories_file:
        check(".stories.jsx created, imports twig + yaml", "FAIL",
              "no .stories.jsx file found")
        fail_count += 1
    else:
        stories_content = stories_file.read_text(errors="replace")
        imports_twig = bool(re.search(r'import.*\.twig', stories_content))
        imports_yml = bool(re.search(r'import.*\.yml', stories_content))

        if imports_twig and imports_yml:
            check(".stories.jsx created, imports twig + yaml", "PASS", stories_file.name)
            pass_count += 1
        elif not imports_twig and imports_yml:
            check(".stories.jsx created, imports twig + yaml", "FAIL",
                  "missing import of .twig file")
            fail_count += 1
        elif imports_twig and not imports_yml:
            check(".stories.jsx created, imports twig + yaml", "FAIL",
                  "missing import of .yml file")
            fail_count += 1
        else:
            check(".stories.jsx created, imports twig + yaml", "FAIL",
                  "missing imports for both .twig and .yml")
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
        description="Review worktrees for film hero component creation."
    )
    parser.add_argument("count", nargs="?", type=int, default=10,
                        help="Number of workers to check (default: 10)")
    parser.add_argument("worker_prefix", nargs="?", default="drupal-test-worker",
                        help="Worker directory prefix (default: drupal-test-worker)")
    args = parser.parse_args()

    print("Film Hero Component Review")
    print("Prompt: create-film-hero.txt")
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
