"""
Todoosy Parser
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from dateutil.relativedelta import relativedelta

from .types import AST, ItemNode, ItemMetadata, ParsedToken, ParenGroup, Settings, Warning
from .relative_date import (
    ResolvedNow,
    resolve_now,
    resolve_keyword,
    try_parse_relative,
)

HEADING_REGEX = re.compile(r'^(#{1,6})\s+(.*)$')
LIST_ITEM_REGEX = re.compile(r'^(\s*)([-*]|\d+\.)\s+(.*)$')
PRIORITY_REGEX = re.compile(r'^p(\d+)$', re.IGNORECASE)
ESTIMATE_REGEX = re.compile(r'^(\d+)([mhd])$', re.IGNORECASE)
HASHTAG_REGEX = re.compile(r'^#([a-zA-Z][a-zA-Z0-9_-]*)$')

MONTH_NAMES: dict[str, int] = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

PROGRESS_STATES = {'done', 'deleted', 'in progress', 'blocked'}


@dataclass
class ParseResult:
    ast: AST
    warnings: list[Warning] = field(default_factory=list)


def infer_year(month: int, day: int, now: ResolvedNow) -> int:
    today_y, today_m, today_d = (int(x) for x in now.today_iso.split('-'))
    try:
        candidate = date(today_y, month, day)
    except ValueError:
        return today_y
    today = date(today_y, today_m, today_d)
    three_months_ago = today - relativedelta(months=3)
    if candidate < three_months_ago:
        return today_y + 1
    return today_y


def parse_iso_date(date_str: str) -> Optional[str]:
    iso_match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2).zfill(2)}-{iso_match.group(3).zfill(2)}"

    iso_short_match = re.match(r'^(\d{2})-(\d{1,2})-(\d{1,2})$', date_str)
    if iso_short_match:
        return f"20{iso_short_match.group(1)}-{iso_short_match.group(2).zfill(2)}-{iso_short_match.group(3).zfill(2)}"

    ymd_slash = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', date_str)
    if ymd_slash:
        return f"{ymd_slash.group(1)}-{ymd_slash.group(2).zfill(2)}-{ymd_slash.group(3).zfill(2)}"

    slash_4yr = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if slash_4yr:
        first = int(slash_4yr.group(1))
        second = int(slash_4yr.group(2))
        year = slash_4yr.group(3)
        if first > 12:
            day = str(first).zfill(2)
            month = str(second).zfill(2)
        else:
            month = str(first).zfill(2)
            day = str(second).zfill(2)
        return f"{year}-{month}-{day}"

    slash = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{1,2})$', date_str)
    if slash:
        first = int(slash.group(1))
        second = int(slash.group(2))
        third = int(slash.group(3))
        if third > 31:
            year = f"20{slash.group(3).zfill(2)}"
            if first > 12:
                day, month = str(first).zfill(2), str(second).zfill(2)
            else:
                month, day = str(first).zfill(2), str(second).zfill(2)
        elif first > 31:
            year = f"20{slash.group(1).zfill(2)}"
            month = str(second).zfill(2)
            day = str(third).zfill(2)
        elif first > 12:
            day = str(first).zfill(2)
            month = str(second).zfill(2)
            year = f"20{slash.group(3).zfill(2)}"
        else:
            month = str(first).zfill(2)
            day = str(second).zfill(2)
            year = f"20{slash.group(3).zfill(2)}"
        return f"{year}-{month}-{day}"

    return None


def parse_text_date(parts: list[str], start_idx: int, now: ResolvedNow) -> Optional[tuple[str, int]]:
    if start_idx + 1 >= len(parts):
        return None

    # Month Day [Year]
    month_str = parts[start_idx].lower()
    month = MONTH_NAMES.get(month_str)
    if month is not None:
        day_match = re.match(r'^(\d{1,2})$', parts[start_idx + 1])
        if day_match:
            day = int(day_match.group(1))
            if 1 <= day <= 31:
                if start_idx + 2 < len(parts):
                    y4 = re.match(r'^(\d{4})$', parts[start_idx + 2])
                    if y4:
                        return f"{y4.group(1)}-{str(month).zfill(2)}-{str(day).zfill(2)}", 3
                    y2 = re.match(r'^(\d{2})$', parts[start_idx + 2])
                    if y2:
                        return f"{2000 + int(y2.group(1))}-{str(month).zfill(2)}-{str(day).zfill(2)}", 3
                year = infer_year(month, day, now)
                return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}", 2

    # Day Month [Year]
    day_first = re.match(r'^(\d{1,2})$', parts[start_idx])
    if day_first:
        day = int(day_first.group(1))
        if 1 <= day <= 31:
            month_str2 = parts[start_idx + 1].lower()
            month2 = MONTH_NAMES.get(month_str2)
            if month2 is not None:
                if start_idx + 2 < len(parts):
                    y4 = re.match(r'^(\d{4})$', parts[start_idx + 2])
                    if y4:
                        return f"{y4.group(1)}-{str(month2).zfill(2)}-{str(day).zfill(2)}", 3
                    y2 = re.match(r'^(\d{2})$', parts[start_idx + 2])
                    if y2:
                        return f"{2000 + int(y2.group(1))}-{str(month2).zfill(2)}-{str(day).zfill(2)}", 3
                year = infer_year(month2, day, now)
                return f"{year}-{str(month2).zfill(2)}-{str(day).zfill(2)}", 2

    return None


def try_parse_single_date(parts: list[str], start_idx: int, now: ResolvedNow) -> Optional[tuple[str, int]]:
    """Try keyword | ISO/slash | text date | relative offset starting at parts[start_idx]."""
    if start_idx >= len(parts):
        return None

    kw = resolve_keyword(parts[start_idx], now)
    if kw is not None:
        return kw, 1

    iso = parse_iso_date(parts[start_idx])
    if iso is not None:
        return iso, 1

    text = parse_text_date(parts, start_idx, now)
    if text is not None:
        return text

    rel = try_parse_relative(parts, start_idx, now)
    if rel is not None:
        return rel

    return None


def _tokenize_content(content: str) -> tuple[list[str], list[int]]:
    """
    Pre-tokenize parens content. Splits by commas/whitespace, then further
    splits each part on `~` so that `~` always appears as its own delimiter
    token. Returns (parts, part_offsets-into-content).
    """
    parts: list[str] = []
    offsets: list[int] = []
    i = 0
    n = len(content)
    while i < n:
        # Skip separators
        while i < n and (content[i] == ',' or content[i].isspace()):
            i += 1
        if i >= n:
            break
        token_start = i
        while i < n and content[i] != ',' and not content[i].isspace():
            i += 1
        raw = content[token_start:i]

        cursor = 0
        while cursor < len(raw):
            tilde_idx = raw.find('~', cursor)
            if tilde_idx == -1:
                seg = raw[cursor:]
                if seg:
                    parts.append(seg)
                    offsets.append(token_start + cursor)
                break
            if tilde_idx > cursor:
                parts.append(raw[cursor:tilde_idx])
                offsets.append(token_start + cursor)
            parts.append('~')
            offsets.append(token_start + tilde_idx)
            cursor = tilde_idx + 1
    return parts, offsets


def parse_tokens_in_paren_group(content: str, group_start: int, now: Optional[ResolvedNow] = None) -> ParenGroup:
    if now is None:
        now = resolve_now()
    tokens: list[ParsedToken] = []
    parts, offsets = _tokenize_content(content)

    def part_end_offset(i: int) -> int:
        return offsets[i] + len(parts[i])

    def abs_start(i: int) -> int:
        return group_start + 1 + offsets[i]

    def abs_end(i: int) -> int:
        return group_start + 1 + part_end_offset(i)

    skip: set[int] = set()
    i = 0
    while i < len(parts):
        if i in skip:
            i += 1
            continue
        part = parts[i]

        # Standalone `~` at this position: soft prefix introducer
        if part == '~':
            inner = try_parse_single_date(parts, i + 1, now)
            if inner is not None:
                date_str, consumed = inner
                end_index = i + consumed  # last consumed index = i + consumed (since parsed parts span [i+1, i+consumed])
                for j in range(i + 1, end_index + 1):
                    skip.add(j)
                raw = content[offsets[i]:part_end_offset(end_index)]
                tokens.append(ParsedToken(
                    type='due',
                    value=date_str,
                    raw=raw,
                    start=abs_start(i),
                    end=abs_end(end_index),
                    soft=True,
                ))
                i = end_index + 1
                continue
            i += 1
            continue

        # 'due' keyword
        if part.lower() == 'due':
            cursor = i + 1
            is_soft_prefix = False
            if cursor < len(parts) and parts[cursor] == '~':
                is_soft_prefix = True
                cursor += 1
            first = try_parse_single_date(parts, cursor, now)
            if first is None:
                i += 1
                continue
            first_date, first_consumed = first
            end_index = cursor + first_consumed - 1
            date_start: Optional[str] = None
            due_date = first_date
            is_soft = is_soft_prefix

            # Span continuation: <date>~<date>
            if end_index + 1 < len(parts) and parts[end_index + 1] == '~':
                second = try_parse_single_date(parts, end_index + 2, now)
                if second is not None and not is_soft_prefix:
                    second_date, second_consumed = second
                    date_start = first_date
                    due_date = second_date
                    end_index = end_index + 1 + second_consumed
                    is_soft = True

            for j in range(i, end_index + 1):
                skip.add(j)
            raw = content[offsets[i]:part_end_offset(end_index)]
            tokens.append(ParsedToken(
                type='due',
                value=due_date,
                raw=raw,
                start=abs_start(i),
                end=abs_end(end_index),
                soft=is_soft if is_soft else None,
                date_start=date_start,
            ))
            i = end_index + 1
            continue

        # priority
        priority_match = PRIORITY_REGEX.match(part)
        if priority_match:
            tokens.append(ParsedToken(
                type='priority',
                value=int(priority_match.group(1)),
                raw=part,
                start=abs_start(i),
                end=abs_end(i),
            ))
            i += 1
            continue

        # estimate (must run before relative-date so bare 2d/2h/2m stay as estimates)
        estimate_match = ESTIMATE_REGEX.match(part)
        if estimate_match:
            num = int(estimate_match.group(1))
            unit = estimate_match.group(2).lower()
            if unit == 'm':
                minutes = num
            elif unit == 'h':
                minutes = num * 60
            elif unit == 'd':
                minutes = num * 480
            else:
                minutes = num
            tokens.append(ParsedToken(
                type='estimate',
                value=minutes,
                raw=part,
                start=abs_start(i),
                end=abs_end(i),
            ))
            i += 1
            continue

        # progress: single-word
        part_lower = part.lower()
        if part_lower in PROGRESS_STATES:
            tokens.append(ParsedToken(
                type='progress',
                value=part_lower,
                raw=part,
                start=abs_start(i),
                end=abs_end(i),
            ))
            i += 1
            continue

        # progress: "in progress" (disambiguate from relative-date "in")
        if part_lower == 'in' and i + 1 < len(parts) and parts[i + 1].lower() == 'progress':
            tokens.append(ParsedToken(
                type='progress',
                value='in progress',
                raw=f'{part} {parts[i + 1]}',
                start=abs_start(i),
                end=abs_end(i + 1),
            ))
            skip.add(i + 1)
            i += 2
            continue

        # hashtag
        hashtag_match = HASHTAG_REGEX.match(part)
        if hashtag_match:
            tokens.append(ParsedToken(
                type='hashtag',
                value=hashtag_match.group(1).lower(),
                raw=part,
                start=abs_start(i),
                end=abs_end(i),
            ))
            i += 1
            continue

        # standalone date / relative / span
        first = try_parse_single_date(parts, i, now)
        if first is not None:
            first_date, first_consumed = first
            end_index = i + first_consumed - 1
            date_start = None
            due_date = first_date
            is_soft = False

            if end_index + 1 < len(parts) and parts[end_index + 1] == '~':
                second = try_parse_single_date(parts, end_index + 2, now)
                if second is not None:
                    second_date, second_consumed = second
                    date_start = first_date
                    due_date = second_date
                    end_index = end_index + 1 + second_consumed
                    is_soft = True

            for j in range(i, end_index + 1):
                skip.add(j)
            raw = content[offsets[i]:part_end_offset(end_index)]
            tokens.append(ParsedToken(
                type='due',
                value=due_date,
                raw=raw,
                start=abs_start(i),
                end=abs_end(end_index),
                soft=is_soft if is_soft else None,
                date_start=date_start,
            ))
            i = end_index + 1
            continue

        i += 1

    return ParenGroup(
        start=group_start,
        end=group_start + len(content) + 2,
        content=content,
        tokens=tokens,
        has_recognized_tokens=len(tokens) > 0,
    )


def extract_paren_groups(line: str, line_start: int, now: Optional[ResolvedNow] = None) -> list[ParenGroup]:
    if now is None:
        now = resolve_now()
    groups: list[ParenGroup] = []
    i = 0
    while i < len(line):
        if line[i] == '(':
            start = i
            depth = 1
            i += 1
            while i < len(line) and depth > 0:
                if line[i] == '(':
                    depth += 1
                elif line[i] == ')':
                    depth -= 1
                i += 1
            if depth == 0:
                content = line[start + 1:i - 1]
                group = parse_tokens_in_paren_group(content, start, now)
                group.start = start
                group.end = i
                groups.append(group)
        else:
            i += 1
    return groups


def build_title_text(raw_text: str, groups: list[ParenGroup]) -> str:
    sorted_groups = sorted(
        [g for g in groups if g.has_recognized_tokens],
        key=lambda g: g.start,
        reverse=True,
    )
    result = raw_text
    for g in sorted_groups:
        result = result[:g.start] + result[g.end:]
    return ' '.join(result.split()).strip()


def build_metadata(groups: list[ParenGroup]) -> ItemMetadata:
    metadata = ItemMetadata()
    all_tokens = [t for g in groups for t in g.tokens]
    hashtag_set: set[str] = set()
    for token in all_tokens:
        if token.type == 'due':
            metadata.due = str(token.value)
            metadata.due_start = token.date_start
            metadata.due_soft = token.soft
        elif token.type == 'priority':
            metadata.priority = int(token.value)
        elif token.type == 'estimate':
            metadata.estimate_minutes = int(token.value)
        elif token.type == 'progress':
            metadata.progress = str(token.value)
        elif token.type == 'hashtag':
            hashtag_set.add(str(token.value))
    metadata.hashtags = sorted(hashtag_set)
    return metadata


def parse(text: str, *, now: Optional[datetime] = None, settings: Optional[Settings] = None) -> ParseResult:
    resolved_now = resolve_now(now=now, settings=settings)
    lines = text.split('\n')
    items: list[ItemNode] = []
    warnings: list[Warning] = []
    next_id = 0
    offset = 0

    list_stack: list[tuple[str, int]] = []
    current_heading_id: Optional[str] = None
    root_ids: list[str] = []
    children_map: dict[str, list[str]] = {}

    for line_num, line in enumerate(lines):
        line_start = offset
        line_end = offset + len(line)

        heading_match = HEADING_REGEX.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            list_stack.clear()
            groups = extract_paren_groups(content, line_start + level + 1, resolved_now)
            title_text = build_title_text(content, groups)
            metadata = build_metadata(groups)
            item_id = str(next_id)
            next_id += 1
            item = ItemNode(
                id=item_id,
                type='heading',
                level=level,
                raw_line=line,
                title_text=title_text,
                metadata=metadata,
                comments=[],
                children=[],
                item_span=(line_start, line_end),
                subtree_span=(line_start, line_end),
                line=line_num + 1,
                column=1,
            )
            items.append(item)
            children_map[item_id] = []
            root_ids.append(item_id)
            current_heading_id = item_id
            offset = line_end + 1
            continue

        list_match = LIST_ITEM_REGEX.match(line)
        if list_match:
            indent = len(list_match.group(1))
            marker = list_match.group(2)
            content = list_match.group(3)
            content_start = line_start + indent + len(marker) + 1
            groups = extract_paren_groups(content, content_start, resolved_now)
            title_text = build_title_text(content, groups)
            metadata = build_metadata(groups)
            is_numbered = bool(re.match(r'^\d+\.$', marker))
            marker_type = 'numbered' if is_numbered else 'bullet'
            sequence_number = int(marker[:-1]) if is_numbered else None
            item_id = str(next_id)
            next_id += 1
            item = ItemNode(
                id=item_id,
                type='list',
                raw_line=line,
                title_text=title_text,
                metadata=metadata,
                comments=[],
                children=[],
                item_span=(line_start, line_end),
                subtree_span=(line_start, line_end),
                line=line_num + 1,
                column=1,
                marker_type=marker_type,
                sequence_number=sequence_number,
            )
            items.append(item)
            children_map[item_id] = []
            while list_stack and list_stack[-1][1] >= indent:
                list_stack.pop()
            if list_stack:
                children_map[list_stack[-1][0]].append(item_id)
            elif current_heading_id is not None:
                children_map[current_heading_id].append(item_id)
            else:
                root_ids.append(item_id)
            list_stack.append((item_id, indent))
            offset = line_end + 1
            continue

        offset = line_end + 1

    # Second pass: comments
    offset = 0
    current_item_index = -1
    has_started_comments = False
    blank_after_comment_start = False

    for line_num, line in enumerate(lines):
        line_start = offset
        line_end = offset + len(line)
        heading_match = HEADING_REGEX.match(line)
        list_match = LIST_ITEM_REGEX.match(line)

        if heading_match or list_match:
            current_item_index = next(
                (i for i, item in enumerate(items) if item.item_span[0] == line_start),
                -1,
            )
            has_started_comments = False
            blank_after_comment_start = False
            offset = line_end + 1
            continue

        if not line.strip():
            if has_started_comments:
                blank_after_comment_start = True
            offset = line_end + 1
            continue

        if current_item_index >= 0 and not blank_after_comment_start:
            current_item = items[current_item_index]
            current_item.comments.append(line.strip())
            current_item.item_span = (current_item.item_span[0], line_end)
            has_started_comments = True
        offset = line_end + 1

    for item in items:
        item.children = children_map.get(item.id, [])

    def compute_subtree_span(item_id: str) -> tuple[int, int]:
        item = next(i for i in items if i.id == item_id)
        end = item.item_span[1]
        for child_id in item.children:
            child_span = compute_subtree_span(child_id)
            end = max(end, child_span[1])
        item.subtree_span = (item.item_span[0], end)
        return item.subtree_span

    for root_id in root_ids:
        compute_subtree_span(root_id)

    actual_root_ids = [
        item.id for item in items
        if not any(item.id in other.children for other in items)
    ]

    item_map = {item.id: item for item in items}

    def compute_effective_hashtags(item_id: str, parent_eff: list[str]) -> None:
        item = item_map[item_id]
        combined = set(parent_eff) | set(item.metadata.hashtags)
        item.metadata.effective_hashtags = sorted(combined)
        for child_id in item.children:
            compute_effective_hashtags(child_id, item.metadata.effective_hashtags)

    for root_id in actual_root_ids:
        compute_effective_hashtags(root_id, [])

    return ParseResult(
        ast=AST(items=items, root_ids=actual_root_ids),
        warnings=warnings,
    )
