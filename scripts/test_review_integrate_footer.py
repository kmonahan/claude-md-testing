#!/usr/bin/env python3
"""Unit tests for review_integrate_footer.py."""

import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import tempfile
import os

# Import the module under test
import review_integrate_footer as rif


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_worktree(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a fake worktree directory with the given files."""
    for rel_path, content in files.items():
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return tmp_path


# ---------------------------------------------------------------------------
# extract_block_content
# ---------------------------------------------------------------------------

class TestExtractBlockContent:
    def test_extracts_block(self):
        twig = "{% block first %}\n  <p>Contact</p>\n{% endblock %}"
        result = rif.extract_block_content(twig, "first")
        assert "Contact" in result

    def test_extracts_correct_block_among_multiple(self):
        twig = (
            "{% block first %}\n  AAA\n{% endblock %}\n"
            "{% block second %}\n  BBB\n{% endblock %}"
        )
        assert "AAA" in rif.extract_block_content(twig, "first")
        assert "BBB" in rif.extract_block_content(twig, "second")
        assert "AAA" not in rif.extract_block_content(twig, "second")

    def test_returns_empty_for_missing_block(self):
        twig = "{% block first %}\n  AAA\n{% endblock %}"
        result = rif.extract_block_content(twig, "third")
        assert result == ""

    def test_block_with_whitespace_variations(self):
        twig = "{%   block   first   %}\n  content\n{% endblock %}"
        result = rif.extract_block_content(twig, "first")
        assert "content" in result

    def test_does_not_bleed_into_next_block(self):
        twig = (
            "{% block first %}\n  FIRST\n{% endblock %}\n"
            "{% block second %}\n  SECOND\n{% endblock %}"
        )
        result = rif.extract_block_content(twig, "first")
        assert "SECOND" not in result


# ---------------------------------------------------------------------------
# CHECK 1: Custom block type config added
# ---------------------------------------------------------------------------

class TestCheck1BlockTypeConfig:
    def test_pass_config_in_config_sync(self, tmp_path):
        files = {
            "config/sync/block_content.type.footer.yml": "id: footer\nlabel: Footer\n",
        }
        wt = make_worktree(tmp_path, files)
        with patch.object(rif, "PARENT_DIR", tmp_path.parent), \
             patch("builtins.print"):
            result = rif.review_worktree.__wrapped__ if hasattr(rif.review_worktree, "__wrapped__") else None

        # Test the logic directly by calling check internals
        config_sync_dir = wt / "config/sync"
        matches = list(config_sync_dir.rglob("block_content.type.*.yml"))
        assert len(matches) == 1

    def test_pass_config_in_gesso_config(self, tmp_path):
        files = {
            f"{rif.GESSO_THEME}/config/block_content.type.gesso_footer.yml": "id: gesso_footer\n",
        }
        wt = make_worktree(tmp_path, files)
        gesso_config_dir = wt / rif.GESSO_THEME / "config"
        matches = list(gesso_config_dir.rglob("block_content.type.*.yml"))
        assert len(matches) == 1

    def test_fail_no_block_type_file(self, tmp_path):
        wt = make_worktree(tmp_path, {
            "config/sync/some_other_config.yml": "key: value\n",
        })
        config_sync_dir = wt / "config/sync"
        gesso_config_dir = wt / rif.GESSO_THEME / "config"
        matches = []
        for d in [config_sync_dir, gesso_config_dir]:
            if d.is_dir():
                matches += list(d.rglob("block_content.type.*.yml"))
        assert len(matches) == 0

    def test_id_extracted_from_yml(self, tmp_path):
        yml_content = "id: my_footer_block\nlabel: My Footer\n"
        files = {"config/sync/block_content.type.my_footer_block.yml": yml_content}
        wt = make_worktree(tmp_path, files)
        config_sync_dir = wt / "config/sync"
        block_type_file = list(config_sync_dir.rglob("block_content.type.*.yml"))[0]
        type_id = ""
        for line in block_type_file.read_text().splitlines():
            m = re.match(r'^id:\s*(.+)', line)
            if m:
                type_id = m.group(1).strip()
                break
        assert type_id == "my_footer_block"


# ---------------------------------------------------------------------------
# CHECK 2: menu-social.twig included/embedded
# ---------------------------------------------------------------------------

class TestCheck2MenuSocialRef:
    def test_pass_reference_in_footer_twig(self, tmp_path):
        files = {
            f"{rif.GESSO_THEME}/templates/layout/footer.html.twig": (
                "{% include '@gesso/menu-social.twig' %}"
            ),
        }
        wt = make_worktree(tmp_path, files)
        templates_dir = wt / rif.GESSO_THEME / "templates"
        found = False
        for f in templates_dir.rglob("*.twig"):
            if f.name == "menu-social.twig":
                continue
            if "menu-social" in f.read_text():
                found = True
                break
        assert found

    def test_pass_reference_in_source_dir(self, tmp_path):
        files = {
            f"{rif.GESSO_THEME}/source/04-templates/footer.twig": (
                "{{ embed('menu-social') }}"
            ),
        }
        wt = make_worktree(tmp_path, files)
        source_dir = wt / rif.GESSO_THEME / "source"
        found = False
        for f in source_dir.rglob("*.twig"):
            if f.name == "menu-social.twig":
                continue
            if "menu-social" in f.read_text():
                found = True
                break
        assert found

    def test_fail_no_reference(self, tmp_path):
        files = {
            f"{rif.GESSO_THEME}/templates/layout/footer.html.twig": (
                "<footer>No social menu here</footer>"
            ),
        }
        wt = make_worktree(tmp_path, files)
        templates_dir = wt / rif.GESSO_THEME / "templates"
        found = False
        for f in templates_dir.rglob("*.twig"):
            if f.name == "menu-social.twig":
                continue
            if "menu-social" in f.read_text():
                found = True
                break
        assert not found

    def test_skips_menu_social_twig_itself(self, tmp_path):
        files = {
            f"{rif.GESSO_THEME}/templates/navigation/menu-social.twig": (
                "{# This IS menu-social.twig, should be skipped #}"
            ),
        }
        wt = make_worktree(tmp_path, files)
        templates_dir = wt / rif.GESSO_THEME / "templates"
        found = False
        for f in templates_dir.rglob("*.twig"):
            if f.name == "menu-social.twig":
                continue
            if "menu-social" in f.read_text():
                found = True
                break
        assert not found


# ---------------------------------------------------------------------------
# CHECK 3: Contact Us block in first footer slot
# ---------------------------------------------------------------------------

class TestCheck3ContactInFirst:
    def _check(self, twig_text: str) -> bool:
        block_content = rif.extract_block_content(twig_text, "first")
        if re.search(r'contact_us|contact-us|gesso_contact_us', block_content, re.IGNORECASE):
            return True
        # Alternate: contact_us block passed as footer_content_first variable
        return bool(re.search(
            r'footer_content_first\s*[=:]\s*[^,\n]*(?:contact_us|contact-us|gesso_contact_us)'
            r'|(?:contact_us|contact-us|gesso_contact_us)[^,\n]*footer_content_first',
            twig_text, re.IGNORECASE
        ))

    def test_pass_contact_us_underscore(self):
        twig = "{% block first %}\n{{ drupal_block('contact_us') }}\n{% endblock %}"
        assert self._check(twig)

    def test_pass_contact_us_hyphen(self):
        twig = "{% block first %}\n{{ drupal_block('contact-us') }}\n{% endblock %}"
        assert self._check(twig)

    def test_pass_gesso_contact_us(self):
        twig = "{% block first %}\n{{ drupal_block('gesso_contact_us') }}\n{% endblock %}"
        assert self._check(twig)

    def test_pass_case_insensitive(self):
        twig = "{% block first %}\n{{ drupal_block('Contact_Us') }}\n{% endblock %}"
        assert self._check(twig)

    def test_fail_contact_in_second_slot(self):
        twig = (
            "{% block first %}\n  nothing here\n{% endblock %}\n"
            "{% block second %}\n  contact_us\n{% endblock %}"
        )
        assert not self._check(twig)

    def test_fail_no_contact_anywhere(self):
        twig = "{% block first %}\n  <p>Hello world</p>\n{% endblock %}"
        assert not self._check(twig)

    def test_fail_contact_outside_block(self):
        twig = "contact_us\n{% block first %}\n  nothing\n{% endblock %}"
        assert not self._check(twig)

    # Alternate approach: contact_us passed via footer_content_first variable
    def test_pass_contact_via_footer_content_first_set(self):
        twig = "{% set footer_content_first = drupal_block('contact_us') %}"
        assert self._check(twig)

    def test_pass_contact_us_hyphen_via_footer_content_first(self):
        twig = "{% set footer_content_first = drupal_block('contact-us') %}"
        assert self._check(twig)

    def test_pass_gesso_contact_us_via_footer_content_first(self):
        twig = "{% set footer_content_first = drupal_block('gesso_contact_us') %}"
        assert self._check(twig)

    def test_pass_footer_content_first_with_with_syntax(self):
        twig = "{% include 'footer.twig' with {footer_content_first: drupal_block('contact_us')} %}"
        assert self._check(twig)

    def test_fail_footer_content_first_without_contact(self):
        twig = "{% set footer_content_first = drupal_block('some_other_block') %}"
        assert not self._check(twig)

    def test_fail_contact_us_not_assigned_to_footer_content_first(self):
        twig = "{% set other_var = drupal_block('contact_us') %}"
        assert not self._check(twig)


# ---------------------------------------------------------------------------
# CHECK 4: Social links + footer menu in second slot
# ---------------------------------------------------------------------------

class TestCheck4SecondSlot:
    def _extract_second(self, twig_text: str):
        return rif.extract_block_content(twig_text, "second")

    def test_pass_both_present(self):
        twig = (
            "{% block second %}\n"
            "  {{ drupal_block('menu_social') }}\n"
            "  {{ drupal_block('gesso_footer') }}\n"
            "{% endblock %}"
        )
        second = self._extract_second(twig)
        social = bool(re.search(r'menu.social|menu-social|social', second, re.IGNORECASE))
        menu = bool(re.search(
            r'footer.*menu|gesso_footer|system_menu_block.*footer|footer.*block|menu.*footer',
            second, re.IGNORECASE))
        assert social and menu

    def test_fail_only_social_no_menu(self):
        twig = (
            "{% block second %}\n"
            "  {{ drupal_block('menu_social') }}\n"
            "{% endblock %}"
        )
        second = self._extract_second(twig)
        social = bool(re.search(r'menu.social|menu-social|social', second, re.IGNORECASE))
        menu = bool(re.search(
            r'footer.*menu|gesso_footer|system_menu_block.*footer|footer.*block|menu.*footer',
            second, re.IGNORECASE))
        assert social and not menu

    def test_fail_only_menu_no_social(self):
        twig = (
            "{% block second %}\n"
            "  {{ drupal_block('gesso_footer') }}\n"
            "{% endblock %}"
        )
        second = self._extract_second(twig)
        social = bool(re.search(r'menu.social|menu-social|social', second, re.IGNORECASE))
        menu = bool(re.search(
            r'footer.*menu|gesso_footer|system_menu_block.*footer|footer.*block|menu.*footer',
            second, re.IGNORECASE))
        assert not social and menu

    def test_fail_neither_present(self):
        twig = (
            "{% block second %}\n"
            "  <p>Nothing useful</p>\n"
            "{% endblock %}"
        )
        second = self._extract_second(twig)
        social = bool(re.search(r'menu.social|menu-social|social', second, re.IGNORECASE))
        menu = bool(re.search(
            r'footer.*menu|gesso_footer|system_menu_block.*footer|footer.*block|menu.*footer',
            second, re.IGNORECASE))
        assert not social and not menu

    def test_pass_footer_menu_pattern_variations(self):
        patterns_that_match = [
            "footer_menu",
            "gesso_footer",
            "system_menu_block--footer",
            "footer_block",
            "menu_footer",
        ]
        regex = re.compile(
            r'footer.*menu|gesso_footer|system_menu_block.*footer|footer.*block|menu.*footer',
            re.IGNORECASE,
        )
        for p in patterns_that_match:
            assert regex.search(p), f"Expected pattern to match: {p}"


# ---------------------------------------------------------------------------
# CHECK 5: Copyright in third footer slot
# ---------------------------------------------------------------------------

class TestCheck5CopyrightInThird:
    def _check(self, twig_text: str) -> bool:
        third = rif.extract_block_content(twig_text, "third")
        hardcoded_in_third = bool(re.search(r'202[0-9]\b', third))
        dynamic_in_third = bool(re.search(
            r'"now"\s*\|\s*date|\'now\'\s*\|\s*date|now\s*\|\s*date|current_year',
            third
        ))
        if dynamic_in_third:
            return True
        if not hardcoded_in_third and re.search(r'copyright', third, re.IGNORECASE):
            return True
        # Alternate: copyright content passed as footer_content_third variable
        return bool(re.search(
            r'footer_content_third\s*[=:]\s*[^,\n]*copyright'
            r'|copyright[^,\n]*footer_content_third',
            twig_text, re.IGNORECASE
        ))

    def test_pass_copyright_lowercase(self):
        twig = "{% block third %}\n  copyright\n{% endblock %}"
        assert self._check(twig)

    def test_pass_copyright_uppercase(self):
        twig = "{% block third %}\n  COPYRIGHT\n{% endblock %}"
        assert self._check(twig)

    def test_pass_copyright_symbol_pattern(self):
        twig = "{% block third %}\n  Copyright &copy; {{ \"now\"|date(\"Y\") }}\n{% endblock %}"
        assert self._check(twig)

    def test_fail_copyright_in_first_slot(self):
        twig = (
            "{% block first %}\n  copyright here\n{% endblock %}\n"
            "{% block third %}\n  nothing\n{% endblock %}"
        )
        assert not self._check(twig)

    def test_fail_no_copyright(self):
        twig = "{% block third %}\n  <p>All rights reserved</p>\n{% endblock %}"
        assert not self._check(twig)

    def test_fail_no_third_block(self):
        twig = "{% block first %}\n  copyright\n{% endblock %}"
        assert not self._check(twig)

    # Alternate approach: copyright passed via footer_content_third variable
    def test_pass_copyright_via_footer_content_third_set(self):
        twig = "{% set footer_content_third = 'Copyright ' ~ current_year %}"
        assert self._check(twig)

    def test_pass_copyright_via_footer_content_third_with_syntax(self):
        twig = "{% include 'footer.twig' with {footer_content_third: 'Copyright ' ~ current_year} %}"
        assert self._check(twig)

    def test_pass_copyright_uppercase_via_footer_content_third(self):
        twig = "{% set footer_content_third = 'COPYRIGHT ' ~ current_year %}"
        assert self._check(twig)

    def test_fail_footer_content_third_without_copyright(self):
        twig = "{% set footer_content_third = 'All rights reserved' %}"
        assert not self._check(twig)

    def test_fail_copyright_not_assigned_to_footer_content_third(self):
        twig = "{% set other_var = 'Copyright 2024' %}"
        assert not self._check(twig)

    # Dynamic year patterns in third slot
    def test_pass_now_date_Y_in_third_slot(self):
        twig = '{% block third %}\n  Copyright {{ "now"|date("Y") }}\n{% endblock %}'
        assert self._check(twig)

    def test_pass_now_date_Y_without_copyright_text(self):
        # {{ "now"|date("Y") }} alone in third slot counts as a valid copyright year block
        twig = '{% block third %}\n  {{ "now"|date("Y") }}\n{% endblock %}'
        assert self._check(twig)

    def test_fail_hardcoded_year_in_third_slot(self):
        twig = "{% block third %}\n  Copyright 2024\n{% endblock %}"
        assert not self._check(twig)


# ---------------------------------------------------------------------------
# CHECK 6: Copyright year is dynamic
# ---------------------------------------------------------------------------

class TestCheck6DynamicYear:
    def _php_dynamic(self, content: str) -> bool:
        return bool(re.search(r"date\(['\"]Y['\"]|current_year|year.*date", content))

    def _twig_dynamic(self, content: str) -> bool:
        return bool(re.search(r"""current_year|["']now["']\s*\|date|now\s*\|date""", content))

    def _hardcoded(self, content: str) -> bool:
        for line in content.splitlines():
            if re.search(r'202[0-9]\b', line) and re.search(r'copyright|year', line, re.IGNORECASE):
                return True
        return False

    # PHP dynamic patterns
    def test_php_date_Y_single_quotes(self):
        assert self._php_dynamic("echo date('Y');")

    def test_php_date_Y_double_quotes(self):
        assert self._php_dynamic('echo date("Y");')

    def test_php_current_year_variable(self):
        assert self._php_dynamic("$current_year = 2024;")

    def test_php_year_date_pattern(self):
        assert self._php_dynamic("$year = date('Y');")

    def test_php_no_dynamic_year(self):
        assert not self._php_dynamic("echo '2024';")

    # Twig dynamic patterns
    def test_twig_current_year_variable(self):
        content = "{{ current_year }}\ncopyright year"
        assert self._twig_dynamic(content)

    def test_twig_now_pipe_date(self):
        content = "{{'now'|date('Y')}}\ncopyright year"
        assert self._twig_dynamic(content)

    def test_twig_now_pipe_date_no_quotes(self):
        content = "{{ now|date('Y') }}\ncopyright year"
        assert self._twig_dynamic(content)

    def test_twig_now_date_Y_double_quotes(self):
        content = '<p class="l-footer__copyright">&copy; {{ "now"|date("Y") }} All rights reserved.</p>'
        assert self._twig_dynamic(content)

    def test_twig_current_year_alone_passes(self):
        content = "{{ current_year }}"
        assert self._twig_dynamic(content)

    def test_twig_no_dynamic_year(self):
        content = "<p>Copyright 2024</p>"
        assert not self._twig_dynamic(content)

    # Hardcoded year detection
    def test_hardcoded_year_in_copyright_line(self):
        content = "<p>Copyright 2024 MyCompany</p>"
        assert self._hardcoded(content)

    def test_hardcoded_year_in_year_label(self):
        content = "Year: 2023"
        assert self._hardcoded(content)

    def test_not_hardcoded_year_without_copyright_keyword(self):
        content = "<p>2024</p>"
        assert not self._hardcoded(content)

    def test_not_hardcoded_for_dynamic_reference(self):
        # Dynamic twig — no literal 202X next to copyright
        content = "{{ current_year }} copyright"
        assert not self._hardcoded(content)

    def test_hardcoded_years_full_range(self):
        for year in range(2020, 2030):
            content = f"Copyright {year} Inc."
            assert self._hardcoded(content), f"Should detect hardcoded year {year}"


# ---------------------------------------------------------------------------
# CHECK 7: footer.twig included/embedded
# ---------------------------------------------------------------------------

class TestCheck7FooterTwigRef:
    _pattern = re.compile(r'footer\.twig|@layouts/footer|embed.*footer|include.*footer\.twig')

    def test_pass_footer_twig_literal(self):
        assert self._pattern.search("{% include 'footer.twig' %}")

    def test_pass_at_layouts_footer(self):
        assert self._pattern.search("{% embed '@layouts/footer' %}")

    def test_pass_embed_footer_generic(self):
        assert self._pattern.search("{% embed 'components/footer' %}")

    def test_pass_include_footer_twig(self):
        assert self._pattern.search("{% include 'layout/footer.twig' %}")

    def test_fail_no_footer_reference(self):
        assert not self._pattern.search("{% include 'header.twig' %}")

    def test_fail_footer_without_twig_extension_or_layouts(self):
        # "footer" alone with no qualifying context should not match
        assert not self._pattern.search("{% block footer %}")

    def test_fail_embed_without_footer_keyword(self):
        assert not self._pattern.search("{% embed 'hero.twig' %}")


# ---------------------------------------------------------------------------
# Integration: review_worktree with a fully passing fake worktree
# ---------------------------------------------------------------------------

class TestReviewWorktreeIntegration:
    def _build_full_worktree(self, tmp_path: Path) -> Path:
        """Create a worktree that should pass all 7 checks."""
        gesso = rif.GESSO_THEME
        footer_twig = (
            "{% block first %}\n"
            "  {{ drupal_block('contact_us') }}\n"
            "{% endblock %}\n"
            "{% block second %}\n"
            "  {{ drupal_block('menu_social') }}\n"
            "  {{ drupal_block('gesso_footer') }}\n"
            "{% endblock %}\n"
            "{% block third %}\n"
            "  Copyright {{ current_year }}\n"
            "{% endblock %}\n"
        )
        files = {
            # Check 1
            "config/sync/block_content.type.footer.yml": "id: footer\n",
            # Check 2
            f"{gesso}/templates/layout/region--footer.html.twig": footer_twig,
            f"{gesso}/templates/navigation/menu--footer.html.twig": (
                "{% include '@gesso/menu-social.twig' %}"
            ),
            # Check 7
            f"{gesso}/templates/layout/page.html.twig": (
                "{% include 'footer.twig' %}"
            ),
        }
        return make_worktree(tmp_path, files)

    def test_fully_passing_worktree(self, tmp_path):
        wt = self._build_full_worktree(tmp_path)
        worker_prefix = "worker"
        index = 1
        worker_dir = tmp_path.parent / f"{worker_prefix}-01"
        # symlink or just reuse tmp_path by patching PARENT_DIR
        with patch.object(rif, "PARENT_DIR", tmp_path.parent), \
             patch("builtins.print"):
            # Rename the tmp_path to match the expected worker name
            wt.rename(worker_dir)
            result = rif.review_worktree(index, worker_prefix)
        assert result is True

    def test_missing_worktree_dir_returns_false(self, tmp_path):
        with patch.object(rif, "PARENT_DIR", tmp_path), \
             patch("builtins.print"):
            result = rif.review_worktree(99, "nonexistent-worker")
        assert result is False
