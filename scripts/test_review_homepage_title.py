#!/usr/bin/env python3
"""Unit tests for review_homepage_title.py."""

import re
import difflib
import pytest
from pathlib import Path
from unittest.mock import patch

import review_homepage_title as rht


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_worktree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel_path, content in files.items():
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return tmp_path


CUSTOM_MOD = "web/modules/custom/mymodule"
GESSO = "web/themes/gesso"


# ---------------------------------------------------------------------------
# collect_php_files / collect_theme_files
# ---------------------------------------------------------------------------

class TestCollectPhpFiles:
    def test_collects_module_files(self, tmp_path):
        make_worktree(tmp_path, {
            f"{CUSTOM_MOD}/mymodule.module": "<?php\n",
            f"{CUSTOM_MOD}/mymodule.inc": "<?php\n",
        })
        files = rht.collect_php_files(tmp_path)
        names = {f.name for f in files}
        assert "mymodule.module" in names
        assert "mymodule.inc" in names

    def test_skips_node_modules(self, tmp_path):
        make_worktree(tmp_path, {
            "web/modules/custom/node_modules/foo/bar.module": "<?php\n",
        })
        files = rht.collect_php_files(tmp_path)
        assert len(files) == 0

    def test_skips_vendor(self, tmp_path):
        make_worktree(tmp_path, {
            "web/themes/gesso/vendor/foo/bar.module": "<?php\n",
        })
        files = rht.collect_php_files(tmp_path)
        assert len(files) == 0

    def test_skips_test_files(self, tmp_path):
        make_worktree(tmp_path, {
            f"{CUSTOM_MOD}/mymodule.test.module": "<?php\n",
        })
        files = rht.collect_php_files(tmp_path)
        assert len(files) == 0

    def test_collects_theme_module_files(self, tmp_path):
        make_worktree(tmp_path, {
            f"{GESSO}/gesso.module": "<?php\n",
        })
        files = rht.collect_php_files(tmp_path)
        assert any(f.name == "gesso.module" for f in files)

    def test_empty_when_no_roots_exist(self, tmp_path):
        files = rht.collect_php_files(tmp_path)
        assert files == []


class TestCollectThemeFiles:
    def test_collects_theme_files(self, tmp_path):
        make_worktree(tmp_path, {f"{GESSO}/gesso.theme": "<?php\n"})
        files = rht.collect_theme_files(tmp_path)
        assert any(f.name == "gesso.theme" for f in files)

    def test_skips_node_modules(self, tmp_path):
        make_worktree(tmp_path, {
            f"{GESSO}/node_modules/foo/bar.theme": "<?php\n",
        })
        files = rht.collect_theme_files(tmp_path)
        assert len(files) == 0

    def test_empty_when_theme_root_missing(self, tmp_path):
        files = rht.collect_theme_files(tmp_path)
        assert files == []


# ---------------------------------------------------------------------------
# CHECK 1: hook_field_widget_complete_paragraphs_form_alter
# ---------------------------------------------------------------------------

class TestCheck1ParagraphsAlter:
    _pattern = re.compile(r'function (\w+_field_widget_complete_paragraphs_form_alter)')

    def test_pass_standard_hook_name(self):
        line = "function mymodule_field_widget_complete_paragraphs_form_alter(&$element, $form_state, $context) {"
        assert self._pattern.search(line)

    def test_pass_any_module_prefix(self):
        line = "function foo_field_widget_complete_paragraphs_form_alter($a) {"
        assert self._pattern.search(line)

    def test_fail_wrong_hook_name(self):
        line = "function mymodule_form_alter($form, $form_state) {"
        assert not self._pattern.search(line)

    def test_fail_no_function(self):
        line = "// field_widget_complete_paragraphs_form_alter"
        assert not self._pattern.search(line)

    def test_pass_extracts_function_name(self):
        line = "function mymod_field_widget_complete_paragraphs_form_alter() {"
        m = self._pattern.search(line)
        assert m and m.group(1) == "mymod_field_widget_complete_paragraphs_form_alter"


# ---------------------------------------------------------------------------
# CHECK 2: hook_preprocess_node using field_is_homepage
# ---------------------------------------------------------------------------

