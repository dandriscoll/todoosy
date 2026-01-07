"""
Todoosy Linter
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .parser import parse
from .types import Warning, Scheme

VALID_DATE_FORMATS = [
    re.compile(r'^\d{4}-\d{2}-\d{2}$'),           # YYYY-MM-DD
    re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$'),       # MM/DD/YYYY
    re.compile(r'^\d{1,2}/\d{1,2}/\d{2}$'),       # MM/DD/YY
]

MONTH_NAMES = {
    'january', 'jan',
    'february', 'feb',
    'march', 'mar',
    'april', 'apr',
    'may',
    'june', 'jun',
    'july', 'jul',
    'august', 'aug',
    'september', 'sep',
    'october', 'oct',
    'november', 'nov',
    'december', 'dec',
}

# Regex for text dates: Month Day or Month Day Year
TEXT_DATE_REGEX = re.compile(
    r'^(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+(\d{1,2})(?:\s+(\d{4}))?$',
    re.IGNORECASE
)


@dataclass
class LintResult:
    warnings: list[Warning] = field(default_factory=list)


def is_valid_date(date_str: str) -> bool:
    """Check if a date string is in a valid format."""
    # Check standard formats
    if any(regex.match(date_str) for regex in VALID_DATE_FORMATS):
        return True
    # Check text date format
    match = TEXT_DATE_REGEX.match(date_str)
    if match:
        day = int(match.group(2))
        return 1 <= day <= 31
    return False


def lint(text: str, scheme: Optional[Scheme] = None) -> LintResult:
    """Lint a todoosy document."""
    result = parse(text)
    ast = result.ast
    warnings: list[Warning] = []
    lines = text.split('\n')

    misc_section_line = None
    misc_section_span = None
    headings_after_misc: list[tuple[int, tuple[int, int]]] = []

    # Check each item
    for item in ast.items:
        raw_line = item.raw_line

        # Check for Misc section
        if item.type == 'heading':
            if misc_section_line is not None:
                # Any heading after Misc (including duplicate Misc) is an error
                headings_after_misc.append((item.line, item.item_span))
            elif item.title_text == 'Misc' and item.level == 1:
                misc_section_line = item.line
                misc_section_span = item.item_span

        # Check for invalid date formats in parentheses
        paren_pattern = re.compile(r'\(([^)]+)\)')
        for match in paren_pattern.finditer(raw_line):
            content = match.group(1)
            paren_start = item.item_span[0] + match.start()

            # Check for due dates - try text date format first (captures more), then standard format
            # Text date: due Month Day [Year]
            text_due_pattern = re.compile(
                r'\bdue\s+((?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+\d{1,2}(?:\s+\d{4})?)',
                re.IGNORECASE
            )
            text_due_indices: set[int] = set()
            for text_due_match in text_due_pattern.finditer(content):
                text_due_indices.add(text_due_match.start())
                date_str = text_due_match.group(1)
                if not is_valid_date(date_str):
                    token_start = paren_start + 1 + text_due_match.start()
                    warnings.append(Warning(
                        code='INVALID_DATE_FORMAT',
                        message=f'Invalid due date format: {date_str}',
                        line=item.line,
                        column=token_start - item.item_span[0] + 1,
                        span=(token_start + 4, token_start + 4 + len(date_str)),
                    ))

            # Standard date formats (single token)
            due_pattern = re.compile(r'\bdue\s+([^\s,)]+)', re.IGNORECASE)
            for due_match in due_pattern.finditer(content):
                # Skip if this was already matched as a text date
                if due_match.start() in text_due_indices:
                    continue

                date_str = due_match.group(1)
                # Skip if this looks like the start of a text date (month name)
                if date_str.lower() in MONTH_NAMES:
                    continue

                if not is_valid_date(date_str):
                    token_start = paren_start + 1 + due_match.start()
                    warnings.append(Warning(
                        code='INVALID_DATE_FORMAT',
                        message=f'Invalid due date format: {date_str}',
                        line=item.line,
                        column=token_start - item.item_span[0] + 1,
                        span=(token_start + 4, token_start + 4 + len(date_str)),
                    ))

            # Check for multiple due dates
            all_due_dates: list[tuple[str, tuple[int, int]]] = []
            for p_match in paren_pattern.finditer(raw_line):
                p_content = p_match.group(1)
                p_start = item.item_span[0] + p_match.start()

                # Check text dates first
                text_due_positions: set[int] = set()
                for tdm in text_due_pattern.finditer(p_content):
                    ds = tdm.group(1)
                    if is_valid_date(ds):
                        text_due_positions.add(tdm.start())
                        d_start = p_start + 1 + tdm.start()
                        all_due_dates.append((ds, (d_start, d_start + len(tdm.group(0)))))

                # Check standard dates
                for dm in due_pattern.finditer(p_content):
                    # Skip if already matched as text date
                    if dm.start() in text_due_positions:
                        continue
                    ds = dm.group(1)
                    # Skip if it's a month name (part of text date)
                    if ds.lower() in MONTH_NAMES:
                        continue
                    if is_valid_date(ds):
                        d_start = p_start + 1 + dm.start()
                        all_due_dates.append((ds, (d_start, d_start + len(dm.group(0)))))

            if len(all_due_dates) > 1:
                for i in range(1, len(all_due_dates)):
                    warnings.append(Warning(
                        code='DUPLICATE_DUE_DATE',
                        message='Multiple due dates found, using last value',
                        line=item.line,
                        column=all_due_dates[i][1][0] - item.item_span[0] + 1,
                        span=all_due_dates[i][1],
                    ))
                break

            # Check for invalid priority tokens (e.g., pX)
            invalid_priority_pattern = re.compile(r'\bp([a-zA-Z][^\s,)]*)', re.IGNORECASE)
            for ip_match in invalid_priority_pattern.finditer(content):
                token_start = paren_start + 1 + ip_match.start()
                warnings.append(Warning(
                    code='INVALID_TOKEN',
                    message=f'Unrecognized token in parentheses: {ip_match.group(0)}',
                    line=item.line,
                    column=token_start - item.item_span[0] + 1,
                    span=(token_start, token_start + len(ip_match.group(0))),
                ))

            # Check for invalid estimate tokens (e.g., 5q)
            invalid_estimate_pattern = re.compile(r'\b(\d+)([a-zA-Z])(?![mhdMHD])\b', re.IGNORECASE)
            for ie_match in invalid_estimate_pattern.finditer(content):
                unit = ie_match.group(2).lower()
                if unit not in ('m', 'h', 'd'):
                    token_start = paren_start + 1 + ie_match.start()
                    warnings.append(Warning(
                        code='INVALID_TOKEN',
                        message=f'Unrecognized token in parentheses: {ie_match.group(0)}',
                        line=item.line,
                        column=token_start - item.item_span[0] + 1,
                        span=(token_start, token_start + len(ie_match.group(0))),
                    ))

        # Check for comment indentation (list items only)
        if item.type == 'list' and item.comments:
            list_match = re.match(r'^(\s*)([-*]|\d+\.)\s', raw_line)
            expected_indent = len(list_match.group(1)) + len(list_match.group(2)) + 1 if list_match else 2

            current_offset = item.item_span[0] + len(raw_line) + 1
            for i, _ in enumerate(item.comments):
                comment_line_index = item.line + i
                if comment_line_index < len(lines):
                    comment_line = lines[comment_line_index]
                    leading_match = re.match(r'^(\s*)', comment_line)
                    leading_spaces = len(leading_match.group(1)) if leading_match else 0

                    if leading_spaces < expected_indent and comment_line.strip():
                        warnings.append(Warning(
                            code='COMMENT_INDENTATION',
                            message='List item comment should be indented',
                            line=comment_line_index + 1,
                            column=1,
                            span=(current_offset, current_offset + len(comment_line)),
                        ))
                current_offset += len(lines[comment_line_index]) + 1 if comment_line_index < len(lines) else 1

    # Check for Misc section issues
    if misc_section_line is None:
        warnings.append(Warning(
            code='MISC_MISSING',
            message="Document is missing required '# Misc' section",
            line=None,
            column=None,
            span=None,
        ))
    elif headings_after_misc:
        warnings.append(Warning(
            code='MISC_NOT_AT_EOF',
            message="'# Misc' section must be at end of file",
            line=misc_section_line,
            column=1,
            span=misc_section_span,
        ))

        for heading_line, heading_span in headings_after_misc:
            warnings.append(Warning(
                code='CONTENT_AFTER_MISC',
                message="Heading found after '# Misc' section",
                line=heading_line,
                column=1,
                span=heading_span,
            ))

    return LintResult(warnings=warnings)
