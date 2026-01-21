"""
Todoosy Golden Tests - Using shared test files
"""

import json
import os
from pathlib import Path

import pytest

from todoosy import (
    parse,
    format,
    lint,
    query_upcoming,
    query_misc,
    parse_scheme,
    parse_settings,
)
from todoosy.linter import lint_scheme, lint_settings

# Get test data directory
TEST_DIR = Path(__file__).parent.parent.parent / 'testdata'


def get_test_cases():
    """Get all test case directories."""
    if not TEST_DIR.exists():
        return []
    return sorted([d.name for d in TEST_DIR.iterdir() if d.is_dir()])


def load_file(test_case: str, filename: str) -> str | None:
    """Load a file from a test case directory."""
    file_path = TEST_DIR / test_case / filename
    if file_path.exists():
        return file_path.read_text()
    return None


def load_json(test_case: str, filename: str):
    """Load a JSON file from a test case directory."""
    content = load_file(test_case, filename)
    if content:
        return json.loads(content)
    return None


class TestParser:
    @pytest.mark.parametrize('test_case', get_test_cases())
    def test_parse(self, test_case):
        input_md = load_file(test_case, 'input.md')
        expected_ast = load_json(test_case, 'expected_ast.json')

        if not input_md or not expected_ast:
            pytest.skip(f'Missing input or expected_ast for {test_case}')

        result = parse(input_md)
        ast = result.ast

        # Compare items count
        assert len(ast.items) == len(expected_ast['items'])

        # Compare each item's essential properties
        for i, (actual, expected) in enumerate(zip(ast.items, expected_ast['items'])):
            assert actual.type == expected['type'], f"Item {i} type mismatch"
            assert actual.title_text == expected['title_text'], f"Item {i} title_text mismatch"
            assert actual.metadata.due == expected['metadata']['due'], f"Item {i} due mismatch"
            assert actual.metadata.priority == expected['metadata']['priority'], f"Item {i} priority mismatch"
            assert actual.metadata.estimate_minutes == expected['metadata']['estimate_minutes'], f"Item {i} estimate mismatch"
            assert actual.comments == expected['comments'], f"Item {i} comments mismatch"
            assert len(actual.children) == len(expected['children']), f"Item {i} children count mismatch"

        # Compare root_ids count
        assert len(ast.root_ids) == len(expected_ast['root_ids'])


class TestFormatter:
    @pytest.mark.parametrize('test_case', get_test_cases())
    def test_format(self, test_case):
        input_md = load_file(test_case, 'input.md')
        expected_formatted = load_file(test_case, 'expected_formatted.md')

        if not input_md or not expected_formatted:
            pytest.skip(f'Missing input or expected_formatted for {test_case}')

        formatted = format(input_md)
        assert formatted == expected_formatted


class TestLinter:
    @pytest.mark.parametrize('test_case', get_test_cases())
    def test_lint(self, test_case):
        input_md = load_file(test_case, 'input.md')
        expected_warnings = load_json(test_case, 'expected_warnings.json')
        scheme_text = load_file(test_case, 'settings.md')
        scheme = parse_scheme(scheme_text) if scheme_text else None

        if not input_md or not expected_warnings:
            pytest.skip(f'Missing input or expected_warnings for {test_case}')

        result = lint(input_md, scheme)

        actual_codes = sorted([w.code for w in result.warnings])
        expected_codes = sorted([w['code'] for w in expected_warnings.get('warnings', [])])
        assert actual_codes == expected_codes


class TestQueryUpcoming:
    @pytest.mark.parametrize('test_case', get_test_cases())
    def test_query_upcoming(self, test_case):
        input_md = load_file(test_case, 'input.md')
        expected_upcoming = load_json(test_case, 'expected_upcoming.json')
        scheme_text = load_file(test_case, 'settings.md')
        scheme = parse_scheme(scheme_text) if scheme_text else None

        if not input_md or not expected_upcoming:
            pytest.skip(f'Missing input or expected_upcoming for {test_case}')

        result = query_upcoming(input_md, scheme)

        assert len(result.items) == len(expected_upcoming['items'])

        for actual, expected in zip(result.items, expected_upcoming['items']):
            assert actual.due == expected['due']
            assert actual.priority == expected['priority']
            if 'priority_label' in expected:
                assert actual.priority_label == expected['priority_label']


class TestQueryMisc:
    @pytest.mark.parametrize('test_case', get_test_cases())
    def test_query_misc(self, test_case):
        input_md = load_file(test_case, 'input.md')
        expected_misc = load_json(test_case, 'expected_misc.json')

        if not input_md or not expected_misc:
            pytest.skip(f'Missing input or expected_misc for {test_case}')

        result = query_misc(input_md)

        assert len(result.items) == len(expected_misc['items'])

        for actual, expected in zip(result.items, expected_misc['items']):
            assert actual.title_text == expected['title_text']