class TestCheck2PreprocessNode:
    def test_pass_preprocess_node_with_field_is_homepage(self):
        content = (
            "function mymodule_preprocess_node(&$variables) {\n"
            "  $node = $variables['node'];\n"
            "  if ($node->hasField('field_is_homepage')) {\n"
            "    $variables['is_homepage'] = TRUE;\n"
            "  }\n"
            "}\n"
        )
        has_fn = bool(re.search(r'function \w+preprocess_node', content))
        has_field = "field_is_homepage" in content
        assert has_fn and has_field

    def test_fail_preprocess_node_without_field_is_homepage(self):
        content = (
            "function mymodule_preprocess_node(&$variables) {\n"
            "  $variables['foo'] = 'bar';\n"
            "}\n"
        )
        has_fn = bool(re.search(r'function \w+preprocess_node', content))
        has_field = "field_is_homepage" in content
        assert has_fn and not has_field

    def test_fail_field_is_homepage_without_preprocess_node(self):
        content = (
            "function mymodule_form_alter(&$form) {\n"
            "  if (isset($form['field_is_homepage'])) {}\n"
            "}\n"
        )
        has_fn = bool(re.search(r'function \w+preprocess_node', content))
        has_field = "field_is_homepage" in content
        assert not has_fn and has_field

    def test_pass_function_name_extracted(self):
        content = "function gesso_preprocess_node_article(&$vars) {\n  $vars['field_is_homepage'] = TRUE;\n}\n"
        m = re.search(r'function (\w*preprocess_node\w*)', content)
        assert m and "preprocess_node" in m.group(1)


# ---------------------------------------------------------------------------
# CHECK 3: Hooks NOT in .theme file
# ---------------------------------------------------------------------------

class TestCheck3HooksNotInTheme:
    _pattern = re.compile(r'^function ([a-zA-Z][a-zA-Z0-9_]*)\(', re.MULTILINE)

    def _public_hooks(self, content: str) -> list:
        return [m.group(1) for m in self._pattern.finditer(content)
                if not m.group(1).startswith("_")]

    def test_fail_public_hook_in_theme(self):
        content = "function mymodule_preprocess_node(&$vars) {\n  // code\n}\n"
        hooks = self._public_hooks(content)
        assert len(hooks) > 0

    def test_pass_no_public_hooks_in_theme(self):
        content = "// Just a comment\n$var = 'value';\n"
        hooks = self._public_hooks(content)
        assert len(hooks) == 0

    def test_pass_private_function_ignored(self):
        content = "function _helper_function() {\n  return TRUE;\n}\n"
        hooks = self._public_hooks(content)
        assert len(hooks) == 0

    def test_fail_multiple_hooks_detects_first(self):
        content = (
            "function first_hook() {}\n"
            "function second_hook() {}\n"
        )
        hooks = self._public_hooks(content)
        assert hooks[0] == "first_hook"

    def test_pass_function_call_not_definition(self):
        # A function call (not at line start) should not match
        content = "  mymodule_preprocess_node($vars);\n"
        hooks = self._public_hooks(content)
        assert len(hooks) == 0


# ---------------------------------------------------------------------------
# CHECK 4: 'Implements hook_' docblock present for new/modified hooks
# ---------------------------------------------------------------------------

