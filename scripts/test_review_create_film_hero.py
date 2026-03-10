#!/usr/bin/env python3
"""Unit tests for review_create_film_hero.py."""

import re
import pytest
from pathlib import Path
from unittest.mock import patch

import review_create_film_hero as rfh


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_worktree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel_path, content in files.items():
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return tmp_path


COMP = f"{rfh.COMPONENTS_DIR}/film-hero"


# ---------------------------------------------------------------------------
# CHECK 1: SCSS file exists and does not start with `_`
# ---------------------------------------------------------------------------

class TestCheck1ScssFile:
    def test_pass_scss_without_underscore(self, tmp_path):
        files = {f"{COMP}/film-hero.scss": ".c-film-hero { color: red; }"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        scss_files = [f for f in comp_dir.glob("*.scss") if not f.name.startswith("_")]
        assert len(scss_files) == 1

    def test_fail_scss_starts_with_underscore(self, tmp_path):
        files = {f"{COMP}/_film-hero.scss": ".c-film-hero { color: red; }"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        scss_files = [f for f in comp_dir.glob("*.scss") if not f.name.startswith("_")]
        underscore_scss = list(comp_dir.glob("_*.scss"))
        assert len(scss_files) == 0
        assert len(underscore_scss) == 1

    def test_fail_no_scss_file(self, tmp_path):
        files = {f"{COMP}/film-hero.twig": "<div></div>"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        scss_files = [f for f in comp_dir.glob("*.scss") if not f.name.startswith("_")]
        underscore_scss = list(comp_dir.glob("_*.scss"))
        assert len(scss_files) == 0
        assert len(underscore_scss) == 0


# ---------------------------------------------------------------------------
# CHECK 2: attach_library in Twig template
# ---------------------------------------------------------------------------

class TestCheck2AttachLibrary:
    def test_pass_attach_library_present(self, tmp_path):
        files = {f"{COMP}/film-hero.twig": "{{ attach_library('gesso/film-hero') }}\n<div></div>"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        twig_file = list(comp_dir.glob("*.twig"))[0]
        assert "attach_library" in twig_file.read_text()

    def test_fail_attach_library_missing(self, tmp_path):
        files = {f"{COMP}/film-hero.twig": "<div class='c-film-hero'></div>"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        twig_file = list(comp_dir.glob("*.twig"))[0]
        assert "attach_library" not in twig_file.read_text()

    def test_fail_no_twig_file(self, tmp_path):
        files = {f"{COMP}/film-hero.scss": ".c-film-hero {}"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        twig_files = list(comp_dir.glob("*.twig"))
        assert len(twig_files) == 0


# ---------------------------------------------------------------------------
# CHECK 3: New library entry in gesso.libraries.yml
# ---------------------------------------------------------------------------

class TestCheck3LibraryEntry:
    def _base_keys(self, base_content: str) -> set:
        keys = set()
        for line in base_content.splitlines():
            m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):', line)
            if m:
                keys.add(m.group(1))
        return keys

    def test_pass_new_key_not_in_base(self):
        base = "global:\n  css: {}\nbuttons:\n  css: {}\n"
        new = "global:\n  css: {}\nbuttons:\n  css: {}\nfilm-hero:\n  css: {}\n"
        base_keys = self._base_keys(base)
        new_found = False
        for line in new.splitlines():
            m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):', line)
            if m and m.group(1) not in base_keys:
                new_found = True
                break
        assert new_found

    def test_fail_no_new_key(self):
        base = "global:\n  css: {}\n"
        new = "global:\n  css: {}\n"
        base_keys = self._base_keys(base)
        new_found = False
        for line in new.splitlines():
            m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):', line)
            if m and m.group(1) not in base_keys:
                new_found = True
                break
        assert not new_found

    def test_pass_no_base_file_any_key_counts(self):
        new = "film-hero:\n  css: {}\n"
        new_found = False
        for line in new.splitlines():
            if re.match(r'^[a-zA-Z][a-zA-Z0-9_-]+:', line):
                new_found = True
                break
        assert new_found

    def test_fail_key_starting_with_digit_ignored(self):
        # Keys must start with a letter per the regex
        line = "1bad-key: value"
        assert not re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):', line)

    def test_pass_hyphenated_key(self):
        line = "film-hero: {}"
        assert re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):', line)

    def test_pass_underscored_key(self):
        line = "film_hero: {}"
        assert re.match(r'^([a-zA-Z][a-zA-Z0-9_-]+):', line)


# ---------------------------------------------------------------------------
# CHECK 4: CSS class names start with c-
# ---------------------------------------------------------------------------

class TestCheck4CssClassNames:
    _allowed = (".c-", ".has-", ".is-", ".js-")

    def _bad_classes(self, scss_content: str) -> list:
        bad = []
        for line in scss_content.splitlines():
            if re.match(r'^\.[a-zA-Z]', line):
                for cls in re.findall(r'\.[a-zA-Z][a-zA-Z0-9_-]*', line):
                    if not any(cls.startswith(p) for p in self._allowed):
                        bad.append(cls)
                        if len(bad) >= 3:
                            break
            if len(bad) >= 3:
                break
        return bad

    def test_pass_c_prefix(self):
        assert self._bad_classes(".c-film-hero { color: red; }") == []

    def test_pass_has_prefix(self):
        assert self._bad_classes(".has-overlay { opacity: 0.5; }") == []

    def test_pass_is_prefix(self):
        assert self._bad_classes(".is-active { display: block; }") == []

    def test_pass_js_prefix(self):
        assert self._bad_classes(".js-hero { display: none; }") == []

    def test_fail_bare_class(self):
        bad = self._bad_classes(".film-hero { color: red; }")
        assert ".film-hero" in bad

    def test_fail_utility_class_without_prefix(self):
        bad = self._bad_classes(".hero { margin: 0; }")
        assert ".hero" in bad

    def test_pass_multiple_allowed_classes(self):
        scss = ".c-hero { }\n.has-image { }\n.is-visible { }"
        assert self._bad_classes(scss) == []

    def test_fail_mixed_good_and_bad(self):
        scss = ".c-hero { }\n.bad-class { }"
        bad = self._bad_classes(scss)
        assert ".bad-class" in bad
        assert ".c-hero" not in bad


# ---------------------------------------------------------------------------
# CHECK 5: CSS logical properties (no directional)
# ---------------------------------------------------------------------------

class TestCheck5LogicalProperties:
    def _directional(self, scss_content: str) -> list:
        found = []
        for lineno, line in enumerate(scss_content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            if re.match(r'^\s*(top|bottom|left|right)\s*:', line):
                found.append(f"{lineno}: {stripped}")
            elif re.match(r'^\s*(margin|padding)-(top|bottom|left|right)\s*:', line):
                found.append(f"{lineno}: {stripped}")
            if len(found) >= 3:
                break
        return found

    def test_pass_logical_margin(self):
        assert self._directional("  margin-block: 1rem;") == []

    def test_pass_logical_padding(self):
        assert self._directional("  padding-inline: 1rem;") == []

    def test_fail_top(self):
        assert len(self._directional("  top: 0;")) == 1

    def test_fail_bottom(self):
        assert len(self._directional("  bottom: 0;")) == 1

    def test_fail_left(self):
        assert len(self._directional("  left: 0;")) == 1

    def test_fail_right(self):
        assert len(self._directional("  right: 0;")) == 1

    def test_fail_margin_top(self):
        assert len(self._directional("  margin-top: 1rem;")) == 1

    def test_fail_padding_left(self):
        assert len(self._directional("  padding-left: 1rem;")) == 1

    def test_pass_comment_skipped(self):
        assert self._directional("  // top: 0;") == []

    def test_pass_background_position_top_not_flagged(self):
        # "top" only flagged at start of value line, not mid-value
        assert self._directional("  background-position: center top;") == []


# ---------------------------------------------------------------------------
# CHECK 6: gesso-spacing() and gesso-font-size() used
# ---------------------------------------------------------------------------

class TestCheck6GessoFunctions:
    def _results(self, content: str):
        has_spacing = "gesso-spacing(" in content
        has_font_size = "gesso-font-size(" in content
        has_display = "display-text-style(" in content
        font_ok = has_font_size or has_display
        return has_spacing, font_ok, has_font_size, has_display

    def test_pass_both_present(self):
        content = "padding: gesso-spacing(2);\nfont-size: gesso-font-size(md);"
        s, f, _, _ = self._results(content)
        assert s and f

    def test_pass_spacing_and_display_text_style(self):
        content = "padding: gesso-spacing(2);\n@include display-text-style(h1);"
        s, f, hf, hd = self._results(content)
        assert s and f and not hf and hd

    def test_fail_spacing_only(self):
        content = "padding: gesso-spacing(2);"
        s, f, _, _ = self._results(content)
        assert s and not f

    def test_fail_font_size_only(self):
        content = "font-size: gesso-font-size(md);"
        s, f, _, _ = self._results(content)
        assert not s and f

    def test_fail_neither(self):
        content = "padding: 1rem;\nfont-size: 1.2rem;"
        s, f, _, _ = self._results(content)
        assert not s and not f

    def test_fail_display_text_style_without_spacing(self):
        content = "@include display-text-style(h1);"
        s, f, _, _ = self._results(content)
        assert not s and f  # font_ok but spacing missing


# ---------------------------------------------------------------------------
# CHECK 7: No bare px values
# ---------------------------------------------------------------------------

class TestCheck7NoBarePixels:
    def _bare_px(self, scss_content: str) -> list:
        found = []
        for lineno, line in enumerate(scss_content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            if re.search(r'[0-9]px', line):
                if re.search(r'rem\([^)]*[0-9]px', line):
                    continue
                if re.search(r'@[a-z]', line):
                    continue
                found.append(f"{lineno}: {stripped}")
                if len(found) >= 3:
                    break
        return found

    def test_pass_rem_wrapped_px(self):
        assert self._bare_px("  width: rem(16px);") == []

    def test_pass_no_px_at_all(self):
        assert self._bare_px("  padding: gesso-spacing(2);") == []

    def test_fail_bare_px_width(self):
        assert len(self._bare_px("  width: 200px;")) == 1

    def test_fail_bare_px_font_size(self):
        assert len(self._bare_px("  font-size: 16px;")) == 1

    def test_pass_px_in_comment(self):
        assert self._bare_px("  // width: 200px;") == []

    def test_pass_px_in_at_rule(self):
        assert self._bare_px("  @media (max-width: 768px) {") == []

    def test_fail_multiple_bare_px_stops_at_3(self):
        lines = "\n".join([f"  prop{i}: {i}px;" for i in range(5)])
        result = self._bare_px(lines)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# CHECK 8: YAML file created
# ---------------------------------------------------------------------------

class TestCheck8YamlFile:
    def test_pass_yml_file_present(self, tmp_path):
        files = {f"{COMP}/film-hero.yml": "title: Film Hero\n"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        assert len(list(comp_dir.glob("*.yml"))) == 1

    def test_fail_no_yml_file(self, tmp_path):
        files = {f"{COMP}/film-hero.twig": "<div></div>"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        assert len(list(comp_dir.glob("*.yml"))) == 0


# ---------------------------------------------------------------------------
# CHECK 9: .stories.jsx created and imports twig + yaml
# ---------------------------------------------------------------------------

class TestCheck9StoriesFile:
    def _check_imports(self, content: str):
        imports_twig = bool(re.search(r'import.*\.twig', content))
        imports_yml = bool(re.search(r'import.*\.yml', content))
        return imports_twig, imports_yml

    def test_pass_both_imports(self):
        content = (
            "import template from './film-hero.twig';\n"
            "import data from './film-hero.yml';\n"
        )
        t, y = self._check_imports(content)
        assert t and y

    def test_fail_missing_twig_import(self):
        content = "import data from './film-hero.yml';\n"
        t, y = self._check_imports(content)
        assert not t and y

    def test_fail_missing_yml_import(self):
        content = "import template from './film-hero.twig';\n"
        t, y = self._check_imports(content)
        assert t and not y

    def test_fail_neither_import(self):
        content = "import React from 'react';\n"
        t, y = self._check_imports(content)
        assert not t and not y

    def test_fail_no_stories_file(self, tmp_path):
        files = {f"{COMP}/film-hero.twig": "<div></div>"}
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        assert len(list(comp_dir.glob("*.stories.jsx"))) == 0

    def test_pass_stories_file_present(self, tmp_path):
        files = {
            f"{COMP}/film-hero.stories.jsx": (
                "import template from './film-hero.twig';\n"
                "import data from './film-hero.yml';\n"
            )
        }
        wt = make_worktree(tmp_path, files)
        comp_dir = wt / COMP
        assert len(list(comp_dir.glob("*.stories.jsx"))) == 1


# ---------------------------------------------------------------------------
# Integration: review_worktree
# ---------------------------------------------------------------------------

class TestReviewWorktreeIntegration:
    def _build_full_worktree(self, tmp_path: Path) -> None:
        base_lib = "global:\n  css: {}\n"
        worker_lib = "global:\n  css: {}\nfilm-hero:\n  css: {}\n"
        scss = (
            ".c-film-hero {\n"
            "  padding: gesso-spacing(2);\n"
            "  font-size: gesso-font-size(md);\n"
            "  width: rem(320px);\n"
            "}\n"
        )
        twig = "{{ attach_library('gesso/film-hero') }}\n<div class='c-film-hero'></div>"
        stories = (
            "import template from './film-hero.twig';\n"
            "import data from './film-hero.yml';\n"
        )
        make_worktree(tmp_path, {
            f"{COMP}/film-hero.scss": scss,
            f"{COMP}/film-hero.twig": twig,
            f"{COMP}/film-hero.yml": "title: Film Hero\n",
            f"{COMP}/film-hero.stories.jsx": stories,
            f"{rfh.GESSO_THEME}/gesso.libraries.yml": worker_lib,
        })
        # Create base repo libraries file for diff
        base = tmp_path.parent / "drupal-test" / rfh.GESSO_THEME
        base.mkdir(parents=True, exist_ok=True)
        (base / "gesso.libraries.yml").write_text(base_lib)

    def test_fully_passing(self, tmp_path):
        self._build_full_worktree(tmp_path)
        worker_dir = tmp_path.parent / "worker-01"
        tmp_path.rename(worker_dir)
        with patch.object(rfh, "PARENT_DIR", worker_dir.parent), \
             patch.object(rfh, "BASE_LIBRARIES", worker_dir.parent / "drupal-test" / rfh.GESSO_THEME / "gesso.libraries.yml"), \
             patch.object(rfh, "BASE_REPO", worker_dir.parent / "drupal-test"), \
             patch("builtins.print"):
            result = rfh.review_worktree(1, "worker")
        assert result is True

    def test_missing_worktree_returns_false(self, tmp_path):
        with patch.object(rfh, "PARENT_DIR", tmp_path), \
             patch("builtins.print"):
            result = rfh.review_worktree(99, "nonexistent")
        assert result is False

    def test_no_component_dir_returns_false(self, tmp_path):
        # worktree exists but components path is empty
        make_worktree(tmp_path, {"placeholder.txt": ""})
        worker_dir = tmp_path.parent / "nocomp-01"
        tmp_path.rename(worker_dir)
        base_comp = worker_dir.parent / "drupal-test" / rfh.COMPONENTS_DIR / "existing-comp"
        base_comp.mkdir(parents=True, exist_ok=True)
        with patch.object(rfh, "PARENT_DIR", worker_dir.parent), \
             patch.object(rfh, "BASE_REPO", worker_dir.parent / "drupal-test"), \
             patch("builtins.print"):
            result = rfh.review_worktree(1, "nocomp")
        assert result is False
