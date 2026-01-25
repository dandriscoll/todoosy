"""
Todoosy Linter
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .parser import parse
from .types import Warning, Scheme, Settings, ItemNode

VALID_DATE_FORMATS = [
    re.compile(r'^\d{4}-\d{1,2}-\d{1,2}$'),       # YYYY-MM-DD or YYYY-M-D
    re.compile(r'^\d{2}-\d{1,2}-\d{1,2}$'),       # YY-MM-DD or YY-M-D
    re.compile(r'^\d{4}/\d{1,2}/\d{1,2}$'),       # YYYY/MM/DD
    re.compile(r'^\d{2}/\d{1,2}/\d{1,2}$'),       # YY/MM/DD or MM/DD/YY (ambiguous but accepted)
    re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$'),       # MM/DD/YYYY or DD/MM/YYYY
    re.compile(r'^\d{1,2}/\d{1,2}/\d{2}$'),       # MM/DD/YY or DD/MM/YY
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

# Regex for text dates: Month Day [Year] or Day Month [Year] (Year can be 2 or 4 digits)
TEXT_DATE_REGEX = re.compile(
    r'^(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+(\d{1,2})(?:\s+(\d{2,4}))?$',
    re.IGNORECASE
)
TEXT_DATE_DAY_FIRST_REGEX = re.compile(
    r'^(\d{1,2})\s+(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)(?:\s+(\d{2,4}))?$',
    re.IGNORECASE
)

VALID_CALENDAR_FORMATS = {'yyyy-mm-dd', 'yyyy/mm/dd', 'mm/dd/yyyy', 'dd/mm/yyyy'}
VALID_FORMATTING_STYLES = {'roomy', 'balanced', 'tight'}
VALID_HASHTAG_REGEX = re.compile(r'^#[a-zA-Z][a-zA-Z0-9_-]*$')
HASHTAG_LIKE_REGEX = re.compile(r'#[^\s,)]*')


@dataclass
class LintResult:
    warnings: list[Warning] = field(default_factory=list)


def parse_misc_location(misc: str) -> tuple[str, str]:
    """Parse misc location string into (filename, heading)."""
    slash_index = misc.find('/')
    if slash_index == -1:
        return (misc, 'Misc')
    return (misc[:slash_index], misc[slash_index + 1:])


def is_valid_date(date_str: str) -> bool:
    """Check if a date string is in a valid format."""
    # Strip soft date prefix (~) for validation
    normalized_date_str = date_str[1:] if date_str.startswith('~') else date_str

    # Check standard formats
    if any(regex.match(normalized_date_str) for regex in VALID_DATE_FORMATS):
        return True
    # Check text date format (Month Day [Year])
    match = TEXT_DATE_REGEX.match(normalized_date_str)
    if match:
        day = int(match.group(2))
        return 1 <= day <= 31
    # Check text date format (Day Month [Year])
    match = TEXT_DATE_DAY_FIRST_REGEX.match(normalized_date_str)
    if match:
        day = int(match.group(1))
        return 1 <= day <= 31
    return False


def lint(text: str, scheme: Optional[Scheme] = None, filename: Optional[str] = None) -> LintResult:
    """Lint a todoosy document."""
    result = parse(text)
    ast = result.ast
    warnings: list[Warning] = []
    lines = text.split('\n')

    # Determine misc location from scheme or use default
    misc_filename, misc_heading = parse_misc_location(scheme.misc if scheme else 'todoosy.md/Misc')
    # If no filename provided, assume it could be the misc file (backward compatibility)
    is_misc_file = filename is None or filename == misc_filename

    misc_section_line = None
    misc_section_span = None
    headings_after_misc: list[tuple[int, tuple[int, int]]] = []

    # Check each item
    for item in ast.items:
        raw_line = item.raw_line

        # Check for Misc section (only relevant for the misc file)
        if is_misc_file and item.type == 'heading':
            if misc_section_line is not None:
                # Any heading after Misc (including duplicate Misc) is an error
                headings_after_misc.append((item.line, item.item_span))
            elif item.title_text == misc_heading and item.level == 1:
                misc_section_line = item.line
                misc_section_span = item.item_span

        # Check for invalid date formats in parentheses
        paren_pattern = re.compile(r'\(([^)]+)\)')
        for match in paren_pattern.finditer(raw_line):
            content = match.group(1)
            paren_start = item.item_span[0] + match.start()

            # Check for due dates - try text date format first (captures more), then standard format
            # Text date: due [~]Month Day [Year] (Year can be 2 or 4 digits, ~ for soft dates)
            text_due_pattern = re.compile(
                r'\bdue\s+(~?(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+\d{1,2}(?:\s+\d{2,4})?)',
                re.IGNORECASE
            )
            # Day-first text date: due [~]Day Month [Year] (Year can be 2 or 4 digits, ~ for soft dates)
            text_due_day_first_pattern = re.compile(
                r'\bdue\s+(~?\d{1,2}\s+(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)(?:\s+\d{2,4})?)',
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
            for text_due_match in text_due_day_first_pattern.finditer(content):
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
            # Allow optional ~ prefix for soft dates
            due_pattern = re.compile(r'\bdue\s+(~?[^\s,)]+)', re.IGNORECASE)
            for due_match in due_pattern.finditer(content):
                # Skip if this was already matched as a text date
                if due_match.start() in text_due_indices:
                    continue

                date_str = due_match.group(1)
                # Skip if this looks like the start of a text date (month name, with or without ~)
                stripped_date_str = date_str[1:] if date_str.startswith('~') else date_str
                if stripped_date_str.lower() in MONTH_NAMES:
                    continue
                # Skip if this looks like a day number (could be start of day-first date, with or without ~)
                if re.match(r'^~?\d{1,2}$', date_str):
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

                # Check text dates first (month-first)
                text_due_positions: set[int] = set()
                for tdm in text_due_pattern.finditer(p_content):
                    ds = tdm.group(1)
                    if is_valid_date(ds):
                        text_due_positions.add(tdm.start())
                        d_start = p_start + 1 + tdm.start()
                        all_due_dates.append((ds, (d_start, d_start + len(tdm.group(0)))))

                # Check day-first text dates
                for tdm in text_due_day_first_pattern.finditer(p_content):
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
                    # Skip if it's a month name (part of text date, with or without ~)
                    stripped_ds = ds[1:] if ds.startswith('~') else ds
                    if stripped_ds.lower() in MONTH_NAMES:
                        continue
                    # Skip if it's a day number (part of day-first text date, with or without ~)
                    if re.match(r'^~?\d{1,2}$', ds):
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
            # Use negative lookbehind to exclude hashtags (e.g., #personal)
            invalid_priority_pattern = re.compile(r'(?<!#)\bp([a-zA-Z][^\s,)]*)', re.IGNORECASE)
            for ip_match in invalid_priority_pattern.finditer(content):
                # Skip if this is "progress" (part of "in progress" progress state)
                if ip_match.group(0).lower() == 'progress':
                    continue
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

            # Check for invalid hashtags (e.g., #123, #)
            for ht_match in HASHTAG_LIKE_REGEX.finditer(content):
                hashtag = ht_match.group(0)
                if not VALID_HASHTAG_REGEX.match(hashtag):
                    token_start = paren_start + 1 + ht_match.start()
                    warnings.append(Warning(
                        code='INVALID_HASHTAG',
                        message=f'Invalid hashtag format: {hashtag} (must start with # followed by a letter)',
                        line=item.line,
                        column=token_start - item.item_span[0] + 1,
                        span=(token_start, token_start + len(hashtag)),
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

    # Check for Misc section issues (only for the misc file)
    if is_misc_file:
        if misc_section_line is None:
            warnings.append(Warning(
                code='MISC_MISSING',
                message=f"Document is missing required '# {misc_heading}' section",
                line=None,
                column=None,
                span=None,
            ))
        elif headings_after_misc:
            warnings.append(Warning(
                code='MISC_NOT_AT_EOF',
                message=f"'# {misc_heading}' section must be at end of file",
                line=misc_section_line,
                column=1,
                span=misc_section_span,
            ))

            for heading_line, heading_span in headings_after_misc:
                warnings.append(Warning(
                    code='CONTENT_AFTER_MISC',
                    message=f"Heading found after '# {misc_heading}' section",
                    line=heading_line,
                    column=1,
                    span=heading_span,
                ))

    # Check for sequence issues (gaps and duplicates in numbered lists)
    item_map = {item.id: item for item in ast.items}

    for item in ast.items:
        if not item.children:
            continue

        # Collect numbered children
        numbered_children: list[tuple[str, int, 'ItemNode']] = []
        for child_id in item.children:
            child = item_map.get(child_id)
            if child and child.marker_type == 'numbered' and child.sequence_number is not None:
                numbered_children.append((child_id, child.sequence_number, child))

        if not numbered_children:
            continue

        # Check for gaps - numbers should be consecutive starting from 1
        for i, (child_id, seq_num, child) in enumerate(numbered_children):
            expected = i + 1
            if seq_num != expected:
                warnings.append(Warning(
                    code='SEQUENCE_GAP',
                    message=f"Sequence gap: expected {expected}, found {seq_num}",
                    line=child.line,
                    column=child.column,
                    span=child.item_span,
                ))

        # Check for duplicates
        seq_num_counts: dict[int, list[tuple[str, int, 'ItemNode']]] = {}
        for child_data in numbered_children:
            seq_num = child_data[1]
            if seq_num not in seq_num_counts:
                seq_num_counts[seq_num] = []
            seq_num_counts[seq_num].append(child_data)

        for seq_num, children in seq_num_counts.items():
            if len(children) > 1:
                # Warn for all but the first occurrence
                for i in range(1, len(children)):
                    child = children[i][2]
                    warnings.append(Warning(
                        code='SEQUENCE_DUPLICATE',
                        message=f"Duplicate sequence number: {seq_num}",
                        line=child.line,
                        column=child.column,
                        span=child.item_span,
                    ))

    return LintResult(warnings=warnings)


def lint_scheme(scheme: Scheme) -> LintResult:
    """Lint a parsed scheme for invalid values."""
    warnings: list[Warning] = []

    # Check if calendar_format is valid
    if scheme.calendar_format.lower() not in VALID_CALENDAR_FORMATS:
        warnings.append(Warning(
            code='INVALID_CALENDAR_FORMAT',
            message=f"Invalid calendar format: '{scheme.calendar_format}'. Valid formats are: {', '.join(sorted(VALID_CALENDAR_FORMATS))}",
            line=None,
            column=None,
            span=None,
        ))

    # Check if formatting_style is valid
    if scheme.formatting_style.lower() not in VALID_FORMATTING_STYLES:
        warnings.append(Warning(
            code='INVALID_FORMATTING_STYLE',
            message=f"Invalid formatting style: '{scheme.formatting_style}'. Valid styles are: {', '.join(sorted(VALID_FORMATTING_STYLES))}",
            line=None,
            column=None,
            span=None,
        ))

    return LintResult(warnings=warnings)


def lint_settings(settings: Settings) -> LintResult:
    """Lint a parsed settings object for invalid values."""
    warnings: list[Warning] = []

    # Check if calendar_format is valid
    if settings.calendar_format.lower() not in VALID_CALENDAR_FORMATS:
        warnings.append(Warning(
            code='INVALID_CALENDAR_FORMAT',
            message=f"Invalid calendar format: '{settings.calendar_format}'. Valid formats are: {', '.join(sorted(VALID_CALENDAR_FORMATS))}",
            line=None,
            column=None,
            span=None,
        ))

    # Check if formatting_style is valid
    if settings.formatting_style.lower() not in VALID_FORMATTING_STYLES:
        warnings.append(Warning(
            code='INVALID_FORMATTING_STYLE',
            message=f"Invalid formatting style: '{settings.formatting_style}'. Valid styles are: {', '.join(sorted(VALID_FORMATTING_STYLES))}",
            line=None,
            column=None,
            span=None,
        ))

    return LintResult(warnings=warnings)