class TestCheck4ImplementsDocblock:
    def _has_docblock(self, lines: list[str], fn_name: str) -> bool:
        for i, line in enumerate(lines, 1):
            if re.match(rf'^function {re.escape(fn_name)}\(', line):
                start = max(0, i - 6)
                context = "\n".join(lines[start:i - 1])
                return bool(re.search(r'Implements hook_', context))
        return False

    def test_pass_docblock_present(self):
        lines = [
            "/**",
            " * Implements hook_preprocess_node().",
            " */",
            "function mymod_preprocess_node(&$vars) {",
            "  // code",
            "}",
        ]
        assert self._has_docblock(lines, "mymod_preprocess_node")

    def test_fail_docblock_missing(self):
        lines = [
            "function mymod_preprocess_node(&$vars) {",
            "  // no docblock above",
            "}",
        ]
        assert not self._has_docblock(lines, "mymod_preprocess_node")

    def test_fail_wrong_comment_text(self):
        lines = [
            "// This function does something",
            "function mymod_preprocess_node(&$vars) {",
            "}",
        ]
        assert not self._has_docblock(lines, "mymod_preprocess_node")

    def test_pass_docblock_within_5_lines(self):
        lines = [
            "// unrelated",
            "/**",
            " * Implements hook_field_widget_complete_paragraphs_form_alter().",
            " */",
            "function mymod_field_widget_complete_paragraphs_form_alter() {",
            "}",
        ]
        assert self._has_docblock(lines, "mymod_field_widget_complete_paragraphs_form_alter")

    def test_fail_docblock_too_far_away(self):
        # More than 5 lines before the function
        lines = [
            "/**",
            " * Implements hook_preprocess_node().",
            " */",
            "// line 4",
            "// line 5",
            "// line 6",
            "// line 7",
            "function mymod_preprocess_node(&$vars) {",
            "}",
        ]
        assert not self._has_docblock(lines, "mymod_preprocess_node")

    def test_new_functions_detected_via_diff(self):
        base = []
        new = [
            "/**",
            " * Implements hook_preprocess_node().",
            " */",
            "function mymod_preprocess_node(&$vars) {",
            "}",
        ]
        diff = list(difflib.unified_diff(base, new, lineterm=""))
        new_fns = []
        for diff_line in diff:
            if diff_line.startswith("+") and not diff_line.startswith("+++"):
                m = re.match(r'^\+function ([a-zA-Z][a-zA-Z0-9_]+)', diff_line)
                if m:
                    new_fns.append(m.group(1))
        assert "mymod_preprocess_node" in new_fns

    def test_modified_lines_only_not_unchanged(self):
        base = ["function existing_fn() {}", "}"]
        new = ["function existing_fn() {}", "}", "function new_fn() {}", "}"]
        diff = list(difflib.unified_diff(base, new, lineterm=""))
        new_fns = []
        for diff_line in diff:
            if diff_line.startswith("+") and not diff_line.startswith("+++"):
                m = re.match(r'^\+function ([a-zA-Z][a-zA-Z0-9_]+)', diff_line)
                if m:
                    new_fns.append(m.group(1))
        assert "new_fn" in new_fns
        assert "existing_fn" not in new_fns


# ---------------------------------------------------------------------------
# Integration: review_worktree
# ---------------------------------------------------------------------------

class TestReviewWorktreeIntegration:
    def _php_content(self, module_name: str) -> str:
        return (
            "<?php\n"
            f"\n"
            f"/**\n"
            f" * Implements hook_field_widget_complete_paragraphs_form_alter().\n"
            f" */\n"
            f"function {module_name}_field_widget_complete_paragraphs_form_alter(&$element, $form_state, $context) {{\n"
            f"  // alter\n"
            f"}}\n"
            f"\n"
            f"/**\n"
            f" * Implements hook_preprocess_node().\n"
            f" */\n"
            f"function {module_name}_preprocess_node(&$variables) {{\n"
            f"  $node = $variables['node'];\n"
            f"  if ($node->hasField('field_is_homepage')) {{\n"
            f"    $variables['is_homepage'] = TRUE;\n"
            f"  }}\n"
            f"}}\n"
        )

    def test_fully_passing(self, tmp_path):
        module_name = "mymodule"
        parent = tmp_path / "env"
        worker_dir = parent / "worker-01"
        files = {
            f"web/modules/custom/{module_name}/{module_name}.module": self._php_content(module_name),
        }
        make_worktree(worker_dir, files)
        with patch.object(rht, "PARENT_DIR", parent), \
             patch.object(rht, "BASE_REPO", parent / "drupal-test"), \
             patch("builtins.print"):
            result = rht.review_worktree(1, "worker")
        assert result is True

    def test_missing_worktree_returns_false(self, tmp_path):
        with patch.object(rht, "PARENT_DIR", tmp_path), \
             patch("builtins.print"):
            result = rht.review_worktree(99, "nonexistent")
        assert result is False

    def test_hooks_in_theme_file_fails_check3(self, tmp_path):
        module_name = "mymodule"
        parent = tmp_path / "env2"
        worker_dir = parent / "themehook-01"
        files = {
            f"web/modules/custom/{module_name}/{module_name}.module": self._php_content(module_name),
            f"{GESSO}/gesso.theme": (
                "<?php\n"
                "/**\n * Implements hook_preprocess_node().\n */\n"
                "function gesso_preprocess_node(&$vars) { }\n"
            ),
        }
        make_worktree(worker_dir, files)
        with patch.object(rht, "PARENT_DIR", parent), \
             patch.object(rht, "BASE_REPO", parent / "drupal-test"), \
             patch("builtins.print"):
            result = rht.review_worktree(1, "themehook")
        assert result is False
