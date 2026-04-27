"""Tests for today/tomorrow keyword resolution, relative offsets, and span syntax."""

from datetime import datetime, timezone

from todoosy import parse, format
from todoosy.query import query_upcoming
from todoosy.types import Settings


# 2026-04-27 is a Monday. Anchored UTC instant.
FIXED_NOW = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)


class TestKeywords:
    def test_today_after_due(self):
        r = parse('- Task (due today)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.due == '2026-04-27'
        assert r.ast.items[0].metadata.due_soft is None

    def test_tomorrow_after_due(self):
        r = parse('- Task (due tomorrow)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.due == '2026-04-28'

    def test_soft_tomorrow(self):
        r = parse('- Task (~tomorrow)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.due == '2026-04-28'
        assert r.ast.items[0].metadata.due_soft is True

    def test_today_case_insensitive(self):
        r = parse('- Task (TODAY)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.due == '2026-04-27'

    def test_formatter_emits_concrete_dates(self):
        out = format('- Task (due today)\n# Misc\n', now=FIXED_NOW)
        assert 'due 2026-04-27' in out
        assert 'today' not in out


class TestRelativeOffsets:
    def test_digit_week_short(self):
        r = parse('- Task (due 2w)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.due == '2026-05-11'

    def test_digit_days_long(self):
        r = parse('- Task (due 3 days)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.due == '2026-04-30'

    def test_in_prefix_optional(self):
        a = parse('- A (due in 2 weeks)\n# Misc\n', now=FIXED_NOW)
        b = parse('- B (due 2 weeks)\n# Misc\n', now=FIXED_NOW)
        assert a.ast.items[0].metadata.due == b.ast.items[0].metadata.due

    def test_from_now_suffix_optional(self):
        a = parse('- A (due 2 weeks from now)\n# Misc\n', now=FIXED_NOW)
        b = parse('- B (due 2 weeks)\n# Misc\n', now=FIXED_NOW)
        assert a.ast.items[0].metadata.due == b.ast.items[0].metadata.due

    def test_number_words_1_to_31(self):
        a = parse('- A (due in two weeks)\n# Misc\n', now=FIXED_NOW)
        assert a.ast.items[0].metadata.due == '2026-05-11'
        b = parse('- B (due in twenty-one days)\n# Misc\n', now=FIXED_NOW)
        assert b.ast.items[0].metadata.due == '2026-05-18'
        c = parse('- C (due in thirty-one days)\n# Misc\n', now=FIXED_NOW)
        assert c.ast.items[0].metadata.due == '2026-05-28'

    def test_compound_number_word_with_space(self):
        r = parse('- Task (due in twenty one days)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.due == '2026-05-18'

    def test_months_calendar_aware(self):
        jan31 = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
        r = parse('- Task (due in 1 month)\n# Misc\n', now=jan31)
        assert r.ast.items[0].metadata.due == '2026-02-28'

    def test_bare_2d_remains_estimate(self):
        r = parse('- Task (2d)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.due is None
        assert r.ast.items[0].metadata.estimate_minutes == 960

    def test_in_progress_still_progress(self):
        r = parse('- Task (in progress)\n# Misc\n', now=FIXED_NOW)
        assert r.ast.items[0].metadata.progress == 'in progress'
        assert r.ast.items[0].metadata.due is None


class TestWindowSpan:
    def test_iso_span_standalone(self):
        r = parse('- Task (2026-04-24~2026-05-08)\n# Misc\n', now=FIXED_NOW)
        m = r.ast.items[0].metadata
        assert m.due_start == '2026-04-24'
        assert m.due == '2026-05-08'
        assert m.due_soft is True

    def test_iso_span_after_due(self):
        r = parse('- Task (due 2026-04-24~2026-05-08)\n# Misc\n', now=FIXED_NOW)
        m = r.ast.items[0].metadata
        assert m.due_start == '2026-04-24'
        assert m.due == '2026-05-08'

    def test_keyword_plus_relative_span(self):
        r = parse('- Task (today~2w)\n# Misc\n', now=FIXED_NOW)
        m = r.ast.items[0].metadata
        assert m.due_start == '2026-04-27'
        assert m.due == '2026-05-11'

    def test_text_date_span(self):
        r = parse('- Task (Apr 24 2026~May 8 2026)\n# Misc\n', now=FIXED_NOW)
        m = r.ast.items[0].metadata
        assert m.due_start == '2026-04-24'
        assert m.due == '2026-05-08'

    def test_formatter_emits_span(self):
        out = format('- Task (Apr 24 2026~May 8 2026)\n# Misc\n', now=FIXED_NOW)
        assert 'due 2026-04-24~2026-05-08' in out

    def test_query_upcoming_sorts_spans_by_start(self):
        text = '# Tasks\n- Span (2026-05-01~2026-06-01)\n- Hard (due 2026-05-15)\n# Misc\n'
        result = query_upcoming(text, now=FIXED_NOW)
        # Span starts 2026-05-01 (earlier than hard 2026-05-15) → sorts first.
        assert result.items[0].path.endswith('Span')


class TestTimezoneAwareToday:
    def test_settings_timezone_affects_today(self):
        # 2026-04-27 23:00 UTC → still 2026-04-27 in LA, already 2026-04-28 in Tokyo.
        instant = datetime(2026, 4, 27, 23, 0, tzinfo=timezone.utc)
        s_la = Settings(timezone='America/Los_Angeles')
        s_tokyo = Settings(timezone='Asia/Tokyo')

        a = parse('- Task (due today)\n# Misc\n', now=instant, settings=s_la)
        b = parse('- Task (due today)\n# Misc\n', now=instant, settings=s_tokyo)

        assert a.ast.items[0].metadata.due == '2026-04-27'
        assert b.ast.items[0].metadata.due == '2026-04-28'

    def test_utc_default_when_no_timezone_setting(self):
        instant = datetime(2026, 4, 27, 23, 30, tzinfo=timezone.utc)
        r = parse('- Task (due today)\n# Misc\n', now=instant)
        assert r.ast.items[0].metadata.due == '2026-04-27'
