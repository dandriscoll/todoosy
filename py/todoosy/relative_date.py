"""
Todoosy Relative Date Parser

Mirror of `js/src/relative-date.ts`. Resolves keywords ("today", "tomorrow")
and relative offsets ("2 weeks", "in 3 days", "two months") to concrete ISO
dates. Resolution always happens at parse time; the persisted form on disk
is always a concrete date.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional, Tuple

from dateutil.relativedelta import relativedelta

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from .types import Settings


@dataclass(frozen=True)
class ResolvedNow:
    """The user's "today" as an ISO YYYY-MM-DD string (in their TZ)."""
    today_iso: str


_NUMBER_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23, 'twenty-four': 24,
    'twenty-five': 25, 'twenty-six': 26, 'twenty-seven': 27, 'twenty-eight': 28,
    'twenty-nine': 29, 'thirty': 30, 'thirty-one': 31,
}

_TENS = {'twenty', 'thirty'}
_ONES_AFTER_TENS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
}

_DAY_UNITS = {'d', 'day', 'days'}
_WEEK_UNITS = {'w', 'wk', 'wks', 'week', 'weeks'}
_MONTH_UNITS = {'month', 'months'}
_YEAR_UNITS = {'y', 'yr', 'yrs', 'year', 'years'}

_FUSED_OFFSET_RE = re.compile(r'^(\d+)([a-z]+)$', re.IGNORECASE)


def resolve_now(now: Optional[datetime] = None, settings: Optional[Settings] = None) -> ResolvedNow:
    instant = now if now is not None else datetime.now(tz=timezone.utc)
    if instant.tzinfo is None:
        # Treat naive as UTC for predictability.
        instant = instant.replace(tzinfo=timezone.utc)

    tz_name = settings.timezone if settings and settings.timezone else 'UTC'
    if ZoneInfo is None:
        local = instant.astimezone(timezone.utc).date()
    else:
        try:
            local = instant.astimezone(ZoneInfo(tz_name)).date()
        except Exception:
            local = instant.astimezone(timezone.utc).date()
    return ResolvedNow(today_iso=local.isoformat())


def _parse_iso(iso: str) -> date:
    y, m, d = (int(x) for x in iso.split('-'))
    return date(y, m, d)


def _add_days(iso: str, days: int) -> str:
    return (_parse_iso(iso) + relativedelta(days=days)).isoformat()


def _add_months(iso: str, months: int) -> str:
    # relativedelta is calendar-aware: Jan 31 + 1 month → Feb 28/29 (clipped).
    return (_parse_iso(iso) + relativedelta(months=months)).isoformat()


def _add_years(iso: str, years: int) -> str:
    return (_parse_iso(iso) + relativedelta(years=years)).isoformat()


def resolve_keyword(word: str, now: ResolvedNow) -> Optional[str]:
    w = word.lower()
    if w == 'today':
        return now.today_iso
    if w == 'tomorrow':
        return _add_days(now.today_iso, 1)
    return None


def _try_parse_number_word(parts: list[str], index: int) -> Optional[Tuple[int, int]]:
    """Returns (value, parts_consumed) or None."""
    if index >= len(parts):
        return None
    w0 = parts[index].lower()
    # Try compound form ("twenty one") before the simple lookup so it isn't
    # pre-empted by the value of "twenty".
    if w0 in _TENS and index + 1 < len(parts):
        w1 = parts[index + 1].lower()
        if w1 in _ONES_AFTER_TENS:
            total = _NUMBER_WORDS[w0] + _ONES_AFTER_TENS[w1]
            if total <= 31:
                return total, 2
    if w0 in _NUMBER_WORDS:
        return _NUMBER_WORDS[w0], 1
    return None


def _classify_unit(word: str) -> Optional[str]:
    w = word.lower()
    if w in _DAY_UNITS:
        return 'days'
    if w in _WEEK_UNITS:
        return 'weeks'
    if w in _MONTH_UNITS:
        return 'months'
    if w in _YEAR_UNITS:
        return 'years'
    return None


def _apply_offset(now: ResolvedNow, count: int, kind: str) -> str:
    if kind == 'days':
        return _add_days(now.today_iso, count)
    if kind == 'weeks':
        return _add_days(now.today_iso, count * 7)
    if kind == 'months':
        return _add_months(now.today_iso, count)
    if kind == 'years':
        return _add_years(now.today_iso, count)
    raise ValueError(f'unknown kind {kind!r}')


def _try_consume_from_suffix(parts: list[str], index: int) -> int:
    if index + 1 < len(parts):
        a = parts[index].lower()
        b = parts[index + 1].lower()
        if a == 'from' and b in ('now', 'today'):
            return 2
    return 0


def try_parse_relative(parts: list[str], index: int, now: ResolvedNow) -> Optional[Tuple[str, int]]:
    """Returns (iso_date, parts_consumed) or None."""
    if index >= len(parts):
        return None

    cursor = index
    consumed_in = 0
    if parts[cursor].lower() == 'in':
        consumed_in = 1
        cursor += 1
        if cursor >= len(parts):
            return None

    # Fused form: "2w", "2years", etc. Estimate units (m/h/d) handled elsewhere
    # — fused day form is intentionally rejected here so bare `2d` keeps
    # estimate semantics.
    fused = _FUSED_OFFSET_RE.match(parts[cursor])
    if fused:
        count = int(fused.group(1))
        kind = _classify_unit(fused.group(2))
        if kind is None or kind == 'days':
            return None
        after = cursor + 1
        suffix = _try_consume_from_suffix(parts, after)
        return _apply_offset(now, count, kind), consumed_in + 1 + suffix

    # Split form: number then unit
    digits = re.match(r'^(\d+)$', parts[cursor])
    if digits:
        count = int(digits.group(1))
        number_consumed = 1
    else:
        word = _try_parse_number_word(parts, cursor)
        if word is None:
            return None
        count, number_consumed = word

    unit_index = cursor + number_consumed
    if unit_index >= len(parts):
        return None
    kind = _classify_unit(parts[unit_index])
    if kind is None:
        return None
    if kind == 'days' and parts[unit_index].lower() == 'd':
        # Reject the bare `d` split form for clarity; require day/days.
        return None

    after = unit_index + 1
    suffix = _try_consume_from_suffix(parts, after)
    return _apply_offset(now, count, kind), consumed_in + number_consumed + 1 + suffix