class TestSettingsParser:
    @pytest.mark.parametrize('test_case', get_test_cases())
    def test_parse_settings(self, test_case):
        settings_text = load_file(test_case, 'settings.md')
        expected_settings = load_json(test_case, 'expected_settings.json')

        if not settings_text or not expected_settings:
            return  # Settings are optional

        settings = parse_settings(settings_text)

        assert settings.timezone == expected_settings['timezone']
        assert settings.priorities == expected_settings['priorities']
        if 'calendar_format' in expected_settings:
            assert settings.calendar_format == expected_settings['calendar_format']

    @pytest.mark.parametrize('test_case', get_test_cases())
    def test_lint_settings(self, test_case):
        settings_text = load_file(test_case, 'settings.md')
        expected_settings_warnings = load_json(test_case, 'expected_settings_warnings.json')

        if not settings_text or expected_settings_warnings is None:
            return  # Settings warnings are optional

        settings = parse_settings(settings_text)
        result = lint_settings(settings)

        actual_codes = sorted([w.code for w in result.warnings])
        expected_codes = sorted([w['code'] for w in expected_settings_warnings])
        assert actual_codes == expected_codes


class TestEdgeCases:
    def test_empty_document(self):
        result = parse('')
        assert len(result.ast.items) == 0
        assert len(result.ast.root_ids) == 0

    def test_whitespace_only(self):
        result = parse('   \n\n   ')
        assert len(result.ast.items) == 0

    def test_numbered_lists(self):
        result = parse('# Tasks\n\n1. First task\n2. Second task')
        assert len(result.ast.items) == 3
        assert result.ast.items[1].title_text == 'First task'
        assert result.ast.items[2].title_text == 'Second task'

    def test_asterisk_lists(self):
        result = parse('# Tasks\n\n* Task one\n* Task two')
        assert len(result.ast.items) == 3
        assert result.ast.items[1].title_text == 'Task one'

    def test_2digit_year_dates(self):
        result = parse('- Task (due 01/15/26)')
        assert result.ast.items[0].metadata.due == '2026-01-15'

    def test_estimate_days(self):
        result = parse('- Task (2d)')
        assert result.ast.items[0].metadata.estimate_minutes == 960

    def test_formatter_adds_misc(self):
        formatted = format('# Work\n\n- Task')
        assert '# Misc' in formatted

    def test_formatter_preserves_non_metadata_parens(self):
        formatted = format('# Work\n\n- Call John (CEO)\n\n# Misc\n')
        assert '(CEO)' in formatted

    def test_linter_warns_missing_misc(self):
        result = lint('# Work\n\n- Task')
        assert any(w.code == 'MISC_MISSING' for w in result.warnings)

    def test_linter_no_warnings_valid_doc(self):
        result = lint('# Work\n\n- Task (due 2026-01-15 p1 2h)\n\n# Misc\n')
        assert len(result.warnings) == 0

    def test_scheme_empty(self):
        scheme = parse_scheme('')
        assert scheme.timezone is None
        assert scheme.priorities == {}

    def test_scheme_timezone_only(self):
        scheme = parse_scheme('# Timezone\n\nEurope/London')
        assert scheme.timezone == 'Europe/London'
        assert scheme.priorities == {}

    def test_scheme_various_bullets(self):
        scheme = parse_scheme('''
# Priorities

- P0 - Critical
* P1 - High
P2 - Medium
''')
        assert scheme.priorities['0'] == 'Critical'
        assert scheme.priorities['1'] == 'High'
        assert scheme.priorities['2'] == 'Medium'

    def test_scheme_calendar_format(self):
        scheme = parse_scheme('''
# Calendar Format

mm/dd/yyyy
''')
        assert scheme.calendar_format == 'mm/dd/yyyy'

    def test_scheme_calendar_format_default(self):
        scheme = parse_scheme('')
        assert scheme.calendar_format == 'yyyy-mm-dd'

    def test_lint_scheme_invalid_format(self):
        scheme = parse_scheme('''
# Calendar Format

invalid-format
''')
        result = lint_scheme(scheme)
        assert any(w.code == 'INVALID_CALENDAR_FORMAT' for w in result.warnings)

    def test_lint_scheme_valid_format(self):
        scheme = parse_scheme('''
# Calendar Format

dd/mm/yyyy
''')
        result = lint_scheme(scheme)
        assert len(result.warnings) == 0

    def test_day_first_text_date(self):
        result = parse('- Task (due 15 January)')
        assert result.ast.items[0].metadata.due is not None
        assert result.ast.items[0].metadata.due.endswith('-01-15')

    def test_day_first_text_date_with_year(self):
        result = parse('- Task (due 20 Feb 2027)')
        assert result.ast.items[0].metadata.due == '2027-02-20'

    def test_soft_date_with_tilde_prefix(self):
        result = parse('- Task (due ~2026-01-25)')
        assert result.ast.items[0].metadata.due == '2026-01-25'
        assert result.ast.items[0].metadata.due_soft is True

    def test_soft_text_date_with_tilde_prefix(self):
        result = parse('- Task (due ~Jan 30)')
        assert result.ast.items[0].metadata.due == '2026-01-30'
        assert result.ast.items[0].metadata.due_soft is True

    def test_standalone_soft_date_with_tilde_prefix(self):
        result = parse('- Task (~2026-02-10)')
        assert result.ast.items[0].metadata.due == '2026-02-10'
        assert result.ast.items[0].metadata.due_soft is True

    def test_standalone_soft_text_date_with_tilde_prefix(self):
        result = parse('- Task (~Feb 15)')
        assert result.ast.items[0].metadata.due == '2026-02-15'
        assert result.ast.items[0].metadata.due_soft is True

    def test_non_soft_dates_have_null_due_soft(self):
        result = parse('- Task (due 2026-01-20)')
        assert result.ast.items[0].metadata.due == '2026-01-20'
        assert result.ast.items[0].metadata.due_soft is None

    def test_formatter_preserves_soft_date_tilde_prefix(self):
        input_text = '# Work\n\n- Task (due ~2026-01-25)\n\n# Misc\n'
        formatted = format(input_text)
        assert '(due ~2026-01-25)' in formatted

    def test_scheme_formatting_style(self):
        scheme = parse_scheme('''
# Formatting Style

balanced
''')
        assert scheme.formatting_style == 'balanced'

    def test_scheme_formatting_style_default(self):
        scheme = parse_scheme('')
        assert scheme.formatting_style == 'roomy'

    def test_lint_scheme_invalid_formatting_style(self):
        scheme = parse_scheme('''
# Formatting Style

invalid-style
''')
        result = lint_scheme(scheme)
        assert any(w.code == 'INVALID_FORMATTING_STYLE' for w in result.warnings)

    def test_lint_scheme_valid_formatting_style(self):
        scheme = parse_scheme('''
# Formatting Style

tight
''')
        result = lint_scheme(scheme)
        assert len(result.warnings) == 0

    def test_roomy_style_adds_blank_lines_around_all_headings(self):
        input_text = '# Work\n\n## Sub\n\n- Task\n\n# Misc\n'
        scheme = {'timezone': None, 'priorities': {}, 'misc': 'todoosy.md/Misc', 'calendar_format': 'yyyy-mm-dd', 'formatting_style': 'roomy'}
        # Create a Scheme object
        from todoosy.types import Scheme
        scheme_obj = Scheme(**scheme)
        formatted = format(input_text, scheme_obj)
        assert '## Sub\n\n- Task' in formatted

    def test_balanced_style_adds_blank_lines_only_around_top_level_headings(self):
        input_text = '# Work\n\n## Sub\n\n- Task\n\n# Misc\n'
        from todoosy.types import Scheme
        scheme_obj = Scheme(timezone=None, priorities={}, misc='todoosy.md/Misc', calendar_format='yyyy-mm-dd', formatting_style='balanced')
        formatted = format(input_text, scheme_obj)
        assert '## Sub\n- Task' in formatted

    def test_tight_style_removes_all_blank_lines_around_headings(self):
        input_text = '# Work\n\n## Sub\n\n- Task\n\n# Misc\n'
        from todoosy.types import Scheme
        scheme_obj = Scheme(timezone=None, priorities={}, misc='todoosy.md/Misc', calendar_format='yyyy-mm-dd', formatting_style='tight')
        formatted = format(input_text, scheme_obj)
        assert '# Work\n## Sub\n- Task' in formatted


class TestExtendedSettings:
    def test_parses_single_value_extended_setting(self):
        settings = parse_settings('''
# Timezone

America/Denver

# UI Color

blue
''')
        assert settings.timezone == 'America/Denver'
        assert settings.extended['UI Color'] == 'blue'

    def test_parses_list_extended_setting(self):
        settings = parse_settings('''
# Tags

- work
- personal
- urgent
''')
        assert settings.extended['Tags'] == ['work', 'personal', 'urgent']

    def test_parses_key_value_extended_setting(self):
        settings = parse_settings('''
# Theme Colors

background - #ffffff
foreground - #000000
accent - #0066cc
''')
        assert settings.extended['Theme Colors'] == {
            'background': '#ffffff',
            'foreground': '#000000',
            'accent': '#0066cc',
        }

    def test_preserves_original_capitalization(self):
        settings = parse_settings('''
# My Custom Setting

value
''')
        assert settings.extended['My Custom Setting'] == 'value'
        assert 'my custom setting' not in settings.extended

    def test_ignores_empty_extended_settings(self):
        settings = parse_settings('''
# Empty Setting

# Non-empty Setting

value
''')
        assert 'Empty Setting' not in settings.extended
        assert settings.extended['Non-empty Setting'] == 'value'
