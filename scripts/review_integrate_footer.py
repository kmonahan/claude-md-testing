#!/usr/bin/env python3
"""
Reviews worktrees for successful integration of the global footer.

Usage:
  python3 review_integrate_footer.py [COUNT] [WORKER_PREFIX]

Checks each worktree against the integrate-footer.txt prompt criteria.
"""

import argparse
import re
from pathlib import Path


PARENT_DIR = Path("/Users/kjmonahan/AgentTests")
BASE_REPO = PARENT_DIR / "drupal-test"
GESSO_THEME = "web/themes/gesso"
CONFIG_SYNC = "config/sync"

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


def extract_block_content(twig_text: str, block_name: str) -> str:
    """Extract content between {% block NAME %} and {% endblock %}."""
    lines = twig_text.splitlines()
    result: list[str] = []
    found = False
    for line in lines:
        if re.search(rf'block\s+{re.escape(block_name)}\b', line):
            found = True
        if found:
            result.append(line)
        if found and "endblock" in line and len(result) > 1:
            break
    return "\n".join(result)


def review_worktree(index: int, worker_prefix: str) -> bool:
    """Review a single worktree. Returns True if fully passing."""
    name = f"{worker_prefix}-{index:02d}"
    wt = PARENT_DIR / name

    if not wt.is_dir():
        return False

    pass_count = 0
    fail_count = 0
    check_count = 7

    print()
    print("==========================================")
    print(f"  {name}")
    print("==========================================")

    gesso_dir = wt / GESSO_THEME
    config_sync_dir = wt / CONFIG_SYNC

    # ------------------------------------------------------------------
    # CHECK 1: Custom block type config added
    # ------------------------------------------------------------------
    block_type_file: Path | None = None
    search_dirs = [config_sync_dir, gesso_dir / "config"]
    for d in search_dirs:
        if d.is_dir():
            matches = list(d.rglob("block_content.type.*.yml"))
            if matches:
                block_type_file = matches[0]
                break

    if block_type_file:
        type_id = ""
        for line in block_type_file.read_text(errors="replace").splitlines():
            m = re.match(r'^id:\s*(.+)', line)
            if m:
                type_id = m.group(1).strip()
                break
        check("Custom block type config added", "PASS",
              f"{block_type_file.name} (id: {type_id})")
        pass_count += 1
    else:
        check("Custom block type config added", "FAIL",
              "no block_content.type.*.yml found in config/sync or theme config")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 2: menu-social.twig included or embedded in a twig file
    # ------------------------------------------------------------------
    menu_social_ref: str | None = None
    twig_search_roots = [gesso_dir / "templates", gesso_dir / "source"]
    for root in twig_search_roots:
        if not root.is_dir():
            continue
        for f in root.rglob("*.twig"):
            if f.name == "menu-social.twig":
                continue
            if "node_modules" in f.parts:
                continue
            if "menu-social" in f.read_text(errors="replace"):
                menu_social_ref = str(f.relative_to(wt))
                break
        if menu_social_ref:
            break

    if menu_social_ref:
        check("menu-social.twig included/embedded", "PASS",
              f"referenced in {menu_social_ref}")
        pass_count += 1
    else:
        check("menu-social.twig included/embedded", "FAIL",
              "no include/embed of menu-social found in any twig file")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 3: Contact Us block in first footer slot
    # ------------------------------------------------------------------
    footer_twig_path = gesso_dir / "templates" / "layout" / "region--footer.html.twig"
    contact_in_first = False

    def check_contact_in_first(twig_text: str) -> bool:
        block_content = extract_block_content(twig_text, "first")
        return bool(re.search(r'contact_us|contact-us|gesso_contact_us', block_content, re.IGNORECASE))

    if footer_twig_path.is_file():
        contact_in_first = check_contact_in_first(footer_twig_path.read_text(errors="replace"))

    if not contact_in_first:
        for root in twig_search_roots:
            if not root.is_dir():
                continue
            for f in root.rglob("*.twig"):
                if f.name in ("footer.twig", "region--footer.html.twig"):
                    continue
                if "node_modules" in f.parts:
                    continue
                if check_contact_in_first(f.read_text(errors="replace")):
                    contact_in_first = True
                    break
            if contact_in_first:
                break

    if contact_in_first:
        check("Contact Us block in first footer slot", "PASS")
        pass_count += 1
    else:
        check("Contact Us block in first footer slot", "FAIL",
              "contact block not found in {% block first %}")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 4: Social links AND footer menu both in second footer slot
    # ------------------------------------------------------------------
    social_in_second = False
    menu_in_second = False

    if footer_twig_path.is_file():
        second_content = extract_block_content(
            footer_twig_path.read_text(errors="replace"), "second"
        )
        social_in_second = bool(
            re.search(r'menu.social|menu-social|social', second_content, re.IGNORECASE)
        )
        menu_in_second = bool(
            re.search(
                r'footer.*menu|gesso_footer|system_menu_block.*footer|footer.*block|menu.*footer',
                second_content,
                re.IGNORECASE,
            )
        )

    if social_in_second and menu_in_second:
        check("Social links + footer menu in second slot", "PASS")
        pass_count += 1
    elif social_in_second and not menu_in_second:
        check("Social links + footer menu in second slot", "FAIL",
              "social found but footer menu missing from block second")
        fail_count += 1
    elif not social_in_second and menu_in_second:
        check("Social links + footer menu in second slot", "FAIL",
              "footer menu found but social links missing from block second")
        fail_count += 1
    else:
        check("Social links + footer menu in second slot", "FAIL",
              "neither social links nor footer menu found in block second")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 5: Copyright in third footer slot
    # ------------------------------------------------------------------
    copyright_in_third = False

    if footer_twig_path.is_file():
        third_content = extract_block_content(
            footer_twig_path.read_text(errors="replace"), "third"
        )
        copyright_in_third = bool(re.search(r'copyright', third_content, re.IGNORECASE))

    if copyright_in_third:
        check("Copyright in third footer slot", "PASS")
        pass_count += 1
    else:
        check("Copyright in third footer slot", "FAIL",
              "copyright not found in {% block third %}")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 6: Copyright year is dynamic
    # ------------------------------------------------------------------
    dynamic_year = False
    year_detail = ""

    # Check PHP/theme files for dynamic year
    php_exts = ("*.php", "*.inc", "*.theme")
    php_files: list[Path] = []
    for ext in php_exts:
        for f in gesso_dir.rglob(ext):
            if "node_modules" not in f.parts and "vendor" not in f.parts:
                php_files.append(f)

    for f in php_files[:20]:
        content = f.read_text(errors="replace")
        if re.search(r"date\(['\"]Y['\"]|current_year|year.*date", content):
            dynamic_year = True
            year_detail = f"PHP dynamic year in {f.name}"
            break

    # Check twig files for dynamic year
    if not dynamic_year:
        for root in twig_search_roots:
            if not root.is_dir():
                continue
            for f in root.rglob("*.twig"):
                if "node_modules" in f.parts:
                    continue
                content = f.read_text(errors="replace")
                if re.search(r"current_year|'now'\s*\|date|now\s*\|date", content) and \
                   re.search(r'year|date', content, re.IGNORECASE):
                    dynamic_year = True
                    year_detail = "Twig dynamic year reference found"
                    break
            if dynamic_year:
                break

    # Negative check: hardcoded year in copyright context
    hardcoded_year = False
    for root in twig_search_roots:
        if not root.is_dir():
            continue
        for f in root.rglob("*.twig"):
            if "node_modules" in f.parts or f.name.endswith(".map"):
                continue
            for line in f.read_text(errors="replace").splitlines():
                if re.search(r'202[0-9]\b', line) and re.search(r'copyright|year', line, re.IGNORECASE):
                    hardcoded_year = True
                    break
            if hardcoded_year:
                break
        if hardcoded_year:
            break

    if hardcoded_year and not dynamic_year:
        check("Copyright year is dynamic", "FAIL", "hardcoded year found")
        fail_count += 1
    elif dynamic_year:
        check("Copyright year is dynamic", "PASS", year_detail)
        pass_count += 1
    else:
        check("Copyright year is dynamic", "WARN",
              "no explicit dynamic year pattern found; manual check recommended")
        fail_count += 1

    # ------------------------------------------------------------------
    # CHECK 7: footer.twig included or embedded somewhere
    # ------------------------------------------------------------------
    footer_twig_ref: str | None = None
    pattern = re.compile(r'footer\.twig|@layouts/footer|embed.*footer|include.*footer\.twig')

    for root in twig_search_roots:
        if not root.is_dir():
            continue
        for f in root.rglob("*.twig"):
            if "node_modules" in f.parts or f.name.endswith(".map"):
                continue
            content = f.read_text(errors="replace")
            for lineno, line in enumerate(content.splitlines(), 1):
                if pattern.search(line):
                    footer_twig_ref = str(f.relative_to(wt))
                    break
            if footer_twig_ref:
                break
        if footer_twig_ref:
            break

    if footer_twig_ref:
        check("footer.twig included/embedded", "PASS", f"in {footer_twig_ref}")
        pass_count += 1
    else:
        check("footer.twig included/embedded", "FAIL",
              "no include/embed of footer.twig found")
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
        description="Review worktrees for footer integration task."
    )
    parser.add_argument("count", nargs="?", type=int, default=10,
                        help="Number of workers to check (default: 10)")
    parser.add_argument("worker_prefix", nargs="?", default="drupal-test-worker",
                        help="Worker directory prefix (default: drupal-test-worker)")
    args = parser.parse_args()

    print("Footer Integration Review")
    print("Prompt: integrate-footer.txt")
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
